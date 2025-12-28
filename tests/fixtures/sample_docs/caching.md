# Caching Infrastructure

## Introduction

The caching subsystem is a critical component of the application's performance architecture. It reduces database load, minimizes API latency, and provides resilience against temporary backend unavailability. This document describes the implementation in `src/core/cache.py`, covering the multi-layer architecture, cache backends, and integration patterns.

## Architecture Overview

Our caching strategy follows a hierarchical model with two distinct layers working in concert. The first layer, known as L1, is an in-memory LRU cache that provides sub-millisecond access times for frequently accessed data. When the L1 cache misses, requests fall through to the L2 layer, which is backed by Redis and provides shared state across all application instances.

The `Cache` class serves as the unified interface for this architecture. When you call `cache.get(key)`, the system first checks the local `MemoryCache`. If the key is not found or has expired, it queries the `RedisCache`. When a value is found in L2 but not L1, the system automatically promotes the value to L1 for faster subsequent access.

This promotion strategy is transparent to application code. Developers interact with a single `Cache` instance without needing to understand the underlying layer mechanics.

## Memory Cache Implementation

The `MemoryCache` class implements an in-memory LRU (Least Recently Used) cache with a configurable maximum size. By default, the cache holds up to 1000 entries, though this can be adjusted at initialization time.

When the cache reaches capacity, the least recently accessed entry is evicted to make room for new data. This eviction strategy ensures that frequently accessed data remains in cache while stale entries are automatically removed. The implementation uses Python's `OrderedDict` to maintain access order with O(1) complexity for both reads and writes.

Each cached entry is wrapped in a `CacheEntry` object that tracks metadata including creation timestamp, expiration time, and hit count. The hit count is particularly useful for analytics and understanding cache effectiveness. Entries automatically expire based on their TTL, and expired entries are lazily removed during read operations.

Thread safety is ensured through asyncio locks. While this adds minimal overhead, it prevents race conditions when multiple coroutines access the cache concurrently.

The cache maintains internal statistics accessible via `get_stats()`:
- Total hits and misses
- Current cache size
- Number of evictions
- Calculated hit rate

These metrics are essential for tuning cache size and TTL values in production.

## Redis Cache Implementation

The `RedisCache` class provides distributed caching through Redis. Unlike the in-memory cache, Redis allows cached data to be shared across multiple application instances, which is essential for load-balanced deployments.

All keys are prefixed with a configurable namespace (default: "cache:") to avoid collisions with other Redis users. Values are serialized to JSON before storage and deserialized on retrieval. This means cached objects must be JSON-serializable.

The Redis backend supports native TTL through the `SETEX` command. When a TTL is specified, Redis automatically expires the key without requiring application-side cleanup. This is more efficient than the lazy expiration used by the memory cache.

Connection management is handled externally. The `RedisCache` expects an already-configured Redis client to be passed during initialization, allowing the application to manage connection pooling and configuration centrally.

## Cache TTL and Expiration

Time-to-live (TTL) values control how long cached data remains valid. The default TTL is one hour, chosen as a balance between freshness and performance. Different data types may warrant different TTL values.

User profile data, which changes infrequently, can use longer TTLs of several hours. Session tokens should use shorter TTLs matching their validity period. Rapidly changing data like real-time metrics may need TTLs of just a few minutes.

When no TTL is specified, entries remain in cache indefinitely until evicted by the LRU algorithm or explicitly invalidated. This behavior should be used carefully to avoid serving stale data.

Expiration is checked lazily in the memory cache. An expired entry remains in memory until the next read attempt, at which point it is removed. This lazy approach reduces overhead but means memory usage may temporarily exceed expectations when entries expire.

## Cache Invalidation

Cache invalidation is one of the two hard problems in computer science. Our system provides several mechanisms for maintaining cache consistency.

The `invalidate(key)` method removes a specific key from all cache layers. This should be called whenever the underlying data changes. The method also publishes a `CACHE_INVALIDATED` event to the `EventBus`, allowing other components to react to invalidation.

For bulk invalidation, the `invalidate_pattern(pattern)` method removes all keys matching a glob pattern. This is useful when an entire category of data becomes stale, such as invalidating all user-related caches when a user is deleted.

The system integrates with the event-driven architecture through the `CacheInvalidationHandler`. This handler subscribes to data modification events (`USER_UPDATED`, `USER_DELETED`, `ITEM_UPDATED`, `ITEM_DELETED`) and automatically invalidates related cache entries. For example, when a user profile is updated, both the `user:{id}` and `user_profile:{id}` cache keys are invalidated.

## The Cached Decorator

For simple caching scenarios, the `@cached` decorator provides a declarative approach. Decorating an async function with `@cached` automatically caches its return value based on the function arguments.

```python
@cached(ttl=timedelta(minutes=30), key_prefix="user")
async def get_user_profile(user_id: int) -> UserProfile:
    return await database.fetch_user_profile(user_id)
```

Cache keys are automatically generated from the function name and all arguments. In the example above, calling `get_user_profile(42)` would use the cache key `user:42`. Long keys (over 200 characters) are automatically hashed using MD5 to prevent key length issues with Redis.

The decorator supports both sync and async functions. For sync functions, the caching layer still operates asynchronously, which may require careful consideration in mixed codebases.

When using the decorator, cache misses result in function execution, and the return value is stored before being returned to the caller. Subsequent calls with the same arguments return the cached value without executing the function.

## Get-or-Set Pattern

The `get_or_set()` method implements the common cache-aside pattern in a single atomic operation. This is the most frequently used caching pattern in the application.

```python
user = await cache.get_or_set(
    f"user:{user_id}",
    lambda: database.fetch_user(user_id),
    ttl=timedelta(hours=2)
)
```

The method first attempts to retrieve the value from cache. If found, it returns immediately. If not found, it executes the factory function, stores the result in cache, and returns the value. This pattern eliminates the common race condition where multiple concurrent requests all miss the cache and simultaneously query the database.

The factory function can be synchronous or asynchronous. If it returns a coroutine, the cache awaits it automatically.

## Default Cache Instance

The module provides a singleton default cache instance for convenience. The `init_cache()` function initializes this instance with the provided L1 and L2 backends. The `get_cache()` function returns the default instance, initializing it with default settings if not already configured.

Most application code should use the default instance rather than creating separate cache instances. This ensures consistent configuration and makes cache statistics aggregation easier.

## Performance Considerations

Cache operations are designed to be fast, but some patterns can cause performance issues.

Avoid caching very large objects. While the system can handle megabytes of data per entry, large entries consume memory rapidly and increase serialization overhead. Consider caching references or IDs instead of full objects when possible.

Be mindful of cache key cardinality. A cache with millions of unique keys may exceed available memory. Use the maximum size parameter to enforce limits.

Monitor the hit rate metric. A hit rate below 50% suggests the cache is not effectively serving its purpose. This could indicate that TTL values are too short, keys are too unique, or the cached data simply isn't accessed frequently enough to benefit from caching.

The memory cache uses asyncio locks for thread safety. Under extreme concurrent load, lock contention could become a bottleneck. In such cases, consider partitioning the cache or using a lockless approach for read-heavy workloads.

## Integration with Other Components

The caching system integrates deeply with other application components. The `EventBus` receives cache invalidation events, allowing components to react to cache state changes. The `CacheInvalidationHandler` listens for data changes and maintains cache consistency automatically.

Payment processing uses caching for frequently accessed payment method tokens and user billing information. Authentication tokens are validated against a cache to avoid repeated database lookups.

The data pipeline framework does not use caching directly, as it processes data in batches where caching individual records would be inefficient. However, pipeline configuration and metadata are cached.
