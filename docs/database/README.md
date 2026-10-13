# Database performance & optimization

From "how does a query run" to principal-level capacity and cost decisions, for PostgreSQL (Aurora
PostgreSQL, RDS, self-managed). MySQL notes appear where the concept differs.

| Piece | Where |
|---|---|
| Advisors (pure Python, no live connection) | [`src/golden/database/`](../../src/golden/database/) — `workload`, `explain`, `indexes`, `capacity` |
| CLI | `golden db workload \| explain \| indexes \| capacity` |
| Aurora PostgreSQL (tuned parameter groups, PI, RDS Proxy, alarms) | [`deploy/terraform/modules/aws/aurora-postgres`](../../deploy/terraform/modules/aws/aurora-postgres/README.md) |
| PgBouncer, postgres_exporter, NetworkPolicy | [`deploy/k8s/database`](../../deploy/k8s/database/README.md) |
| Alerts / dashboard | [`database_rules.yml`](../../observability/prometheus/rules/database_rules.yml), [`golden-database.json`](../../observability/grafana/dashboards/golden-database.json) |
| Incident runbook ("the database is slow") | [`ops/runbooks/playbooks/database_performance.md`](../../ops/runbooks/playbooks/database_performance.md) |
| Moving databases (not tuning them) | [docs/modernization/database-migration.md](../modernization/database-migration.md) |

Every advisor returns explainable findings — a stable `code`, a `severity`, the `evidence` numbers that
triggered the rule, and a concrete remediation (usually a SQL statement). Nothing is a black box: each
threshold is a keyword argument you can change.

---

## 1. How a query executes

```
SQL text ─► parser ─► rewriter ─► planner/optimizer ─► executor ─► rows
             (syntax)  (views,     (cost-based: which      (pulls tuples through
                        rules)      scans, join order,       a tree of nodes; reads
                                    join methods)            pages via shared_buffers)
```

1. **Parse** — text to a parse tree; syntax errors happen here.
2. **Rewrite** — views and rules are expanded.
3. **Plan** — the optimizer enumerates access paths (Seq Scan, Index Scan, Index Only Scan, Bitmap
   scans) and join strategies (Nested Loop, Hash Join, Merge Join), estimates the cost of each from
   **table statistics** (`pg_statistic`: row counts, null fraction, distinct values, most-common values,
   histograms, correlation) and the cost constants (`seq_page_cost`, `random_page_cost`,
   `cpu_tuple_cost`, `effective_cache_size`) and keeps the cheapest. Join order search is exhaustive up
   to `join_collapse_limit` tables, then genetic (GEQO).
4. **Execute** — a demand-pull tree of nodes; each node asks its children for rows. Pages are read
   through `shared_buffers`; misses go to the OS cache, then storage.

**Consequence:** almost every bad plan is a *wrong estimate*, not a wrong algorithm. Fix statistics before
reaching for hints (PostgreSQL has none built in, deliberately).

Prepared statements are planned with a *custom* plan for their first five executions and may switch to
a *generic* plan afterwards; skewed data can make the generic plan bad (`plan_cache_mode`).

MySQL: the optimizer is also cost-based, but InnoDB tables are **clustered on the primary key** (rows live
in the PK B-tree), so secondary-index lookups are two B-tree traversals unless the index covers the query.

## 2. Reading EXPLAIN

Always capture with real execution and buffers:

```sql
EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) SELECT …;   -- on a replica, or BEGIN; …; ROLLBACK; for writes
```

What to look at, in order:

| Signal | Meaning | `golden db explain` code |
|---|---|---|
| `Plan Rows` vs `Actual Rows` differ ≥ 10x | Statistics are stale / insufficient / columns correlated — the planner chose for a different data shape | `ROW_MISESTIMATE` |
| `Seq Scan` with `Rows Removed by Filter` ≫ rows returned | Missing index for a selective predicate | `SEQ_SCAN_SELECTIVE` |
| Index Scan with large `Rows Removed by Filter` | Index exists but does not include the filter columns | `INDEX_FILTER_INEFFICIENT` |
| `Nested Loop` with inner `Actual Loops` in the thousands | Inner side repeated per outer row; catastrophic if the inner is a Seq Scan | `NESTED_LOOP_LARGE` |
| Hash Join reading a whole large table to produce a few rows | Join key not indexed | `MISSING_JOIN_INDEX` |
| `Sort Space Type: Disk`, `Hash Batches > 1`, `HashAgg Batches > 1` | Spilled past `work_mem` | `SORT_SPILL`, `HASH_SPILL` |
| `Lossy Heap Blocks` in a Bitmap Heap Scan | Bitmap exceeded `work_mem`, rows rechecked | `LOSSY_BITMAP` |
| `Shared Read Blocks` high vs `Shared Hit Blocks` | Data came from outside `shared_buffers` | (hottest-node table) |

