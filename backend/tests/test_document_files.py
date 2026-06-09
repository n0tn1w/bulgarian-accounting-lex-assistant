import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.security import create_access_token
from app.db.base import admin_engine
from app.main import app

_PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


def _make_tenant():
    tid, uid = uuid.uuid4(), uuid.uuid4()
    with admin_engine.begin() as c:
        c.execute(text("INSERT INTO tenants (id, name) VALUES (:i,'t')"), {"i": str(tid)})
        c.execute(
            text("INSERT INTO users (id, tenant_id, email, password_hash, role) "
                 "VALUES (:u,:t,:e,'x','owner')"),
            {"u": str(uid), "t": str(tid), "e": f"{uid}@t.io"},
        )
    client = TestClient(app)
    client.headers.update({"Authorization": f"Bearer {create_access_token(str(uid), str(tid))}"})
    return client, tid


def _cleanup(tid):
    with admin_engine.begin() as c:
        c.execute(text("DELETE FROM document_files WHERE tenant_id=:t"), {"t": str(tid)})
        c.execute(text("DELETE FROM users WHERE tenant_id=:t"), {"t": str(tid)})
        c.execute(text("DELETE FROM tenants WHERE id=:t"), {"t": str(tid)})


@pytest.fixture()
def two_tenants():
    a = _make_tenant()
    b = _make_tenant()
    yield a, b
    _cleanup(a[1])
    _cleanup(b[1])


@pytest.mark.db
def test_store_and_fetch_roundtrip(two_tenants):
    (client, _), _ = two_tenants
    up = client.post(
        "/workspace/documents/EXT-1/file",
        files={"file": ("inv.pdf", _PDF, "application/pdf")},
    )
    assert up.status_code == 200 and up.json()["size"] == len(_PDF)

    got = client.get("/workspace/documents/EXT-1/file")
    assert got.status_code == 200
    assert got.headers["content-type"].startswith("application/pdf")
    assert got.content == _PDF


@pytest.mark.db
def test_reupload_upserts(two_tenants):
    (client, _), _ = two_tenants
    client.post("/workspace/documents/EXT-2/file", files={"file": ("a.pdf", _PDF, "application/pdf")})
    newer = _PDF + b"more"
    client.post("/workspace/documents/EXT-2/file", files={"file": ("b.pdf", newer, "application/pdf")})
    got = client.get("/workspace/documents/EXT-2/file")
    assert got.content == newer  # newest wins, single row


@pytest.mark.db
def test_cross_tenant_isolation(two_tenants):
    (client_a, _), (client_b, _) = two_tenants
    client_a.post("/workspace/documents/SHARED/file", files={"file": ("a.pdf", _PDF, "application/pdf")})
    # tenant B must not see tenant A's file (RLS)
    assert client_b.get("/workspace/documents/SHARED/file").status_code == 404


@pytest.mark.db
def test_missing_file_404(two_tenants):
    (client, _), _ = two_tenants
    assert client.get("/workspace/documents/NOPE/file").status_code == 404
