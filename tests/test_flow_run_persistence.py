"""Offline SSE-to-SQLite integration coverage; never uses the application DB."""

import asyncio
import copy
import json
from datetime import datetime
from types import SimpleNamespace

import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker

from app.backend.database import get_db
from app.backend.database.models import Base, HedgeFundFlow, HedgeFundFlowRun, HedgeFundFlowRunCycle
from app.backend.models.schemas import HedgeFundRequest
from app.backend.routes import flow_runs, flows, hedge_fund
from app.backend.services import backtest_service
from app.backend.services.flow_run_recorder import recover_interrupted_runs


@pytest.fixture
def persisted_api(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'flow-history.sqlite3'}", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    with sessions() as db:
        db.add_all([HedgeFundFlow(name="Test flow", nodes=[], edges=[]), HedgeFundFlow(name="Other flow", nodes=[], edges=[])])
        db.commit()
        ids = db.scalars(select(HedgeFundFlow.id).order_by(HedgeFundFlow.id)).all()

    app = FastAPI()
    app.include_router(hedge_fund.router)
    app.include_router(flow_runs.router)
    app.include_router(flows.router)

    def isolated_db():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = isolated_db
    monkeypatch.setattr(hedge_fund, "create_graph", lambda **_kwargs: SimpleNamespace(compile=lambda: object()))
    # Every test supplies a fake model and credentials. No providers are invoked.
    with TestClient(app) as client:
        yield SimpleNamespace(client=client, sessions=sessions, flow_id=ids[0], other_flow_id=ids[1])
    engine.dispose()


def payload(flow_id=None):
    data = {
        "tickers": ["600519"],
        "graph_nodes": [{"id": "portfolio_manager", "data": {"api_keys": {"OPENAI_API_KEY": "nested-test-secret"}, "label": "Keep this label"}}],
        "graph_edges": [],
        "model_name": "offline-test-model",
        "model_provider": "OpenAI",
        "api_keys": {"OPENAI_API_KEY": "request-test-secret"},
        "start_date": "2026-09-01",
        "end_date": "2026-09-03",
        "initial_cash": 100000,
    }
    if flow_id is not None:
        data["flow_id"] = flow_id
    return data


