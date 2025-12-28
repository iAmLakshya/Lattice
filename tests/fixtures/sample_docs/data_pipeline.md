# Data Pipeline Framework

## Overview

The data pipeline framework in `src/services/data_pipeline.py` provides a composable, type-safe approach to data processing. Inspired by functional programming patterns and Unix pipes, the framework allows developers to build complex data transformations from simple, reusable stages.

The framework is used extensively for ETL operations, data validation, batch processing, and real-time stream transformations. Its design emphasizes correctness through strong typing, observability through hooks and events, and flexibility through composition.

## Core Concepts

The fundamental unit of work is the `PipelineStage`. Each stage takes input of one type, performs some transformation, and produces output of another type. Stages are pure functions in the conceptual sense: given the same input and context, they produce the same output. This purity makes pipelines predictable and testable.

Stages compose through chaining. When you connect stage A to stage B using the `>>` operator, you create a new `ChainedStage` that feeds A's output into B's input. This chaining can continue indefinitely, building arbitrarily complex pipelines from simple building blocks.

The `Pipeline` class wraps a sequence of stages and provides orchestration, error handling, hooks, and event integration. While you can chain stages directly, the Pipeline class adds production-ready features that bare stages lack.

## Pipeline Context

Every stage receives a `PipelineContext` object that carries execution metadata and accumulates state as the pipeline runs. The context includes a unique pipeline ID, start timestamp, metadata dictionary, error list, and stage progress tracking.

The context is particularly useful for debugging and monitoring. You can inspect which stages have completed, what errors occurred, and how long execution has taken. Stages can also write to the metadata dictionary to communicate information downstream.

The context is mutable by design. Stages can record errors, mark their completion, and add metadata. This mutation is safe because pipeline execution is sequential within a single run.

## Stage Results

When a stage completes, it returns a `StageResult` object containing the output data, success flag, optional error, timing information, and record counts. This structured result enables the pipeline to make intelligent decisions about how to proceed.

If a stage returns a failed result, the pipeline typically halts execution and returns the failure upstream. This fail-fast behavior prevents corrupted data from propagating through subsequent stages.

Record counts are especially valuable for batch processing. Knowing how many records were processed versus how many failed helps diagnose data quality issues and estimate completion times.

## Built-in Stages

The framework provides several commonly needed stages out of the box.

The `MapStage` applies a transformation function to each element in a collection. It supports both synchronous and asynchronous mapping functions, automatically detecting and awaiting coroutines. The `continue_on_error` parameter controls whether individual item failures halt the stage or are collected for later analysis.

The `FilterStage` retains only elements matching a predicate function. Like MapStage, it supports async predicates. Filtering is a common preprocessing step to remove invalid or irrelevant records before expensive transformations.

The `BatchStage` splits a collection into fixed-size batches for parallel processing or to respect rate limits. Batching is essential when working with external APIs that have request limits or when you want to parallelize processing across workers.

The `FlattenStage` reverses the effect of batching, combining nested lists into a single flat list. This is typically used after parallel processing of batches to reconstitute a unified result set.

The `AggregateStage` reduces a collection to a single value using an aggregator function. Common aggregations include counting records, summing values, computing statistics, and building summary reports.

The `ValidateStage` checks data against validation rules. The validator function can return `True` for success, `False` for failure, or a string error message. Validation stages often appear early in pipelines to reject bad data before processing begins.

The `BranchStage` enables parallel processing paths. Given a dictionary of named stages, it runs all of them concurrently on the same input and collects results into a dictionary. Branching is useful when multiple independent transformations must be applied to the same data.

## Composing Stages

The `>>` operator chains stages together. When you write `stage_a >> stage_b`, you create a new `ChainedStage` that:

1. Runs stage_a with the input
2. If stage_a succeeds, passes its output to stage_b
3. If stage_a fails, short-circuits and returns the failure

Chained stages are themselves stages, so they can be chained further. This composability is the framework's key strength.

Type safety flows through chains. If stage_a produces type X and stage_b expects type Y, the type checker will flag the mismatch. This catches pipeline construction errors at development time rather than runtime.

## Building Pipelines

While direct stage chaining works for simple cases, the `Pipeline` class provides a more feature-rich approach for production use.

```python
pipeline = (
    Pipeline[InputType, OutputType]("my_pipeline")
    .add_stage(ValidationStage())
    .add_stage(TransformStage())
    .add_stage(LoadStage())
)
```