`Actual Rows` is **per loop** — multiply by `Actual Loops`. Node times are inclusive of children; the
advisor computes *exclusive* time per node to point at where time is actually spent. Nodes under a
`LIMIT` legitimately return fewer rows than estimated; the advisor does not flag those.

MySQL: `EXPLAIN ANALYZE` (8.0.18+) — watch `type: ALL` (full scan), `Using filesort`, `Using temporary`,
and estimated vs actual rows.

## 3. Indexes

| Type | Use for | Notes |
|---|---|---|
| **B-tree** (default) | `=`, ranges, `ORDER BY`, `LIKE 'prefix%'` (with `text_pattern_ops` or C collation) | The right answer 90 % of the time |
| **Hash** | `=` only | WAL-logged since PG10; rarely better than B-tree |
| **GIN** | `jsonb` containment (`@>`), arrays, full-text, trigram (`pg_trgm` for `LIKE '%x%'`) | Slow to update — `fastupdate` / pending list |
| **GiST / SP-GiST** | Geometry, ranges, nearest-neighbour, exclusion constraints | |
| **BRIN** | Huge append-only tables where the column correlates with physical order (time-series `created_at`) | Kilobytes instead of gigabytes; lossy |
| **Partial** | `WHERE status = 'pending'` when the hot subset is small | The query must imply the predicate |
| **Covering** (`INCLUDE`) | Index-only scans without widening the key | Needs a well-vacuumed visibility map |
| **Expression** | `lower(email)`, `date_trunc('day', ts)` | Query must use the identical expression |

**Multi-column order:** equality columns first, then **one** range column, then `ORDER BY` columns —
`(merchant_id, status, created_at DESC)` serves `WHERE merchant_id = ? AND status = ? ORDER BY created_at
DESC LIMIT 50` with no sort and early termination. An index on `(a, b)` makes an index on `(a)` redundant
(`REDUNDANT_INDEX`).

**Cost of indexes:** every index is written on every INSERT and on every UPDATE that is not HOT
(heap-only tuple; HOT requires no indexed column to change *and* free space on the page — hence
`fillfactor`). `golden db indexes` estimates write amplification per table and lists unused,
duplicate and prefix-redundant indexes, plus foreign keys without an index (every parent DELETE/UPDATE
then scans the child table).

**Creating and dropping safely:** always `CREATE INDEX CONCURRENTLY` / `DROP INDEX CONCURRENTLY` on a live
system (no write lock; cannot run inside a transaction; a failed build leaves an `INVALID` index to drop).
Before dropping an "unused" index check `idx_scan` on **every replica** and how long stats have
accumulated (`pg_stat_database.stats_reset`) — month-end jobs exist.

MySQL: `sys.schema_unused_indexes`, `sys.schema_redundant_indexes`; online DDL `ALGORITHM=INPLACE, LOCK=NONE`
or gh-ost / pt-online-schema-change for big tables. Secondary indexes implicitly contain the PK.

## 4. Statistics

`ANALYZE` samples `300 × default_statistics_target` rows per table. Fixes, in escalating order:

1. `ANALYZE table;` — after bulk loads, autovacuum's analyze may lag.
2. Lower `autovacuum_analyze_scale_factor` for large tables (per-table storage parameter).
3. `ALTER TABLE t ALTER COLUMN c SET STATISTICS 1000;` for skewed columns.
4. **Extended statistics** for correlated columns (the planner assumes independence otherwise):
   `CREATE STATISTICS s (dependencies, ndistinct, mcv) ON merchant_id, created_at FROM payments;`
   `golden db explain` generates this when a misestimated node filters on ≥ 2 columns.
5. Expression indexes also gather statistics on the expression (`lower(email)`).

## 5. MVCC, vacuum and bloat

UPDATE = new row version + old version marked dead; DELETE = mark dead. **VACUUM** makes dead space
reusable, maintains the visibility map (index-only scans) and **freezes** old transaction IDs.

- **Bloat**: autovacuum falls behind (default `autovacuum_vacuum_scale_factor = 0.2` waits for 20 % dead
  rows — 200M on a 1B-row table) or is *blocked* by the xmin horizon: long transactions,
  idle-in-transaction sessions, abandoned replication slots, `hot_standby_feedback` from a replica with
  long queries. Remove the blocker first; tuning cannot fix a held horizon.
