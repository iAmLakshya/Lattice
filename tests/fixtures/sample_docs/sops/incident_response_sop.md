# Incident Response Standard Operating Procedure

## Document Control

**Version:** 2.1
**Last Updated:** November 2024
**Owner:** Security Operations Team
**Review Cycle:** Quarterly

## Purpose

This procedure defines the steps for detecting, analyzing, containing, and recovering from security incidents affecting the application. It ensures consistent, effective response to minimize impact and prevent recurrence.

## Incident Classification

Incidents are classified by severity to determine response urgency and escalation requirements.

### Critical Severity

Critical incidents involve active exploitation, data breach, or complete service unavailability. Examples include successful unauthorized access to admin functions, payment data exfiltration, and infrastructure compromise.

Response time: Immediate acknowledgment, active response within 15 minutes.

### High Severity

High severity incidents involve potential compromise or significant service degradation. Examples include repeated authentication failures suggesting brute force attacks, payment processing failures affecting multiple users, and detection of malware or suspicious processes.

Response time: Acknowledgment within 30 minutes, active response within 1 hour.

### Medium Severity

Medium severity incidents involve security policy violations or isolated failures. Examples include single-user account compromise, failed security scans, and unusual access patterns not indicating active attack.

Response time: Acknowledgment within 2 hours, active response within 4 hours.

### Low Severity

Low severity incidents involve minor policy deviations or informational security events. Examples include expired certificates, configuration drift, and policy exception requests.

Response time: Acknowledgment within 24 hours, resolution within 1 week.

## Detection

### Automated Detection

The `EventBus` publishes security-relevant events that trigger automated detection. The `NotificationHandler` monitors these events and generates alerts based on configured thresholds.

Failed login monitoring watches for `USER_LOGIN_FAILED` events. When more than 5 failures occur for a single email within 10 minutes, a high severity alert is generated. When more than 20 failures occur across different emails from the same IP within 5 minutes, a critical severity alert is generated.

Payment fraud monitoring watches for patterns in `PaymentError` events. Multiple declined transactions for the same user, or rapid sequential attempts, trigger investigation.

Error rate monitoring uses `ERROR_OCCURRED` events to track system health. Elevated error rates may indicate an attack or system failure requiring investigation.

The `AuditLogHandler` captures all events for retrospective analysis. Security analysts can query the audit log to investigate anomalies or conduct threat hunting.

### Manual Detection

Users may report suspicious activity through support channels. All user reports must be logged and investigated regardless of apparent severity.

Regular security reviews examine access logs, configuration changes, and user activity patterns. These reviews may identify incidents not caught by automated detection.

Third-party notifications from payment providers, security researchers, or law enforcement must be treated as potential incident reports and investigated promptly.

## Initial Assessment

Upon receiving an alert or report, the responder must quickly assess the situation to determine classification and response approach.

Verify the event is genuine and not a false positive. Check the `EventBus` event stream for related events that confirm or contradict the initial report. Query the `AuditLogHandler` records for additional context.

Identify the scope of impact. How many users are affected? What data or functions are involved? Is the incident ongoing or historical?

Determine if the incident involves active attacker presence. Evidence includes ongoing unauthorized access attempts, data exfiltration in progress, or attacker persistence mechanisms.

Document initial findings and notify appropriate stakeholders based on severity. Critical incidents require immediate executive notification.

## Containment

Containment prevents the incident from spreading while preserving evidence for analysis.

### Account Compromise

If user accounts are compromised, immediately disable affected accounts by setting `is_active = False`. The `AuthService.login()` method checks this flag and rejects authentication for deactivated accounts.

Invalidate all active sessions for affected users by removing their tokens from `AuthService._active_tokens`. This forces re-authentication which will fail due to the deactivated account.

If admin accounts are compromised, additionally rotate all API keys and secrets that the compromised account could access.

### Payment Incidents

For payment-related incidents, cancel any pending payment intents using `PaymentService.cancel()`. This prevents processing of potentially fraudulent transactions.

Contact payment providers to report the incident. Providers may have additional containment measures available such as blocking specific cards or accounts.

Review recent refunds processed through `PaymentService.refund()` for unauthorized activity.

### System Compromise

If system infrastructure is compromised, isolate affected components from the network while preserving running state for forensic analysis.

Capture memory dumps and disk images before shutdown if forensic analysis is required. These artifacts may contain evidence that would be lost on restart.

Rotate all credentials that may have been exposed including database passwords, API keys, and encryption keys.

## Investigation

Thorough investigation determines root cause and full scope of the incident.

### Evidence Collection

Collect all relevant logs from the `AuditLogHandler` output covering the incident timeframe plus 24 hours before and after. The audit log contains a complete record of system events including authentication, authorization, and data access.

Export relevant events from the `EventBus` stream if real-time capture was enabled. Event payloads contain details about each action including user IDs, IP addresses, and affected resources.

Gather application logs, system logs, and network logs from affected infrastructure. Correlate timestamps across sources to build a timeline.

### Timeline Construction

Build a detailed timeline of attacker activity or system failure progression. Start from the earliest evidence of anomaly and trace through to containment.

Identify the initial entry point. For authentication incidents, this may be a specific `USER_LOGIN` event with stolen credentials. For system compromise, this may be an exploited vulnerability.

Document each step of attacker activity or failure cascade. What did they access? What changes did they make? What data may have been exposed?

### Root Cause Analysis

Determine why the incident was possible. Was there a vulnerability in the code? A misconfiguration? A failure of security controls?

Review the relevant code paths. For authentication issues, examine `AuthService` and the `hash_password()` / `verify_hash()` functions. For payment issues, examine `PaymentService` and the provider implementations.

Identify any gaps in detection that allowed the incident to persist. Were there events that should have triggered alerts but didn't?

## Recovery

Recovery restores normal operations while ensuring the threat is eliminated.

### Account Recovery

For compromised user accounts, require password reset using the `hash_password()` function to generate new credentials. Notify affected users of the incident and the steps taken.

For reactivating disabled accounts, verify the user's identity through out-of-band confirmation before setting `is_active = True`.

Review and revoke any API tokens or OAuth grants associated with compromised accounts.

### Data Recovery

If data was corrupted or destroyed, restore from backups after verifying the backup is from before the compromise.

Validate data integrity after restoration. Checksums and consistency checks help identify any tampering.

### System Recovery

For system compromises, rebuild affected systems from known-good images rather than attempting to clean the compromise.

Verify that vulnerabilities exploited in the incident are patched before returning systems to production.

Conduct security testing on recovered systems before declaring the incident resolved.

## Post-Incident Activities

### Incident Report

Document the incident comprehensively including timeline, impact, root cause, and response actions. The report serves as a reference for future incidents and process improvement.

Include metrics: time to detect, time to contain, time to recover, and total duration. These metrics track incident response effectiveness over time.

### Lessons Learned

Conduct a blameless post-incident review with all involved parties. Focus on process and system improvements rather than individual fault.

Identify specific improvements to prevent recurrence. These may include code fixes, configuration changes, monitoring enhancements, or process updates.

Track improvement items to completion. Assign owners and deadlines for each action item.

### Control Updates

Update security controls based on incident findings. This may include new `EventBus` event types for detection, modified `NotificationHandler` alerting thresholds, or enhanced `AuthService` validation logic.

Update this SOP if process gaps were identified during response. Lessons learned should translate into procedural improvements.

Review and update detection rules to catch similar incidents earlier in future. Test new detections against the incident data to verify effectiveness.
