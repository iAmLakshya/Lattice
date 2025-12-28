# Payment Processing System

## Overview

The payment system is implemented in `src/services/payment.py` using the Strategy pattern with multiple provider implementations. The `PaymentService` class orchestrates payment flows with automatic retry and fallback logic.

## Payment Providers

### Supported Providers

The system supports three payment providers:

- **Stripe** (`StripeProvider`): Primary payment processor
- **PayPal** (`PayPalProvider`): Secondary fallback
- **Square** (`SquareProvider`): Tertiary fallback

> **DRIFT EXAMPLE (MISSING):** The code only implements Stripe and PayPal. Square is mentioned here but not implemented.

### PaymentProvider Interface

All providers implement the abstract `PaymentProvider` class:

```python
class PaymentProvider(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    async def create_customer(self, user_id: str, email: str) -> str:
        pass

    @abstractmethod
    async def tokenize_card(
        self,
        customer_id: str,
        card_number: str,
        exp_month: int,
        exp_year: int,
        cvv: str,
    ) -> str:
        pass

    @abstractmethod
    async def authorize(
        self,
        amount: Decimal,
        currency: str,
        token: str,
        idempotency_key: str,
    ) -> str:
        pass

    @abstractmethod
    async def capture(self, transaction_id: str, amount: Decimal) -> bool:
        pass

    @abstractmethod
    async def refund(
        self,
        transaction_id: str,
        amount: Decimal | None = None,
    ) -> str:
        pass

    @abstractmethod
    async def void(self, transaction_id: str) -> bool:
        pass
```

### PaymentProviderFactory

The `PaymentProviderFactory` manages provider registration and selection:

```python
PaymentProviderFactory.register(stripe_provider)
PaymentProviderFactory.set_primary("stripe")
provider = PaymentProviderFactory.get_primary()
```

## PaymentService

The `PaymentService` class provides the main entry point for payment operations.

### Initialization

```python
class PaymentService:
    def __init__(self, max_retries: int = 5, retry_delay: float = 2.0):
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._intents: dict[str, PaymentIntent] = {}
```

> **DRIFT EXAMPLE (PARAMETER):** The actual code uses `max_retries=3` and `retry_delay=1.0`, not 5 and 2.0 as documented.

### Creating Payment Intents

```python
async def create_intent(
    amount: Decimal,
    currency: str,
    user_id: str,
    description: str,
    metadata: dict = None
) -> PaymentIntent
```

Creates a new payment intent in `PENDING` status and publishes an `ITEM_CREATED` event to the `EventBus`.

### Processing Payments

```python
async def process_payment(intent_id: str, payment_method_id: str) -> PaymentIntent
```

Processes a payment with automatic retry and fallback logic:

1. Attempts payment with primary provider (Stripe)
2. On retriable errors, retries up to 5 times with exponential backoff starting at 2 seconds
3. If primary fails completely, falls back to secondary providers in order
4. Emits `ITEM_UPDATED` event on success, `ERROR_OCCURRED` on failure

> **DRIFT EXAMPLE (BEHAVIORAL):** The actual retry count is 3, not 5. The actual initial delay is 1.0 seconds, not 2.0.

### Refunds

```python
async def refund(intent_id: str, amount: Decimal = None) -> str
```

Refunds a captured payment. If `amount` is `None`, refunds the full payment amount. Partial refunds are supported.

**Requirements:**
- Payment must be in `CAPTURED` status
- Raises `PaymentError` with code `INVALID_STATE` if payment is not captured

### Cancellation

```python
async def cancel(intent_id: str) -> bool
```

Cancels a payment intent. Only works for intents in `PENDING` or `AUTHORIZED` states.

For authorized payments, the system automatically voids the authorization with the provider before marking as cancelled.

## Payment States

The `PaymentStatus` enum defines the payment lifecycle:

| Status       | Description                          | Can Transition To                |
|--------------|--------------------------------------|----------------------------------|
| `PENDING`    | Initial state after creation         | `PROCESSING`, `CANCELLED`        |
| `PROCESSING` | Currently being processed            | `AUTHORIZED`, `FAILED`           |
| `AUTHORIZED` | Funds reserved but not captured      | `CAPTURED`, `CANCELLED`          |
| `CAPTURED`   | Payment successfully completed       | `REFUNDED`                       |
| `FAILED`     | Processing failed                    | (terminal state)                 |
| `REFUNDED`   | Payment has been refunded            | (terminal state)                 |
| `CANCELLED`  | Intent was cancelled                 | (terminal state)                 |
| `EXPIRED`    | Intent expired before processing     | (terminal state)                 |

