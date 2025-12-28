# Event-Driven Architecture

## Philosophy and Design

The application follows an event-driven architecture that decouples components through asynchronous message passing. Rather than components calling each other directly, they communicate by publishing and subscribing to events. This pattern promotes loose coupling, making the system more maintainable, testable, and extensible.

The event system is implemented in `src/core/events.py` and serves as the nervous system of the application. Every significant action, from user authentication to payment processing, generates events that other components can observe and react to.

## The EventBus

At the heart of the event system is the `EventBus` class. It implements the publish-subscribe pattern as a singleton, ensuring all components share the same event infrastructure. The singleton pattern is intentional here because events must flow through a single channel to maintain consistency and enable global features like audit logging.

You obtain the EventBus instance by calling `EventBus.get_instance()`. The class manages its own lifecycle, creating the instance on first access and reusing it thereafter. For testing purposes, `EventBus.reset()` clears the singleton and allows fresh initialization.

The EventBus maintains a registry of handlers organized by event type. When you publish an event, the bus looks up all handlers registered for that event type and dispatches the event to each one concurrently using `asyncio.gather()`. This concurrent dispatch ensures handlers don't block each other, though it means handlers must be designed to operate independently.

## Event Structure

Events are represented by the `Event` dataclass. Each event carries a type, payload, timestamp, source identifier, and optional correlation ID.

The event type is an enum value from `EventType` that categorizes the event. The payload is a dictionary containing event-specific data. The timestamp is automatically set to the current UTC time when the event is created. The source identifies which component generated the event. The correlation ID enables tracing related events across the system.

Events are immutable by convention. Once created, their properties should not be modified. This immutability is essential for reliable event handling, as multiple handlers may process the same event concurrently.

The `to_dict()` method serializes an event for logging or transmission. The serialized form uses ISO 8601 format for timestamps and the enum value string for the event type.

## Event Types

The `EventType` enum defines all event categories recognized by the system. Events are organized into three main groups: user events, data events, and system events.

User events track the user lifecycle. `USER_CREATED` fires when a new user registers. `USER_UPDATED` fires when profile information changes. `USER_DELETED` fires when an account is removed. Authentication events include `USER_LOGIN` for successful logins, `USER_LOGOUT` for explicit logouts, and `USER_LOGIN_FAILED` for failed authentication attempts.

Data events signal changes to business entities. The generic `ITEM_CREATED`, `ITEM_UPDATED`, and `ITEM_DELETED` events cover most entity lifecycle changes. These events carry the entity type and ID in their payload.

System events handle infrastructure concerns. `CACHE_INVALIDATED` signals when cache entries are removed. `ERROR_OCCURRED` broadcasts error conditions for centralized handling. `AUDIT_LOG` captures security-relevant actions for compliance.

## Event Handlers

Event handlers are classes that implement the `EventHandler` abstract base class. Each handler must implement two things: the `event_types` property that returns a list of event types the handler wants to receive, and the `handle()` method that processes incoming events.

Handlers are registered with the EventBus by calling `subscribe(handler)`. The bus automatically routes matching events to each handler. A handler can subscribe to multiple event types, and multiple handlers can subscribe to the same event type.

The `unsubscribe()` method removes a handler from all its registered event types. This is primarily used during testing or when dynamically reconfiguring the system.

Handler execution is asynchronous and concurrent. If one handler raises an exception, it does not prevent other handlers from receiving the event. Exceptions are collected but not re-raised to the publisher.

## Built-in Handlers

The system includes several built-in handlers for common cross-cutting concerns.

The `AuditLogHandler` subscribes to all event types and records them for compliance purposes. Events are buffered in memory and flushed to disk when the buffer reaches 100 entries or when explicitly flushed. This batching reduces I/O overhead while maintaining a complete audit trail.

The `CacheInvalidationHandler` maintains cache consistency by listening for data modification events. When it receives a `USER_UPDATED` or `USER_DELETED` event, it invalidates the corresponding user cache entries. Similarly, `ITEM_UPDATED` and `ITEM_DELETED` events trigger invalidation of item caches. This automatic invalidation ensures the cache never serves stale data.

The `NotificationHandler` sends notifications for important events. New user registrations trigger welcome emails. Repeated login failures may indicate a brute force attack and trigger security alerts. Critical errors are reported to administrators immediately.

## Middleware

The EventBus supports middleware functions that process events before they reach handlers. Middleware can inspect events, modify them, or block them entirely.

To add middleware, call `add_middleware()` with a callable that takes an event and returns either a (possibly modified) event or `None`. Returning `None` stops the event from propagating further.

Middleware runs synchronously in the order added. Each middleware receives the event as modified by previous middleware. This chain allows for filtering, transformation, enrichment, and access control.

Common middleware use cases include adding trace IDs for distributed tracing, filtering sensitive events from reaching certain handlers, rate limiting event propagation, and logging all events for debugging.

## Publishing Events

Publishing an event is straightforward. Create an `Event` instance with the appropriate type and payload, then call `publish()` on the EventBus.

```python
await EventBus.get_instance().publish(
    Event(
        type=EventType.USER_LOGIN,
        payload={"user_id": user.id, "ip_address": request.ip},
        source="auth_service",
    )
)
```

The publish call is asynchronous and waits for all handlers to complete. If you need fire-and-forget semantics, wrap the publish in `asyncio.create_task()`.

For publishing multiple events atomically, use `publish_many()`. This method dispatches all events concurrently, which is more efficient than sequential publishing.

## The on_event Decorator

For simple handler use cases, the `@on_event` decorator provides a functional approach. Decorating a function with `@on_event` automatically creates a handler class and registers it with the EventBus.

```python
@on_event(EventType.USER_CREATED, EventType.USER_UPDATED)
async def handle_user_change(event: Event):
    user_id = event.payload.get("user_id")
    await sync_user_to_external_system(user_id)
```

The decorator supports both sync and async functions. Decorated functions are automatically wrapped in a handler class and registered at module load time.

## Error Handling

Event handling errors are isolated to prevent cascade failures. When a handler raises an exception, the exception is caught and collected, but other handlers continue processing the event normally.

The `ERROR_OCCURRED` event type is specifically designed for error reporting. When errors occur, components should publish this event type to enable centralized error handling and monitoring.

For critical errors that require immediate attention, the `NotificationHandler` can be configured to send alerts. The handler examines the error severity and routes notifications appropriately.

## Testing Events

Testing event-driven code requires care because of the global singleton nature of the EventBus. The `reset()` class method clears all state, including registered handlers and middleware. Call this in test setup to ensure a clean slate.

For testing specific handlers, you can subscribe a mock handler and verify it receives expected events. For testing publishers, you can inspect the event types and payloads that were published.

Integration tests should use the full event infrastructure to verify that components work together correctly. Unit tests should isolate components by mocking the EventBus.

## Performance Characteristics

Event publishing is designed for low latency. The publish path involves a dictionary lookup for handler registration and concurrent dispatch to handlers. For most workloads, publishing overhead is negligible.

Handler execution time directly impacts publish latency because `publish()` awaits all handlers. Long-running handlers should offload work to background tasks or queues to avoid blocking the publisher.

The EventBus does not persist events. If the application crashes, in-flight events are lost. For critical events that must not be lost, consider publishing to an external message queue in addition to the EventBus.

Memory usage scales with the number of registered handlers. Each handler registration adds a small amount of overhead. The event objects themselves are short-lived and garbage collected after all handlers complete.
