class BatchQueries:
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
