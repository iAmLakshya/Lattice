# Authentication API

This document describes the authentication system for our application.

## Overview

The `AuthService` class handles all authentication operations including:

- User login with email/password
- User logout and token invalidation
- Token verification
- User registration

## AuthService

Located in `src/api/auth.py`, this service is initialized with a `UserRepository`.

### Login

```python
async def login(email: str, password: str) -> AuthToken
```

Authenticates a user and creates a session token valid for 24 hours.

**Raises:**
- `AuthenticationError`: If credentials are invalid or account is deactivated

### Logout

```python
async def logout(token: str) -> bool
```

Invalidates an authentication token. Returns True if successful.

### Verify Token

```python
async def verify_token(token: str) -> Optional[User]
```

Verifies a token and returns the associated user if valid.

### Register

```python
async def register(email: str, username: str, password: str) -> User
```

Registers a new user account.

**Raises:**
- `ValueError`: If email is already registered

## Token Expiration

Tokens expire after 24 hours (configurable via `TOKEN_EXPIRY_HOURS`).

## Security Notes

- Passwords are hashed using `hash_password` from `utils.crypto`
- Tokens are generated using `generate_token` from `utils.crypto`
- Invalid login attempts return generic error messages to prevent enumeration
