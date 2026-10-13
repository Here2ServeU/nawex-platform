"""Deterministic sample inputs: an OLTP payments database with deliberate problems.

Schema (PostgreSQL)::

    merchants(id PK, name, api_key_hash, country)
    customers(id PK, email, country, created_at)
    payments(id PK, merchant_id → merchants, customer_id → customers, customer_email, amount, currency,
             status, created_at, updated_at, legacy_ref)
    refunds(id PK, payment_id → payments, amount, created_at)            -- FK not indexed (bug)
    ledger_entries(id PK, payment_id → payments, account_id, direction, amount, created_at)
    audit_log(id PK, entity, entity_id, action, payload jsonb, created_at)  -- append-only, huge
    idempotency_keys(key PK, response, created_at)

Planted defects (the tests assert each one is detected):

* ``lower(customer_email) = $1`` lookups do a Seq Scan on payments (needs an expression index);
* refunds are fetched one payment at a time (N+1) and refunds.payment_id has no index;
* the daily settlement report sorts / hashes on disk and its row estimates are stale;
* payments has a duplicate status index, a redundant (merchant_id) index, and a 2 GiB unused index;
* ledger_entries carries 8 indexes with few HOT updates (write amplification);
* audit_log is 45 % dead tuples, autovacuum 12 days stale; database xid age at ~54 % of wraparound;
* 60 app pods × pool 20 exceed max_connections; a db.r6i.4xlarge runs at ~30 % CPU p95.
"""

from __future__ import annotations

import math
import random
from typing import Any


# --------------------------------------------------------------------------- pg_stat_statements
def sample_statements() -> list[dict[str, Any]]:
    """A pg_stat_statements export (PostgreSQL 13+ columns, times in ms)."""

    def row(qid: int, query: str, calls: int, mean: float, rows: int, hit: int, read: int, temp: int = 0):
        return {
            "queryid": str(qid),
            "query": query,
            "calls": calls,
            "total_exec_time": round(calls * mean, 3),
            "mean_exec_time": mean,
            "rows": rows,
            "shared_blks_hit": hit,
            "shared_blks_read": read,
            "temp_blks_written": temp,
        }

    return [
        row(-8123, "SELECT * FROM payments WHERE id = $1", 9_400_000, 0.045, 9_400_000, 47_000_000, 12_000),
        row(
            -7311,
            "UPDATE payments SET status = $1, updated_at = now() WHERE id = $2",
            3_100_000,
            0.11,
            3_100_000,
            21_700_000,
            40_000,
        ),
        row(
            -6022,
            "INSERT INTO ledger_entries (payment_id, account_id, direction, amount, created_at) "
            "VALUES ($1, $2, $3, $4, now())",
            6_200_000,
            0.19,
            6_200_000,
            74_400_000,
            310_000,
        ),
        # N+1: refunds fetched per payment by the payments API serializer
        row(-5110, "SELECT * FROM refunds WHERE payment_id = $1", 2_450_000, 0.09, 61_000, 9_800_000, 2_000),
        # Seq Scan on payments for a case-insensitive email lookup (support console)
        row(
            -4404,
            "SELECT * FROM payments WHERE lower(customer_email) = lower($1) ORDER BY created_at DESC LIMIT $2",
            41_000,
            820.0,
            123_000,
            9_100_000_000,
            1_450_000_000,
        ),
        # Merchant dashboard list
        row(
            -3307,
            "SELECT id, amount, currency, status, created_at FROM payments WHERE merchant_id = $1 "
            "AND status = $2 ORDER BY created_at DESC LIMIT $3",
            380_000,
            14.5,
            19_000_000,
            1_140_000_000,
            61_000_000,
        ),
        # Daily settlement report: spills to disk, poor cache hit
        row(
            -2208,
            "SELECT merchant_id, date_trunc('day', created_at) AS day, currency, sum(amount), count(*) "
            "FROM payments WHERE created_at >= $1 AND created_at < $2 GROUP BY 1, 2, 3 ORDER BY 1, 2",
            96,
            48_500.0,
            1_900_000,
            310_000_000,
            118_000_000,
            9_600_000,
        ),
        # IN-list variants of one shape (distinct queryids before PostgreSQL 18)
        row(-1101, "SELECT * FROM payments WHERE id IN ($1, $2, $3)", 120_000, 0.3, 360_000, 1_800_000, 900),
        row(
            -1102,
            "SELECT * FROM payments WHERE id IN ($1, $2, $3, $4, $5)",
            95_000,
            0.4,
            475_000,
            2_300_000,
            700,
        ),
        row(
            -1103,
            "SELECT * FROM payments WHERE id IN ($1, $2, $3, $4, $5, $6, $7, $8)",
            40_000,
            0.6,
            320_000,
            1_600_000,
            500,
        ),
        # Fraud feature: join with recent window
        row(
            -909,
            "SELECT p.id, p.amount, c.country FROM payments p JOIN customers c ON c.id = p.customer_id "
            "WHERE c.country = $1 AND p.created_at > now() - interval '1 hour'",
            720_000,
            6.2,
            8_600_000,
            150_000_000,
            1_200_000,
        ),
        # Export job pulling everything
        row(-808, "SELECT * FROM audit_log WHERE entity = $1", 30, 21_000.0, 9_000_000, 3_000_000, 6_100_000),
        row(
            -707,
            "SELECT key, response FROM idempotency_keys WHERE key = $1",
            3_000_000,
            0.03,
            410_000,
            9_000_000,
            300,
        ),
    ]


