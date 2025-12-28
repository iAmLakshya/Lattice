class ProjectQueries:
    CREATE_PROJECT = """
    MERGE (p:Project {name: $name})
    ON CREATE SET p.created_at = datetime()
    SET p.path = $path,
        p.last_indexed_at = datetime()
    RETURN p
    """

    GET_PROJECT = """
    MATCH (p:Project {name: $name})
    RETURN p
    """

    LIST_PROJECTS = """
    MATCH (p:Project)
    OPTIONAL MATCH (f:File)
    WHERE f.path STARTS WITH p.path
    WITH p, count(DISTINCT f) as file_count
    RETURN p.name as name,
           p.path as path,
           p.created_at as created_at,
           p.last_indexed_at as last_indexed_at,
           file_count
    ORDER BY p.name
    """

    DELETE_PROJECT = """
    MATCH (p:Project {name: $name})
    OPTIONAL MATCH (f:File)
    WHERE f.path STARTS WITH p.path
    OPTIONAL MATCH (f)-[r1]->(e)
    OPTIONAL MATCH (e)-[r2]-()
    OPTIONAL MATCH (i:Import)
    WHERE i.file_path STARTS WITH p.path
    DETACH DELETE r1, r2, e, f, i, p
    """


class FileQueries:
    CREATE_FILE = """
    MERGE (f:File {path: $path})
    SET f.name = $name,
        f.language = $language,
        f.hash = $hash,
        f.line_count = $line_count,
        f.summary = $summary,
        f.indexed_at = datetime()
    RETURN f
    """

    GET_FILE = """
    MATCH (f:File {path: $path})
    RETURN f
    """

    GET_FILE_BY_HASH = """
    MATCH (f:File {path: $path, hash: $hash})
    RETURN f
    """

    DELETE_FILE_ENTITIES = """
    MATCH (f:File {path: $path})
    OPTIONAL MATCH (f)-[r1]->(entity)
    OPTIONAL MATCH (entity)-[r2]->()
    DETACH DELETE entity
    """

    GET_FILE_ENTITIES = """
    MATCH (f:File {path: $path})-[:DEFINES]->(entity)
    RETURN entity.name as name,
           entity.qualified_name as qualified_name,
           labels(entity)[0] as type,
           entity.signature as signature,
           entity.summary as summary,
           entity.start_line as start_line,
           entity.end_line as end_line
    """

    FIND_FILE_DEPENDENCIES = """
    MATCH (f:File {path: $path})-[:IMPORTS]->(i:Import)
    RETURN i.name as import_name,
           i.source as source,
           i.is_external as is_external
    """


class EntityQueries:
    CREATE_CLASS = """
    MERGE (c:Class {qualified_name: $qualified_name})
    SET c.name = $name,
        c.signature = $signature,
        c.docstring = $docstring,
        c.summary = $summary,
        c.start_line = $start_line,
        c.end_line = $end_line,
        c.file_path = $file_path,
        c.project_id = $project_id
    RETURN c
    """

    CREATE_FUNCTION = """
    MERGE (f:Function {qualified_name: $qualified_name})
    SET f.name = $name,
        f.signature = $signature,
        f.docstring = $docstring,
        f.summary = $summary,
        f.is_async = $is_async,
        f.start_line = $start_line,
        f.end_line = $end_line,
        f.file_path = $file_path,
        f.project_id = $project_id
    RETURN f
    """

    CREATE_METHOD = """
    MERGE (m:Method {qualified_name: $qualified_name})
    SET m.name = $name,
        m.signature = $signature,
        m.docstring = $docstring,
        m.summary = $summary,
        m.is_async = $is_async,
        m.is_static = $is_static,
        m.is_classmethod = $is_classmethod,
        m.start_line = $start_line,
        m.end_line = $end_line,
        m.file_path = $file_path,
        m.parent_class = $parent_class,
        m.project_id = $project_id
    RETURN m
    """

    BACKFILL_PROJECT_ID = """
    MATCH (p:Project)
    WITH p.name as proj_name, p.path as proj_path
    MATCH (n)
    WHERE (n:Function OR n:Class OR n:Method)
      AND n.file_path STARTS WITH proj_path
      AND n.project_id IS NULL
    SET n.project_id = proj_name
    RETURN count(n) as updated
    """

    CREATE_IMPORT = """
    MERGE (i:Import {name: $name, file_path: $file_path})
    SET i.alias = $alias,
        i.source = $source,
        i.is_external = $is_external,
        i.line_number = $line_number
    RETURN i
    """


