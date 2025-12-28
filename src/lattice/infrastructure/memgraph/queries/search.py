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