> **DRIFT EXAMPLE (MISSING):** The `EXPIRED` status is documented but not actually implemented in the `PaymentStatus` enum in the code.

## Error Handling

### Exception Hierarchy

```python
class PaymentError(Exception):
    def __init__(self, message: str, code: str, retriable: bool = False):
        self.code = code
        self.retriable = retriable
```

### Error Types

| Exception                  | Code                   | Retriable | Description                        |
|----------------------------|------------------------|-----------|-------------------------------------|
| `InsufficientFundsError`   | `INSUFFICIENT_FUNDS`   | No        | Payment source has insufficient funds |
| `PaymentDeclinedError`     | `PAYMENT_DECLINED`     | No        | Card declined by issuer             |
| `PaymentTimeoutError`      | `TIMEOUT`              | Yes       | Provider request timed out          |
| `ProviderUnavailableError` | `PROVIDER_UNAVAILABLE` | Yes       | Provider service is down            |
| `FraudDetectedError`       | `FRAUD_DETECTED`       | No        | Potential fraud detected            |

> **DRIFT EXAMPLE (MISSING):** The `FraudDetectedError` is documented but not implemented in the code.

### Retry Logic

When a retriable error occurs:

1. System waits for `retry_delay * (2 ** attempt)` seconds (exponential backoff)
2. Retries up to `max_retries` times with the same provider
3. If all retries fail, moves to the next provider in the fallback chain

## PaymentIntent Model

```python
@dataclass
class PaymentIntent:
    id: str
    amount: Decimal
    currency: str
    user_id: str
    description: str
    status: PaymentStatus = PaymentStatus.PENDING
    payment_method_id: str | None = None
    provider: str | None = None
    provider_transaction_id: str | None = None
    error_message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
```

### State Transition Validation

The `can_transition_to()` method validates state transitions:

```python
if not intent.can_transition_to(PaymentStatus.CAPTURED):
    raise PaymentError("Invalid state transition", "INVALID_STATE")
```

## Configuration

Set these environment variables:

| Variable                | Description                    | Default |
|-------------------------|--------------------------------|---------|
| `STRIPE_API_KEY`        | Stripe API key                 | Required |
| `STRIPE_WEBHOOK_SECRET` | Stripe webhook signing secret  | Required |
| `PAYPAL_CLIENT_ID`      | PayPal client ID               | Required |
| `PAYPAL_CLIENT_SECRET`  | PayPal client secret           | Required |
| `PAYMENT_RETRY_COUNT`   | Number of retry attempts       | 5       |
| `PAYMENT_RETRY_DELAY`   | Initial retry delay in seconds | 2.0     |

> **DRIFT EXAMPLE (BEHAVIORAL):** The documented defaults (5 retries, 2.0s delay) differ from the actual code defaults (3 retries, 1.0s delay).

## Event Integration

### Published Events

The payment service publishes events to the `EventBus`:

**On Intent Creation:**
```python
Event(
    type=EventType.ITEM_CREATED,
    payload={"intent_id": intent.id, "amount": str(amount)},
    source="payment_service",
)
```

**On Payment Success:**
```python
Event(
    type=EventType.ITEM_UPDATED,
    payload={
        "intent_id": intent.id,
        "status": intent.status.value,
        "amount": str(intent.amount),
        "provider": intent.provider,
    },
    source="payment_service",
)
```

**On Payment Failure:**
```python
Event(
    type=EventType.ERROR_OCCURRED,
    payload={
        "intent_id": intent.id,
        "error_code": error.code,
        "error_message": str(error),
    },
    source="payment_service",
)
```

## Stripe Provider Details

The `StripeProvider` implementation:

- Simulates API calls with 100-200ms latency
- Returns transaction IDs prefixed with `pi_`
- Declines payments when amount ends in `13` (for testing)

## PayPal Provider Details

The `PayPalProvider` implementation:

- Simulates higher latency (200-300ms) than Stripe
- Returns transaction IDs prefixed with `PAY-`
- Supports sandbox mode via constructor parameter

## Usage Example

```python
payment_service = PaymentService(max_retries=3, retry_delay=1.0)

intent = await payment_service.create_intent(
    amount=Decimal("99.99"),
    currency="USD",
    user_id="user_123",
    description="Premium subscription",
    metadata={"subscription_id": "sub_456"},
)

try:
    result = await payment_service.process_payment(
        intent_id=intent.id,
        payment_method_id="pm_card_visa",
    )
    print(f"Payment succeeded: {result.status}")
except PaymentDeclinedError as e:
    print(f"Payment declined: {e.reason}")
except PaymentError as e:
    print(f"Payment failed: {e.code}")
```
