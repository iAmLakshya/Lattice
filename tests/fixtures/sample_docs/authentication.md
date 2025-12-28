# Authentication System

## Overview

This document describes the authentication and authorization system implemented in `src/api/auth.py`. The `AuthService` class handles all authentication operations including user login, logout, token management, and registration.

## AuthService Class

The `AuthService` is initialized with a `UserRepository` for data access:

```python
class AuthService:
    TOKEN_EXPIRY_HOURS = 24

    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo
        self._active_tokens: dict[str, AuthToken] = {}
```

### Login

```python
async def login(email: str, password: str) -> AuthToken
```

Authenticates a user and creates a session token valid for 24 hours.

**Process:**
1. Looks up user by email via `user_repo.find_by_email()`
2. Verifies the account is active (`user.is_active`)
3. Validates password using `user.verify_password()`
4. Creates and stores an `AuthToken` with expiration

**Raises:**
- `AuthenticationError`: If credentials are invalid or account is deactivated

**Security Note:** Invalid login attempts return a generic "Invalid email or password" message to prevent user enumeration.

### Logout

```python
async def logout(token: str) -> bool
```

Invalidates an authentication token by removing it from the `_active_tokens` dictionary.

**Returns:** `True` if the token was found and invalidated, `False` otherwise.

### Token Verification

```python
async def verify_token(token: str) -> Optional[User]
```

Verifies a token and returns the associated user.

**Process:**
1. Looks up token in `_active_tokens`
2. Checks if token has expired by comparing `datetime.now()` with `auth_token.expires_at`
3. If expired, removes token and returns `None`
4. Returns user via `user_repo.find_by_id(auth_token.user_id)`

### User Registration

```python
async def register(email: str, username: str, password: str) -> User
```

Registers a new user account.

**Process:**
1. Checks for existing user with same email
2. Hashes password using `hash_password()` from `utils.crypto`
3. Creates `User` instance with `created_at` timestamp
4. Persists via `user_repo.create()`

**Raises:**
- `ValueError`: If email is already registered

## AuthToken Model

```python
@dataclass
class AuthToken:
    token: str
    user_id: int
    expires_at: datetime
```

Tokens are generated using `generate_token()` from `utils.crypto` which produces URL-safe random strings using `secrets.token_urlsafe(32)`.

## Token Expiration

Tokens expire after 24 hours (configurable via `TOKEN_EXPIRY_HOURS` class attribute). The expiration is calculated using:

```python
expires_at = datetime.now() + timedelta(hours=self.TOKEN_EXPIRY_HOURS)
```

## Password Security

Passwords are never stored in plain text. The `hash_password()` function in `utils/crypto.py` uses:

- **Algorithm:** PBKDF2-SHA256
- **Iterations:** 100,000 rounds
- **Salt:** 32-byte random salt generated via `secrets.token_hex()`
- **Output format:** `{salt}${hash}`

Password verification uses `secrets.compare_digest()` for timing-safe comparison.

## AuthenticationError Exception

```python
class AuthenticationError(Exception):
    """Raised when authentication fails."""
    pass
```

This exception is raised for all authentication failures:
- Invalid email
- Invalid password
- Deactivated account

## Security Best Practices

### Generic Error Messages

All authentication failures return the same generic error message:
```
"Invalid email or password"
```

This prevents attackers from determining whether an email exists in the system.

### Account Deactivation

Deactivated accounts (`is_active=False`) cannot log in. The error message is:
```
"Account is deactivated"
```

### Token Storage

Active tokens are stored in an in-memory dictionary (`_active_tokens`). In production, this would typically be Redis for:
- Persistence across restarts
- Shared state across instances
- Automatic expiration via Redis TTL

## Integration with Other Systems

### Event Publishing

Login and logout events are published to the `EventBus`:

- `USER_LOGIN`: Published on successful login
- `USER_LOGOUT`: Published on logout
- `USER_LOGIN_FAILED`: Published on failed login attempt

### Cache Invalidation

The `CacheInvalidationHandler` listens for user events and invalidates cached user data when accounts are modified.

## Example Usage

```python
auth_service = AuthService(user_repo=UserRepository(db))

try:
    token = await auth_service.login("user@example.com", "password123")
    print(f"Logged in, token expires at: {token.expires_at}")
except AuthenticationError as e:
    print(f"Login failed: {e}")

user = await auth_service.verify_token(token.token)
if user:
    print(f"Token valid for user: {user.username}")

success = await auth_service.logout(token.token)
```
