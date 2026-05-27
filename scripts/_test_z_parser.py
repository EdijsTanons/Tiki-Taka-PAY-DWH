import duckdb
from tikitaka_dwh.config import get_settings
from tikitaka_dwh.transform.decode import extract_z_report_data

db = duckdb.connect(str(get_settings().app_data_dir / "warehouse.duckdb"), read_only=True)

# Z reports that have cross-joined sales > 0
rows = db.execute("""
    SELECT z.id, z.doc_date, z.store_number, z.pos_id, z.raw_xml,
           COUNT(s.id) as cnt, COALESCE(SUM(s.doc_sum), 0) as calc_total
    FROM fct_documents z
    LEFT JOIN fct_documents s
           ON s.doc_date = z.doc_date AND s.store_number = z.store_number
          AND s.pos_id = z.pos_id AND s.doc_type = 'sale'
    WHERE z.doc_type = 'z_report'
    GROUP BY z.id, z.doc_date, z.store_number, z.pos_id, z.raw_xml
    HAVING COUNT(s.id) > 0
    ORDER BY z.doc_date DESC
    LIMIT 5
""").fetchall()

for doc_id, doc_date, store, pos, raw_xml, cnt, calc_total in rows:
    parsed = extract_z_report_data(raw_xml or "")
    z_total = parsed["total"]
    match = "OK" if z_total is not None and abs(z_total - float(calc_total)) <= 0.01 else ("?" if z_total is None else "MISMATCH")
    print(f"id={doc_id} date={doc_date} store={store} pos={pos} txns={cnt} calc={calc_total:.2f} z_total={z_total} {match}")
    print(f"  cancelled={parsed['cancelled_count']} voids={parsed['cancelled_amount']} refunds={parsed['refund_count']} cash_in={parsed['cash_in']} cash_out={parsed['cash_out']}")
    print(f"  vat_rows={parsed['vat_rows']}")
    print()

db.close()
