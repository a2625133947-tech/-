import asyncio
import base64
import json
import time
import urllib.request
import websockets

def run_sse(ticker):
    print(f"\n==========================================")
    print(f"=== Starting Real SSE Execution for {ticker} ===")
    print(f"==========================================")
    
    req = urllib.request.urlopen("http://127.0.0.1:8000/flows/3")
    flow = json.loads(req.read().decode())
    nodes = flow["nodes"]
    edges = flow["edges"]

    payload = {
        "tickers": [ticker],
        "graph_nodes": nodes,
        "graph_edges": edges,
        "start_date": "2025-09-25",
        "end_date": "2026-09-25",
        "initial_cash": 100000.0,
        "model_name": "deepseek-chat",
        "model_provider": "DeepSeek"
    }

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
                    for line_item in part.splitlines():
                        if line_item.startswith("event:"):
                            event_type = line_item[len("event:"):].strip()
                        elif line_item.startswith("data:"):
                            event_data = json.loads(line_item[len("data:"):].strip())
                    
                    elapsed = time.time() - start_time
                    if event_type and event_data:
                        events.append({"elapsed": elapsed, "type": event_type, "data": event_data})
                        if event_type == "progress":
                            agent = event_data.get("agent")
                            st = event_data.get("status")
                            analysis = event_data.get("analysis")
                            print(f"[{elapsed:6.2f}s] [PROGRESS] Agent={agent:28s} Status={st}")
                            if analysis:
                                agent_outputs[agent] = analysis
                        elif event_type == "complete":
                            print(f"[{elapsed:6.2f}s] [COMPLETE] Run successfully finished!")
                            completed_event = event_data

    total_time = time.time() - start_time
    print(f"\nExecution finished in {total_time:.2f} seconds!")
    record = {
        "ticker": ticker,
        "total_duration_seconds": total_time,
        "payload": payload,
        "events": events,
        "agent_outputs": agent_outputs,
        "complete_result": completed_event
    }
    filename = f"docs/baselines/full_demo_run_{ticker}.json" if ticker == "600519" else f"docs/baselines/second_stock_run_{ticker}.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)
    print(f"Saved complete execution record to {filename}")
    return record


async def capture_browser_report(record):
    print("\nConnecting to Chrome to capture new Investment Report dialog...")
    tabs = json.loads(urllib.request.urlopen("http://127.0.0.1:9222/json").read().decode())
    target = [t for t in tabs if "5173" in t.get("url", "")][0]

    async with websockets.connect(target["webSocketDebuggerUrl"], max_size=50_000_000) as ws:
        async def evaluate(expr):
            req_id = int(time.time() * 1000) % 1000000
            await ws.send(json.dumps({
                "id": req_id,
                "method": "Runtime.evaluate",
                "params": {"expression": expr, "returnByValue": True, "awaitPromise": True}
            }))
            while True:
                msg = json.loads(await ws.recv())
                if msg.get("id") == req_id:
                    return msg.get("result", {}).get("result", {}).get("value")

        async def capture_screenshot(path):
            req_id = int(time.time() * 1000) % 1000000
            await ws.send(json.dumps({
                "id": req_id,
                "method": "Page.captureScreenshot",
                "params": {"format": "png"}
            }))
            while True:
                msg = json.loads(await ws.recv())
                if msg.get("id") == req_id:
                    data = msg["result"]["data"]
                    with open(path, "wb") as f:
                        f.write(base64.b64decode(data))
                    print(f"Saved screenshot: {path}")
                    break

        # Switch to Flow Tab
        await evaluate('''(() => {
            const tabDivs = Array.from(document.querySelectorAll('.group.relative.flex.items-center'));
            const targetTab = tabDivs.find(d => d.innerText.includes('贵州茅台'));
            if (targetTab) targetTab.click();
        })()''')
        await asyncio.sleep(1.0)

        # Trigger Run on Canvas so UI gets the live SSE connection & nodeContext update
        print("Triggering Play button on canvas to sync React NodeContext...")
        await evaluate('''(() => {
            const stockNode = Array.from(document.querySelectorAll('.react-flow__node')).find(n => n.innerText.includes('股票分析器') || n.innerText.includes('Stock Analyzer'));
            if (!stockNode) return 'no stock node';
            const btns = Array.from(stockNode.querySelectorAll('button'));
            if (btns[2]) btns[2].click();
        })()''')
        
        # Wait for full UI completion
        print("Waiting for UI execution to complete...")
        for _ in range(40):
            await asyncio.sleep(1.0)
            status = await evaluate('''(() => {
                const nodes = Array.from(document.querySelectorAll('.react-flow__node'));
                const pm = nodes.find(n => n.innerText.includes('投资组合经理') || n.innerText.includes('Portfolio Manager'));
                return pm ? pm.innerText : '';
            })()''')
            if '已完成' in status or 'Done' in status:
                print("UI execution reached COMPLETED state!")
                break

        await asyncio.sleep(2.0)

        # Click '投资综合研报'
        print("Clicking '投资综合研报' button...")
        await evaluate('''(() => {
            const reportBtn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('投资综合研报') || b.innerText.includes('Investment Report'));
            if (reportBtn) reportBtn.click();
        })()''')
        await asyncio.sleep(2.0)

        # Screenshot 1: Report Top & Thesis
        print("Capturing 08_new_investment_report_top.png...")
        await capture_screenshot("/tmp/demo_screenshots/08_new_investment_report_top.png")

        # Scroll dialog down to Key Debates & Evidence Matrix
        print("Scrolling dialog to Key Debates and Evidence Matrix...")
        await evaluate('''(() => {
            const dialog = document.querySelector('[role=\"dialog\"]');
            if (dialog) {
                dialog.scrollTop = 580;
            }
        })()''')
        await asyncio.sleep(1.0)
        print("Capturing 09_new_investment_report_debates_matrix.png...")
        await capture_screenshot("/tmp/demo_screenshots/09_new_investment_report_debates_matrix.png")

        # Scroll dialog down to Analyst Dossiers
        print("Scrolling dialog to Analyst Research section...")
        await evaluate('''(() => {
            const dialog = document.querySelector('[role=\"dialog\"]');
            if (dialog) {
                dialog.scrollTop = 1250;
            }
        })()''')
        await asyncio.sleep(1.0)
        print("Capturing 10_new_analyst_dossiers.png...")
        await capture_screenshot("/tmp/demo_screenshots/10_new_analyst_dossiers.png")

        # Click the first Raw JSON toggle to verify collapsible Machine Layer
        print("Expanding Raw Analysis JSON on first analyst card...")
        await evaluate('''(() => {
            const rawBtn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('原始分析数据'));
            if (rawBtn) rawBtn.click();
        })()''')
        await asyncio.sleep(1.0)
        print("Capturing 11_raw_json_collapsed_verified.png...")
        await capture_screenshot("/tmp/demo_screenshots/11_raw_json_collapsed_verified.png")

        print("All screenshots successfully captured!")


if __name__ == "__main__":
    # 1. Run 600519
    rec1 = run_sse("600519")
    asyncio.run(capture_browser_report(rec1))

    # 2. Run Second Stock: 000858 (Wuliangye)
    rec2 = run_sse("000858")
    print(f"\nBoth 600519 and 000858 real runs completed!")