- **Per-table autovacuum** (what `golden db indexes` emits): scale factor 0.01–0.05 by table size,
  `autovacuum_vacuum_cost_limit = 2000`, and `autovacuum_vacuum_insert_scale_factor` for append-only tables.
- **Wraparound**: XIDs are 32-bit; tables must be frozen before `age(relfrozenxid)` reaches ~2.1 billion
  or PostgreSQL stops accepting writes. Alert at 50 % (`PostgresXIDWraparoundRisk`) — long before
  anti-wraparound autovacuum becomes an emergency.
- **Reclaiming disk**: `VACUUM FULL` takes an ACCESS EXCLUSIVE lock — use `pg_repack` online instead.

MySQL/InnoDB: no VACUUM; old versions live in undo logs and the purge thread cleans them — long
transactions show up as a growing *history list length*. Same root cause, same fix.

## 6. Connection pooling

A PostgreSQL connection is a process (~5–10 MB, more with `work_mem` in use). Throughput peaks around
**`active connections ≈ cores × 2 + effective_spindles`** and falls beyond it (context switching, lock
contention, ProcArray scans). Hundreds of app pods × 20-connection pools blow past `max_connections`
during a deploy surge.

- **PgBouncer transaction mode** ([deploy/k8s/database/pgbouncer.yaml](../../deploy/k8s/database/pgbouncer.yaml)):
  thousands of clients share tens of server connections. Caveats: no session `SET` (use `SET LOCAL`),
  advisory locks, `LISTEN`, or `WITH HOLD` cursors across transactions; prepared statements need
  PgBouncer ≥ 1.21 `max_prepared_statements`.
- **RDS Proxy** (Terraform module): managed, IAM auth, keeps client connections across failovers; pins
  sessions for some statements (watch `DatabaseConnectionsCurrentlySessionPinned`).
- `golden db capacity` → `pool_sizing()` computes the optimal active count, flags oversubscription
  (`CONNECTIONS_OVERSUBSCRIBED`) and emits PgBouncer settings.

MySQL: threads instead of processes (cheaper), but the same contention curve; ProxySQL or RDS Proxy.

## 7. Caching layers

From cheapest to most complex: **don't query** (compute once, denormalise) → in-process cache (per pod,
tiny TTL, no coordination) → **shared cache** (Redis, [deploy/helm/redis](../../deploy/helm/redis) /
[deploy/terraform/modules/redis](../../deploy/terraform/modules/redis)) with cache-aside, TTL + explicit
invalidation on write, jittered TTLs and request coalescing to avoid stampedes → materialized views /
rollup tables for aggregates → `shared_buffers` / OS cache (automatic).

Cache what is read far more often than written and tolerates staleness; never cache around a missing
index. `read_scaling()` recommends a cache when a small hot key set receives ≥ 20 % of reads.

## 8. Read replicas and CQRS

Replicas scale **reads that tolerate staleness**; they do nothing for writes. Aurora readers share
storage (lag typically < 100 ms); RDS / self-managed streaming replicas can lag seconds under write
bursts. Keep read-your-writes paths on the writer (or route by session after a write). `read_scaling()`
recommends readers when the read/write ratio ≥ 4 and lag tolerance ≥ 1 s, sized from read-driven CPU.

**CQRS** goes further: a purpose-built read model (denormalised table, search index, cache) fed from the
write path via the outbox pattern → Kafka → projection. Use it when read shapes and write shapes
diverge, not just for scale.

## 9. Partitioning and sharding

**Declarative range partitioning** (by month, or day for very high growth) pays off for large
time-series tables when most queries filter on the partition key: partition pruning, smaller indexes,
per-partition vacuum, and **retention by `DETACH PARTITION … CONCURRENTLY` + `DROP`** instead of a
bloat-generating `DELETE`. Requirements: the PK/unique constraints include the partition key; manage
partitions with `pg_partman`. Partitioning a table queries do *not* filter by the key makes them slower
(`PARTITIONING_NOT_INDICATED`). `partitioning_plan()` applies these rules.

**Sharding** (Citus, application-level by tenant/merchant) when one node cannot hold the write rate or
the data volume makes vacuum/backup/restore windows unacceptable (~10 TB+). Choose a shard key that
keeps transactions single-shard.

## 10. Schema design trade-offs

- Right-size types: `bigint` keys (int overflow at 2.1B rows is an outage), `numeric` for money,
  `timestamptz` always, `text` over `varchar(n)`.