# --------------------------------------------------------------------------- EXPLAIN plans
def _scan(
    rel: str, alias: str, plan_rows: float, rows: float, loops: int, ms: float, **extra: Any
) -> dict[str, Any]:
    node = {
        "Node Type": "Seq Scan",
        "Parallel Aware": False,
        "Relation Name": rel,
        "Schema": "public",
        "Alias": alias,
        "Plan Rows": plan_rows,
        "Actual Rows": rows,
        "Actual Loops": loops,
        "Actual Total Time": ms,
    }
    node.update(extra)
    return node


def sample_explain_plans() -> dict[str, list[dict[str, Any]]]:
    """EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) outputs for the sample workload, keyed by scenario."""
    email_lookup = [
        {
            "Plan": {
                "Node Type": "Limit",
                "Plan Rows": 50,
                "Actual Rows": 3,
                "Actual Loops": 1,
                "Actual Total Time": 842.7,
                "Plans": [
                    {
                        "Node Type": "Sort",
                        "Sort Key": ["created_at DESC"],
                        "Sort Method": "quicksort",
                        "Sort Space Used": 25,
                        "Sort Space Type": "Memory",
                        "Plan Rows": 61_000,
                        "Actual Rows": 3,
                        "Actual Loops": 1,
                        "Actual Total Time": 842.6,
                        "Plans": [
                            _scan(
                                "payments",
                                "payments",
                                61_000,
                                3,
                                1,
                                842.1,
                                Filter="(lower((customer_email)::text) = 'ana@example.com'::text)",
                                **{
                                    "Rows Removed by Filter": 12_199_997,
                                    "Shared Hit Blocks": 240_000,
                                    "Shared Read Blocks": 1_160_000,
                                },
                            )
                        ],
                    }
                ],
            },
            "Planning Time": 0.21,
            "Execution Time": 842.9,
        }
    ]

    merchant_status = [
        {
            "Plan": {
                "Node Type": "Limit",
                "Plan Rows": 50,
                "Actual Rows": 50,
                "Actual Loops": 1,
                "Actual Total Time": 14.1,
                "Plans": [
                    {
                        "Node Type": "Index Scan",
                        "Index Name": "idx_payments_merchant_created",
                        "Relation Name": "payments",
                        "Alias": "payments",
                        "Scan Direction": "Backward",
                        "Index Cond": "(merchant_id = 42)",
                        "Filter": "((status)::text = 'pending'::text)",
                        "Rows Removed by Filter": 48_200,
                        "Plan Rows": 4_100,
                        "Actual Rows": 50,
                        "Actual Loops": 1,
                        "Actual Total Time": 14.0,
                    }
                ],
            },
            "Planning Time": 0.3,
            "Execution Time": 14.2,
        }
    ]

    settlement_report = [
        {
            "Plan": {
                "Node Type": "Sort",
                "Sort Key": ["merchant_id", "(date_trunc('day'::text, created_at))"],
                "Sort Method": "external merge",
                "Sort Space Used": 412_000,
                "Sort Space Type": "Disk",
                "Plan Rows": 1_800,
                "Actual Rows": 1_900_000,
                "Actual Loops": 1,
                "Actual Total Time": 48_420.0,
                "Plans": [
                    {
                        "Node Type": "HashAggregate",
                        "Group Key": ["merchant_id", "date_trunc('day'::text, created_at)", "currency"],
                        "Plan Rows": 1_800,
                        "Actual Rows": 1_900_000,
                        "Actual Loops": 1,
                        "Actual Total Time": 39_900.0,
                        "HashAgg Batches": 33,
                        "Disk Usage": 702_000,
                        "Plans": [
                            _scan(
                                "payments",
                                "payments",
                                9_800_000,
                                10_400_000,
                                1,
                                21_000.0,
                                Filter="((created_at >= '2026-10-12 00:00:00+00'::timestamp with time zone) AND "
                                "(created_at < '2026-10-13 00:00:00+00'::timestamp with time zone))",
                                **{"Rows Removed by Filter": 1_800_000, "Temp Written Blocks": 0},
                            )
                        ],
                    }
                ],
            },
            "Planning Time": 0.4,
            "Execution Time": 48_500.0,
        }
    ]

    refund_join = [
        {
            "Plan": {
                "Node Type": "Nested Loop",
                "Join Type": "Left",
                "Plan Rows": 12,
                "Actual Rows": 6_100,
                "Actual Loops": 1,
                "Actual Total Time": 9_870.0,
                "Join Filter": "(r.payment_id = p.id)",
                "Rows Removed by Join Filter": 54_000_000,
                "Plans": [
                    {
                        "Node Type": "Index Scan",
                        "Relation Name": "payments",
                        "Alias": "p",
                        "Index Name": "idx_payments_merchant_created",
                        "Index Cond": "((merchant_id = 42) AND (created_at > '2026-10-01 00:00:00+00'::timestamp with time zone))",
                        "Plan Rows": 12,
                        "Actual Rows": 5_000,
                        "Actual Loops": 1,
                        "Actual Total Time": 18.0,
                    },
                    _scan("refunds", "r", 10_800, 10_800, 5_000, 0.9),
                ],
            },
            "Planning Time": 0.5,
            "Execution Time": 9_871.0,
        }
    ]

    bitmap_lossy = [
        {
            "Plan": {
                "Node Type": "Bitmap Heap Scan",
                "Relation Name": "ledger_entries",
                "Alias": "ledger_entries",
                "Recheck Cond": "(account_id = 9001)",
                "Rows Removed by Index Recheck": 2_400_000,
                "Exact Heap Blocks": 18_000,
                "Lossy Heap Blocks": 61_000,
                "Plan Rows": 880_000,
                "Actual Rows": 910_000,
                "Actual Loops": 1,
                "Actual Total Time": 3_120.0,
                "Plans": [
                    {
                        "Node Type": "Bitmap Index Scan",
                        "Index Name": "idx_ledger_entries_account_id",
                        "Index Cond": "(account_id = 9001)",
                        "Plan Rows": 880_000,
                        "Actual Rows": 910_000,
                        "Actual Loops": 1,
                        "Actual Total Time": 140.0,
                    }
                ],
            },
            "Planning Time": 0.2,
            "Execution Time": 3_160.0,
        }
    ]

    ledger_hash_join = [
        {
            "Plan": {
                "Node Type": "Hash Join",
                "Join Type": "Inner",
                "Hash Cond": "(l.payment_id = p.id)",
                "Plan Rows": 40,
                "Actual Rows": 38,
                "Actual Loops": 1,
                "Actual Total Time": 6_400.0,
                "Plans": [
                    _scan("ledger_entries", "l", 48_000_000, 48_000_000, 1, 4_900.0),
                    {
                        "Node Type": "Hash",
                        "Plan Rows": 20,
                        "Actual Rows": 19,
                        "Actual Loops": 1,
                        "Actual Total Time": 0.2,
                        "Hash Batches": 1,
                        "Original Hash Batches": 1,
                        "Peak Memory Usage": 9,
                        "Plans": [
                            {
                                "Node Type": "Index Scan",
                                "Relation Name": "payments",
                                "Alias": "p",
                                "Index Cond": "(customer_id = 777)",
                                "Plan Rows": 20,
                                "Actual Rows": 19,
                                "Actual Loops": 1,
                                "Actual Total Time": 0.1,
                            }
                        ],
                    },
                ],
            },
            "Planning Time": 0.3,
            "Execution Time": 6_401.0,
        }
    ]

    healthy = [
        {
            "Plan": {
                "Node Type": "Index Scan",
                "Relation Name": "payments",
                "Alias": "payments",
                "Index Name": "payments_pkey",
                "Index Cond": "(id = 123456)",
                "Plan Rows": 1,
                "Actual Rows": 1,
                "Actual Loops": 1,
                "Actual Total Time": 0.03,
                "Shared Hit Blocks": 4,
            },
            "Planning Time": 0.06,
            "Execution Time": 0.05,
        }
    ]
    return {
        "email_lookup": email_lookup,
        "merchant_status": merchant_status,
        "settlement_report": settlement_report,
        "refund_join": refund_join,
        "bitmap_lossy": bitmap_lossy,
        "ledger_hash_join": ledger_hash_join,
        "healthy": healthy,
    }