The Pipeline is generic over its input and output types. The pipeline name is used for logging and event identification. Stages are added using `add_stage()`, which returns the pipeline for fluent chaining.

The `execute()` method runs the pipeline with provided input data. It creates a fresh PipelineContext, runs each stage in sequence, handles errors, invokes hooks, and publishes events.

## Pipeline Hooks

Hooks allow custom code to run at key points during pipeline execution without modifying stages. The pipeline supports four hook types: before_stage, after_stage, on_error, and on_complete.

Before-stage hooks run immediately before each stage processes. They receive the stage name, input data, and context. Use these for logging, metrics, or data inspection.

After-stage hooks run immediately after each successful stage. They receive the stage name, output data, and context. Use these for checkpointing, progress reporting, or conditional logic.

Error hooks run when a stage fails. They receive the stage name, exception, and context. Use these for error reporting, alerting, or recovery attempts.

Completion hooks run after the pipeline finishes successfully. They receive the final output data and context. Use these for cleanup, notifications, or publishing results.

Hooks can be synchronous or asynchronous. Async hooks are awaited automatically.

## Error Handling

Pipeline execution follows a fail-fast approach by default. When a stage returns a failed result, execution stops immediately and the failure propagates to the caller.

The `MapStage` offers a more forgiving option through `continue_on_error`. When enabled, individual item failures are recorded in the context but don't halt stage execution. The stage completes with partial results, and the pipeline continues. This is useful for batch processing where occasional bad records shouldn't invalidate the entire batch.

Exceptions thrown by stage code are caught and wrapped in `StageResult` failures. This prevents uncaught exceptions from crashing the pipeline infrastructure while still surfacing the error appropriately.

The context accumulates all errors encountered during execution. After a pipeline completes (successfully or not), you can inspect `context.errors` to see everything that went wrong.

## Event Integration

Pipelines integrate with the `EventBus` to provide observability and enable reactive architectures.

At pipeline start, an `ITEM_CREATED` event is published with the pipeline ID, name, and stage count. This signals that a new pipeline run has begun.

At pipeline completion, an `ITEM_UPDATED` event is published with the pipeline ID, final status, total duration, and list of completed stages. This provides a summary of the run for monitoring dashboards and alerting.

Components interested in pipeline execution can subscribe to these events. For example, a monitoring service might track active pipelines and their durations, alerting when pipelines take too long or fail.

## ETL Helper

The `create_etl_pipeline()` function simplifies the common Extract-Transform-Load pattern. Given an extract function, transform function, and load function, it constructs a complete pipeline with appropriate stages.

The extract stage fetches data from a source and returns a list of records. The transform stage applies to each record individually via MapStage. The load stage receives the full list of transformed records and persists them.

This helper covers many standard ETL scenarios while allowing customization through the provided functions.

## Performance Optimization

Pipelines execute stages sequentially by default, which ensures predictable ordering but may not utilize resources optimally. For I/O-bound stages, consider batching followed by concurrent processing of batch elements.

The `BranchStage` enables parallel processing of independent transformations. When multiple analyses must be applied to the same data, branching avoids redundant data passes.

Memory usage can spike when processing large datasets. Consider streaming approaches for very large inputs, processing data in batches and accumulating results incrementally.

Stage duration is tracked in `StageResult.duration_ms`. Monitoring these timings helps identify bottleneck stages that warrant optimization.

## Testing Pipelines

Pipeline testing follows a layered approach. Unit tests verify individual stages in isolation by calling `stage.process()` directly with test data and a mock context. Integration tests verify that stages compose correctly by running short pipelines end-to-end.

The `PipelineContext` can be pre-populated with test data before execution. This is useful for testing stages that depend on context metadata set by earlier stages.

Hooks provide a non-invasive way to observe pipeline execution during tests. A test can add a hook that records all stage results, then assert on those results after execution.

## Real-World Usage Patterns

User import pipelines validate incoming user records, transform them to internal format, deduplicate against existing users, and batch-insert into the database. Error records are collected for human review rather than blocking the import.

Data export pipelines query the database in batches, transform records to the export format, and write to external storage. Rate limiting hooks prevent overwhelming external systems.

Analytics pipelines aggregate raw events into metrics, compute derived values, and store results for dashboarding. Branch stages compute multiple metrics in parallel from the same event stream.