- Normalise for writes and integrity; denormalise deliberately for hot reads (with a single writer of
  the copy).
- UUIDv4 keys scatter B-tree inserts (random I/O, bloat) — prefer `bigint identity` or time-ordered
  UUIDv7.
- `jsonb` for genuinely schemaless attributes, not to avoid migrations; index with GIN `jsonb_path_ops`.
- Wide rows with rarely read columns → TOAST handles large values, but frequently updated narrow
  columns next to large ones defeat HOT; split hot/cold columns.
- Foreign keys need an index on the referencing column (`FK_WITHOUT_INDEX`).

## 11. Capacity and cost

`golden db capacity` (`assess_capacity`) combines:

- **Memory parameters** (`memory_parameters`): `shared_buffers` ≈ 25 % of RAM on RDS/self-managed (the
  OS cache holds the rest), ~75 % on Aurora (no OS-cache double buffering for data files);
  `effective_cache_size` ≈ 75 % (a planner hint, allocates nothing); `work_mem` =
  (RAM − shared_buffers) × 0.5 / (max_connections × 2 ops), capped per workload — raise it **per role or
  `SET LOCAL`** for reports, never globally; `maintenance_work_mem` ≈ 5 % up to 2 GB. Parameter-group
  units (8 kB pages / kB) are emitted for RDS/Aurora.
- **Rightsizing** (`rightsize`): required vCPU = current vCPU × p95 CPU × (1 + headroom), required
  memory = (RAM − p5 freeable) × (1 + headroom) — never shrinks memory when cache hit < 99 %; picks the
  cheapest fitting class, preferring **Graviton** (r7g/r6g, ~10–20 % better price-performance, no app
  change for managed PostgreSQL).
- **Aurora I/O-Optimized vs Standard**: Standard bills per I/O request; I/O-Optimized has no I/O charge
  but ~30 % higher instance and ~2.25x storage prices. Break-even is around **I/O ≥ 25 % of the
  bill**; the advisor computes both bills explicitly.
- **RDS Proxy** cost is per vCPU of the target; it pays for itself when it lets you avoid a bigger
  instance chosen only for connection count.

Prices come from a table passed in — default [`src/golden/database/pricing.yaml`](../../src/golden/database/pricing.yaml),
**illustrative only** (approximate us-east-1 list prices); point `GOLDEN_DB_PRICING_FILE` at your
contracted prices before quoting savings. Results carry `illustrative_prices: true` when the default
table is used.

## 12. Observability

| Source | Gives you | Set up by |
|---|---|---|
| `pg_stat_statements` | Per-statement calls, time, rows, buffer hits/reads, temp spill | Terraform parameter group (`shared_preload_libraries`) + `CREATE EXTENSION` |
| `auto_explain` | Plans of statements slower than a threshold, in the PostgreSQL log | Terraform parameter group (`log_timing = 0` keeps overhead low) |
| `log_min_duration_statement`, `log_lock_waits`, `log_temp_files`, `log_autovacuum_min_duration` | Slow queries, lock waits, spills, slow vacuums | Terraform parameter group |
| `track_io_timing` | I/O time in pg_stat_statements / EXPLAIN | Terraform parameter group |
| **Performance Insights** | DB load by wait event, SQL, user, host — the first screen in an incident | Terraform (KMS, retention) |
| Enhanced Monitoring | OS-level metrics at 1–60 s | Terraform |
| postgres_exporter (+ custom queries) | Prometheus metrics: connections, cache hit, deadlocks, locks, dead tuples, XID age, top statements | [deploy/k8s/database](../../deploy/k8s/database/README.md) |
| CloudWatch alarms | CPU, freeable memory, connections, replica lag, deadlocks, `MaximumUsedTransactionIDs` | Terraform |

**Wait events** tell you *what* sessions wait on: `CPU` (inefficient plans or too many active
connections), `IO:DataFileRead` (working set not cached / missing index), `Lock:transactionid` /
`Lock:tuple` (row contention), `LWLock:*` (internal contention — often too many connections),
`Client:ClientRead` (app is slow to send — idle in transaction).

## 13. The tuning workflow

Measure → find top offenders → explain → fix → verify. Never tune a parameter you cannot tie to a
measurement.

