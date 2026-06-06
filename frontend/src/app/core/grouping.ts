import { CompanyGroup, Invoice } from './models';

/** Group invoices into per-company working sets (mirrors backend group_by_company).
 *  Invoices already carry company_key/company_name from the backend. */
export function groupInvoices(invoices: Invoice[]): CompanyGroup[] {
  const map = new Map<string, CompanyGroup>();
  for (const inv of invoices) {
    const key = inv.company_key || 'unknown';
    let g = map.get(key);
    if (!g) {
      g = {
        company: {
          key,
          name: inv.company_name || 'Unknown company',
          vat: inv.supplier?.vat_number ?? null,
          eik: inv.supplier?.eik ?? null,
          invoice_count: 0,
        },
        invoices: [],
      };
      map.set(key, g);
    }
    g.invoices.push(inv);
  }
  const groups = [...map.values()];
  groups.forEach((g) => (g.company.invoice_count = g.invoices.length));
  return groups.sort(
    (a, b) =>
      (a.company.key === 'unknown' ? 1 : 0) - (b.company.key === 'unknown' ? 1 : 0) ||
      b.company.invoice_count - a.company.invoice_count,
  );
}
