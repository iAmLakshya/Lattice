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
