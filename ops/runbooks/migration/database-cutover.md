# Runbook: Database Migration Cutover (DMS full load + CDC / native replication)

| | |
|---|---|
| **Applies to** | Any database moved with `deploy/terraform/modules/aws/dms` or native replication, per its `golden.migration.database` assessment |
| **Owner** | DBA / migration engineer (R), engagement lead (A), app owner (C) |
| **Alerts** | `<name>-dms-CDCLatencySource`, `<name>-dms-CDCLatencyTarget`, `<name>-dms-free-storage` (CloudWatch → SNS) |
| **Background** | [docs/modernization/database-migration.md](../../../docs/modernization/database-migration.md) |
| **Related** | VM wave [cutover.md](./cutover.md), [rollback.md](./rollback.md) |

Values to fill in the change ticket: `TASK_ARN`, source/target hosts, downtime budget, lag threshold for
cutover (default: under 60 s sustained), rollback window, rollback method (reverse CDC / read-only source).

## T-7 days — readiness

1. Assessment reviewed and current. Strategy, target and blockers are signed off. No `blocker` findings remain open:

   ```python
   from golden.migration.database import Database, assess_database
   print(assess_database(Database(...), bandwidth_gbps=1.0).to_dict())
   ```

2. Target provisioned (Terraform applied), with encryption, parameter group, backups, Performance
   Insights and monitoring. For heterogeneous moves, the converted schema is applied **without** FKs and
   triggers enabled.
3. CDC prerequisites on the source (supplemental logging / `binlog_format=ROW` / `wal_level=logical`).
   Log retention ≥ full load + catch-up time plus 24 h.
4. Endpoint connectivity tested over TLS:

   ```bash
   aws dms test-connection --replication-instance-arn "$RI_ARN" --endpoint-arn "$SOURCE_EP_ARN"
   aws dms test-connection --replication-instance-arn "$RI_ARN" --endpoint-arn "$TARGET_EP_ARN"
   aws dms describe-connections --filters Name=endpoint-arn,Values="$SOURCE_EP_ARN"
   ```

5. Rehearsal done on a copy. Recorded: full-load duration, peak CDC latency, validation result, and the
   time from cutover start to writes re-enabled.
6. Rollback method chosen and tested (reverse DMS task target → source created **stopped**, or
   read-only source plus an agreed data-loss window).
7. Change ticket approved (CAB). DBA, app owner, network and on-call SRE booked for the window.

## T-3 days — full load + CDC running

1. Start replication (critical action, needs approval):

   ```bash
   aws dms start-replication-task --replication-task-arn "$TASK_ARN" \
     --start-replication-task-type start-replication
   ```

   Native replication instead: create the publication/subscription (PostgreSQL), or configure binlog
   replication (`mysql.rds_set_external_master` / Aurora equivalent), and start it.
2. Watch the full load:

   ```bash
   aws dms describe-table-statistics --replication-task-arn "$TASK_ARN" \
     --query 'TableStatistics[?TableState!=`Table completed`].[SchemaName,TableName,TableState,FullLoadRows]' --output table
   ```

3. When the full load is done: CDC latency (`CDCLatencySource`, `CDCLatencyTarget`) stays below the
   threshold through a business peak. No `Table error` states.

## T-1 day — validation and go/no-go prep

1. DMS validation: every table shows `ValidationState = Validated`:

   ```bash
   aws dms describe-table-statistics --replication-task-arn "$TASK_ARN" \
     --query 'TableStatistics[?ValidationState!=`Validated`].[TableName,ValidationState,ValidationFailedRecords]' --output table
   ```

2. Row counts and checksums on critical tables. Compare per key range, and record results in the ticket.
3. App smoke tests against the target (read-only), plus a performance check on the top queries.
4. Connection-string / DNS change prepared (secret version or CNAME staged, TTL lowered to ≤ 60 s).

## T-0 — go / no-go (30 min before window)

- [ ] CDC latency below threshold for the last hour; no DMS or replication alarms firing
- [ ] Validation clean; checksums signed off by the app owner
- [ ] Rollback path ready (reverse task created and stopped, or source read-only plan agreed)
- [ ] DBA, app owner, SRE, network on the bridge

Record the decision in the change ticket and the audit log.

## Cutover

1. **Stop writes**: maintenance page, stop batch/ETL jobs, drain queues, and block app users at the DB
   if needed (revoke write grants / set the source read-only).
2. **Drain**: wait until CDC latency is about 0 and the last source change is on the target. Compare a
   sentinel row or the highest key/timestamp on hot tables.
3. **Stop replication**:

   ```bash
   aws dms stop-replication-task --replication-task-arn "$TASK_ARN"
   ```

4. **Finalize the target**: enable FKs and triggers, reset sequences/identities above the source max,
   gather statistics.
5. **Final validation**: row counts on all tables, checksums on critical tables.
6. **Start reverse replication** (if that is the rollback method), from the target's current position
   to the source.
7. **Switch**: update the connection secret / DNS, then restart or roll the app pods so they reconnect.
8. **Re-enable writes**. Smoke test the critical business transactions end to end.

## T+1 day — hypercare

- Error rates, latency and DB metrics (CPU, IOPS, locks, slow queries) compared with the baseline.
- Reverse replication healthy (if used). Source stays read-only and intact.
- Business reconciliation (e.g. day totals) signed off by the app owner.
- After the rollback window closes: stop reverse replication, delete the DMS task/instance (Terraform),
  take a final source backup, and schedule source decommission with the VM decommission steps.

## Rollback

Triggers: validation failures that can't be fixed in the window, critical app defects on the target,
SLO breach beyond the agreed threshold, or loss of data integrity.

1. Stop writes on the target (maintenance page).
2. If reverse replication runs: wait for latency about 0, then stop it. Otherwise apply the agreed
   reconciliation (replay from app audit logs) or accept the agreed loss window.
3. Revert the connection secret / DNS to the source and set the source back to read-write.
4. Restart the app. Smoke test. Record the failure reason and keep the target for analysis.

## Troubleshooting

| Symptom | Likely cause | Action |
|---|---|---|
| `CDCLatencySource` rising | Source log reader slow, archive logs on slow storage, LogMiner limits | Binary Reader for Oracle, more task parallelism, check source I/O |
| `CDCLatencyTarget` rising | Target apply bottleneck, missing indexes for updates/deletes, triggers/FKs on | Batch apply, add PK/unique indexes, scale target, split the task by tables |
| Table `Table error` | Unsupported data type, LOB truncation, missing PK | Check task logs (CloudWatch `dms-tasks-<instance>`), fix mapping/LOB size, reload the table |
| `Mismatched records` in validation | Truncated LOBs, collation/precision differences, writes during the check | Re-validate after drain; fix type mapping; reload the table |
| Free storage alarm | Cached changes piling up on the instance (target slow) | Fix target throughput; increase allocated storage |
| PostgreSQL WAL growth on the source | Replication slot not consumed | Restart the subscriber/task; drop stale slots after cutover |
