"""Idempotent database bootstrap, run at startup as the admin role.

Creates the pgvector extension, the app role, the tables, grants, and Row-Level
Security (with FORCE) on the tenant-scoped table so the non-superuser app role is
isolated per tenant. Safe to re-run.
"""

from __future__ import annotations

import logging

from sqlalchemy import text

from app.core import get_settings
from app.db.base import Base, admin_engine
from app.db import models  # noqa: F401  (register tables on Base.metadata)

logger = logging.getLogger(__name__)


def init_db() -> None:
    settings = get_settings()
    role = settings.app_db_role
    pwd = settings.app_db_password

    with admin_engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

        # App login role (NOSUPERUSER => subject to RLS).
        conn.execute(
            text(
                f"""
                DO $$ BEGIN
                  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{role}') THEN
                    CREATE ROLE {role} LOGIN PASSWORD '{pwd}' NOSUPERUSER NOBYPASSRLS;
                  END IF;
                END $$;
                """
            )
        )

    # Create tables (as admin / table owner).
    Base.metadata.create_all(admin_engine)

    with admin_engine.begin() as conn:
        # Privileges for the app role.
        conn.execute(text(f"GRANT USAGE ON SCHEMA public TO {role}"))
        conn.execute(
            text(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {role}")
        )
        conn.execute(text(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {role}"))
        conn.execute(
            text(
                f"ALTER DEFAULT PRIVILEGES IN SCHEMA public "
                f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {role}"
            )
        )

        # Row-Level Security: tenant isolation on stored_invoices.
        conn.execute(text("ALTER TABLE stored_invoices ENABLE ROW LEVEL SECURITY"))
        conn.execute(text("ALTER TABLE stored_invoices FORCE ROW LEVEL SECURITY"))
        conn.execute(text("DROP POLICY IF EXISTS tenant_isolation ON stored_invoices"))
        conn.execute(
            text(
                """
                CREATE POLICY tenant_isolation ON stored_invoices
                USING (tenant_id = current_setting('app.current_tenant', true)::uuid)
                WITH CHECK (tenant_id = current_setting('app.current_tenant', true)::uuid)
                """
            )
        )

        # Indexes: per-company lookups + vector similarity (cosine).
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_invoices_tenant_company "
                "ON stored_invoices (tenant_id, company_key)"
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_invoices_embedding "
                "ON stored_invoices USING hnsw (embedding vector_cosine_ops)"
            )
        )

    logger.info("Database bootstrap complete (pgvector, tables, RLS, role=%s)", role)
