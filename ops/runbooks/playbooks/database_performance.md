# Database Performance Playbook — "the database is slow"

PostgreSQL / Aurora PostgreSQL. Background and tooling: [docs/database/README.md](../../../docs/database/README.md).
Alerts that link here: `observability/prometheus/rules/database_rules.yml`. Dashboard: Grafana
`golden-database`; Performance Insights for the cluster.

## Goals
- Restore latency / availability first; root-cause second.
- Never make it worse: no blocking DDL, no restarts, no `max_connections` bumps under pressure.
- Leave evidence (queries, plans, PI screenshots) for the post-incident tuning work.

## 0. Declare and scope (2 minutes)
- Which symptom? Latency (p99 up), errors (`too many clients`, timeouts), or saturation (CPU / I/O)?
- Since when, and what changed (deploy, migration, batch job, traffic, failover)? Check
  `deployment_rollback_gitops.md` if a deploy lines up — rolling back the app is often the fastest fix.
- Performance Insights → *Database load* by **wait event** and **top SQL**:
  `CPU` → bad plans / too many active sessions · `IO:DataFileRead` → cache misses / missing index ·
  `Lock:*` → contention (go to step 3) · `LWLock:*` → too many connections · `Client:ClientRead` →
  idle in transaction.

## 1. What is running right now
```sql
SELECT pid, usename, application_name, client_addr, state, wait_event_type, wait_event,
       now() - xact_start  AS xact_age,
       now() - query_start AS query_age,
       left(query, 120)    AS query
  FROM pg_stat_activity
 WHERE backend_type = 'client backend' AND state <> 'idle'
 ORDER BY xact_start NULLS LAST
 LIMIT 50;

-- connection budget
SELECT count(*) AS total,
       count(*) FILTER (WHERE state = 'active')              AS active,
       count(*) FILTER (WHERE state = 'idle in transaction') AS idle_in_txn,
       current_setting('max_connections')::int               AS max_connections
  FROM pg_stat_activity WHERE backend_type = 'client backend';
```
Active sessions ≫ `vCPU × 2` means the server is thrashing: shed load at the pooler (PgBouncer
`PAUSE`/`max_client_conn`, RDS Proxy borrow timeout) rather than letting more in.

## 2. Long and idle-in-transaction sessions
They hold locks and the xmin horizon (vacuum stops everywhere).
```sql
SELECT pid, usename, application_name, state, now() - xact_start AS xact_age, left(query, 120) AS last_query
  FROM pg_stat_activity
 WHERE xact_start < now() - interval '5 minutes'
 ORDER BY xact_start;
```

## 3. Locks and blocking chains
```sql
-- who blocks whom (head of the chain has an empty blocked_by)
SELECT a.pid, pg_blocking_pids(a.pid) AS blocked_by, a.wait_event_type, a.wait_event,
       now() - a.query_start AS waiting_for, left(a.query, 120) AS query
  FROM pg_stat_activity a
 WHERE cardinality(pg_blocking_pids(a.pid)) > 0
 ORDER BY waiting_for DESC;

-- the blockers themselves
SELECT pid, usename, application_name, state, now() - xact_start AS xact_age, left(query, 160) AS query
  FROM pg_stat_activity
 WHERE pid IN (SELECT unnest(pg_blocking_pids(pid)) FROM pg_stat_activity);

-- lock detail for one relation
SELECT l.pid, l.mode, l.granted, c.relname
  FROM pg_locks l LEFT JOIN pg_class c ON c.oid = l.relation
 WHERE c.relname = 'payments';
```
Classic pattern: a DDL (`ALTER TABLE`, `CREATE INDEX` without `CONCURRENTLY`) waits for an
ACCESS EXCLUSIVE lock behind one long transaction, and **every** query on the table queues behind the
DDL. Cancel the DDL first, then deal with the long transaction.