| Step | Do | Golden |
|---|---|---|
| 0. Baseline | Record p50/p99 latency, TPS, CPU, cache hit, DB load (PI) for a representative window | Grafana `golden-database` dashboard |
| 1. Measure | Export pg_stat_statements (below) after `pg_stat_statements_reset()` + a representative period | — |
| 2. Top offenders | Rank by **total time** (capacity), **mean time** (user pain), **I/O**; find N+1 and spills | `golden db workload pgss.csv` → `golden.database.analyse_workload(load_statements(path))` |
| 3. Explain | `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)` the top 3 with production parameters | `golden db explain plan.json` → `golden.database.analyse_plan(load_plan(path))` |
| 4. Schema health | Unused/duplicate/missing indexes, FK indexes, bloat, autovacuum, wraparound | `golden db indexes snapshot.json` → `golden.database.analyse_indexes(snapshot)` |
| 5. Fix | One change at a time: index `CONCURRENTLY`, query rewrite, statistics, per-table autovacuum, `work_mem` per role | DDL from the reports' `statements` |
| 6. Capacity | Pools, memory parameters, replicas/cache, partitioning, rightsizing, I/O-Optimized | `golden db capacity profile.json` → `golden.database.assess_capacity(profile)` |
| 7. Verify | Same window, same metrics as step 0; check the statement's mean time and the plan changed | dashboard + re-run step 2 |

Every command also accepts `--sample` (the bundled payments workload with planted defects) and `--json`.

### Export queries

```sql
-- 1. pg_stat_statements (CSV via \copy)
\copy (SELECT queryid, query, calls, total_exec_time, mean_exec_time, rows,
              shared_blks_hit, shared_blks_read, temp_blks_written
         FROM pg_stat_statements
        WHERE dbid = (SELECT oid FROM pg_database WHERE datname = current_database())
        ORDER BY total_exec_time DESC LIMIT 500) TO 'pgss.csv' CSV HEADER

-- 3. plan
EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) <statement with real parameters>;

-- 4. catalog snapshot (assemble into one JSON document; keys as in golden.database.indexes)
SELECT now() AS captured_at, stats_reset FROM pg_stat_database WHERE datname = current_database();
SELECT datname, age(datfrozenxid) AS datfrozenxid_age,
       current_setting('autovacuum_freeze_max_age')::bigint AS autovacuum_freeze_max_age
  FROM pg_database WHERE datname = current_database();
SELECT s.*, pg_total_relation_size(s.relid) AS size_bytes, age(c.relfrozenxid) AS relfrozenxid_age
  FROM pg_stat_user_tables s JOIN pg_class c ON c.oid = s.relid;                          -- "tables"
SELECT s.schemaname, s.relname, s.indexrelname, s.idx_scan, pg_relation_size(s.indexrelid) AS size_bytes,
       i.indisunique AS is_unique, i.indisprimary AS is_primary, pg_get_indexdef(s.indexrelid) AS indexdef
  FROM pg_stat_user_indexes s JOIN pg_index i ON i.indexrelid = s.indexrelid;             -- "indexes"
SELECT conrelid::regclass::text AS "table", conname AS "constraint",
       confrelid::regclass::text AS referenced_table,
       array(SELECT a.attname FROM unnest(conkey) WITH ORDINALITY k(attnum, ord)
              JOIN pg_attribute a ON a.attrelid = conrelid AND a.attnum = k.attnum
             ORDER BY k.ord) AS columns
  FROM pg_constraint WHERE contype = 'f';                                                  -- "foreign_keys"
```

### Python

```python
from golden.database import (analyse_workload, load_statements, analyse_plan, load_plan,
                             analyse_indexes, assess_capacity, sample_capacity_profile)

report = analyse_workload(load_statements("pgss.csv"), top_n=10)
for f in report.findings:
    print(f.severity, f.code, f.target, f.message, "→", f.remediation)

plan = analyse_plan(load_plan("plan.json"))
print("\n".join(plan.statements))          # CREATE INDEX CONCURRENTLY … / CREATE STATISTICS …

cap = assess_capacity(sample_capacity_profile())
print(cap.rightsizing.recommended_class, cap.rightsizing.monthly_savings)
```

## 14. Principal-level checklist

- Is the problem **one query** (top-offender table dominated by one fingerprint) or **the system**
  (load spread evenly, CPU or I/O saturated)? The first is an index/rewrite; the second is capacity.
- Is the database even the bottleneck? N+1 patterns show thousands of sub-millisecond calls — latency
  is round trips, fixed in the application.
- Every index has a write cost; every cache has an invalidation cost; every replica has a staleness
  cost; every partition scheme has a query-shape assumption. Name the cost before adding one.
- Prefer reversible steps: `CONCURRENTLY` DDL, per-role settings, reader-first instance changes,
  parameter changes that apply without reboot.
- Write the before/after numbers into the change record — the next engineer inherits your reasoning.
