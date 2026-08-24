"""
Vocabulary Endpoints for CFR EVO API Gateway.

Serves the controlled vocabularies from public.vocabulary so the HITL review UI can offer
the same terms the parser matches against.

Only ACTIVE, CANONICAL terms are returned. Recognition aliases live in
vocabulary.metadata->'aliases' and are deliberately withheld: an alias exists so the parser
can match a spelling faster-whisper produces (American "smoldering" for the department's
"smouldering"), and offering it to a reviewer would reintroduce the split ground truth this
endpoint exists to prevent. See punch-list #43.
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

try:
    from backend.api.database import get_db
except ModuleNotFoundError:
    from api.database import get_db

router = APIRouter(prefix="/api/vocabulary", tags=["vocabulary"])


@router.get("")
def get_vocabulary(
    db: Session = Depends(get_db),
    category: Optional[str] = Query(
        None,
        description="Vocabulary category, e.g. 'call_type', 'unit', 'radio_channel'. "
                    "Omit to return every active category.",
    ),
):
    """Return active canonical vocabulary terms, grouped by category."""
    sql = (
        "SELECT category, term FROM public.vocabulary "
        "WHERE is_active = TRUE {filt} ORDER BY category, sort_order, term"
    ).format(filt="AND category = :cat" if category else "")

    try:
        rows = db.execute(text(sql), {"cat": category} if category else {}).fetchall()
    except Exception as e:
        logging.error(f"Vocabulary query failed (category={category!r}): {e}")
        # An empty list would read to the UI as "this vocabulary has no terms", which is a
        # plausible wrong answer. Surface the failure instead (CLAUDE.md §6.1).
        raise

    grouped: dict[str, list[str]] = {}
    for cat, term in rows:
        grouped.setdefault(cat, []).append(term)

    return grouped.get(category, []) if category else grouped
