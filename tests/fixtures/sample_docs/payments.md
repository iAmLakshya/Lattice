# Payment Processing

This document describes the payment processing system.

## Overview

The payment system uses the Strategy pattern with multiple provider implementations:

- Stripe (primary)
- PayPal (fallback)
- Square (fallback)

## PaymentService

The main entry point for payment processing.

### Creating a Payment Intent

```python
async def create_intent(
    amount: Decimal,
    currency: str,
    user_id: str,
    description: str,
    metadata: dict = None
) -> PaymentIntent
```

Creates a new payment intent in PENDING status.

### Processing Payments

```python
async def process_payment(intent_id: str, payment_method_id: str) -> PaymentIntent
```

Processes a payment with automatic retry and fallback logic:

1. Attempts payment with primary provider (Stripe)
2. On failure, retries up to 5 times with exponential backoff
3. If primary fails, falls back to secondary providers
4. Emits events for success/failure tracking

### Refunds

```python
async def refund(intent_id: str, amount: Decimal = None) -> str
```

Refunds a captured payment. Partial refunds supported.

### Cancellation

```python
async def cancel(intent_id: str) -> bool
```

Cancels a payment intent. Only works for PENDING or AUTHORIZED states.

## Payment States

| Status     | Description       |
| ---------- | ----------------- |
| PENDING    | Initial state     |
| PROCESSING | Being processed   |
| AUTHORIZED | Funds reserved    |
| CAPTURED   | Payment complete  |
| FAILED     | Processing failed |
| REFUNDED   | Payment refunded  |
| CANCELLED  | Intent cancelled  |
| EXPIRED    | Intent expired    |

## Error Handling

The system defines these error types:

- `PaymentError`: Base exception
- `InsufficientFundsError`: Not enough funds
- `PaymentDeclinedError`: Card declined
- `PaymentTimeoutError`: Provider timeout (retriable)
- `ProviderUnavailableError`: Provider down (retriable)
- `FraudDetectedError`: Potential fraud detected

## Configuration

Set these environment variables:

- `STRIPE_API_KEY`: Stripe API key
- `STRIPE_WEBHOOK_SECRET`: Webhook signing secret
- `PAYPAL_CLIENT_ID`: PayPal client ID
- `PAYPAL_CLIENT_SECRET`: PayPal secret
- `PAYMENT_RETRY_COUNT`: Number of retries (default: 5)
