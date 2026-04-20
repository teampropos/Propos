"""Tone memory management for per-client reply personalisation."""

from typing import Optional

TONE_MEMORY_CAP = 15


def get_tone_memory(client_id: str, db_session=None) -> list[str]:
    """Return the last 15 approved replies for a client, most recent first.

    When db_session is None (no database connected), returns an empty list.
    Once PostgreSQL is live, uncomment the query below.
    """
    if db_session is None:
        return []

    # ── PostgreSQL query (uncomment when DB is live) ──────────────
    #
    # result = db_session.execute(
    #     """
    #     SELECT reply_text FROM tone_memory
    #     WHERE client_id = :client_id
    #     ORDER BY
    #         CASE WHEN edited = true THEN 0 ELSE 1 END,
    #         created_at DESC
    #     LIMIT :cap
    #     """,
    #     {"client_id": client_id, "cap": TONE_MEMORY_CAP},
    # )
    # return [row[0] for row in result.fetchall()]
    #
    # ──────────────────────────────────────────────────────────────

    return []


def trim_tone_memory(client_id: str, db_session) -> None:
    """Trim tone memory to cap, dropping oldest unedited approvals first.

    Call after saving a new approved reply.
    """
    # ── PostgreSQL query (uncomment when DB is live) ──────────────
    #
    # # Count total
    # count = db_session.execute(
    #     "SELECT COUNT(*) FROM tone_memory WHERE client_id = :client_id",
    #     {"client_id": client_id},
    # ).scalar()
    #
    # if count <= TONE_MEMORY_CAP:
    #     return
    #
    # # Delete oldest unedited first, then oldest edited
    # excess = count - TONE_MEMORY_CAP
    # db_session.execute(
    #     """
    #     DELETE FROM tone_memory WHERE id IN (
    #         SELECT id FROM tone_memory
    #         WHERE client_id = :client_id
    #         ORDER BY edited ASC, created_at ASC
    #         LIMIT :excess
    #     )
    #     """,
    #     {"client_id": client_id, "excess": excess},
    # )
    # db_session.commit()
    #
    # ──────────────────────────────────────────────────────────────
    pass