# --------------------------------------------------------------------------- catalog snapshot
GiB = 1 << 30
MiB = 1 << 20


def sample_index_snapshot() -> dict[str, Any]:
    """pg_stat_user_tables / pg_stat_user_indexes / pg_indexes / FK snapshot for the payments database."""

    def ix(
        table: str, name: str, cols: str, scans: int, size: int, *, unique: bool = False, pk: bool = False
    ):
        kind = "UNIQUE INDEX" if unique or pk else "INDEX"
        return {
            "schemaname": "public",
            "relname": table,
            "indexrelname": name,
            "idx_scan": scans,
            "size_bytes": size,
            "is_unique": unique or pk,
            "is_primary": pk,
            "indexdef": f"CREATE {kind} {name} ON public.{table} USING btree ({cols})",
        }

    indexes = [
        ix("merchants", "merchants_pkey", "id", 41_000_000, 40 * MiB, pk=True),
        ix("customers", "customers_pkey", "id", 88_000_000, 900 * MiB, pk=True),
        ix("customers", "customers_email_key", "email", 2_000_000, 1100 * MiB, unique=True),
        ix("payments", "payments_pkey", "id", 950_000_000, 6 * GiB, pk=True),
        ix("payments", "idx_payments_merchant", "merchant_id", 1_200, 4 * GiB),
        ix("payments", "idx_payments_merchant_created", "merchant_id, created_at DESC", 410_000_000, 7 * GiB),
        ix("payments", "idx_payments_status", "status", 210_000, 3 * GiB),
        ix("payments", "idx_payments_status_v2", "status", 9_000, 3 * GiB),
        ix("payments", "idx_payments_legacy_ref", "legacy_ref", 0, 2 * GiB + 200 * MiB),
        ix("payments", "idx_payments_customer", "customer_id", 72_000_000, 5 * GiB),
        ix("refunds", "refunds_pkey", "id", 300_000, 120 * MiB, pk=True),
        ix("ledger_entries", "ledger_entries_pkey", "id", 1_000, 11 * GiB, pk=True),
        ix("ledger_entries", "idx_ledger_entries_payment_id", "payment_id", 6_200_000, 10 * GiB),
        ix("ledger_entries", "idx_ledger_entries_account_id", "account_id", 3_100_000, 10 * GiB),
        ix(
            "ledger_entries",
            "idx_ledger_entries_account_created",
            "account_id, created_at",
            800_000,
            14 * GiB,
        ),
        ix("ledger_entries", "idx_ledger_entries_created", "created_at", 2_000, 10 * GiB),
        ix("ledger_entries", "idx_ledger_entries_direction", "direction", 0, 9 * GiB),
        ix("ledger_entries", "idx_ledger_entries_amount", "amount", 40, 10 * GiB),
        ix("ledger_entries", "idx_ledger_entries_pay_dir", "payment_id, direction", 900, 13 * GiB),
        ix("audit_log", "audit_log_pkey", "id", 10, 40 * GiB, pk=True),
        ix("idempotency_keys", "idempotency_keys_pkey", "key", 3_000_000, 2 * GiB, pk=True),
    ]

    def tbl(name: str, **kw: Any) -> dict[str, Any]:
        base = {
            "schemaname": "public",
            "relname": name,
            "seq_scan": 0,
            "seq_tup_read": 0,
            "idx_scan": 0,
            "n_live_tup": 0,
            "n_dead_tup": 0,
            "n_tup_ins": 0,
            "n_tup_upd": 0,
            "n_tup_hot_upd": 0,
            "n_tup_del": 0,
            "last_autovacuum": "2026-10-12T22:10:00Z",
            "last_autoanalyze": "2026-10-12T22:11:00Z",
            "relfrozenxid_age": 150_000_000,
            "size_bytes": 0,
        }
        base.update(kw)
        return base

    tables = [
        tbl("merchants", seq_scan=9_000, n_live_tup=48_000, idx_scan=41_000_000, size_bytes=30 * MiB),
        tbl(
            "customers",
            seq_scan=40,
            n_live_tup=21_000_000,
            idx_scan=90_000_000,
            n_tup_ins=400_000,
            size_bytes=6 * GiB,
        ),
        tbl(
            "payments",
            seq_scan=41_500,
            seq_tup_read=506_000_000_000,
            n_live_tup=12_200_000,
            n_dead_tup=600_000,
            idx_scan=1_500_000_000,
            n_tup_ins=9_000_000,
            n_tup_upd=31_000_000,
            n_tup_hot_upd=22_000_000,
            size_bytes=38 * GiB,
        ),
        tbl(
            "refunds",
            seq_scan=2_450_000,
            seq_tup_read=26_000_000_000,
            n_live_tup=10_800,
            n_tup_ins=60_000,
            size_bytes=4 * MiB,
        ),
        tbl(
            "ledger_entries",
            seq_scan=300,
            n_live_tup=48_000_000,
            n_dead_tup=1_900_000,
            idx_scan=10_000_000,
            n_tup_ins=6_200_000,
            n_tup_upd=1_400_000,
            n_tup_hot_upd=100_000,
            size_bytes=820 * GiB,
            relfrozenxid_age=640_000_000,
        ),
        tbl(
            "audit_log",
            seq_scan=30,
            n_live_tup=310_000_000,
            n_dead_tup=254_000_000,
            n_tup_ins=40_000_000,
            n_tup_del=250_000_000,
            last_autovacuum="2026-10-01T03:00:00Z",
            relfrozenxid_age=1_160_000_000,
            size_bytes=1400 * GiB,
        ),
        tbl(
            "idempotency_keys",
            seq_scan=2,
            n_live_tup=4_100_000,
            n_dead_tup=90_000,
            n_tup_ins=3_000_000,
            n_tup_del=2_900_000,
            size_bytes=3 * GiB,
        ),
    ]
    foreign_keys = [
        {
            "table": "payments",
            "constraint": "payments_merchant_id_fkey",
            "columns": ["merchant_id"],
            "referenced_table": "merchants",
        },
        {
            "table": "payments",
            "constraint": "payments_customer_id_fkey",
            "columns": ["customer_id"],
            "referenced_table": "customers",
        },
        {
            "table": "refunds",
            "constraint": "refunds_payment_id_fkey",
            "columns": ["payment_id"],
            "referenced_table": "payments",
        },
        {
            "table": "ledger_entries",
            "constraint": "ledger_entries_payment_id_fkey",
            "columns": ["payment_id"],
            "referenced_table": "payments",
        },
    ]
    return {
        "captured_at": "2026-10-13T08:00:00Z",
        "stats_reset": "2026-07-01T00:00:00Z",
        "database": {
            "datname": "payments",
            "datfrozenxid_age": 1_160_000_000,
            "autovacuum_freeze_max_age": 200_000_000,
        },
        "tables": tables,
        "indexes": indexes,
        "foreign_keys": foreign_keys,
    }


