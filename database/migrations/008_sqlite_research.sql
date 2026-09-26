-- Research persistence: normalized external knowledge items (Research R1A).

CREATE TABLE IF NOT EXISTS research_items (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    external_ref TEXT NOT NULL,
    title TEXT NOT NULL,
    url TEXT,
    summary TEXT,
    published_at TEXT,
    fetched_at TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    epistemic TEXT NOT NULL,
    entity_tickers TEXT NOT NULL DEFAULT '[]',
    normalization_status TEXT NOT NULL,
    provider TEXT,
    ingestion_method TEXT,
    language TEXT,
    reasons TEXT,
    external_ref_derived INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_research_items_source_external
ON research_items(source_id, external_ref);

CREATE INDEX IF NOT EXISTS idx_research_items_source
ON research_items(source_id);

CREATE INDEX IF NOT EXISTS idx_research_items_published
ON research_items(published_at DESC);

CREATE INDEX IF NOT EXISTS idx_research_items_epistemic
ON research_items(epistemic);