def events(response):
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/event-stream")
    return [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")]


def graph_result():
    return {
        "messages": [SimpleNamespace(content=json.dumps({"600519": {"action": "hold", "quantity": 0}}))],
        "data": {
            "analyst_signals": {"test_agent": {"600519": {"signal": "neutral", "confidence": 65}}},
            "current_prices": {"600519": 1500.0},
            "research_contexts": {"600519": {"summary": "Offline fixture"}},
        },
    }


def latest_run(api):
    with api.sessions() as db:
        run = db.scalars(select(HedgeFundFlowRun).order_by(HedgeFundFlowRun.id.desc())).first()
        db.expunge_all()
        return run


def stored_cycles(api, run_id):
    with api.sessions() as db:
        cycles = db.scalars(select(HedgeFundFlowRunCycle).where(HedgeFundFlowRunCycle.flow_run_id == run_id).order_by(HedgeFundFlowRunCycle.cycle_number)).all()
        db.expunge_all()
        return cycles


def test_analysis_stream_persists_result_and_sanitized_configuration(persisted_api, monkeypatch):
    result = graph_result()

    async def fake_graph(**kwargs):
        # The runtime still receives the key; only the historical copy is redacted.
        assert kwargs["request"].api_keys["OPENAI_API_KEY"] == "request-test-secret"
        return result

    monkeypatch.setattr(hedge_fund, "run_graph_async", fake_graph)
    received = events(persisted_api.client.post("/hedge-fund/run", json=payload(persisted_api.flow_id)))
    assert received[0]["type"] == "start"
    assert received[-1]["type"] == "complete"
    run = latest_run(persisted_api)
    assert received[0]["run_id"] == run.id
    assert run.flow_id == persisted_api.flow_id
    assert run.status == "COMPLETE"
    assert run.started_at is not None and run.completed_at is not None
    assert run.initial_portfolio["cash"] == 100000
    assert run.final_portfolio["cash"] == 100000
    assert run.results["decisions"] == {"600519": {"action": "hold", "quantity": 0}}
    for field in ("analyst_signals", "current_prices", "research_contexts"):
        assert run.results[field] == result["data"][field]
    saved_config = json.dumps(run.request_data)
    assert "request-test-secret" not in saved_config
    assert "nested-test-secret" not in saved_config
    assert "Keep this label" in saved_config
    assert "api_keys" not in run.request_data
    cycles = stored_cycles(persisted_api, run.id)
    assert len(cycles) == 1
    assert cycles[0].status == "COMPLETED"
    assert cycles[0].cycle_number == 1
    assert cycles[0].analyst_signals == result["data"]["analyst_signals"]
    assert cycles[0].trading_decisions == run.results["decisions"]
    assert cycles[0].market_conditions["date"] == "2026-09-03"
    assert cycles[0].market_conditions["current_prices"] == {"600519": 1500.0}


@pytest.mark.parametrize("failure", ["exception", "empty-messages", "invalid-json"])
def test_analysis_failures_emit_error_and_finish_history(persisted_api, monkeypatch, failure):
    async def fake_graph(**_kwargs):
        if failure == "exception":
            raise RuntimeError("offline graph failure")
        if failure == "invalid-json":
            return {"messages": [SimpleNamespace(content="not a JSON decision")], "data": {}}
        return {"messages": [], "data": {}}

    monkeypatch.setattr(hedge_fund, "run_graph_async", fake_graph)
    received = events(persisted_api.client.post("/hedge-fund/run", json=payload(persisted_api.flow_id)))
    assert received[-1]["type"] == "error"
    assert all(item["type"] != "complete" for item in received)
    run = latest_run(persisted_api)
    assert run.status == "ERROR"
    assert run.completed_at is not None
    assert run.error_message
    assert stored_cycles(persisted_api, run.id) == []


def day_result(date, cash):
    return {
        "date": date,
        "portfolio_value": cash + 15000,
        "cash": cash,
        "decisions": {"600519": {"action": "buy", "quantity": 10}},
        "executed_trades": {"600519": 10},
        "analyst_signals": {"test_agent": {"600519": {"signal": "bullish"}}},
        "current_prices": {"600519": 1500.0},
        "long_exposure": 15000.0,
        "short_exposure": 0.0,
        "gross_exposure": 15000.0,
        "net_exposure": 15000.0,
        "long_short_ratio": None,
        "portfolio_return": (cash + 15000) / 100000 - 1,
        "performance_metrics": {"sharpe_ratio": 0.0, "max_drawdown": 0.0},
    }


def test_backtest_persists_each_date_and_final_portfolio(persisted_api, monkeypatch):
    days = [day_result("2026-09-01", 85000), day_result("2026-09-02", 86000)]
    final = {"cash": 86000, "positions": {"600519": {"long": 10, "short": 0}}}

    class FakeBacktestService:
        def __init__(self, **kwargs):
            self.portfolio = kwargs["portfolio"]

        async def run_backtest_async(self, progress_callback):
            for day in days:
                self.portfolio["cash"] = day["cash"]
                progress_callback({"type": "backtest_result", "data": copy.deepcopy(day)})
                await asyncio.sleep(0)
            return {"results": days, "performance_metrics": {"sharpe_ratio": 1.25, "max_drawdown": 0.0}, "final_portfolio": final}

    monkeypatch.setattr(hedge_fund, "BacktestService", FakeBacktestService)
    request = payload(persisted_api.flow_id)
    request["initial_capital"] = request.pop("initial_cash")
    received = events(persisted_api.client.post("/hedge-fund/backtest", json=request))
    assert received[-1]["type"] == "complete"
    run = latest_run(persisted_api)
    assert run.status == "COMPLETE"
    assert run.initial_portfolio["cash"] == 100000  # Must not alias the mutated portfolio.
    assert run.final_portfolio == final
    assert run.results["results"] == days
    assert run.results["performance_metrics"]["sharpe_ratio"] == 1.25
    cycles = stored_cycles(persisted_api, run.id)
    assert [cycle.cycle_number for cycle in cycles] == [1, 2]
    for cycle, day in zip(cycles, days):
        assert cycle.status == "COMPLETED"
        assert cycle.market_conditions["date"] == day["date"]
        assert cycle.market_conditions["current_prices"] == day["current_prices"]
        assert cycle.analyst_signals == day["analyst_signals"]
        assert cycle.trading_decisions == day["decisions"]
        assert cycle.executed_trades == day["executed_trades"]
        assert cycle.performance_metrics == day["performance_metrics"]
        for field in ("date", "cash", "portfolio_value", "long_exposure", "short_exposure", "gross_exposure", "net_exposure"):
            assert cycle.portfolio_snapshot[field] == day[field]

    cycle_response = persisted_api.client.get(f"/flows/{run.flow_id}/runs/{run.id}/cycles")
    assert cycle_response.status_code == 200
    assert [cycle["cycle_number"] for cycle in cycle_response.json()] == [1, 2]
    assert persisted_api.client.get(f"/flows/{persisted_api.other_flow_id}/runs/{run.id}/cycles").status_code == 404
    deleted = persisted_api.client.delete(f"/flows/{run.flow_id}/runs/{run.id}")
    assert deleted.status_code in (200, 204)
    assert latest_run(persisted_api) is None
    assert stored_cycles(persisted_api, run.id) == []


@pytest.mark.parametrize("failure", ["exception", "empty-result"])
def test_backtest_failure_keeps_completed_days_and_marks_error(persisted_api, monkeypatch, failure):
    day = day_result("2026-09-01", 85000)

    class FailingBacktestService:
        def __init__(self, **kwargs):
            self.portfolio = kwargs["portfolio"]

        async def run_backtest_async(self, progress_callback):
            self.portfolio["cash"] = day["cash"]
            progress_callback({"type": "backtest_result", "data": day})
            if failure == "exception":
                raise RuntimeError("offline backtest failure")
            return None

    monkeypatch.setattr(hedge_fund, "BacktestService", FailingBacktestService)
    request = payload(persisted_api.flow_id)
    request["initial_capital"] = request.pop("initial_cash")
    received = events(persisted_api.client.post("/hedge-fund/backtest", json=request))
    assert received[-1]["type"] == "error"
    run = latest_run(persisted_api)
    assert run.status == "ERROR"
    assert run.completed_at is not None
    assert run.error_message
    assert run.final_portfolio["cash"] == day["cash"]
    cycles = stored_cycles(persisted_api, run.id)
    assert len(cycles) == 1
    assert cycles[0].status == "COMPLETED"
    assert cycles[0].market_conditions["date"] == day["date"]


def test_graph_setup_failure_is_recorded(persisted_api, monkeypatch):
    def invalid_graph(**_kwargs):
        raise ValueError("offline graph setup failure")

    monkeypatch.setattr(hedge_fund, "create_graph", invalid_graph)
    response = persisted_api.client.post("/hedge-fund/run", json=payload(persisted_api.flow_id))
    assert response.status_code == 500
    run = latest_run(persisted_api)
    assert run.status == "ERROR"
    assert run.started_at is not None and run.completed_at is not None
    assert run.error_message


@pytest.mark.parametrize("failure", ["exception", "empty-messages", "invalid-json"])
def test_real_backtest_graph_failures_stop_execution_and_persist_error_cycle(persisted_api, monkeypatch, failure):
    # Exercise the real service through the SSE route; only its input providers
    # and graph are replaced. A failed graph must never become a HOLD decision.
    monkeypatch.setattr(backtest_service.BacktestService, "prefetch_data", lambda _self: None)
    monkeypatch.setattr(backtest_service, "get_price_data", lambda *_args: pd.DataFrame({"close": [1500.0]}))

    def unexpected_trade(*_args, **_kwargs):
        pytest.fail("A failed analysis must not execute trades or silently hold")

    monkeypatch.setattr(backtest_service.BacktestService, "execute_trade", unexpected_trade)

    async def failing_graph(**_kwargs):
        if failure == "exception":
            raise RuntimeError("provider-key-secret-must-not-be-saved")
        if failure == "invalid-json":
            return {"messages": [SimpleNamespace(content="not a JSON decision")], "data": {}}
        return {"messages": [], "data": {}}

    monkeypatch.setattr(backtest_service, "run_graph_async", failing_graph)
    request = payload(persisted_api.flow_id)
    request["initial_capital"] = request.pop("initial_cash")
    received = events(persisted_api.client.post("/hedge-fund/backtest", json=request))
    assert received[-1]["type"] == "error"
    assert all(item["type"] != "complete" for item in received)
    run = latest_run(persisted_api)
    assert run.status == "ERROR"
    assert run.final_portfolio["cash"] == 100000
    assert run.completed_at is not None
    cycles = stored_cycles(persisted_api, run.id)
    assert len(cycles) == 1
    assert cycles[0].status == "ERROR"
    assert cycles[0].error_message.startswith("Backtest analysis failed:")
    assert cycles[0].market_conditions == {"date": "2026-09-01", "current_prices": {"600519": 1500.0}}
    assert cycles[0].executed_trades == {}
    assert "provider-key-secret" not in json.dumps(received)
    assert "provider-key-secret" not in run.error_message
    assert "provider-key-secret" not in cycles[0].error_message


def seed_history(api, flow_id=None, statuses=("COMPLETE", "COMPLETE")):
    when = datetime(2026, 9, 1, 12, 0)
    run_ids = []
    with api.sessions() as db:
        for number, status in enumerate(statuses, 1):
            run = HedgeFundFlowRun(
                flow_id=flow_id or api.flow_id, status=status, run_number=number,
                created_at=when, started_at=when,
                completed_at=when if status in ("COMPLETE", "CANCELLED") else None,
                error_message="Original terminal status" if status == "CANCELLED" else None,
            )
            db.add(run)
            db.flush()
            db.add(HedgeFundFlowRunCycle(flow_run_id=run.id, cycle_number=1, started_at=when, completed_at=when, status="COMPLETED"))
            run_ids.append(run.id)
        db.commit()
    return run_ids


def test_same_timestamp_latest_run_and_count_route(persisted_api):
    ids = seed_history(persisted_api)
    latest = persisted_api.client.get(f"/flows/{persisted_api.flow_id}/runs/latest")
    assert latest.status_code == 200
    assert latest.json()["id"] == ids[-1]
    count = persisted_api.client.get(f"/flows/{persisted_api.flow_id}/runs/count")
    assert count.status_code == 200
    assert count.json() == {"flow_id": persisted_api.flow_id, "total_runs": 2}


@pytest.mark.parametrize("delete_flow", [False, True], ids=["bulk-runs", "flow-and-runs"])
def test_deleting_all_history_cleans_cycles_with_foreign_keys(persisted_api, delete_flow):
    ids = seed_history(persisted_api)
    other_ids = seed_history(persisted_api, flow_id=persisted_api.other_flow_id, statuses=("COMPLETE",))
    path = f"/flows/{persisted_api.flow_id}"
    if not delete_flow:
        path += "/runs/"
    response = persisted_api.client.delete(path)
    assert response.status_code in (200, 204), response.text
    with persisted_api.sessions() as db:
        assert db.scalars(select(HedgeFundFlowRun).where(HedgeFundFlowRun.flow_id == persisted_api.flow_id)).all() == []
        assert db.scalars(select(HedgeFundFlowRunCycle).where(HedgeFundFlowRunCycle.flow_run_id.in_(ids))).all() == []
        assert (db.get(HedgeFundFlow, persisted_api.flow_id) is None) == delete_flow
        assert db.get(HedgeFundFlowRun, other_ids[0]) is not None
        assert db.scalar(select(HedgeFundFlowRunCycle).where(HedgeFundFlowRunCycle.flow_run_id == other_ids[0])) is not None


def test_backend_restart_recovers_only_unfinished_runs(persisted_api):
    ids = seed_history(persisted_api, statuses=("IN_PROGRESS", "COMPLETE", "CANCELLED"))
    assert recover_interrupted_runs(persisted_api.sessions) == 1
    assert recover_interrupted_runs(persisted_api.sessions) == 0
    with persisted_api.sessions() as db:
        interrupted, complete, cancelled = [db.get(HedgeFundFlowRun, run_id) for run_id in ids]
        assert interrupted.status == "ERROR"
        assert interrupted.completed_at is not None
        assert "restarted" in interrupted.error_message
        assert complete.status == "COMPLETE"
        assert complete.completed_at == datetime(2026, 9, 1, 12, 0)
        assert complete.error_message is None
        assert cancelled.status == "CANCELLED"
        assert cancelled.completed_at == datetime(2026, 9, 1, 12, 0)
        assert cancelled.error_message == "Original terminal status"


@pytest.mark.parametrize("endpoint", ["run", "backtest"])
def test_invalid_flow_rejected_before_execution(persisted_api, monkeypatch, endpoint):
    def unexpected_graph(**_kwargs):
        pytest.fail("Invalid flow must be rejected before constructing the graph")

    monkeypatch.setattr(hedge_fund, "create_graph", unexpected_graph)
    response = persisted_api.client.post(f"/hedge-fund/{endpoint}", json=payload(99999))
    assert response.status_code == 404
    assert latest_run(persisted_api) is None


@pytest.mark.parametrize("flow_id", [0, -1])
def test_nonpositive_flow_id_rejected(persisted_api, flow_id):
    response = persisted_api.client.post("/hedge-fund/run", json=payload(flow_id))
    assert response.status_code == 422
    assert latest_run(persisted_api) is None


def test_request_without_flow_remains_compatible(persisted_api, monkeypatch):
    async def fake_graph(**_kwargs):
        return graph_result()

    monkeypatch.setattr(hedge_fund, "run_graph_async", fake_graph)
    received = events(persisted_api.client.post("/hedge-fund/run", json=payload()))
    assert received[-1]["type"] == "complete"
    assert latest_run(persisted_api) is None


@pytest.mark.parametrize("disconnect", [False, True], ids=["generator-close", "client-disconnect"])
def test_stopping_analysis_stream_cancels_and_finishes_run(persisted_api, monkeypatch, disconnect):
    cancelled = []

    async def blocked_graph(**_kwargs):
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.append(True)

    class ConnectedRequest:
        async def receive(self):
            if disconnect:
                return {"type": "http.disconnect"}
            await asyncio.Event().wait()

    monkeypatch.setattr(hedge_fund, "run_graph_async", blocked_graph)

    async def close_stream():
        with persisted_api.sessions() as db:
            response = await hedge_fund.run(HedgeFundRequest(**payload(persisted_api.flow_id)), ConnectedRequest(), db)
            assert "event: start" in await anext(response.body_iterator)
            await asyncio.sleep(0)  # Let graph enter its cancellation-protected work.
            if disconnect:
                with pytest.raises(StopAsyncIteration):
                    await asyncio.wait_for(anext(response.body_iterator), timeout=3)
            else:
                await response.body_iterator.aclose()

    asyncio.run(close_stream())
    assert cancelled == [True]
    run = latest_run(persisted_api)
    assert run.status == "CANCELLED"
    assert run.completed_at is not None
    assert stored_cycles(persisted_api, run.id) == []