# --------------------------------------------------------------------------- capacity profile
def _series(
    n: int, base: float, amplitude: float, noise: float, seed: int, floor: float = 0.0
) -> list[float]:
    """Diurnal sine + bounded noise, deterministic for a seed (one point per 5 minutes)."""
    rng = random.Random(seed)
    out = []
    for i in range(n):
        day_phase = 2 * math.pi * (i % 288) / 288
        out.append(
            max(
                floor,
                round(base + amplitude * math.sin(day_phase - math.pi / 2) + rng.uniform(-noise, noise), 2),
            )
        )
    return out


def sample_capacity_profile(days: int = 14) -> dict[str, Any]:
    """Two weeks of 5-minute CloudWatch-style samples for an over-provisioned Aurora writer."""
    n = 288 * days
    return {
        "workload": "oltp",
        "cache_hit_ratio": 0.995,
        "instance": {
            "engine": "aurora-postgresql",
            "platform": "aurora",
            "class": "db.r6i.4xlarge",
            "instance_count": 2,  # writer + one reader
            "max_connections": 1000,
            "storage_gb": 2400,
            "storage_config": "standard",
        },
        "application": {
            "instances": 60,
            "pool_size_per_instance": 20,
            "pgbouncer": True,
            "reads_per_s": 9_000,
            "writes_per_s": 1_200,
            "replica_lag_tolerance_s": 2.0,
            "hot_key_share": 0.35,
        },
        "samples": {
            "cpu_pct": _series(n, base=19, amplitude=8, noise=3, seed=11, floor=1),
            "freeable_memory_gb": _series(n, base=92, amplitude=4, noise=2, seed=12, floor=1),
            "read_iops": _series(n, base=14_000, amplitude=6_000, noise=1_500, seed=13),
            "write_iops": _series(n, base=6_000, amplitude=2_000, noise=800, seed=14),
        },
        "tables": [
            {
                "name": "ledger_entries",
                "size_gb": 820,
                "timestamp_column": "created_at",
                "range_predicate_share": 0.8,
                "growth_gb_per_month": 60,
                "retention_months": 84,
            },
            {
                "name": "audit_log",
                "size_gb": 1400,
                "timestamp_column": "created_at",
                "range_predicate_share": 0.95,
                "growth_gb_per_month": 110,
                "retention_months": 13,
            },
            {
                "name": "payments",
                "size_gb": 350,
                "timestamp_column": "created_at",
                "range_predicate_share": 0.3,
            },
            {"name": "merchants", "size_gb": 0.03, "timestamp_column": None},
        ],
    }
