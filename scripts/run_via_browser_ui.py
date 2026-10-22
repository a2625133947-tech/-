import asyncio
import base64
import json
import time
import urllib.request
import websockets

async def run_ui():
    resp = urllib.request.urlopen("http://127.0.0.1:9222/json")
    tabs = json.loads(resp.read().decode())
    target = [t for t in tabs if "5173" in t.get("url", "")][0]
    print(f"Connecting to tab: {target['title']} ({target['id']})")

    async with websockets.connect(target["webSocketDebuggerUrl"], max_size=50_000_000) as ws:
        async def evaluate(expr):
            req_id = int(time.time() * 1000) % 1000000
            await ws.send(json.dumps({
                "id": req_id,
                "method": "Runtime.evaluate",
                "params": {"expression": expr, "returnByValue": True}
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

        # 1. Verify Stock Analyzer Node has 600519
        print("Checking Stock Analyzer input...")
        ticker_val = await evaluate('''(() => {
            const stockNode = Array.from(document.querySelectorAll('.react-flow__node')).find(n => n.innerText.includes('股票分析器') || n.innerText.includes('Stock Analyzer'));
            if (!stockNode) return 'no-node';
            const input = stockNode.querySelector('input');
            return input ? input.value : 'no-input';
        })()''')
        print(f"Current ticker: {ticker_val}")

        # 2. Trigger Play Button on Canvas
        print("Triggering Play button on Stock Analyzer Node...")
        click_res = await evaluate('''(() => {
            const stockNode = Array.from(document.querySelectorAll('.react-flow__node')).find(n => n.innerText.includes('股票分析器') || n.innerText.includes('Stock Analyzer'));
            if (!stockNode) return 'no-node';
            const btns = Array.from(stockNode.querySelectorAll('button'));
            const playBtn = btns[2];
            if (playBtn) {
                playBtn.click();
                return 'clicked';
            }
            return 'no-play-btn';
        })()''')
        print("Click result:", click_res)

        # 3. Wait 1.5s and take running pipeline screenshot
        await asyncio.sleep(1.5)
        print("Capturing 03_running_pipeline.png...")
        await capture_screenshot("/tmp/demo_screenshots/03_running_pipeline.png")

        # 4. Wait for execution to finish (about 12-15 seconds)
        print("Waiting for full workflow execution...")
        for i in range(25):
            await asyncio.sleep(1.0)
            status = await evaluate('''(() => {
                const nodes = Array.from(document.querySelectorAll('.react-flow__node'));
                const pm = nodes.find(n => n.innerText.includes('投资组合经理') || n.innerText.includes('Portfolio Manager'));
                return pm ? pm.innerText : '';
            })()''')
            if '已完成' in status or 'Done' in status or 'Completed' in status or 'hold' in status or 'Mixed' in status:
                print(f"Execution finished in UI at second {i+2.5}!")
                break

        await asyncio.sleep(2.0)

        # 5. Capture Workflow with finished Agent results
        print("Capturing 04_agent_analysis_results.png...")
        await capture_screenshot("/tmp/demo_screenshots/04_agent_analysis_results.png")

        # 6. Zoom in on Portfolio Manager Node and capture
        print("Focusing on Portfolio Manager...")
        await evaluate('''(() => {
            const pmNode = Array.from(document.querySelectorAll('.react-flow__node')).find(n => n.innerText.includes('投资组合经理') || n.innerText.includes('Portfolio Manager'));
            if (pmNode) {
                pmNode.scrollIntoView({ behavior: 'auto', block: 'center', inline: 'center' });
            }
        })()''')
        await asyncio.sleep(1.0)
        await capture_screenshot("/tmp/demo_screenshots/05_portfolio_manager_result.png")

        # 7. Open and capture Bottom Panel Output
        print("Opening Bottom Panel Output...")
        await evaluate('''(() => {
            const bottomToggle = document.querySelector('#tour-sidebar-toggle-bottom');
            if (bottomToggle) bottomToggle.click();
        })()''')
        await asyncio.sleep(1.5)
        await capture_screenshot("/tmp/demo_screenshots/06_bottom_panel_output.png")

        # 8. Open Research Dashboard and capture
        print("Opening Research Dashboard...")
        await evaluate('''(() => {
            const researchBtn = document.querySelector('#tour-topbar-research');
            if (researchBtn) researchBtn.click();
        })()''')
        await asyncio.sleep(2.0)
        await capture_screenshot("/tmp/demo_screenshots/07_research_dashboard.png")

        print("All UI demo operations completed!")

asyncio.run(run_ui())
