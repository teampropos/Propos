"""Tone memory management for per-client reply personalisation."""

import random

TONE_MEMORY_CAP = 15
EXAMPLES_PER_GENERATION = 6


def get_tone_memory(client_id: int, db_session=None) -> list[str]:
    """Return a sample of approved replies for a client, to use as a style
    reference when generating a new one.

    Always includes edited replies (weight=2) — the owner deliberately
    rewrote these, so they're the strongest signal of the real voice. The
    remaining slots are a random sample of unedited approvals rather than
    always the same most-recent ones: a business with a lot of reviews
    would otherwise see the exact same handful of examples on every single
    generation, which pushes the model toward reusing the same opening and
    closing lines instead of the variety a real business's replies should
    have. Falls back to empty list if no DB session provided.
    """
    if db_session is None:
        return []

    from app.models import ToneMemory

    rows = (
        db_session.query(ToneMemory)
        .filter(ToneMemory.client_id == client_id)
        .order_by(ToneMemory.weight.desc(), ToneMemory.created_at.desc())
        .limit(TONE_MEMORY_CAP)
        .all()
    )
    if len(rows) <= EXAMPLES_PER_GENERATION:
        return [row.reply_text for row in rows]

    edited = [row for row in rows if row.weight >= 2]
    unedited = [row for row in rows if row.weight < 2]
    remaining_slots = max(EXAMPLES_PER_GENERATION - len(edited), 0)
    sampled_unedited = random.sample(unedited, min(remaining_slots, len(unedited)))

    selected = edited[:EXAMPLES_PER_GENERATION] + sampled_unedited
    return [row.reply_text for row in selected]


def save_to_tone_memory(client_id: int, reply_text: str, edited: bool, db_session) -> None:
    """Save an approved reply to tone memory and trim if over cap."""
    from app.models import ToneMemory

    entry = ToneMemory(
        client_id=client_id,
        reply_text=reply_text,
        edited=edited,
        weight=2 if edited else 1,
    )
    db_session.add(entry)
    db_session.flush()
    _trim_tone_memory(client_id, db_session)
    db_session.commit()


def _trim_tone_memory(client_id: int, db_session) -> None:
    """Trim to cap, dropping oldest unedited approvals first."""
    from app.models import ToneMemory

    count = db_session.query(ToneMemory).filter(ToneMemory.client_id == client_id).count()
    if count <= TONE_MEMORY_CAP:
        return

    excess = count - TONE_MEMORY_CAP
    to_delete = (
        db_session.query(ToneMemory)
        .filter(ToneMemory.client_id == client_id)
        .order_by(ToneMemory.weight.asc(), ToneMemory.created_at.asc())
        .limit(excess)
        .all()
    )
    for row in to_delete:
        db_session.delete(row)
