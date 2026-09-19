# Runbook: High CPU Usage

## Symptoms
- `cpu_usage_percent` sustained above 80-85%.
- Increased response latency; possible ERROR logs from timeouts downstream.

## Common Root Causes
1. **Traffic spike** — legitimate load increase beyond current capacity.
2. **Runaway process / infinite loop** in application code.
3. **Noisy-neighbor** workload on a shared host.

## Recommended Remediation
- Identify the offending process/service from recent logs.
- Prefer scaling out (add capacity) or restarting the specific service
  over a full `system_reboot`, which is high-risk and should only be used
  as a last resort when the host is NOT under critical database load.

## Verification
Confirm `cpu_usage_percent` for the server has dropped below 70% and no
new ERROR logs are appearing for the affected service.
