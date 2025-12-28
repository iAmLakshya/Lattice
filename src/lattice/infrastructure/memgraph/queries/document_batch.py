class DocumentBatchQueries:
    BATCH_CREATE_CHUNKS = """
    UNWIND $batch AS row
    CREATE (c:DocumentChunk {
        id: row.id,
        document_path: row.document_path,
        project_name: row.project_name,
        heading_path: row.heading_path,
        heading_level: row.heading_level,
        content_preview: row.content_preview,
        content_hash: row.content_hash,
        start_line: row.start_line,
        end_line: row.end_line,
        drift_status: 'unknown'
    })
    """

    BATCH_LINK_CHUNKS_TO_DOCUMENT = """
    UNWIND $batch AS row
    MATCH (d:Document {file_path: row.document_path})
    MATCH (c:DocumentChunk {id: row.chunk_id})
    MERGE (d)-[:CONTAINS_CHUNK]->(c)
    """

    BATCH_CREATE_LINKS = """
    UNWIND $batch AS row
    MATCH (c:DocumentChunk {id: row.chunk_id})
    MATCH (e) WHERE e.qualified_name = row.entity_name
    MERGE (c)-[r:DOCUMENTS]->(e)
    SET r.link_type = row.link_type,
        r.confidence = row.confidence,
        r.line_start = row.line_start,
        r.line_end = row.line_end,
        r.code_hash = row.code_hash,
        r.reasoning = row.reasoning,
        r.created_at = datetime()
    RETURN count(*) AS created
    """
