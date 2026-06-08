"""
verify_stack.py — single-shot health check for the local dev stack.

Run this AFTER `docker compose up --build` has settled, from inside the
backend container so it inherits the right env + Django settings:

    docker compose exec backend-service python scripts/verify_stack.py

It checks, in order:
  1. Django settings load and the DB is reachable.
  2. The `vector` extension is enabled in the app DB (pgvector).
  3. The Product model has the `embedding` VectorField column.
  4. Redis is reachable on CELERY_BROKER_URL.
  5. The Celery app can talk to its broker.
  6. A live Celery worker is registered (i.e. `celery worker` is up).
  7. The beat schedule includes the embedding sweep we expect.

Exit code 0 = all green, 1 = at least one failure. Each check prints a
single line so a failed run is obvious from terminal output alone.

This script makes NO network calls to Replicate, Cloudinary, or M-Pesa —
verifying those is out of scope (and would burn credits).
"""

from __future__ import annotations

import os
import sys
import traceback
from typing import Callable, List, Tuple

# ---------------------------------------------------------------------------
# Make the script runnable as `python scripts/verify_stack.py` from /code.
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "e_commerce_backend.settings")

import django  # noqa: E402

django.setup()


# ---------------------------------------------------------------------------
# Each check is a (label, callable) pair. Callables return (ok, detail).
# ---------------------------------------------------------------------------

def check_db_connection() -> Tuple[bool, str]:
    from django.db import connection

    with connection.cursor() as cur:
        cur.execute("SELECT version();")
        version = cur.fetchone()[0]
    return True, version.split(",")[0]


def check_pgvector_extension() -> Tuple[bool, str]:
    from django.db import connection

    with connection.cursor() as cur:
        cur.execute("SELECT extversion FROM pg_extension WHERE extname = 'vector';")
        row = cur.fetchone()
    if not row:
        return False, "extension 'vector' is NOT installed in the app DB"
    return True, f"vector extension v{row[0]}"


def check_embedding_column() -> Tuple[bool, str]:
    from django.db import connection

    with connection.cursor() as cur:
        cur.execute(
            """
            SELECT data_type, udt_name
            FROM information_schema.columns
            WHERE table_name = 'products_product' AND column_name = 'embedding';
            """
        )
        row = cur.fetchone()
    if not row:
        return False, "products_product.embedding column missing — did migrations run?"
    # udt_name will be 'vector' when pgvector is wired up.
    return True, f"products_product.embedding type={row[1]}"


def check_redis_reachable() -> Tuple[bool, str]:
    import redis
    from django.conf import settings

    r = redis.from_url(settings.CELERY_BROKER_URL)
    pong = r.ping()
    if not pong:
        return False, "PING returned falsy"
    return True, f"PING ok on {settings.CELERY_BROKER_URL}"


def check_celery_broker() -> Tuple[bool, str]:
    from e_commerce_backend.celery import app

    # `connection_or_acquire` opens (or pools) a connection to the broker.
    with app.connection_or_acquire() as conn:
        conn.ensure_connection(max_retries=1)
    return True, f"connected to {app.conf.broker_url}"


def check_celery_worker_alive() -> Tuple[bool, str]:
    from e_commerce_backend.celery import app

    # `inspect().ping()` returns a dict {worker_name: {'ok': 'pong'}} or None
    # if no workers are running. Short timeout so we fail fast in CI.
    replies = app.control.inspect(timeout=2.0).ping()
    if not replies:
        return False, "no celery worker responded to ping — is the `celery` service up?"
    workers = ", ".join(replies.keys())
    return True, f"worker(s) online: {workers}"


def check_beat_schedule() -> Tuple[bool, str]:
    from django.conf import settings

    schedule = getattr(settings, "CELERY_BEAT_SCHEDULE", {}) or {}
    expected_task = "products.tasks.embed_missing_products"
    found = [name for name, cfg in schedule.items() if cfg.get("task") == expected_task]
    if not found:
        return False, f"no beat entry routes to {expected_task}"
    return True, f"{expected_task} scheduled as {found[0]}"


CHECKS: List[Tuple[str, Callable[[], Tuple[bool, str]]]] = [
    ("DB connection", check_db_connection),
    ("pgvector extension", check_pgvector_extension),
    ("Product.embedding column", check_embedding_column),
    ("Redis reachable", check_redis_reachable),
    ("Celery broker handshake", check_celery_broker),
    ("Celery worker ping", check_celery_worker_alive),
    ("Beat schedule entry", check_beat_schedule),
]


def main() -> int:
    print("=" * 60)
    print("TryOn.ke stack verification")
    print("=" * 60)
    failures = 0
    for label, fn in CHECKS:
        try:
            ok, detail = fn()
        except Exception:  # pragma: no cover — diagnostic path
            ok, detail = False, "exception: " + traceback.format_exc(limit=2).strip().splitlines()[-1]
        mark = "PASS" if ok else "FAIL"
        print(f"  [{mark}] {label:<28} {detail}")
        if not ok:
            failures += 1
    print("=" * 60)
    if failures:
        print(f"{failures} check(s) failed.")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
