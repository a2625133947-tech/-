"""Unit and integration tests for backend research API endpoints."""

from fastapi.testclient import TestClient
import pytest

from app.backend.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_get_stock_overview(client):
    response = client.get("/api/research/stocks/600519")
    assert response.status_code == 200
    data = response.json()

    assert data["ticker"] == "600519"
    assert "贵州茅台" in data["stock_name"] or "600519" in data["stock_name"]
    assert data["production_decision"]["mode"] == "LEGACY"
    assert "LEGACY" in data["research_mode_banner"]

    cards = data["investor_cards"]
    assert len(cards) == 10
    profile_ids = [c["profile_id"] for c in cards]
    assert "zhang_kun" in profile_ids
    assert "feng_liu" in profile_ids
    assert "fu_pengbo" in profile_ids
    assert "duan_yongping" in profile_ids

    # Check NOT_READY cards
    not_ready = data["not_ready_cards"]
    assert len(not_ready) == 2
    nr_ids = [c["profile_id"] for c in not_ready]
    assert "wang_yawei" in nr_ids
    assert "lin_yuan" in nr_ids
    for card in not_ready:
        assert card["status"] == "NOT_READY"
        assert card["not_ready_reason"] is not None


def test_invalid_ticker_returns_400(client):
    response = client.get("/api/research/stocks/INVALID")
    assert response.status_code == 400
    assert "无效" in response.json()["detail"]


def test_get_investor_detail_feng_liu(client):
    response = client.get("/api/research/stocks/600519/investors/feng_liu")
    assert response.status_code == 200
    data = response.json()

    assert data["profile_id"] == "feng_liu"
    assert data["display_name"] == "冯柳"
    assert data["profile_version"] == "v1"
    assert data["status"] == "READY"

    # Factor contributions
    factors = data["factor_contributions"]
    assert len(factors) > 0
    roles = {f["role"] for f in factors}
    assert "core" in roles
    proxy_factor = next((f for f in factors if f["factor_id"] == "low_expectation_proxy"), None)
    assert proxy_factor is not None
    assert proxy_factor["display_name"] == "低预期代理"

    # Signal explanation
    exp = data["signal_explanation"]
    assert exp is not None
    assert exp["policy_style"] == "proxy_plus_improvement"
    assert exp["gate_id"] == "low_expectation_proxy_and_operating_improvement"
    assert len(exp["gate_checks"]) > 0

    # Confidence breakdown
    conf = data["confidence_breakdown"]
    assert conf is not None
    assert "不代表上涨概率或胜率" in conf["notice"]

    # Known missing dimensions
    dims = data["known_missing_dimensions"]
    assert len(dims) > 0
    assert "真实市场预期" in dims

    # Legacy comparison
    leg = data["legacy_comparison"]
    assert leg is not None
    assert leg["legacy_signal"] in ("bullish", "neutral", "bearish")


def test_not_ready_investor_returns_not_ready_status(client):
    response = client.get("/api/research/stocks/600519/investors/wang_yawei")
    assert response.status_code == 200
    data = response.json()

    assert data["profile_id"] == "wang_yawei"
    assert data["display_name"] == "王亚伟"
    assert data["status"] == "NOT_READY"
    assert "重组" in data["not_ready_reason"]
    assert data["factor_contributions"] == []


def test_unknown_profile_returns_404(client):
    response = client.get("/api/research/stocks/600519/investors/unknown_investor")
    assert response.status_code == 404


def test_corpus_summary(client):
    response = client.get("/api/research/corpus/summary")
    assert response.status_code == 200
    data = response.json()

    assert "snapshot_count" in data
    assert "ticker_count" in data
    assert "signal_distribution" in data
    assert "confidence_distribution" in data
    assert data["health_status"] in ("Healthy", "Warnings Detected", "Empty Corpus")


def test_lin_yuan_not_ready_status(client):
    response = client.get("/api/research/stocks/600519/investors/lin_yuan")
    assert response.status_code == 200
    data = response.json()
    assert data["profile_id"] == "lin_yuan"
    assert data["display_name"] == "林园"
    assert data["status"] == "NOT_READY"
    assert "垄断" in data["not_ready_reason"]
    assert data["factor_contributions"] == []


def test_shadow_alias_endpoint(client):
    response = client.get("/api/research/shadow/600519/zhang_kun")
    assert response.status_code == 200
    data = response.json()
    assert data["profile_id"] == "zhang_kun"
    assert data["display_name"] == "张坤"
    assert data["profile_version"] == "v2"
    assert data["status"] == "READY"
    assert len(data["factor_contributions"]) > 0


def test_stock_overview_with_explicit_as_of(client):
    response = client.get("/api/research/stocks/600519?as_of=2026-09-27")
    assert response.status_code == 200
    data = response.json()
    assert data["ticker"] == "600519"
    assert "2026-09-27" in data["as_of"]


def test_corpus_snapshots_filter_by_ticker(client):
    response = client.get("/api/research/corpus/snapshots?ticker=000001&limit=5")
    assert response.status_code == 200
    snapshots = response.json()
    for s in snapshots:
        assert s["ticker"] == "000001"
