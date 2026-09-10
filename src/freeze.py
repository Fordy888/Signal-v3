"""Lean freeze + exactly-once delivery for Signal editions (SQLite).

The contract, end to end:

    1. RENDER ONCE.       The edition HTML is built a single time.
    2. FREEZE.            The exact payload bytes are hashed (SHA-256) and
                          stored, once, against the edition number.
    3. PROOF.             The proof sends *those bytes* and quotes the hash.
    4. APPROVE.           Approval binds to the hash, not to the edition number
                          — approving edition 0051 approves one specific payload.
    5. SEND.              Loads the frozen bytes, re-verifies the hash, checks
                          the approval matches that hash, claims a send-ledger
                          row (unique per edition+recipient), sends the exact
                          bytes, and records the send.

Nothing re-renders or mutates the payload between proof and send. That closes
both failure modes seen on 0049: content drifting between what was approved and
what was sent, and an edition going out twice.

PERSISTENCE (important): Render cron jobs get an ephemeral filesystem, so a
database under ``data/`` does NOT survive between runs. Freeze→proof→approve
→send therefore only spans runs if the database sits on a Render Disk (or
equivalent). Within a single run — which is what the current proof path does —
the ephemeral file is sufficient. ``SIGNAL_FREEZE_DB`` overrides the location.
"""
from __future__ import annotations

import hashlib
import logging
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger(__name__)

DEFAULT_DB = "data/freeze.sqlite3"

SCHEMA = """
CREATE TABLE IF NOT EXISTS frozen_edition (
    edition_number INTEGER PRIMARY KEY,
    sha256         TEXT    NOT NULL UNIQUE,
    subject        TEXT    NOT NULL,
    payload        BLOB    NOT NULL,
    frozen_at      TEXT    NOT NULL
);
CREATE TABLE IF NOT EXISTS approval (
    sha256      TEXT PRIMARY KEY,
    approved_by TEXT NOT NULL,
    approved_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS send_ledger (
    edition_number INTEGER NOT NULL,
    recipient      TEXT    NOT NULL,
    sha256         TEXT    NOT NULL,
    sent_at        TEXT    NOT NULL,
    PRIMARY KEY (edition_number, recipient)
);
"""


class FreezeError(RuntimeError):
    """Base class for freeze/exactly-once violations."""


class FreezeConflict(FreezeError):
    """A different payload was already frozen for this edition."""


class PayloadCorrupt(FreezeError):
    """Stored bytes no longer hash to the recorded digest."""


class NotApproved(FreezeError):
    """The frozen payload has no approval bound to its hash."""


class AlreadySent(FreezeError):
    """This edition was already sent to this recipient."""


@dataclass(frozen=True)
class FrozenEdition:
    """One immutable edition payload."""

    edition_number: int
    sha256: str
    subject: str
    payload: bytes
    frozen_at: str

    @property
    def html(self) -> str:
        """The exact bytes decoded for the mail API. Never re-rendered."""
        return self.payload.decode("utf-8")

    @property
    def short_hash(self) -> str:
        return self.sha256[:12]


def digest(payload: bytes) -> str:
    """SHA-256 over the exact payload bytes."""
    return hashlib.sha256(payload).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(root: Path | None = None, db_path: str | None = None) -> sqlite3.Connection:
    """Open (and initialise) the freeze database."""
    location = db_path or os.environ.get("SIGNAL_FREEZE_DB") or DEFAULT_DB
    path = Path(location)
    if not path.is_absolute() and root is not None:
        path = root / path
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    conn.commit()
    log.info("Freeze store ready at %s", path)
    return conn


# ─────────────────────────────── freeze ───────────────────────────────────


def freeze_edition(
    conn: sqlite3.Connection,
    edition_number: int,
    subject: str,
    html: str,
) -> FrozenEdition:
    """Freeze the rendered edition, or return the payload already frozen.

    Idempotent by design: calling twice with identical HTML returns the same
    frozen payload. Calling with *different* HTML raises FreezeConflict rather
    than overwriting — an edition is rendered once, and a second render is a
    bug worth surfacing, not a silent replacement.
    """
    payload = html.encode("utf-8")
    sha = digest(payload)

    existing = load_frozen(conn, edition_number)
    if existing is not None:
        if existing.sha256 != sha:
            raise FreezeConflict(
                f"Edition {edition_number:04d} is already frozen as "
                f"{existing.short_hash} but a different payload was offered "
                f"({sha[:12]}). The edition must be rendered exactly once."
            )
        log.info(
            "Edition %04d already frozen as %s — reusing frozen bytes",
            edition_number,
            existing.short_hash,
        )
        return existing

    frozen_at = _now()
    conn.execute(
        "INSERT INTO frozen_edition (edition_number, sha256, subject, payload, frozen_at)"
        " VALUES (?, ?, ?, ?, ?)",
        (edition_number, sha, subject, payload, frozen_at),
    )
    conn.commit()
    log.info(
        "Edition %04d frozen: sha256=%s (%d bytes)", edition_number, sha, len(payload)
    )
    return FrozenEdition(edition_number, sha, subject, payload, frozen_at)


