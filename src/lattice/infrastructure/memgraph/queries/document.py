class DocumentQueries:
    CREATE_DOCUMENT = """
    MERGE (d:Document {file_path: $file_path})
    SET d.relative_path = $relative_path,
        d.project_name = $project_name,
        d.title = $title,
        d.document_type = $document_type,
        d.content_hash = $content_hash,
        d.chunk_count = $chunk_count,
        d.drift_status = $drift_status,
        d.drift_score = $drift_score,
        d.indexed_at = datetime()
    RETURN d
    """

    GET_DOCUMENT = """
    MATCH (d:Document {file_path: $file_path})
    RETURN d
    """

    GET_DOCUMENT_BY_HASH = """
    MATCH (d:Document {file_path: $file_path, content_hash: $content_hash})
    RETURN d
    """

    LIST_PROJECT_DOCUMENTS = """
    MATCH (d:Document {project_name: $project_name})
    RETURN d.file_path, d.title, d.document_type, d.drift_status, d.drift_score,
           d.chunk_count, d.link_count, d.indexed_at
    ORDER BY d.file_path
    """

    LIST_DRIFTED_DOCUMENTS = """
    MATCH (d:Document {project_name: $project_name})
    WHERE d.drift_status IN ['minor_drift', 'major_drift']
    RETURN d.file_path, d.title, d.drift_status, d.drift_score
    ORDER BY d.drift_score DESC
    """

    DELETE_DOCUMENT = """
    MATCH (d:Document {file_path: $file_path})
    OPTIONAL MATCH (d)-[:CONTAINS_CHUNK]->(c:DocumentChunk)
    OPTIONAL MATCH (c)-[r:DOCUMENTS]->()
    DETACH DELETE r, c, d
    """

    UPDATE_DRIFT_STATUS = """
    MATCH (d:Document {file_path: $file_path})
    SET d.drift_status = $drift_status,
        d.drift_score = $drift_score,
        d.last_drift_check_at = datetime()
    RETURN d
    """
