"""Exercise the existing website's live API graph with cached, authorized research.

Uses the existing fundamental -> risk -> Portfolio path and real configured data/model
providers. Does not modify saved flows or submit trades. Only the already approved
600519 September report context is reused; new report discovery is disabled.
"""
import json
import time
from pathlib import Path

import httpx

root = Path(__file__).resolve().parents[1]
base = "http://127.0.0.1:8000"
with httpx.Client(timeout=180) as client:
    flow_response = client.get(f"{base}/flows/3")
    flow_response.raise_for_status()
    flow = flow_response.json()
    ids = {"stock-analyzer-node_demo01", "fundamentals_analyst_demo02", "portfolio_manager_demo09"}
    nodes = [n for n in flow["nodes"] if n["id"] in ids]
    assert len(nodes) == 3
    edges = [e for e in flow["edges"] if e["source"] in ids and e["target"] in ids]
    payload = {"tickers": ["600519"], "graph_nodes": nodes, "graph_edges": edges,
               "start_date": "2026-09-01", "end_date": "2026-09-30", "initial_cash": 100000,
               "include_research": False, "model_name": "deepseek-chat", "model_provider": "DeepSeek"}
    started = time.monotonic()
    stages, result, errors, event = [], None, [], None
    with client.stream("POST", f"{base}/hedge-fund/run", json=payload) as response:
        response.raise_for_status()
        for line in response.iter_lines():
            if line.startswith("event:"):
                event = line[6:].strip()
            elif line.startswith("data:"):
                data = json.loads(line[5:].strip())
                if event == "progress":
                    stage = {k: data.get(k) for k in ("agent", "ticker", "status")}
                    stages.append(stage)
                    print(json.dumps(stage, ensure_ascii=False), flush=True)
                elif event == "complete":
                    result = data.get("data", data)
                elif event == "error":
                    errors.append(data)
    verification = {"graph_completed": result is not None, "errors": errors}
    if result:
        decision = result["decisions"]["600519"]
        research = decision.get("research_opinions", {})
        context = result.get("research_contexts", {}).get("600519", {})
        verification.update({"report_count": context.get("report_count"),
                             "research_citations": len(research.get("citations", [])),
                             "information_provenance": decision.get("information_provenance"),
                             "current_price": result.get("current_prices", {}).get("600519"),
                             "action": decision["action"],
                             "market_data_status": "available" if result.get("current_prices", {}).get("600519", 0) > 0 else "insufficient",
                             "portfolio_model_path": "eligible" if result.get("current_prices", {}).get("600519", 0) > 0 else "deterministic no-price hold",
                             "data_quality": decision.get("data_quality")})
        assert context.get("report_count") == 1
        assert research.get("citations") and research["provenance"] == "broker_research_opinions"
        assert set(decision["information_provenance"]) == {"financial_data", "research_opinions", "ai_analysis"}
    output = {"scope": "live original website API graph, real data/model providers; cached authorized 600519 report only",
              "elapsed_seconds": round(time.monotonic() - started, 3), "stages": stages,
              "verification": verification, "result": result}
    target = root / "docs/baselines/research_intelligence_downstream_live.json"
    target.write_text(json.dumps(output, ensure_ascii=False, indent=2))
    print(json.dumps({"output": str(target), **verification}, ensure_ascii=False))
    assert result is not None, "original graph did not return a complete event"
