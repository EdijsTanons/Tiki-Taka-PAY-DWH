import duckdb, html, re, xml.etree.ElementTree as ET
from tikitaka_dwh.config import get_settings

db = duckdb.connect(str(get_settings().app_data_dir / "warehouse.duckdb"), read_only=True)

# Find Z reports that have same-day sales (non-zero) so we see a populated receipt
rows = db.execute("""
    SELECT z.id, z.doc_date, z.store_number, z.pos_id, z.raw_xml,
           COUNT(s.id) as sale_count, SUM(s.doc_sum) as sales_total
    FROM fct_documents z
    LEFT JOIN fct_documents s
           ON s.doc_date = z.doc_date AND s.store_number = z.store_number
          AND s.pos_id = z.pos_id AND s.doc_type = 'sale'
    WHERE z.doc_type = 'z_report'
    GROUP BY z.id, z.doc_date, z.store_number, z.pos_id, z.raw_xml
    HAVING SUM(s.doc_sum) > 0
    ORDER BY z.doc_date DESC
    LIMIT 3
""").fetchall()

for row in rows:
    doc_id, doc_date, store, pos, raw_xml, cnt, total = row
    print(f"\n=== Z report id={doc_id} date={doc_date} store={store} pos={pos} sales={cnt} total={total} ===")
    if raw_xml:
        try:
            root = ET.fromstring(raw_xml)
            ceka = root.find("ceka_saturs")
            if ceka is not None and ceka.text:
                text = html.unescape(ceka.text)
                print(text[:3000])
        except Exception as e:
            print(f"XML parse error: {e}")
            print(raw_xml[:500])

db.close()
