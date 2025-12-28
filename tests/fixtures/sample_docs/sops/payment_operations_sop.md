# Payment Operations Standard Operating Procedure

## Document Control

**Version:** 1.4
**Last Updated:** December 2024
**Owner:** Payments Team
**Review Cycle:** Monthly

## Purpose

This procedure documents the operational processes for managing payment transactions, handling disputes, processing refunds, and maintaining payment provider integrations. It ensures consistent handling of payment-related activities while maintaining compliance with financial regulations.

## Payment Processing Architecture

The payment system is built on the Strategy pattern as implemented in `src/services/payment.py`. The `PaymentService` class orchestrates payment flows using provider implementations that inherit from `PaymentProvider`.

Currently, the system supports two active providers. The `StripeProvider` serves as the primary processor, handling the majority of transactions with high reliability and fast processing times. The `PayPalProvider` acts as the fallback processor, receiving traffic when Stripe is unavailable or when transactions fail on the primary provider.

The `PaymentProviderFactory` manages provider selection and failover logic. The factory maintains the fallback chain and provides methods for runtime provider configuration.

All payment intents are tracked through the `PaymentIntent` model, which captures the complete transaction lifecycle from creation through final disposition.

## Transaction Lifecycle

### Intent Creation

When a user initiates a payment, the system creates a `PaymentIntent` through the `PaymentService.create_intent()` method. The intent is created in `PENDING` status and assigned a unique identifier.

The creation event is published to the `EventBus` as an `ITEM_CREATED` event, enabling downstream systems to track payment initiation for analytics and fraud detection.

At this stage, no funds have been reserved or charged. The intent represents the user's intention to pay, not an actual financial transaction.

### Payment Processing

The `PaymentService.process_payment()` method executes the actual payment. This is where funds are authorized and captured from the user's payment method.

The process begins by attempting the transaction with the primary provider (Stripe). If the authorization succeeds, the payment moves to `AUTHORIZED` status briefly, then to `CAPTURED` status upon successful capture.

If the primary provider fails with a retriable error such as `PaymentTimeoutError` or `ProviderUnavailableError`, the system retries up to 3 times with exponential backoff. The initial delay is 1.0 seconds, doubling with each retry attempt.

If retries are exhausted or the provider is completely unavailable, the system falls back to the secondary provider (PayPal). The same retry logic applies to the fallback provider.

If all providers and retries fail, the payment moves to `FAILED` status. An `ERROR_OCCURRED` event is published with details about the failure for monitoring and alerting.

### Successful Completion

Upon successful capture, the payment moves to `CAPTURED` status. An `ITEM_UPDATED` event is published with the final status, amount, and provider used.

The provider transaction ID is stored in `provider_transaction_id` for reconciliation with provider records. This ID is essential for refunds, disputes, and financial auditing.

The payment is now complete from the system's perspective. Downstream fulfillment processes should listen for the success event to trigger order completion.

### Failure Handling

Failed payments remain in `FAILED` status with the error message stored in `error_message`. The user can attempt the payment again by creating a new intent.

Different failure types require different responses. `InsufficientFundsError` suggests the user should try a different payment method. `PaymentDeclinedError` may indicate fraud risk and should be logged for review. Provider timeouts are typically transient and may succeed on retry.

Operations staff should monitor payment failure rates daily. Elevated failure rates may indicate provider issues, fraud attacks, or integration problems.

## Refund Processing

### When to Process Refunds

Refunds are processed when goods are returned, services are cancelled, or disputes are resolved in the customer's favor. All refunds must be authorized according to the refund authorization matrix (see appendix).

Refunds for transactions older than 180 days require additional approval due to chargeback risk considerations. Some providers may not support refunds for very old transactions.

### Executing Refunds

Refunds are processed through `PaymentService.refund()`. The method accepts the original intent ID and an optional amount for partial refunds.

The payment must be in `CAPTURED` status before refunding. Attempting to refund a pending or failed payment will raise a `PaymentError` with code `INVALID_STATE`.

For full refunds, omit the amount parameter. The system will refund the full captured amount. For partial refunds, specify the amount to refund. The total of all partial refunds cannot exceed the original captured amount.

Upon successful refund, the payment status changes to `REFUNDED`. The provider refund ID is returned for reference.

### Refund Best Practices

Process refunds promptly. Delayed refunds increase customer dissatisfaction and support burden.

Use partial refunds when appropriate. If a customer returns one item from a multi-item order, refund only that item's value.

Document refund reasons in the payment metadata. This information supports fraud analysis and business intelligence.

Monitor refund rates by merchant category and customer segment. High refund rates may indicate product quality issues or fraud patterns.

## Cancellation Processing