def load_frozen(conn: sqlite3.Connection, edition_number: int) -> FrozenEdition | None:
    """Load the frozen payload, verifying the bytes still match the digest."""
    row = conn.execute(
        "SELECT edition_number, sha256, subject, payload, frozen_at"
        " FROM frozen_edition WHERE edition_number = ?",
        (edition_number,),
    ).fetchone()
    if row is None:
        return None

    frozen = FrozenEdition(row[0], row[1], row[2], row[3], row[4])
    actual = digest(frozen.payload)
    if actual != frozen.sha256:
        raise PayloadCorrupt(
            f"Edition {edition_number:04d} stored bytes hash to {actual[:12]} "
            f"but the recorded digest is {frozen.short_hash}"
        )
    return frozen


# ────────────────────────────── approval ──────────────────────────────────


def approve(conn: sqlite3.Connection, sha256: str, approved_by: str) -> None:
    """Bind an approval to one exact payload hash."""
    conn.execute(
        "INSERT OR REPLACE INTO approval (sha256, approved_by, approved_at)"
        " VALUES (?, ?, ?)",
        (sha256, approved_by, _now()),
    )
    conn.commit()
    log.info("Approval recorded for payload %s by %s", sha256[:12], approved_by)


def is_approved(conn: sqlite3.Connection, sha256: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM approval WHERE sha256 = ?", (sha256,)
    ).fetchone()
    return row is not None


# ──────────────────────────── exactly-once ────────────────────────────────


def claim_send(
    conn: sqlite3.Connection,
    edition_number: int,
    recipient: str,
    sha256: str,
) -> None:
    """Claim the right to send this edition to this recipient, exactly once.

    The send-ledger primary key (edition_number, recipient) is the guard: a
    second claim raises AlreadySent instead of producing a duplicate email.
    Claim *before* sending, so a crash mid-send cannot become a resend.
    """
    try:
        conn.execute(
            "INSERT INTO send_ledger (edition_number, recipient, sha256, sent_at)"
            " VALUES (?, ?, ?, ?)",
            (edition_number, recipient.strip().lower(), sha256, _now()),
        )
        conn.commit()
    except sqlite3.IntegrityError as exc:
        raise AlreadySent(
            f"Edition {edition_number:04d} was already sent to {recipient}"
        ) from exc


def release_send(conn: sqlite3.Connection, edition_number: int, recipient: str) -> None:
    """Release a claim when the send itself failed, so a retry is possible."""
    conn.execute(
        "DELETE FROM send_ledger WHERE edition_number = ? AND recipient = ?",
        (edition_number, recipient.strip().lower()),
    )
    conn.commit()
    log.warning(
        "Send claim released for edition %04d / %s — delivery failed, retry allowed",
        edition_number,
        recipient,
    )


def already_sent(conn: sqlite3.Connection, edition_number: int, recipient: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM send_ledger WHERE edition_number = ? AND recipient = ?",
        (edition_number, recipient.strip().lower()),
    ).fetchone()
    return row is not None


def load_for_send(
    conn: sqlite3.Connection,
    edition_number: int,
    *,
    require_approval: bool = True,
) -> FrozenEdition:
    """Load frozen bytes for delivery, enforcing every precondition.

    Verifies (in order): the edition was frozen; the stored bytes still hash to
    the recorded digest; and an approval is bound to *that* hash. Returns the
    exact bytes to send — the caller must not modify them.
    """
    frozen = load_frozen(conn, edition_number)
    if frozen is None:
        raise FreezeError(
            f"Edition {edition_number:04d} has not been frozen — nothing to send"
        )
    if require_approval and not is_approved(conn, frozen.sha256):
        raise NotApproved(
            f"Edition {edition_number:04d} payload {frozen.short_hash} has no "
            "approval bound to it. Approval binds to the payload hash, so a "
            "re-rendered edition needs approving again."
        )
    return frozen
