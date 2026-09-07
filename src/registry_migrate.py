"""Apply and verify the additive DTL Signal release-registry schema."""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Callable


MIGRATION_VERSION = "001_release_registry"
MIGRATION_PATH = Path(__file__).resolve().parents[1] / "migrations" / f"{MIGRATION_VERSION}.sql"
EXPECTED_TABLES = {
    "signal_releases",
    "signal_release_recipients",
    "signal_release_events",
    "signal_registry_migrations",
}
EXPECTED_TRIGGERS = {
    "signal_release_update_guard",
    "signal_recipient_update_guard",
    "signal_events_no_update",
}
EXPECTED_FUNCTIONS = {
    "signal_validate_release_update",
    "signal_validate_recipient_update",
    "signal_events_append_only",
}
EXPECTED_INDEXES = {
    "signal_release_recipients_pending_idx",
    "signal_release_events_release_time_idx",
}
EXPECTED_CONSTRAINTS = {
    "signal_releases_edition_type_scope_unique",
    "signal_releases_issue_type_scope_unique",
    "signal_releases_window_order",
    "signal_releases_html_sha_format",
    "signal_releases_audience_sha_format",
    "signal_releases_image_pair",
    "signal_releases_claim_pair",
    "signal_release_recipient_unique",
    "signal_release_idempotency_unique",
    "signal_release_provider_message_unique",
    "signal_release_recipient_hash_format",
    "signal_release_recipient_html_sha_format",
    "signal_release_provider_state_check",
}


class RegistryMigrationError(RuntimeError):
    pass


def migration_sha256(sql: str) -> str:
    return hashlib.sha256(sql.encode("utf-8")).hexdigest()


def validate_additive_migration(sql: str) -> None:
    upper = sql.upper()
    forbidden = (
        r"\bDROP\s+(?:TABLE|DATABASE|SCHEMA|TRIGGER|FUNCTION)\b",
        r"\bTRUNCATE\b",
        r"\bALTER\s+TABLE\b[^;]*\bDROP\b",
        r"^\s*DELETE\s+FROM\b",
        r"^\s*UPDATE\s+[^;]+\s+SET\b",
        r"\bCOMMIT\b",
        r"\bROLLBACK\b",
    )
    if any(re.search(pattern, upper, flags=re.MULTILINE) for pattern in forbidden):
        raise RegistryMigrationError("registry migration contains a forbidden destructive statement")
    for table in EXPECTED_TABLES - {"signal_registry_migrations"}:
        if f"CREATE TABLE IF NOT EXISTS {table.upper()}" not in upper:
            raise RegistryMigrationError(f"registry migration does not create {table}")
    for trigger in EXPECTED_TRIGGERS:
        if f"CREATE TRIGGER {trigger.upper()}" not in upper:
            raise RegistryMigrationError(f"registry migration does not create {trigger}")
    for function in EXPECTED_FUNCTIONS:
        if f"FUNCTION {function.upper()}()" not in upper:
            raise RegistryMigrationError(f"registry migration does not create {function}")
    for index in EXPECTED_INDEXES:
        if f"CREATE INDEX IF NOT EXISTS {index.upper()}" not in upper:
            raise RegistryMigrationError(f"registry migration does not create {index}")
    for constraint in EXPECTED_CONSTRAINTS:
        if constraint.upper() not in upper:
            raise RegistryMigrationError(f"registry migration does not define {constraint}")


