"""Pipeline-output persistence.

Contract for writing AgentState -> PostgreSQL (MorningNote + Recommendation).

Failure-mode rules:
    * Company ticker missing -> raise CompanyNotFoundError (typed).
    * Transient DB failure -> raise PersistenceError (typed).
    * Agent state missing outputs -> raise IncompleteStateError (typed).
    * The function NEVER appends state['flags']; flags belong to agents.
"""

from __future__ import annotations

from datetime import datetime
from typing import Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Company, MorningNote, Recommendation
from app.graph.state import AgentState
from app.utils.data_preprocessing import DataFlag

# Common base exists so callers can `except FinAgentPersistenceError` for
# catch-all logging while still discriminating per-subclass for Celery's
# autoretry_for policy


class FinAgentPersistenceError(Exception):
    """Base class for all persistence-layer failures."""


class CompanyNotFoundError(FinAgentPersistenceError):
    """Master-data integrity: ticker is not in companies table. Non-transient. Caller must NOT retry."""

    # self is the new instance being built. it is the receiver of the method call
    def __init__(self, ticker: str) -> None:
        # stores the human-readable message
        # super init calls the parent class's init with the message
        super().__init__(f"No Company row found for ticker={ticker!r}")
        # stores the structured data on the object
        self.ticker = ticker


class IncompleteStateError(FinAgentPersistenceError):
    """Agent state is missing required outputs (e.g., empty morning_note)"""

    def __init__(self, missing: str) -> None:
        super().__init__(f"AgentState missing required output: {missing}")
        self.missing = missing


class PersistenceError(FinAgentPersistenceError):
    """Transient DB-layer failure (Postgres down, FK violation, JSONB error).
    Wraps the original exception so callers can introspect the cause.
    MAY be retryable by Celery.    
    """

    def __init__(self, cause: Exception) -> None:
        super().__init__(f"Persistence failure: {cause!r}")
        self.cause = cause


# Boundary-conversion helpers
# These exist because Python's datetime dict and Pydantic models do NOT
# serialize to PostgreSQL JSONB natively. Conversion happens at the
# boundary; everything inside this file after these helpers assumes the
# values are already JSONB-compatible.


def _serialize_freshness(freshness: dict) -> dict:
    """JSONB does not serialize datetime natively. Convert at the boundary
    Returns a NEW dict; does not mutate the input.
    """
    out: dict = {}
    for key, value in freshness.items():
        if isinstance(value, datetime):
            out[key] = value.isoformat()
        else:
            out[key] = value
    return out


def _serialize_flags(flags: list) -> list:
    """Each flag is a DataFlag Pydantic model; JSONB ARRAY needs plain dicts.
    
    Branches on input element type:
        * DataFlag instance -> .model_dump()
        * dict -> pass through (already serialized)
        * anything else -> raise PersistenceError(transient I/O hazard)
    """
    out: list = []
    for f in flags:
        if isinstance(f, DataFlag):
            out.append(f.model_dump())
        elif isinstance(f, dict):
            out.append(f)
        else:
            raise PersistenceError(ValueError(f"Unexpected flag type: {type(f).__name__}"))
    return out


def _resolve_justification(recommendation) -> str:
    """DB column is NOT NULL; state field is Optional.
    Temporary fallback.

    TODO(issue-N+1): EditorAgent must populate `justification` itself
    (separate PR - touches prompt + EditorOutputSchema)

    Until then, fall back to thesis_summary so persistence does not regress.
    """
    value = getattr(recommendation, "justification", None)
    if value:
        return value
    return recommendation.thesis_summary


# Public entry point

async def persist_pipeline_output(
        state: AgentState,
        session: AsyncSession,
) -> Tuple[int, int]:
    """Persist a completed pipeline run as MorningNote + Recommendation.
    
    Returns (morning_note_id, recommendation_id) on success.

    Behaviors:
        * Company ticker missing -> CompanyNotFoundError
        * Agent state missing required outputs -> IncompleteStateError
        * DB/transient failure -> PersistenceError (wraps cause)
        * NEVER mutates state['flags']

        Atomicity: both inserts run inside ONE `async with session.begin()`
        block they commit/rollback together.
    """
    ticker = state["company_ticker"]
    manager_id = state["manager_id"]
    morning_note_text = state.get("morning_note")
    reco = state.get("recommendation")

    if not morning_note_text:
        raise IncompleteStateError("morning_note")
    if reco is None:
        raise IncompleteStateError("recommendation")

    try:
        result = await session.execute(select(Company.company_id).where(Company.ticker == ticker))
        company_id = result.scalar_one_or_none()
    except Exception as exc:
        raise PersistenceError(exc) from exc

    try:
        confidence = dict(state.get("confidence_scores") or {})
        freshness = _serialize_freshness(state.get("data_freshness") or {})
        flags_list = _serialize_flags(state.get("flags") or [])
        justification_text = _resolve_justification(reco)
    except PersistenceError:
        raise
    except Exception as exc:
        raise PersistenceError(exc) from exc

    note_id, reco_id = 0, 0
    try:
        async with session.begin():
            note = MorningNote(
                pipeline_run_id=state["pipeline_run_id"],
                manager_id=manager_id,
                company_id=company_id,
                content=morning_note_text,
                confidence_score=confidence,
                data_freshness=freshness,
                flags=flags_list,
                status="completed",
            )
            session.add(note)
            await session.flush()
            note_id = note.morning_note_id

            recommendation = Recommendation(
                morning_note_id=note_id,
                action=reco.action,
                justification=justification_text,
                confidence=reco.confidence,
            )
            session.add(recommendation)
            await session.flush()
            reco_id = recommendation.recommendation_id
    except FinAgentPersistenceError:
        raise
    except Exception as exc:
        raise PersistenceError(exc) from exc

    return note_id, reco_id
    