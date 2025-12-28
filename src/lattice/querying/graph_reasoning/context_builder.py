import asyncio

from lattice.infrastructure.memgraph.client import MemgraphClient
from lattice.querying.graph_reasoning.graph_queries import (
    find_class_with_methods,
    find_file_context,
)
from lattice.querying.graph_reasoning.models import GraphContext
from lattice.querying.graph_reasoning.traversal import (
    find_call_chain,
    find_full_hierarchy,
    find_implementation_context,
    find_transitive_callers,
    find_transitive_callees,
)
from lattice.querying.query_planner import QueryPlan


async def gather_caller_context(
    client: MemgraphClient,
    context: GraphContext,
    plan: QueryPlan,
) -> None:
    max_hops = plan.max_hops if plan.requires_multi_hop else 1

    if context.primary_entities:
        for entity in context.primary_entities:
            callers = await find_transitive_callers(
                client,
                entity.qualified_name or entity.name,
                max_hops=max_hops,
            )
            context.callers.extend(callers)
    else:
        for entity in plan.entities:
            callers = await find_transitive_callers(
                client,
                entity.name,
                max_hops=max_hops,
            )
            context.callers.extend(callers)


async def gather_callee_context(
    client: MemgraphClient,
    context: GraphContext,
    plan: QueryPlan,
) -> None:
    max_hops = plan.max_hops if plan.requires_multi_hop else 1

    if context.primary_entities:
        for entity in context.primary_entities:
            callees = await find_transitive_callees(
                client,
                entity.qualified_name or entity.name,
                max_hops=max_hops,
            )
            context.callees.extend(callees)
    else:
        for entity in plan.entities:
            callees = await find_transitive_callees(
                client,
                entity.name,
                max_hops=max_hops,
            )
            context.callees.extend(callees)


async def gather_call_chain_context(
    client: MemgraphClient,
    context: GraphContext,
    plan: QueryPlan,
) -> None:
    if len(plan.entities) >= 2:
        source = plan.entities[0].name
        target = plan.entities[1].name
        chains = await find_call_chain(client, source, target, plan.max_hops)
        context.call_chains.extend(chains)


async def gather_hierarchy_context(
    client: MemgraphClient,
    context: GraphContext,
    plan: QueryPlan,
) -> None:
    for entity in context.primary_entities:
        if entity.node_type == "Class":
            _, ancestors, descendants = await find_full_hierarchy(
                client,
                entity.qualified_name or entity.name,
            )
            context.parent_classes.extend(ancestors)
            context.child_classes.extend(descendants)
        else:
            callers = await find_transitive_callers(
                client,
                entity.qualified_name or entity.name,
                max_hops=plan.max_hops if plan.requires_multi_hop else 1,
            )
            context.callers.extend(callers)

    resolved_names = {e.name.lower() for e in context.primary_entities}
    resolved_names.update(e.qualified_name.lower() for e in context.primary_entities if e.qualified_name)

    for plan_entity in plan.entities:
        if plan_entity.name.lower() not in resolved_names:
            callers = await find_transitive_callers(
                client,
                plan_entity.name,
                max_hops=plan.max_hops if plan.requires_multi_hop else 1,
            )
            context.callers.extend(callers)


async def gather_implementation_context(
    client: MemgraphClient,
    context: GraphContext,
    plan: QueryPlan,
) -> None:
    for entity in context.primary_entities:
        impl_context = await find_implementation_context(
            client,
            entity.qualified_name or entity.name,
        )

        if impl_context:
            context.callers.extend(impl_context.get("callers", []))
            context.callees.extend(impl_context.get("callees", []))
            context.file_context.extend(impl_context.get("siblings", []))

        if entity.node_type == "Class":
            _, methods = await find_class_with_methods(
                client,
                entity.qualified_name or entity.name,
            )
            context.methods.extend(methods)


async def gather_dependency_context(
    client: MemgraphClient,
    context: GraphContext,
    plan: QueryPlan,
) -> None:
    for entity in context.primary_entities:
        if entity.file_path:
            file_ctx = await find_file_context(client, entity.file_path)
            for fc in file_ctx:
                if fc.get("entity"):
                    context.file_context.append(fc["entity"])


async def gather_comprehensive_context(
    client: MemgraphClient,
    context: GraphContext,
    plan: QueryPlan,
) -> None:
    tasks = []

    for entity in context.primary_entities[:3]:
        entity_name = entity.qualified_name or entity.name

        tasks.append(find_transitive_callers(client, entity_name, max_hops=2, limit=10))
        tasks.append(find_transitive_callees(client, entity_name, max_hops=2, limit=10))

        if entity.node_type == "Class":
            tasks.append(find_class_with_methods(client, entity_name))

    if tasks:
        results = await asyncio.gather(*tasks, return_exceptions=True)

        idx = 0
        for entity in context.primary_entities[:3]:
            if idx < len(results) and isinstance(results[idx], list):
                context.callers.extend(results[idx])
            idx += 1

            if idx < len(results) and isinstance(results[idx], list):
                context.callees.extend(results[idx])
            idx += 1

            if entity.node_type == "Class":
                if idx < len(results) and isinstance(results[idx], tuple):
                    _, methods = results[idx]
                    context.methods.extend(methods)
                idx += 1
