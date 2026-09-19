# Runbook: Disk I/O and Network Latency Issues

## Symptoms
- Slow log write throughput, WARN logs mentioning timeouts.
- Elevated network latency between regions (e.g. US-East <-> US-West).

## Common Root Causes
1. Disk nearing capacity, causing I/O contention.
2. Cross-region network congestion or a routing issue.
3. A backup or batch job competing for I/O bandwidth during business hours.

## Recommended Remediation
- Reschedule or throttle batch/backup jobs.
- If disk is the bottleneck, clear temp/log rotation backlog before
  considering any reboot.
- Network issues are typically outside the blast radius of a single
  server remediation — escalate to the network on-call if the issue spans
  multiple servers/regions.

## Verification
Latency and I/O wait metrics return to baseline; no new WARN logs
referencing timeouts for the affected service.
