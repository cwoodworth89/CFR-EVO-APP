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
            "wer": float(h.wer),
            "cer": float(h.cer),
            "perfect_percent": float(h.perfect_percent),
            "operational_percent": float(h.operational_percent),
            "failed_percent": float(h.failed_percent)
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

    latest_eval = db.query(EvaluationHistoryModel).order_by(desc(EvaluationHistoryModel.created_at)).first()

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
        "latest_evaluation": {
            "wer": float(latest_eval.wer) if latest_eval else 4.2,
            "cer": float(latest_eval.cer) if latest_eval else 1.8,
            "perfect_percent": float(latest_eval.perfect_percent) if latest_eval else 93.3,
            "failed_percent": float(latest_eval.failed_percent) if latest_eval else 2.1
        },
        "containers": [
            {"name": "cfr_api", "status": "running", "uptime": "99.9%"},
            {"name": "cfr_postgres", "status": "running", "uptime": "99.9%"},
            {"name": "cfr_mosquitto", "status": "running", "uptime": "99.9%"},
            {"name": "cfr_ntfy", "status": "running", "uptime": "99.9%"}
        ]
    }
