import json
import time
import urllib.request

def run_sse_workflow():
    # 1. Fetch Flow 3 configuration from DB/API
    req = urllib.request.urlopen("http://127.0.0.1:8000/flows/3")
    flow = json.loads(req.read().decode())
    nodes = flow["nodes"]
    edges = flow["edges"]

    payload = {
        "tickers": ["600519"],
        "graph_nodes": nodes,
        "graph_edges": edges,
        "start_date": "2025-09-25",
        "end_date": "2026-09-25",
        "initial_cash": 100000.0,
        "model_name": "deepseek-chat",
        "model_provider": "DeepSeek"
    }

    print("=== Submitting Hedge Fund Run Request ===")
    print(f"Ticker: 600519, Nodes: {len(nodes)}, Edges: {len(edges)}")
    print(f"Date range: 2025-09-25 to 2026-09-25, Model: DeepSeek V3 (deepseek-chat)")
    
    post_data = json.dumps(payload).encode("utf-8")
    run_req = urllib.request.Request(
        "http://127.0.0.1:8000/hedge-fund/run",
        data=post_data,
        headers={"Content-Type": "application/json", "Accept": "text/event-stream"},
        method="POST"
    )

    start_time = time.time()
    events = []
    agent_outputs = {}
    completed_event = None

    with urllib.request.urlopen(run_req, timeout=600) as response:
        print("Connected to SSE stream! Receiving real-time updates...\n")
        buffer = ""
        for raw_line in response:
            line = raw_line.decode("utf-8")
            buffer += line
            if "\n\n" in buffer:
                parts = buffer.split("\n\n")
                buffer = parts.pop()
                for part in parts:
                    if not part.strip():
                        continue
                    event_type = None
                    event_data = None
                    for line in part.splitlines():
                        if line.startswith("event:"):
                            event_type = line[len("event:"):].strip()
                        elif line.startswith("data:"):
                            event_data = json.loads(line[len("data:"):].strip())
                    
                    elapsed = time.time() - start_time
                    if event_type and event_data:
                        events.append({"elapsed": elapsed, "type": event_type, "data": event_data})
                        if event_type == "start":
                            print(f"[{elapsed:6.2f}s] [START] {event_data.get('message')}")
                        elif event_type == "progress":
                            agent = event_data.get("agent")
                            ticker = event_data.get("ticker")
                            status = event_data.get("status")
                            analysis = event_data.get("analysis")
                            print(f"[{elapsed:6.2f}s] [PROGRESS] Agent={agent:28s} Ticker={ticker or '-':8s} Status={status}")
                            if analysis:
                                agent_outputs[agent] = analysis
                                print(f"         >>> Analysis snippet: {str(analysis)[:120]}...")
                        elif event_type == "complete":
                            print(f"[{elapsed:6.2f}s] [COMPLETE] Run successfully finished!")
                            completed_event = event_data
                        elif event_type == "error":
                            print(f"[{elapsed:6.2f}s] [ERROR] {event_data}")

    total_time = time.time() - start_time
    print(f"\n==========================================")
    print(f"Execution Finished in {total_time:.2f} seconds!")
    print(f"Total Progress Events: {len([e for e in events if e['type'] == 'progress'])}")
    print(f"Unique Agent Outputs: {len(agent_outputs)}")

    # Save complete run result to file
    final_record = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_duration_seconds": total_time,
        "payload": payload,
        "events": events,
        "agent_outputs": agent_outputs,
        "complete_result": completed_event
    }
    with open("docs/baselines/full_demo_run_600519.json", "w", encoding="utf-8") as f:
        json.dump(final_record, f, ensure_ascii=False, indent=2)
    print("Saved complete execution record to docs/baselines/full_demo_run_600519.json")

if __name__ == "__main__":
    run_sse_workflow()
