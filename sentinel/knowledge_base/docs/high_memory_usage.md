# Runbook: High Memory Usage

## Symptoms
- `memory_usage_percent` on a server exceeds 85-90%.
- Services on the host become slow or start throwing ERROR-level logs.
- On database hosts this often correlates with query latency spikes.

## Common Root Causes
1. **Unbounded caching** — a service (e.g. a reporting/cache layer) caches
   query results without an eviction policy or TTL.
2. **Memory leak** — a long-running process's heap grows unbounded over
   time without being restarted.
3. **Connection pool bloat** — too many open DB connections each holding
   buffers in memory.

## Recommended Remediation
- If a specific service's cache is implicated: `restart_service` on that
  service (safe, non-high-risk) to release the memory, then monitor.
- If the whole host is affected and non-critical: `system_reboot` may be
  proposed, but this is a HIGH-RISK command and must be blocked while the
  host is under critical load — page a human instead.
- Long term: add cache TTLs / eviction, and connection pool limits.

## Verification
Re-check `memory_usage_percent` for the affected `server_id`. Consider it
resolved when memory usage drops below 75%.
