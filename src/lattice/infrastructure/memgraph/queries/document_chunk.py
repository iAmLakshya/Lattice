class DocumentChunkQueries:
    CREATE_CHUNK = """
    CREATE (c:DocumentChunk {
        id: $id,
        document_path: $document_path,
        project_name: $project_name,
        heading_path: $heading_path,
        heading_level: $heading_level,
        content_preview: $content_preview,
        content_hash: $content_hash,
        start_line: $start_line,
        end_line: $end_line,
        drift_status: 'unknown'
    })
    RETURN c
    """

    LINK_CHUNK_TO_DOCUMENT = """
    MATCH (d:Document {file_path: $document_path})
    MATCH (c:DocumentChunk {id: $chunk_id})
    MERGE (d)-[:CONTAINS_CHUNK]->(c)
    """

    GET_DOCUMENT_CHUNKS = """
    MATCH (d:Document {file_path: $document_path})-[:CONTAINS_CHUNK]->(c:DocumentChunk)
    RETURN c.id, c.heading_path, c.heading_level, c.content_preview,
           c.drift_status, c.drift_score, c.start_line, c.end_line
    ORDER BY c.start_line
    """

    UPDATE_CHUNK_DRIFT = """
    MATCH (c:DocumentChunk {id: $chunk_id})
    SET c.drift_status = $drift_status,
        c.drift_score = $drift_score,
        c.last_drift_check_at = datetime()
    RETURN c
    """

    DELETE_DOCUMENT_CHUNKS = """
    MATCH (d:Document {file_path: $document_path})-[:CONTAINS_CHUNK]->(c:DocumentChunk)
    OPTIONAL MATCH (c)-[r:DOCUMENTS]->()
    DETACH DELETE r, c
    """