class RelationshipQueries:
    CREATE_FILE_DEFINES_CLASS = """
    MATCH (f:File {path: $file_path})
    MATCH (c:Class {qualified_name: $class_name})
    MERGE (f)-[:DEFINES]->(c)
    """

    CREATE_FILE_DEFINES_FUNCTION = """
    MATCH (f:File {path: $file_path})
    MATCH (fn:Function {qualified_name: $function_name})
    MERGE (f)-[:DEFINES]->(fn)
    """

    CREATE_CLASS_DEFINES_METHOD = """
    MATCH (c:Class {qualified_name: $class_name})
    MATCH (m:Method {qualified_name: $method_name})
    MERGE (c)-[:DEFINES_METHOD]->(m)
    """

    CREATE_CLASS_EXTENDS = """
    MATCH (child:Class {qualified_name: $child_name})
    MATCH (parent:Class {qualified_name: $parent_name})
    MERGE (child)-[:EXTENDS]->(parent)
    """

    CREATE_FILE_IMPORTS = """
    MATCH (f:File {path: $file_path})
    MATCH (i:Import {name: $import_name, file_path: $file_path})
    MERGE (f)-[:IMPORTS]->(i)
    """

    CREATE_FUNCTION_CALLS = """
    MATCH (caller) WHERE caller.qualified_name = $caller_name
    MATCH (callee) WHERE callee.qualified_name = $callee_name
    MERGE (caller)-[:CALLS]->(callee)
    """

    CREATE_METHOD_CALLS_BY_NAME = """
    MATCH (caller) WHERE caller.qualified_name = $caller_name
    MATCH (callee:Method) WHERE callee.name = $method_name
    MERGE (caller)-[:CALLS]->(callee)
    """


class SearchQueries:
    FIND_CALLERS = """
    MATCH (caller)-[:CALLS]->(target {qualified_name: $qualified_name})
    RETURN caller.name as caller_name,
           caller.qualified_name as qualified_name,
           labels(caller)[0] as type,
           caller.file_path as file_path
    """

    FIND_CALLEES = """
    MATCH (source {qualified_name: $qualified_name})-[:CALLS]->(callee)
    RETURN callee.name as callee_name,
           callee.qualified_name as qualified_name,
           labels(callee)[0] as type,
           callee.file_path as file_path
    """

    FIND_CLASS_HIERARCHY = """
    MATCH path = (child:Class {qualified_name: $qualified_name})-[:EXTENDS*0..5]->(parent:Class)
    RETURN [node in nodes(path) | node.qualified_name] as hierarchy
    """

    SEARCH_BY_NAME = """
    MATCH (n)
    WHERE n.name CONTAINS $query OR n.qualified_name CONTAINS $query
    RETURN n.name as name,
           n.qualified_name as qualified_name,
           labels(n)[0] as type,
           n.file_path as file_path,
           n.summary as summary
    LIMIT $limit
    """

    GET_STATS = """
    MATCH (f:File)
    WITH count(f) as file_count
    MATCH (c:Class)
    WITH file_count, count(c) as class_count
    MATCH (fn:Function)
    WITH file_count, class_count, count(fn) as function_count
    MATCH (m:Method)
    RETURN file_count, class_count, function_count, count(m) as method_count
    """


