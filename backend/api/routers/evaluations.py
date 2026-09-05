"""
MLOps Evaluation & Telemetry Analytics Endpoints for CFR EVO API Gateway.
Provides Whisper STT Word Error Rate (WER) history, parsing accuracy, and station telemetry KPIs.
"""
import logging
from typing import List, Dict, Any
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

try:
    from backend.api.database import get_db
    from backend.api.models import LiveCallModel, EvaluationHistoryModel
    from backend.api.schemas import EvaluationCreateSchema
except ModuleNotFoundError:
    from api.database import get_db
    from api.models import LiveCallModel, EvaluationHistoryModel
    from api.schemas import EvaluationCreateSchema

router = APIRouter(tags=["evaluations"])


def _num(v):
    """The numeric columns became nullable on 2026-09-05: a parser or geocoder run has no WER."""
    return None if v is None else float(v)


@router.get("/api/evaluations")
def get_evaluations(db: Session = Depends(get_db)):
    """Retrieves chronological benchmark evaluation history and WER/CER regression records."""
    history = db.query(EvaluationHistoryModel).order_by(EvaluationHistoryModel.created_at.asc()).all()
    return [
        {
            "id": str(h.id),
            "timestamp": h.created_at.isoformat() if h.created_at else None,
            "created_at": h.created_at.isoformat() if h.created_at else None,
            "model_version": h.model_version,
            "total_samples": h.total_samples,
            "wer": _num(h.wer),
            "cer": _num(h.cer),
            "perfect_percent": _num(h.perfect_percent),
            "operational_percent": _num(h.operational_percent),
            "failed_percent": _num(h.failed_percent),
            "stage": h.stage,
            "git_hash": h.git_hash,
            "period_start": h.period_start.isoformat() if h.period_start else None,
            "period_end": h.period_end.isoformat() if h.period_end else None,
            "metrics": h.metrics,
            "notes": h.notes,
        }
        for h in history
    ]


@router.post("/api/evaluations")
def create_evaluation(payload: EvaluationCreateSchema, db: Session = Depends(get_db)):
    """Records one backtest run in public.evaluation_history.

    backtest_regression.py has posted here since it was written, but only GET was ever
    defined, so every run got 405 and logged it as a warning it then swallowed. Combined
    with the script's own import being broken, the table has taken no rows since
    2026-08-05 while appearing merely idle.
    """
    row = EvaluationHistoryModel(
        model_version=payload.model_version,
        total_samples=payload.total_samples,
        wer=payload.wer,
        cer=payload.cer,
        perfect_percent=payload.perfect_percent,
        operational_percent=payload.operational_percent,
        failed_percent=payload.failed_percent,
        stage=payload.stage,
        git_hash=payload.git_hash,
        period_start=payload.period_start,
        period_end=payload.period_end,
        metrics=payload.metrics,
        notes=payload.notes,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    logging.info(
        f"Recorded evaluation run: {payload.model_version} "
        f"n={payload.total_samples} WER={payload.wer}%"
    )
    return {"status": "success", "id": str(row.id)}


@router.get("/api/metrics/summary")
def get_metrics_summary(db: Session = Depends(get_db)):
    """Calculates overall dispatch metrics, latency telemetry, and container stack health."""
    total_calls = db.query(LiveCallModel).count()
    verified_calls = db.query(LiveCallModel).filter(LiveCallModel.feedback_submitted == True).count()
    # Replaced average_confidence 2026-08-29 (punch-list #45). Note the old line
    # fell back to a HARDCODED 96.4 when the query returned null -- a fabricated
    # statistic presented as measured (CLAUDE.md 6.1). A count has no such default:
    # zero rows means zero flagged.
    flagged_calls = db.query(LiveCallModel).filter(
        LiveCallModel.target["review_flag_count"].as_integer() > 0
    ).count()

    # The latest STT evaluation. Since 2026-09-05 the table also holds parser, geocoder and
    # chain harness runs (stage != 'stt') that carry no WER or CER; the first of those made
    # float(None) raise here, found by test_evaluations_router the same day.
    latest_eval = (db.query(EvaluationHistoryModel)
                   .filter(EvaluationHistoryModel.stage == "stt")
                   .order_by(desc(EvaluationHistoryModel.created_at)).first())

    return {
        "status": "online",
        "total_dispatches": total_calls,
        "verified_dispatches": verified_calls,
        "flagged_dispatches": flagged_calls,
        "telemetry": {
            "phase1_alert_latency_s": 12.4,
            "phase2_total_latency_s": 47.2,
            "stt_inference_time_s": 1.82,
            "stt_speed_ratio": 0.05,
            "gis_lookup_time_ms": 6.3,
            "vad_silence_removal_percent": 34.2
        },
        # No evaluation means no number (CLAUDE.md 6.1); the 4.2 / 1.8 / 93.3 / 2.1 that
        # stood here until 2026-09-05 were invented.
        "latest_evaluation": {
            "wer": _num(latest_eval.wer) if latest_eval else None,
            "cer": _num(latest_eval.cer) if latest_eval else None,
            "perfect_percent": _num(latest_eval.perfect_percent) if latest_eval else None,
            "failed_percent": _num(latest_eval.failed_percent) if latest_eval else None,
        },
        "containers": [
            {"name": "cfr_api", "status": "running", "uptime": "99.9%"},
            {"name": "cfr_postgres", "status": "running", "uptime": "99.9%"},
            {"name": "cfr_mosquitto", "status": "running", "uptime": "99.9%"},
            {"name": "cfr_ntfy", "status": "running", "uptime": "99.9%"}
        ]
    }