## 4. Cancel or terminate — decision rules
| Situation | Action |
|---|---|
| Runaway SELECT / report on the primary | `SELECT pg_cancel_backend(pid);` (cancels the statement, keeps the session) |
| Idle in transaction holding locks / xmin | `SELECT pg_terminate_backend(pid);` (rolls back; the app reconnects) |
| Blocking DDL queue | Cancel the DDL; re-run later with `SET lock_timeout = '3s';` and retries |
| Head of a blocking chain is a business write | Ask the owning team (≤ 5 minutes) unless customer impact is severe; then terminate and record the pid/query |
| Migration / batch job | Pause the job at its controller (not in the DB) so it does not immediately retry |
| Autovacuum (anti-wraparound) | **Do not kill** — it restarts and the risk grows; remove what blocks it instead |

Always record `pid, usename, application_name, query, xact_age` before terminating.

Avoid during an incident: restarting/failing over the writer to "clear" load (cold cache makes it
worse), raising `max_connections` (needs reboot, more contention), global `work_mem` increases.

## 5. Find the expensive statements
```sql
SELECT queryid, calls, round(total_exec_time) AS total_ms, round(mean_exec_time::numeric, 2) AS mean_ms,
       rows, shared_blks_read, temp_blks_written, left(query, 120) AS query
  FROM pg_stat_statements
 ORDER BY total_exec_time DESC
 LIMIT 15;
```
Export it and run `golden db workload pgss.csv` (dominant query, cache misses, spills, N+1). For the
top statement, capture a plan **on a replica** (or inside `BEGIN … ROLLBACK` for writes):
`EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) …` → `golden db explain plan.json`. `auto_explain` has
already logged plans of statements slower than 1 s in the PostgreSQL log (CloudWatch Logs).

Plan regression after a deploy or bulk load? `ANALYZE <table>;` is cheap and often the whole fix.

## 6. Safe index creation during an incident
```sql
SET lock_timeout = '5s';                -- never queue behind long transactions
SET maintenance_work_mem = '1GB';       -- session only; faster build
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_refunds_payment_id ON refunds (payment_id);

-- verify it is valid (a failed CONCURRENTLY build leaves an INVALID index)
SELECT c.relname, i.indisvalid FROM pg_index i JOIN pg_class c ON c.oid = i.indexrelid
 WHERE c.relname = 'idx_refunds_payment_id';
ANALYZE refunds;
```
- `CONCURRENTLY` cannot run inside a transaction block (no migration-tool wrappers that add `BEGIN`).
- It takes two table scans and waits for running transactions: expect minutes to hours on big tables;
  watch `pg_stat_progress_create_index`.
- Build it during the incident only if the plan proves it fixes the hot statement; otherwise schedule it.

## 7. Rollback
| Change | Rollback |
|---|---|
| New index hurts writes or is unused | `DROP INDEX CONCURRENTLY IF EXISTS <name>;` |
| Invalid index from a failed build | `DROP INDEX CONCURRENTLY IF EXISTS <name>;` then retry |
| Per-role / per-table setting | `ALTER ROLE app RESET work_mem;` · `ALTER TABLE t RESET (autovacuum_vacuum_scale_factor);` |
| Parameter group change | Revert in Terraform (`deploy/terraform/modules/aws/aurora-postgres`) and apply; dynamic params apply without reboot |
| Instance class change | Modify back (reader first, then fail over); RDS Proxy holds client connections |
| Query rewrite in the app | Roll back the deploy (GitOps) |

## 8. Verify and close
- p99 latency, active sessions, DB load (PI) and the statement's `mean_exec_time` back to baseline for
  30 minutes.
- No growth in `PostgresLongRunningTransaction`, `PostgresLockContention`, `PgBouncerClientsWaiting`.
- File the follow-ups: `golden db indexes` (unused/missing indexes, bloat, autovacuum) and
  `golden db capacity` (pools, memory, rightsizing) on a snapshot from the incident window; attach plans
  and PI screenshots to the postmortem.

MySQL equivalents: `SHOW FULL PROCESSLIST` / `performance_schema.threads`, `sys.innodb_lock_waits`
(blocking chains), `KILL QUERY <id>` (cancel) vs `KILL <id>` (terminate),
`performance_schema.events_statements_summary_by_digest` (top statements), gh-ost / pt-osc or
`ALGORITHM=INPLACE, LOCK=NONE` for online index builds.