class BatchQueries:
    """Batch query templates using UNWIND for bulk operations."""

    BATCH_CREATE_CLASS = """
    MERGE (c:Class {qualified_name: row.qualified_name})
    SET c.name = row.name,
        c.signature = row.signature,
        c.docstring = row.docstring,
        c.summary = row.summary,
        c.start_line = row.start_line,
        c.end_line = row.end_line,
        c.file_path = row.file_path
    """

    BATCH_CREATE_FUNCTION = """
    MERGE (f:Function {qualified_name: row.qualified_name})
    SET f.name = row.name,
        f.signature = row.signature,
        f.docstring = row.docstring,
        f.summary = row.summary,
        f.is_async = row.is_async,
        f.start_line = row.start_line,
        f.end_line = row.end_line,
        f.file_path = row.file_path
    """

    BATCH_CREATE_METHOD = """
    MERGE (m:Method {qualified_name: row.qualified_name})
    SET m.name = row.name,
        m.signature = row.signature,
        m.docstring = row.docstring,
        m.summary = row.summary,
        m.is_async = row.is_async,
        m.is_static = row.is_static,
        m.is_classmethod = row.is_classmethod,
        m.start_line = row.start_line,
        m.end_line = row.end_line,
        m.file_path = row.file_path,
        m.parent_class = row.parent_class
    """

    BATCH_CREATE_IMPORT = """
    MERGE (i:Import {name: row.name, file_path: row.file_path})
    SET i.alias = row.alias,
        i.source = row.source,
        i.is_external = row.is_external,
        i.line_number = row.line_number
    """

    BATCH_CREATE_FILE = """
    MERGE (f:File {path: row.path})
    SET f.name = row.name,
        f.language = row.language,
        f.hash = row.hash,
        f.line_count = row.line_count,
        f.summary = row.summary,
        f.indexed_at = datetime()
    """

    BATCH_CREATE_DEFINES_CLASS = """
    MATCH (f:File {path: row.file_path})
    MATCH (c:Class {qualified_name: row.class_name})
    MERGE (f)-[:DEFINES]->(c)
    """

    BATCH_CREATE_DEFINES_FUNCTION = """
    MATCH (f:File {path: row.file_path})
    MATCH (fn:Function {qualified_name: row.function_name})
    MERGE (f)-[:DEFINES]->(fn)
    """

    BATCH_CREATE_DEFINES_METHOD = """
    MATCH (c:Class {qualified_name: row.class_name})
    MATCH (m:Method {qualified_name: row.method_name})
    MERGE (c)-[:DEFINES_METHOD]->(m)
    """

    BATCH_CREATE_EXTENDS = """
    MATCH (child:Class {qualified_name: row.child_name})
    MATCH (parent:Class {qualified_name: row.parent_name})
    MERGE (child)-[:EXTENDS]->(parent)
    """

    BATCH_CREATE_IMPORTS = """
    MATCH (f:File {path: row.file_path})
    MATCH (i:Import {name: row.import_name, file_path: row.file_path})
    MERGE (f)-[:IMPORTS]->(i)
    """

    BATCH_CREATE_CALLS = """
    MATCH (caller) WHERE caller.qualified_name = row.caller_name
    MATCH (callee) WHERE callee.qualified_name = row.callee_name
    MERGE (caller)-[:CALLS]->(callee)
    RETURN count(*) as created
    """


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


class CypherQueries:
    """Legacy combined query collection for backward compatibility."""

    CREATE_PROJECT = ProjectQueries.CREATE_PROJECT
    GET_PROJECT = ProjectQueries.GET_PROJECT
    LIST_PROJECTS = ProjectQueries.LIST_PROJECTS
    DELETE_PROJECT = ProjectQueries.DELETE_PROJECT

    CREATE_FILE = FileQueries.CREATE_FILE
    GET_FILE = FileQueries.GET_FILE
    GET_FILE_BY_HASH = FileQueries.GET_FILE_BY_HASH
    DELETE_FILE_ENTITIES = FileQueries.DELETE_FILE_ENTITIES
    GET_FILE_ENTITIES = FileQueries.GET_FILE_ENTITIES
    FIND_FILE_DEPENDENCIES = FileQueries.FIND_FILE_DEPENDENCIES

    CREATE_CLASS = EntityQueries.CREATE_CLASS
    CREATE_FUNCTION = EntityQueries.CREATE_FUNCTION
    CREATE_METHOD = EntityQueries.CREATE_METHOD
    CREATE_IMPORT = EntityQueries.CREATE_IMPORT

    CREATE_FILE_DEFINES_CLASS = RelationshipQueries.CREATE_FILE_DEFINES_CLASS
    CREATE_FILE_DEFINES_FUNCTION = RelationshipQueries.CREATE_FILE_DEFINES_FUNCTION
    CREATE_CLASS_DEFINES_METHOD = RelationshipQueries.CREATE_CLASS_DEFINES_METHOD
    CREATE_CLASS_EXTENDS = RelationshipQueries.CREATE_CLASS_EXTENDS
    CREATE_FILE_IMPORTS = RelationshipQueries.CREATE_FILE_IMPORTS
    CREATE_FUNCTION_CALLS = RelationshipQueries.CREATE_FUNCTION_CALLS

    FIND_CALLERS = SearchQueries.FIND_CALLERS
    FIND_CALLEES = SearchQueries.FIND_CALLEES
    FIND_CLASS_HIERARCHY = SearchQueries.FIND_CLASS_HIERARCHY
    SEARCH_BY_NAME = SearchQueries.SEARCH_BY_NAME
    GET_STATS = SearchQueries.GET_STATS