def _verify_schema(cursor: Any) -> dict[str, list[str]]:
    cursor.execute(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = ANY(%s)
        ORDER BY table_name
        """,
        (sorted(EXPECTED_TABLES),),
    )
    tables = [row["table_name"] for row in cursor.fetchall()]
    cursor.execute(
        """
        SELECT DISTINCT trigger_name
        FROM information_schema.triggers
        WHERE trigger_schema = 'public' AND trigger_name = ANY(%s)
        ORDER BY trigger_name
        """,
        (sorted(EXPECTED_TRIGGERS),),
    )
    triggers = [row["trigger_name"] for row in cursor.fetchall()]
    cursor.execute(
        """
        SELECT routine_name
        FROM information_schema.routines
        WHERE routine_schema = 'public' AND routine_name = ANY(%s)
        ORDER BY routine_name
        """,
        (sorted(EXPECTED_FUNCTIONS),),
    )
    functions = [row["routine_name"] for row in cursor.fetchall()]
    cursor.execute(
        """
        SELECT indexname
        FROM pg_indexes
        WHERE schemaname = 'public' AND indexname = ANY(%s)
        ORDER BY indexname
        """,
        (sorted(EXPECTED_INDEXES),),
    )
    indexes = [row["indexname"] for row in cursor.fetchall()]
    cursor.execute(
        """
        SELECT constraint_name
        FROM information_schema.table_constraints
        WHERE constraint_schema = 'public' AND constraint_name = ANY(%s)
        ORDER BY constraint_name
        """,
        (sorted(EXPECTED_CONSTRAINTS),),
    )
    constraints = [row["constraint_name"] for row in cursor.fetchall()]
    missing_tables = EXPECTED_TABLES - set(tables)
    missing_triggers = EXPECTED_TRIGGERS - set(triggers)
    missing_functions = EXPECTED_FUNCTIONS - set(functions)
    missing_indexes = EXPECTED_INDEXES - set(indexes)
    missing_constraints = EXPECTED_CONSTRAINTS - set(constraints)
    if (
        missing_tables
        or missing_triggers
        or missing_functions
        or missing_indexes
        or missing_constraints
    ):
        raise RegistryMigrationError(
            f"registry schema verification failed: missing tables={sorted(missing_tables)} "
            f"missing triggers={sorted(missing_triggers)} "
            f"missing functions={sorted(missing_functions)} "
            f"missing indexes={sorted(missing_indexes)} "
            f"missing constraints={sorted(missing_constraints)}"
        )
    return {
        "tables": tables,
        "triggers": triggers,
        "functions": functions,
        "indexes": indexes,
        "constraints": constraints,
    }


def apply_registry_migration(
    database_url: str,
    *,
    connect: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    if not database_url:
        raise RegistryMigrationError("SIGNAL_REGISTRY_DATABASE_URL is required")
    sql = MIGRATION_PATH.read_text(encoding="utf-8")
    validate_additive_migration(sql)
    checksum = migration_sha256(sql)
    if connect is None:
        from psycopg import connect as psycopg_connect

        connect = psycopg_connect
    with connect(
        database_url,
        connect_timeout=10,
        application_name="dtl-signal-registry-migrate",
    ) as connection:
        with connection.cursor(row_factory=__import__("psycopg").rows.dict_row) as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS signal_registry_migrations (
                    version TEXT PRIMARY KEY,
                    migration_sha256 CHAR(64) NOT NULL,
                    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            cursor.execute(
                "SELECT migration_sha256 FROM signal_registry_migrations WHERE version = %s",
                (MIGRATION_VERSION,),
            )
            existing = cursor.fetchone()
            if existing and existing["migration_sha256"] != checksum:
                raise RegistryMigrationError("applied registry migration checksum does not match source")
            if not existing:
                cursor.execute(sql)
                cursor.execute(
                    """
                    INSERT INTO signal_registry_migrations (version, migration_sha256)
                    VALUES (%s, %s)
                    """,
                    (MIGRATION_VERSION, checksum),
                )
            verified = _verify_schema(cursor)
        connection.commit()
    return {
        "version": MIGRATION_VERSION,
        "migration_sha256": checksum,
        "applied": not bool(existing),
        **verified,
    }


def main() -> int:
    result = apply_registry_migration(os.getenv("SIGNAL_REGISTRY_DATABASE_URL", ""))
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
