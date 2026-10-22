import asyncio
import base64
import json
import time
import urllib.request
import websockets

async def capture_details():
    resp = urllib.request.urlopen("http://127.0.0.1:9222/json")
    tabs = json.loads(resp.read().decode())
    target = [t for t in tabs if "5173" in t.get("url", "")][0]

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

        # 1. Close bottom panel to see research dashboard clearly
        await evaluate('''(() => {
            const closeBtn = document.querySelector('#tour-bottom-panel button') || Array.from(document.querySelectorAll('button')).find(b => b.querySelector('svg.lucide-x'));
            if (closeBtn) closeBtn.click();
        })()''')
        await asyncio.sleep(2.0)
        print("Capturing loaded Research Dashboard...")
        await capture_screenshot("/tmp/demo_screenshots/07_research_dashboard_loaded.png")

        # 2. Switch back to Flow 3 tab
        print("Switching back to Flow Tab...")
        await evaluate('''(() => {
            const tabDivs = Array.from(document.querySelectorAll('.group.relative.flex.items-center'));
            const flowTab = tabDivs.find(d => d.innerText.includes('贵州茅台'));
            if (flowTab) flowTab.click();
        })()''')
        await asyncio.sleep(1.5)

        # 3. Click '投资综合研报' button on Portfolio Manager Node
        print("Clicking '投资综合研报' button...")
        click_report = await evaluate('''(() => {
            const reportBtn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('投资综合研报') || b.innerText.includes('Investment Report'));
            if (reportBtn) {
                reportBtn.click();
                return 'report-btn-clicked';
            }
            return 'report-btn-not-found';
        })()''')
        print("Report button click result:", click_report)
        await asyncio.sleep(1.5)

        # 4. Capture Investment Report Modal / Dialog
        print("Capturing Investment Report Dialog...")
        await capture_screenshot("/tmp/demo_screenshots/08_investment_report_dialog.png")

asyncio.run(capture_details())
