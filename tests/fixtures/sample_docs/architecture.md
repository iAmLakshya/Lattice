# System Architecture

## Overview

This document describes the overall architecture of the sample project, including core patterns, module responsibilities, and integration points.

## Module Structure

```
src/
├── api/           # HTTP API endpoints
│   ├── auth.py    # Authentication endpoints (AuthService, AuthToken)
│   └── handlers.py # Request handlers
├── services/      # Business logic
│   ├── payment.py # Payment processing (PaymentService, PaymentProvider)
│   └── data_pipeline.py # Data processing (Pipeline, PipelineStage)
├── models/        # Data models
│   ├── user.py    # User model
│   └── base.py    # Base model
├── repositories/  # Data access
│   └── base.py    # BaseRepository
├── core/          # Core utilities
│   ├── events.py  # Event system (EventBus, Event, EventHandler)
│   ├── cache.py   # Caching (Cache, MemoryCache, RedisCache)
│   └── middleware.py # HTTP middleware
└── utils/         # Helper utilities
    └── crypto.py  # Cryptographic utilities (hash_password, generate_token)

frontend/
├── components/    # React components (LoginForm, UserProfile, DataTable)
├── hooks/         # Custom React hooks (useAuth, useApi)
└── store/         # Redux state management
```

## Core Design Patterns

### Repository Pattern

All data access operations go through repository classes that extend `BaseRepository`. This provides:

- Consistent interface for CRUD operations
- Transaction management
- Query building abstraction
- Connection pooling

### Event-Driven Architecture

The `EventBus` class implements a publish-subscribe pattern for decoupling components. It is implemented as a singleton accessible via `EventBus.get_instance()`.

Events are published for:

- User lifecycle events (`USER_CREATED`, `USER_UPDATED`, `USER_DELETED`)
- Authentication events (`USER_LOGIN`, `USER_LOGOUT`, `USER_LOGIN_FAILED`)
- Data change events (`ITEM_CREATED`, `ITEM_UPDATED`, `ITEM_DELETED`)
- System events (`CACHE_INVALIDATED`, `ERROR_OCCURRED`, `AUDIT_LOG`)

The EventBus supports middleware for event preprocessing:

```python
bus = EventBus.get_instance()
bus.add_middleware(my_middleware)
bus.subscribe(MyHandler())
await bus.publish(event)
```

### Strategy Pattern

Payment providers implement the `PaymentProvider` abstract base class, allowing runtime provider selection. Current implementations:

- `StripeProvider`: Primary payment processor
- `PayPalProvider`: Secondary fallback provider

The `PaymentProviderFactory` manages provider registration and fallback chain configuration.

### Decorator-Based Caching

The `@cached` decorator provides transparent caching for expensive operations:

```python
from core.cache import cached
from datetime import timedelta

@cached(ttl=timedelta(minutes=30), key_prefix="user")
async def get_user(user_id: int) -> User:
    return await db.fetch_user(user_id)
```

Cache keys are automatically generated from function name and arguments.

## Multi-Layer Cache Architecture

The caching system uses a two-tier architecture:

- **L1 Cache** (`MemoryCache`): In-process LRU cache with 1000 entry limit
- **L2 Cache** (`RedisCache`): Distributed cache for shared state across instances

The `Cache` class provides a unified interface that checks L1 first, falls back to L2, and populates upper layers on cache misses. Default TTL is 1 hour.

## Data Pipeline Framework

The `Pipeline` class enables composable data processing workflows:

```python
pipeline = (
    Pipeline[list[dict], list[User]]("user_import")
    .add_stage(ValidateStage(validate_user_data))
    .add_stage(MapStage(transform_to_user))
    .add_stage(FilterStage(lambda u: u.is_active))
    .add_stage(BatchStage(100))
)
```

Available stages:
- `MapStage`: Transform each item in a collection
- `FilterStage`: Filter items by predicate
- `BatchStage`: Split data into fixed-size batches
- `FlattenStage`: Flatten nested lists
- `AggregateStage`: Reduce collection to single value
- `ValidateStage`: Validate data against rules
- `BranchStage`: Execute parallel processing paths

Stages are composable using the `>>` operator for chaining.

## Frontend Architecture

### Components

React components using TypeScript with the following key components:

- `LoginForm.tsx`: User login with email/password
- `UserProfile.tsx`: Profile display and management
- `DataTable.tsx`: Generic data display with sorting and pagination

### Custom Hooks

- `useAuth`: Authentication state and login/logout methods
- `useApi`: API calls with automatic caching and retry logic

### State Management

Redux-based state management in `store/`. Actions are dispatched through the `useAuth` and `useApi` hooks.

## Security Architecture

### Authentication

JWT-based authentication with 24-hour token expiration. Tokens are managed by `AuthService` and stored in `_active_tokens` dictionary.

The `AuthService.verify_token()` method validates tokens and returns the associated user.

### Password Security

Passwords are hashed using PBKDF2-SHA256 with 100,000 iterations via the `hash_password()` function in `utils/crypto.py`. Salts are 32 bytes generated using `secrets.token_hex()`.

### Authorization

Role-based access control with three roles:
- `admin`: Full system access
- `user`: Standard user access
- `guest`: Read-only access

## Infrastructure

### Databases

- **PostgreSQL**: Primary relational data store for users, payments, and transactions
- **Redis**: Caching layer and session storage

### Message Queue

RabbitMQ for asynchronous processing of:
- Email notifications
- Webhook deliveries
- Background job execution

### Monitoring

Application metrics exposed via Prometheus endpoint at `/metrics`.
