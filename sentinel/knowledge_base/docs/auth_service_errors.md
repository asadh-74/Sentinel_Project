# Runbook: Auth-Service ERROR Spike

## Symptoms
- Elevated count of `log_level = 'ERROR'` rows where `service_name =
  'Auth-Service'`.
- Users report failed logins or 401/403 errors.

## Common Root Causes
1. Expired or misconfigured signing certificate/JWT secret.
2. Downstream identity-provider outage or timeout.
3. Database connectivity issues from the auth service to its user store.

## Recommended Remediation
- `restart_service` targeting `auth-service` clears transient connection
  issues in most cases.
- If errors persist after restart, escalate to a human — this may require
  a certificate rotation, which is outside automated remediation scope.

## Verification
ERROR-level logs from Auth-Service in the last window should drop to
baseline (roughly the WARN/INFO ratio seen on a healthy day).
