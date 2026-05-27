import duckdb
from tikitaka_dwh.config import get_settings

db = duckdb.connect(str(get_settings().app_data_dir / "warehouse.duckdb"), read_only=True)

print("Z report count and range")
print(db.execute("SELECT COUNT(*) as cnt, MIN(doc_date) as first, MAX(doc_date) as last FROM fct_documents WHERE doc_type = 'z_report'").df().to_string())

print("\nNon-null columns in Z reports")
print(db.execute("""
SELECT
    COUNT(*) FILTER(WHERE doc_sum IS NOT NULL) AS has_doc_sum,
    COUNT(*) FILTER(WHERE store_number IS NOT NULL) AS has_store,
    COUNT(*) FILTER(WHERE pos_id IS NOT NULL) AS has_pos,
    COUNT(*) FILTER(WHERE operator_id IS NOT NULL) AS has_operator,
    COUNT(*) FILTER(WHERE raw_xml IS NOT NULL AND raw_xml != '') AS has_xml
FROM fct_documents WHERE doc_type = 'z_report'
""").df().to_string())

print("\nSample Z report rows")
print(db.execute("""
SELECT doc_date, store_number, pos_id, doc_sum, doc_num, doc_type_raw, dok_operation
FROM fct_documents WHERE doc_type = 'z_report'
ORDER BY doc_date DESC LIMIT 10
""").df().to_string())

print("\nSale lines linked to Z reports")
print(db.execute("""
SELECT COUNT(*) as cnt
FROM fct_sale_lines sl JOIN fct_documents d ON sl.doc_id = d.id
WHERE d.doc_type = 'z_report'
""").df().to_string())

print("\nPayments linked to Z reports")
print(db.execute("""
SELECT COUNT(*) as cnt
FROM fct_payments p JOIN fct_documents d ON p.doc_id = d.id
WHERE d.doc_type = 'z_report'
""").df().to_string())

print("\nSample raw_xml from a Z report")
row = db.execute("""
SELECT raw_xml FROM fct_documents
WHERE doc_type = 'z_report' AND raw_xml IS NOT NULL AND raw_xml != ''
LIMIT 1
""").fetchone()
if row:
    print(row[0][:2000])
else:
    print("No XML found")

db.close()
