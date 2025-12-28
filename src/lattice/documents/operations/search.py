from lattice.documents.indexer import DocumentSearcher


async def search_documents(
    query: str,
    searcher: DocumentSearcher,
    project_name: str | None = None,
    limit: int = 10,
):
    return await searcher.search(
        query=query,
        project_name=project_name,
        limit=limit,
    )
