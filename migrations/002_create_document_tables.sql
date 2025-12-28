CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_name VARCHAR(255) NOT NULL,
    file_path TEXT NOT NULL,
    relative_path TEXT NOT NULL,
    title TEXT,
    document_type VARCHAR(100) DEFAULT 'markdown',
    content_hash VARCHAR(64) NOT NULL,
    chunk_count INTEGER DEFAULT 0,
    link_count INTEGER DEFAULT 0,
    drift_status VARCHAR(20) DEFAULT 'unknown',
    drift_score REAL,
    indexed_at TIMESTAMPTZ,
    last_drift_check_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(project_name, file_path),
    CONSTRAINT valid_drift_status CHECK (
        drift_status IN ('aligned', 'minor_drift', 'major_drift', 'unknown')
    )
);

CREATE INDEX idx_documents_project ON documents(project_name);
CREATE INDEX idx_documents_type ON documents(document_type);
CREATE INDEX idx_documents_drift ON documents(drift_status);
CREATE INDEX idx_documents_path ON documents(file_path);

CREATE TABLE document_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    project_name VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    heading_path TEXT[] NOT NULL DEFAULT '{}',
    heading_level INTEGER NOT NULL DEFAULT 0,
    start_line INTEGER NOT NULL,
    end_line INTEGER NOT NULL,
    content_hash VARCHAR(64) NOT NULL,
    embedding_id VARCHAR(255),
    explicit_references TEXT[] DEFAULT '{}',
    drift_status VARCHAR(20) DEFAULT 'unknown',
    drift_score REAL,
    last_drift_check_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT valid_chunk_drift_status CHECK (
        drift_status IN ('aligned', 'minor_drift', 'major_drift', 'unknown')
    )
);

CREATE INDEX idx_chunks_document ON document_chunks(document_id);
CREATE INDEX idx_chunks_project ON document_chunks(project_name);
CREATE INDEX idx_chunks_drift ON document_chunks(drift_status);
CREATE INDEX idx_chunks_heading ON document_chunks USING GIN(heading_path);

CREATE TABLE document_links (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_chunk_id UUID NOT NULL REFERENCES document_chunks(id) ON DELETE CASCADE,
    code_entity_qualified_name TEXT NOT NULL,
    code_entity_type VARCHAR(50) NOT NULL,
    code_file_path TEXT NOT NULL,
    link_type VARCHAR(20) NOT NULL,
    confidence_score REAL NOT NULL,
    line_range_start INTEGER,
    line_range_end INTEGER,
    code_version_hash VARCHAR(64),
    reasoning TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_calibrated_at TIMESTAMPTZ,
    CONSTRAINT valid_link_type CHECK (link_type IN ('explicit', 'implicit'))
);

CREATE INDEX idx_links_chunk ON document_links(document_chunk_id);
CREATE INDEX idx_links_entity ON document_links(code_entity_qualified_name);
CREATE INDEX idx_links_type ON document_links(link_type);
CREATE INDEX idx_links_file ON document_links(code_file_path);

CREATE TABLE drift_analyses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_chunk_id UUID NOT NULL REFERENCES document_chunks(id) ON DELETE CASCADE,
    document_path TEXT NOT NULL,
    linked_entity_qualified_name TEXT NOT NULL,
    analysis_trigger VARCHAR(50) NOT NULL,
    drift_detected BOOLEAN NOT NULL,
    drift_severity VARCHAR(20) NOT NULL,
    drift_score REAL NOT NULL,
    issues JSONB DEFAULT '[]',
    explanation TEXT,
    doc_excerpt TEXT,
    code_excerpt TEXT,
    doc_version_hash VARCHAR(64) NOT NULL,
    code_version_hash VARCHAR(64) NOT NULL,
    analyzed_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT valid_drift_severity CHECK (
        drift_severity IN ('aligned', 'minor_drift', 'major_drift', 'unknown')
    )
);

CREATE INDEX idx_analyses_chunk ON drift_analyses(document_chunk_id);
CREATE INDEX idx_analyses_entity ON drift_analyses(linked_entity_qualified_name);
CREATE INDEX idx_analyses_time ON drift_analyses(analyzed_at DESC);
CREATE INDEX idx_analyses_drift ON drift_analyses(drift_detected, drift_severity);