### Cancelling Pending Payments

Payments in `PENDING` status can be cancelled through `PaymentService.cancel()`. This removes the intent from processing without any financial transaction occurring.

Cancellation is appropriate when the user abandons the checkout flow, when inventory becomes unavailable, or when fraud is detected before processing.

### Cancelling Authorized Payments

Payments in `AUTHORIZED` status have reserved funds on the user's payment method but haven't completed capture. These can still be cancelled.

Cancellation of authorized payments releases the hold on the user's funds through a void operation with the provider. The `PaymentProvider.void()` method is called automatically during cancellation.

Once a payment is captured, it cannot be cancelled. Captured payments require refund processing to return funds.

## Dispute Management

### Dispute Receipt

Payment providers notify us of disputes (chargebacks) through webhook callbacks. The webhook handler creates an internal dispute record and publishes an event for processing.

Immediately upon dispute receipt, the operations team must gather evidence for the dispute response. Relevant evidence includes order details, delivery confirmation, customer communication, and transaction logs.

### Evidence Gathering

Query the `AuditLogHandler` records for all events related to the disputed payment intent. This includes the original `ITEM_CREATED` event, processing events, and any status changes.

Retrieve customer authentication events using `USER_LOGIN` records around the transaction time. Strong authentication evidence supports our case in fraud-related disputes.

Export the complete `PaymentIntent` record including metadata. Payment metadata often contains evidence valuable for dispute resolution.

### Response Submission

Compile evidence according to provider requirements. Each provider has specific formats and required fields for dispute responses.

Submit the response within the provider's deadline, typically 7-14 days from dispute receipt. Late responses result in automatic loss of the dispute.

Track dispute outcomes for analysis. Patterns in lost disputes may indicate operational improvements needed.

## Provider Management

### Health Monitoring

Monitor provider availability through the `PaymentProviderFactory.get_primary()` and processing success rates. Availability below 99.5% triggers investigation.

The `ProviderUnavailableError` exception indicates complete provider outage. The `PaymentTimeoutError` indicates degraded performance. Track both metrics separately.

Set up alerts for provider error rate spikes. Use `EventBus` error events to monitor payment failures in real time.

### Failover Testing

Regularly test failover to the secondary provider. Simulate primary provider outage and verify transactions process successfully through PayPal.

Test the full fallback chain by disabling providers in sequence. Verify the `PaymentProviderFactory.get_fallback_chain()` returns providers in the expected order.

Document failover test results. Testing should occur monthly at minimum, and after any provider integration changes.

### Credential Rotation

Rotate provider API keys annually or immediately upon any suspected compromise. Keys are stored in environment variables as specified in the security policy.

During rotation, update the new key in staging first. Verify payment processing works before updating production.

Maintain the old key temporarily during rotation to handle in-flight transactions. Revoke the old key only after confirming no transactions are pending.

## Daily Operations

### Transaction Reconciliation

Daily, reconcile processed transactions against provider settlement reports. The `PaymentIntent` records should match provider transaction counts and amounts.

Investigate discrepancies immediately. Common causes include webhook delivery failures, duplicate processing, and timezone differences in reporting.

Use the `provider_transaction_id` field to match internal records with provider records. This unique identifier appears in both systems.

### Fraud Monitoring

Review transactions flagged by provider fraud scoring. High-risk transactions may require manual review before fulfillment.

Monitor for patterns suggesting fraud rings: multiple transactions from similar IP ranges, same payment methods used for different users, or unusually high transaction volumes.

The `PaymentDeclinedError` with reason `do_not_honor` often indicates fraud detection at the issuer level. Repeated occurrences for the same payment method warrant investigation.

### Cash Flow Reporting

Generate daily payment summaries including transaction counts, volumes by provider, and failure rates. These metrics inform business planning and provider negotiations.

Track payment method distribution. Changes in method popularity may require adjusting provider priorities in the `PaymentProviderFactory`.

## Escalation Procedures

### Provider Outages

If the primary provider experiences extended outage (more than 15 minutes), manually adjust traffic routing to the fallback provider using `PaymentProviderFactory.set_primary()`.

Notify stakeholders of the outage and expected impact. Payment processing may be slower on the fallback provider.

Document the outage for post-incident review with the provider. Chronic outages may warrant renegotiating the provider agreement or finding alternatives.

### Payment Anomalies

Unusual transaction patterns require immediate investigation. Examples include spike in high-value transactions, concentration of transactions from a single IP range, or elevated decline rates.

For suspected fraud attacks, consider temporarily restricting payment acceptance through rate limiting or additional verification requirements.

Escalate confirmed fraud to the security team per the Incident Response SOP. Payment fraud may indicate broader system compromise.
