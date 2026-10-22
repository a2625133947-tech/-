"""Persist streamed executions using short, independent database transactions."""

from datetime import datetime
import math
from threading import RLock

from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy import func
from sqlalchemy.orm import sessionmaker

from app.backend.database.models import HedgeFundFlow, HedgeFundFlowRun, HedgeFundFlowRunCycle


def safe_payload(value):
    """Copy JSON data without credentials or non-finite numeric values."""
    value = jsonable_encoder(value)
    if isinstance(value, dict):
        return {key: safe_payload(item) for key, item in value.items() if key.lower() not in {"api_keys", "api_key", "key_value", "authorization", "password", "token", "secret", "access_token"} and not key.lower().endswith(("_api_key", "_token", "_secret"))}
    if isinstance(value, list):
        return [safe_payload(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


class FlowRunRecorder:
    def __init__(self, db, request, trading_mode):
        self.sessions = sessionmaker(bind=db.get_bind(), expire_on_commit=False)
        self.run_id = None
        self.lock = RLock()
        self.started_at = datetime.utcnow()
        if request.flow_id is None:
            return  # Keep standalone API callers compatible; saved flows are tracked.
        with self.sessions() as session:
            if session.get(HedgeFundFlow, request.flow_id) is None:
                raise HTTPException(status_code=404, detail="Flow not found")
            number = session.query(func.max(HedgeFundFlowRun.run_number)).filter_by(flow_id=request.flow_id).scalar()
            run = HedgeFundFlowRun(
                flow_id=request.flow_id,
                run_number=(number or 0) + 1,
                trading_mode=trading_mode,
                status="IN_PROGRESS",
                started_at=self.started_at,
                request_data=safe_payload(request.model_dump(mode="json", exclude={"api_keys"})),
            )
            session.add(run)
            session.commit()
            self.run_id = run.id

    def configure(self, request, portfolio):
        if self.run_id is None:
            return
        with self.lock, self.sessions() as session:
            run = session.get(HedgeFundFlowRun, self.run_id)
            run.request_data = safe_payload(request.model_dump(mode="json", exclude={"api_keys"}))
            run.initial_portfolio = safe_payload(portfolio)
            session.commit()

    def cycle(self, data, portfolio=None, started_at=None, status="COMPLETED", error=None):
        if self.run_id is None:
            return
        data = safe_payload(data)
        now = datetime.utcnow()
        with self.lock, self.sessions() as session:
            run = session.get(HedgeFundFlowRun, self.run_id)
            if run is None or run.status != "IN_PROGRESS":
                return  # A cancelled worker must not append more results.
            number = session.query(func.max(HedgeFundFlowRunCycle.cycle_number)).filter_by(flow_run_id=self.run_id).scalar()
            snapshot = {
                key: data[key]
                for key in (
                    "date",
                    "cash",
                    "portfolio_value",
                    "long_exposure",
                    "short_exposure",
                    "gross_exposure",
                    "net_exposure",
                    "long_short_ratio",
                    "ticker_details",
                )
                if key in data
            }
            if portfolio is not None:
                snapshot.update(safe_payload(portfolio))
            session.add(
                HedgeFundFlowRunCycle(
                    flow_run_id=self.run_id,
                    cycle_number=(number or 0) + 1,
                    started_at=started_at or self.started_at,
                    completed_at=now,
                    status=status,
                    error_message=error,
                    analyst_signals=data.get("analyst_signals", {}),
                    trading_decisions=data.get("decisions", {}),
                    executed_trades=data.get("executed_trades", {}),
                    portfolio_snapshot=snapshot,
                    performance_metrics=data.get("performance_metrics", {}),
                    market_conditions={"date": data.get("date"), "current_prices": data.get("current_prices", {})},
                    trigger_reason="backtest" if run.trading_mode == "backtest" else "manual",
                )
            )
            session.commit()

    def finish(self, status, results=None, portfolio=None, error=None):
        if self.run_id is None:
            return
        with self.lock, self.sessions() as session:
            run = session.get(HedgeFundFlowRun, self.run_id)
            if run is None or run.status != "IN_PROGRESS":
                return
            run.status = status
            run.completed_at = datetime.utcnow()
            if results is not None:
                run.results = safe_payload(results)
            if portfolio is not None:
                run.final_portfolio = safe_payload(portfolio)
            run.error_message = error
            session.commit()


def recover_interrupted_runs(session_factory):
    """Close unfinished executions when this single-worker desktop backend restarts."""
    with session_factory() as session:
        count = (
            session.query(HedgeFundFlowRun)
            .filter_by(status="IN_PROGRESS")
            .update(
                {
                    HedgeFundFlowRun.status: "ERROR",
                    HedgeFundFlowRun.completed_at: datetime.utcnow(),
                    HedgeFundFlowRun.error_message: "Backend restarted before execution completed",
                },
                synchronize_session=False,
            )
        )
        session.commit()
        return count
