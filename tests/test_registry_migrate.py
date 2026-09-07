from __future__ import annotations

import unittest

from src.registry_migrate import (
    EXPECTED_CONSTRAINTS,
    EXPECTED_FUNCTIONS,
    EXPECTED_INDEXES,
    EXPECTED_TABLES,
    EXPECTED_TRIGGERS,
    MIGRATION_PATH,
    MIGRATION_VERSION,
    RegistryMigrationError,
    apply_registry_migration,
    migration_sha256,
    validate_additive_migration,
)


class FakeCursor:
    def __init__(self, existing_checksum: str | None = None) -> None:
        self.existing_checksum = existing_checksum
        self.executions: list[tuple[str, object]] = []
        self.last_query = ""

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, query, params=None) -> None:
        self.last_query = str(query)
        self.executions.append((self.last_query, params))

    def fetchone(self):
        if "SELECT migration_sha256" in self.last_query:
            if self.existing_checksum is None:
                return None
            return {"migration_sha256": self.existing_checksum}
        raise AssertionError(f"unexpected fetchone query: {self.last_query}")

    def fetchall(self):
        if "information_schema.tables" in self.last_query:
            return [{"table_name": value} for value in sorted(EXPECTED_TABLES)]
        if "information_schema.triggers" in self.last_query:
            return [{"trigger_name": value} for value in sorted(EXPECTED_TRIGGERS)]
        if "information_schema.routines" in self.last_query:
            return [{"routine_name": value} for value in sorted(EXPECTED_FUNCTIONS)]
        if "FROM pg_indexes" in self.last_query:
            return [{"indexname": value} for value in sorted(EXPECTED_INDEXES)]
        if "information_schema.table_constraints" in self.last_query:
            return [{"constraint_name": value} for value in sorted(EXPECTED_CONSTRAINTS)]
        raise AssertionError(f"unexpected fetchall query: {self.last_query}")


class FakeConnection:
    def __init__(self, existing_checksum: str | None = None) -> None:
        self.cursor_instance = FakeCursor(existing_checksum)
        self.commit_count = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def cursor(self, **_kwargs):
        return self.cursor_instance

    def commit(self) -> None:
        self.commit_count += 1


class RegistryMigrationTests(unittest.TestCase):
    def test_source_migration_is_additive_and_complete(self) -> None:
        sql = MIGRATION_PATH.read_text(encoding="utf-8")
        validate_additive_migration(sql)
        self.assertEqual(64, len(migration_sha256(sql)))
        self.assertNotIn("COMMIT;", sql.upper())
        self.assertNotIn("DROP TRIGGER", sql.upper())

    def test_schema_verification_contract_matches_source(self) -> None:
        sql = MIGRATION_PATH.read_text(encoding="utf-8").upper()
        for trigger in EXPECTED_TRIGGERS:
            self.assertIn(f"CREATE TRIGGER {trigger.upper()}", sql)
        for function in EXPECTED_FUNCTIONS:
            self.assertIn(f"FUNCTION {function.upper()}()", sql)
        for index in EXPECTED_INDEXES:
            self.assertIn(f"CREATE INDEX IF NOT EXISTS {index.upper()}", sql)
        for constraint in EXPECTED_CONSTRAINTS:
            self.assertIn(constraint.upper(), sql)

    def test_destructive_registry_migration_is_rejected(self) -> None:
        for statement in (
            "DROP TABLE signal_releases",
            "DROP TRIGGER signal_release_update_guard ON signal_releases",
            "COMMIT;",
            "DELETE FROM signal_releases",
        ):
            with self.subTest(statement=statement):
                with self.assertRaises(RegistryMigrationError):
                    validate_additive_migration(statement)

    def test_apply_executes_source_once_records_checksum_and_verifies_schema(self) -> None:
        connection = FakeConnection()
        calls = []

        def connect(database_url, **kwargs):
            calls.append((database_url, kwargs))
            return connection

        result = apply_registry_migration("masked-dsn", connect=connect)
        source = MIGRATION_PATH.read_text(encoding="utf-8")
        self.assertTrue(result["applied"])
        self.assertEqual(MIGRATION_VERSION, result["version"])
        self.assertEqual(migration_sha256(source), result["migration_sha256"])
        self.assertEqual(1, connection.commit_count)
        self.assertEqual("masked-dsn", calls[0][0])
        self.assertEqual(10, calls[0][1]["connect_timeout"])
        self.assertTrue(
            any(query == source for query, _params in connection.cursor_instance.executions)
        )
        self.assertTrue(
            any(
                "INSERT INTO signal_registry_migrations" in query
                for query, _params in connection.cursor_instance.executions
            )
        )

    def test_matching_applied_checksum_is_idempotent(self) -> None:
        source = MIGRATION_PATH.read_text(encoding="utf-8")
        connection = FakeConnection(migration_sha256(source))
        result = apply_registry_migration(
            "masked-dsn", connect=lambda *_args, **_kwargs: connection
        )
        self.assertFalse(result["applied"])
        self.assertEqual(1, connection.commit_count)
        self.assertFalse(
            any(query == source for query, _params in connection.cursor_instance.executions)
        )

    def test_applied_checksum_mismatch_fails_before_schema_execution(self) -> None:
        source = MIGRATION_PATH.read_text(encoding="utf-8")
        connection = FakeConnection("0" * 64)
        with self.assertRaises(RegistryMigrationError):
            apply_registry_migration(
                "masked-dsn", connect=lambda *_args, **_kwargs: connection
            )
        self.assertEqual(0, connection.commit_count)
        self.assertFalse(
            any(query == source for query, _params in connection.cursor_instance.executions)
        )


if __name__ == "__main__":
    unittest.main()
