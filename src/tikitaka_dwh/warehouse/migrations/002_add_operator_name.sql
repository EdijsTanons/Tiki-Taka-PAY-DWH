-- Add operator_name to fct_documents so staging Parquet is self-contained
-- (enables dim_operator to be built without re-reading raw JSON)
ALTER TABLE fct_documents ADD COLUMN IF NOT EXISTS operator_name VARCHAR;
