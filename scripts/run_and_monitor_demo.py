import asyncio
import base64
import json
import time
import urllib.request
import websockets

async def run_pipeline():
    resp = urllib.request.urlopen("http://localhost:9222/json")
    tabs = json.loads(resp.read().decode())
    target = [t for t in tabs if "5173" in t.get("url", "")][0]
    print(f"Connecting to tab: {target['title']} ({target['id']})")

    async with websockets.connect(target["webSocketDebuggerUrl"], max_size=50_000_000) as ws:
        async def evaluate(expr):
            await ws.send(json.dumps({
                "id": int(time.time() * 1000) % 1000000,
                "method": "Runtime.evaluate",
                "params": {"expression": expr, "returnByValue": True}
            }))
            res = json.loads(await ws.recv())
            return res.get("result", {}).get("result", {}).get("value")

        async def capture_screenshot(path):
            await ws.send(json.dumps({
                "id": int(time.time() * 1000) % 1000000,
                "method": "Page.captureScreenshot",
                "params": {"format": "png"}
            }))
            res = json.loads(await ws.recv())
            data = res["result"]["data"]
            with open(path, "wb") as f:
                f.write(base64.b64decode(data))
            print(f"Saved screenshot: {path}")

        # Enable Console & Runtime events
        await ws.send(json.dumps({"id": 101, "method": "Console.enable"}))
        await ws.recv()
        await ws.send(json.dumps({"id": 102, "method": "Runtime.enable"}))
        await ws.recv()

        # Check Stock Input Node and verify ticker is 600519
        check_res = await evaluate('''(() => {
            const stockNode = Array.from(document.querySelectorAll('.react-flow__node')).find(n => n.innerText.includes('股票分析器') || n.innerText.includes('Stock Analyzer'));
            if (!stockNode) return { status: 'no-stock-node' };
            const input = stockNode.querySelector('input');
            const btns = Array.from(stockNode.querySelectorAll('button'));
            return {
                status: 'ready',
                ticker: input ? input.value : null,
                buttonCount: btns.length
            };
        })()''')
        print("Stock Node Status before run:", check_res)

        # Trigger Run button (button 2 in stock node)
        print(">>> Triggering Run on Web Canvas...")
        start_time = time.time()
        click_run = await evaluate('''(() => {
            const stockNode = Array.from(document.querySelectorAll('.react-flow__node')).find(n => n.innerText.includes('股票分析器') || n.innerText.includes('Stock Analyzer'));
            if (!stockNode) return 'no stock node';
            const btns = Array.from(stockNode.querySelectorAll('button'));
            // Button 2 is the play button
            const playBtn = btns[2];
            if (playBtn) {
                playBtn.click();
                return 'play-btn-clicked';
            }
            return 'no-play-btn';
        })()''')
        print("Click result:", click_run)

        # Monitor loop
        running_screenshot_taken = False
        completed = False
        progress_events = []
        agent_timings = {}
        last_status_str = ""

        # Timeout 300s
        deadline = time.time() + 300

        while time.time() < deadline:
            await asyncio.sleep(1.0)
            now = time.time()

            # Poll node statuses from DOM
            status_data = await evaluate('''(() => {
                const nodes = Array.from(document.querySelectorAll('.react-flow__node'));
                const result = {};
                for (const node of nodes) {
                    const text = node.innerText;
                    // Extract name and status
                    let name = 'unknown';
                    if (text.includes('股票分析器')) name = 'Stock Input';
                    else if (text.includes('Fundamentals Analyst')) name = 'Fundamentals Analyst';
                    else if (text.includes('Valuation Analyst')) name = 'Valuation Analyst';
                    else if (text.includes('Technical Analyst')) name = 'Technical Analyst';
                    else if (text.includes('News Sentiment Analyst')) name = 'News Sentiment Analyst';
                    else if (text.includes('段永平')) name = '段永平';
                    else if (text.includes('冯柳')) name = '冯柳';
                    else if (text.includes('傅鹏博')) name = '傅鹏博';
                    else if (text.includes('投资组合经理') || text.includes('Portfolio Manager')) name = 'Portfolio Manager';
                    
                    let status = 'Unknown';
                    if (text.includes('进行中') || text.includes('Running') || text.includes('In Progress')) status = 'IN_PROGRESS';
                    else if (text.includes('已完成') || text.includes('Completed') || text.includes('Done')) status = 'COMPLETED';
                    else if (text.includes('空闲') || text.includes('Idle')) status = 'IDLE';
                    else if (text.includes('错误') || text.includes('Error')) status = 'ERROR';
                    
                    result[name] = status;
                }
                
                // Also check bottom panel output if any
                const bottomText = document.querySelector('#tour-bottom-panel') ? document.querySelector('#tour-bottom-panel').innerText : '';
                return { nodes: result, bottomSnippet: bottomText.substring(0, 150) };
            })()''')

            if not status_data:
                continue

            node_statuses = status_data.get("nodes", {})
            status_str = ", ".join([f"{k}: {v}" for k, v in node_statuses.items() if k != "unknown"])
            if status_str != last_status_str:
                elapsed = now - start_time
                print(f"[{elapsed:5.1f}s] Node Statuses: {status_str}")
                last_status_str = status_str

            # Record timings
            for name, st in node_statuses.items():
                if st == "IN_PROGRESS" and name not in agent_timings:
                    agent_timings[name] = {"start": now, "end": None, "duration": None, "status": "IN_PROGRESS"}
                elif st == "COMPLETED" and name in agent_timings and agent_timings[name]["end"] is None:
                    agent_timings[name]["end"] = now
                    agent_timings[name]["duration"] = round(now - agent_timings[name]["start"], 2)
                    agent_timings[name]["status"] = "COMPLETED"

            # Take running screenshot once some agents are in progress
            if not running_screenshot_taken:
                has_in_progress = any(st == "IN_PROGRESS" for st in node_statuses.values())
                if has_in_progress:
                    print(">>> Capturing running pipeline screenshot...")
                    await capture_screenshot("/tmp/demo_screenshots/03_running_pipeline.png")
                    running_screenshot_taken = True

            # Check if Portfolio Manager is completed
            pm_status = node_statuses.get("Portfolio Manager", "IDLE")
            if pm_status == "COMPLETED":
                # Check if all other agents are also completed or finished
                analyst_done = all(st == "COMPLETED" for k, st in node_statuses.items() if k not in ("Stock Input", "Portfolio Manager", "unknown"))
                if analyst_done:
                    print(f">>> All Agents & Portfolio Manager completed in {now - start_time:.1f}s!")
                    completed = True
                    break

        total_duration = time.time() - start_time
        print(f"Total Execution Time: {total_duration:.2f} seconds")

        # Save timings
        with open("/tmp/demo_screenshots/timings.json", "w", encoding="utf-8") as f:
            json.dump({"total_duration": total_duration, "agent_timings": agent_timings}, f, ensure_ascii=False, indent=2)

        await asyncio.sleep(2.0)

        # 1. Capture Agent Analysis Results (04_agent_analysis_results.png)
        print("Capturing completed workflow and Agent cards...")
        await capture_screenshot("/tmp/demo_screenshots/04_agent_analysis_results.png")

        # 2. Zoom in or open Portfolio Manager details
        print("Capturing Portfolio Manager Result (05_portfolio_manager_result.png)...")
        # Scroll or fit view to portfolio manager node
        await evaluate('''(() => {
            const pmNode = Array.from(document.querySelectorAll('.react-flow__node')).find(n => n.innerText.includes('投资组合经理') || n.innerText.includes('Portfolio Manager'));
            if (pmNode) {
                pmNode.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
        })()''')
        await asyncio.sleep(1.0)
        await capture_screenshot("/tmp/demo_screenshots/05_portfolio_manager_result.png")

        # 3. Open and capture bottom panel output (06_bottom_panel_output.png)
        print("Opening and capturing Bottom Panel Output...")
        await evaluate('''(() => {
            // Open bottom panel toggle if collapsed
            const bottomToggle = document.querySelector('#tour-sidebar-toggle-bottom');
            if (bottomToggle) bottomToggle.click();
        })()''')
        await asyncio.sleep(1.5)
        await capture_screenshot("/tmp/demo_screenshots/06_bottom_panel_output.png")

        # 4. Open Research Dashboard and capture (07_research_dashboard.png)
        print("Navigating to Research Dashboard and capturing...")
        await evaluate('''(() => {
            const researchBtn = document.querySelector('#tour-topbar-research');
            if (researchBtn) researchBtn.click();
        })()''')
        await asyncio.sleep(2.0)
        await capture_screenshot("/tmp/demo_screenshots/07_research_dashboard.png")

        print("All screenshots successfully captured!")

asyncio.run(run_pipeline())
