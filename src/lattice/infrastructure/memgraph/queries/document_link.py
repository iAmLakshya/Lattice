class DocumentLinkQueries:
    CREATE_LINK = """
    MATCH (c:DocumentChunk {id: $chunk_id})
    MATCH (e) WHERE e.qualified_name = $entity_qualified_name
    MERGE (c)-[r:DOCUMENTS]->(e)
    SET r.link_type = $link_type,
        r.confidence = $confidence,
        r.line_start = $line_start,
        r.line_end = $line_end,
        r.code_hash = $code_hash,
        r.reasoning = $reasoning,
        r.created_at = datetime()
    RETURN r
    """

    GET_CHUNK_LINKS = """
    MATCH (c:DocumentChunk {id: $chunk_id})-[r:DOCUMENTS]->(e)
    RETURN e.qualified_name AS entity_name,
           e.file_path AS entity_file,
           labels(e)[0] AS entity_type,
           e.start_line AS entity_start_line,
           e.end_line AS entity_end_line,
           r.link_type AS link_type,
           r.confidence AS confidence,
           r.line_start AS line_start,
           r.line_end AS line_end,
           r.code_hash AS code_hash
    ORDER BY r.confidence DESC
    """

    GET_ENTITY_DOCUMENTATION = """
    MATCH (c:DocumentChunk)-[r:DOCUMENTS]->(e {qualified_name: $entity_name})
    MATCH (d:Document)-[:CONTAINS_CHUNK]->(c)
    RETURN d.file_path AS document_path,
           d.title AS document_title,
           c.id AS chunk_id,
           c.heading_path AS heading_path,
           c.content_preview AS preview,
           c.drift_status AS drift_status,
           c.drift_score AS drift_score,
           r.link_type AS link_type,
           r.confidence AS confidence
    ORDER BY r.confidence DESC
    """

    GET_CHUNKS_FOR_CODE_CHANGE = """
    MATCH (c:DocumentChunk)-[r:DOCUMENTS]->(e {qualified_name: $entity_name})
    WHERE r.code_hash <> $new_code_hash
    RETURN c.id AS chunk_id,
           c.heading_path AS heading_path,
           r.link_type AS link_type,
           r.confidence AS confidence
    """

    FIND_ALL_DRIFTED = """
    MATCH (c:DocumentChunk)-[r:DOCUMENTS]->(e)
    WHERE c.project_name = $project_name
      AND c.drift_status IN ['minor_drift', 'major_drift']
    MATCH (d:Document)-[:CONTAINS_CHUNK]->(c)
    RETURN d.file_path AS document_path,
           c.heading_path AS heading_path,
           e.qualified_name AS entity_name,
           e.file_path AS entity_file,
           c.drift_status AS drift_status,
           c.drift_score AS drift_score
    ORDER BY c.drift_score DESC
    """

    UPDATE_LINK_LINE_RANGE = """
    MATCH (c:DocumentChunk {id: $chunk_id})-[r:DOCUMENTS]->(e {qualified_name: $entity_name})
    SET r.line_start = $line_start,
        r.line_end = $line_end,
        r.code_hash = $code_hash,
        r.calibrated_at = datetime()
    RETURN r
    """

    DELETE_CHUNK_LINKS = """
    MATCH (c:DocumentChunk {id: $chunk_id})-[r:DOCUMENTS]->()
    DELETE r
    """
