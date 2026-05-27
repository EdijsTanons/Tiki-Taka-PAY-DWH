-- Initial schema: fact tables, dimension tables, dim_date, dim_doc_type, aggregates

-- ── Fact: documents ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS fct_documents (
    id                      BIGINT PRIMARY KEY,
    doc_uid                 INTEGER,
    doc_num                 INTEGER,
    doc_datetime_local      TIMESTAMP,
    doc_datetime_utc        TIMESTAMP,
    doc_date                DATE,
    doc_type                VARCHAR,
    doc_type_raw            VARCHAR,
    dok_operation           VARCHAR,
    store_number            VARCHAR,
    pos_id                  INTEGER,
    operator_id             VARCHAR,
    doc_sum                 DECIMAL(12,2),
    currency                VARCHAR(3),
    non_fiscal              BOOLEAN,
    doc_sha                 VARCHAR,
    device_serial_number    VARCHAR,
    customer_card_number    VARCHAR,
    client_reg_number       VARCHAR,
    raw_xml                 TEXT,
    ingested_at             TIMESTAMP,
    source_rev              INTEGER DEFAULT 1
);

-- ── Fact: sale lines ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS fct_sale_lines (
    doc_id          BIGINT,
    row_num         INTEGER,
    product_code    VARCHAR,
    product_name    VARCHAR,
    department      VARCHAR,
    quantity        DECIMAL(12,3),
    unit            VARCHAR,
    price           DECIMAL(12,4),
    product_sum     DECIMAL(12,2),
    discount_amount DECIMAL(12,2),
    discount_type   VARCHAR,
    excise          DECIMAL(12,2),
    sum_without_vat DECIMAL(12,2),
    vat_sum         DECIMAL(12,2),
    vat_rate        DECIMAL(5,2),
    vat_title       VARCHAR,
    total_sum       DECIMAL(12,2),
    row_type        VARCHAR,
    pos_code        VARCHAR,
    doc_date        DATE,
    PRIMARY KEY (doc_id, row_num)
);

-- ── Fact: payments ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS fct_payments (
    doc_id                  BIGINT,
    payment_seq             INTEGER,
    payment_type            VARCHAR,
    payment_method          VARCHAR,
    amount                  DECIMAL(12,2),
    card_type               VARCHAR,
    card_pan_masked         VARCHAR,
    card_tid                VARCHAR,
    card_reference_number   VARCHAR,
    gift_card_number        VARCHAR,
    doc_date                DATE,
    PRIMARY KEY (doc_id, payment_seq)
);

-- ── Dimension: store ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS dim_store (
    store_number    VARCHAR PRIMARY KEY,
    store_name      VARCHAR,
    country         VARCHAR(2) DEFAULT 'LV'
);

-- ── Dimension: POS terminal ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS dim_pos (
    pos_id                  INTEGER PRIMARY KEY,
    device_serial_number    VARCHAR,
    first_seen              TIMESTAMP,
    last_seen               TIMESTAMP
);

-- ── Dimension: operator ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS dim_operator (
    operator_id     VARCHAR PRIMARY KEY,
    operator_name   VARCHAR,
    first_seen      TIMESTAMP,
    last_seen       TIMESTAMP
);

-- ── Dimension: product (SCD1) ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS dim_product (
    product_code    VARCHAR PRIMARY KEY,
    product_name    VARCHAR,
    department      VARCHAR,
    vat_rate        DECIMAL(5,2)
);

-- ── Dimension: customer ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS dim_customer (
    customer_key            VARCHAR PRIMARY KEY,
    customer_kind           VARCHAR,   -- 'loyalty' | 'b2b'
    customer_card_number    VARCHAR,
    client_reg_number       VARCHAR,
    client_title            VARCHAR
);

-- ── Dimension: document type (static) ────────────────────────────────────────
CREATE TABLE IF NOT EXISTS dim_doc_type (
    doc_type        VARCHAR PRIMARY KEY,
    doc_type_lv     VARCHAR,
    has_line_items  BOOLEAN,
    use_for_revenue BOOLEAN
);

INSERT INTO dim_doc_type VALUES
    ('sale',           'darījums',       true,  true),
    ('z_report',       'Z pārskats',     false, false),
    ('x_report',       'X pārskats',     false, false),
    ('initialization', 'inicializācija', false, false),
    ('non_fiscal',     'nefiskāls',      false, false),
    ('cash_drawer',    'nauda',          false, false),
    ('unknown',        '',               false, false)
ON CONFLICT DO NOTHING;

-- ── Dimension: date (2020-01-01 to 2035-12-31) ───────────────────────────────
CREATE TABLE IF NOT EXISTS dim_date (
    date            DATE PRIMARY KEY,
    year            INTEGER,
    quarter         INTEGER,
    month           INTEGER,
    week            INTEGER,
    day_of_week     INTEGER,  -- 1=Monday
    is_weekend      BOOLEAN,
    day_name_en     VARCHAR,
    day_name_lv     VARCHAR,
    month_name_en   VARCHAR
);

INSERT INTO dim_date
SELECT
    d::DATE                                     AS date,
    YEAR(d)                                     AS year,
    QUARTER(d)                                  AS quarter,
    MONTH(d)                                    AS month,
    WEEKOFYEAR(d)                               AS week,
    ISODOW(d)                                   AS day_of_week,  -- 1=Monday … 7=Sunday
    ISODOW(d) IN (6, 7)                         AS is_weekend,
    DAYNAME(d)                                  AS day_name_en,
    CASE ISODOW(d)
        WHEN 1 THEN 'Pirmdiena'
        WHEN 2 THEN 'Otrdiena'
        WHEN 3 THEN 'Trešdiena'
        WHEN 4 THEN 'Ceturtdiena'
        WHEN 5 THEN 'Piektdiena'
        WHEN 6 THEN 'Sestdiena'
        WHEN 7 THEN 'Svētdiena'
    END                                         AS day_name_lv,
    MONTHNAME(d)                                AS month_name_en
FROM generate_series(DATE '2020-01-01', DATE '2035-12-31', INTERVAL 1 DAY) AS t(d)
ON CONFLICT DO NOTHING;

-- ── Aggregate: daily revenue ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS agg_daily_revenue (
    doc_date        DATE,
    store_number    VARCHAR,
    pos_id          INTEGER,
    operator_id     VARCHAR,
    gross           DECIMAL(14,2),
    txn_count       INTEGER,
    item_count      INTEGER,
    PRIMARY KEY (doc_date, store_number, pos_id, operator_id)
);

-- ── Aggregate: product daily ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS agg_product_daily (
    doc_date        DATE,
    product_code    VARCHAR,
    qty             DECIMAL(14,3),
    gross           DECIMAL(14,2),
    lines           INTEGER,
    PRIMARY KEY (doc_date, product_code)
);

-- ── Aggregate: hourly ────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS agg_hourly (
    doc_date        DATE,
    hour_of_day     INTEGER,
    store_number    VARCHAR,
    txn_count       INTEGER,
    gross           DECIMAL(14,2),
    PRIMARY KEY (doc_date, hour_of_day, store_number)
);

-- ── Data quality issues log ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS _data_quality_issues (
    doc_id          BIGINT,
    issue_type      VARCHAR,
    detail          VARCHAR,
    recorded_at     TIMESTAMP DEFAULT current_timestamp
);
