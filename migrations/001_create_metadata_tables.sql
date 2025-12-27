CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE project_metadata (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_name VARCHAR(255) NOT NULL UNIQUE,
    version INTEGER NOT NULL DEFAULT 1,
    folder_structure JSONB,           -- FolderNode tree
    project_overview TEXT,            -- 3-5 paragraph description
    core_features JSONB,              -- Array of CoreFeature objects
    architecture_diagram TEXT,        -- ASCII diagram
    tech_stack JSONB,                 -- TechStack object
    dependencies JSONB,               -- DependencyInfo object
    entry_points JSONB,               -- Array of EntryPoint objects
    generated_by VARCHAR(50) NOT NULL DEFAULT 'claude-agent',
    generation_model VARCHAR(100),
    generation_duration_ms INTEGER,
    generation_tokens_used INTEGER,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    indexed_at TIMESTAMPTZ,
    CONSTRAINT valid_version CHECK (version > 0),
    CONSTRAINT valid_status CHECK (status IN ('pending', 'generating', 'completed', 'failed', 'partial'))
);

CREATE TABLE metadata_generation_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_metadata_id UUID REFERENCES project_metadata(id) ON DELETE CASCADE,
    field_name VARCHAR(100) NOT NULL,
    status VARCHAR(20) NOT NULL,
    error_message TEXT,
    duration_ms INTEGER,
    tokens_used INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_project_metadata_name ON project_metadata(project_name);
CREATE INDEX idx_project_metadata_updated ON project_metadata(updated_at);
CREATE INDEX idx_project_metadata_status ON project_metadata(status);
CREATE INDEX idx_generation_log_project ON metadata_generation_log(project_metadata_id);
CREATE INDEX idx_generation_log_created ON metadata_generation_log(created_at);
