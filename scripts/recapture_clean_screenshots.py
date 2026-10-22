import asyncio
import base64
import json
import time
import urllib.request
import websockets

async def capture_all():
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

        # Check if dialog is open, if not click open
        print("Ensuring dialog is open...")
        await evaluate('''(() => {
            const dialog = document.querySelector('[role=\"dialog\"]');
            if (!dialog) {
                const btn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('投资综合研报'));
                if (btn) btn.click();
            }
        })()''')
        await asyncio.sleep(1.5)

        # 1. Top of dialog
        await evaluate('''(() => {
            const dialog = document.querySelector('[role=\"dialog\"]');
            if (dialog) dialog.scrollTop = 0;
        })()''')
        await asyncio.sleep(0.8)
        await capture_screenshot("/tmp/demo_screenshots/08_new_investment_report_top.png")

        # 2. Key Debates & Evidence Matrix
        await evaluate('''(() => {
            const dialog = document.querySelector('[role=\"dialog\"]');
            if (dialog) dialog.scrollTop = 550;
        })()''')
        await asyncio.sleep(0.8)
        await capture_screenshot("/tmp/demo_screenshots/09_new_investment_report_debates_matrix.png")

        # 3. Analyst Dossiers
        await evaluate('''(() => {
            const dialog = document.querySelector('[role=\"dialog\"]');
            if (dialog) dialog.scrollTop = 1600;
        })()''')
        await asyncio.sleep(0.8)
        await capture_screenshot("/tmp/demo_screenshots/10_new_analyst_dossiers.png")

        # 4. Expand Raw JSON and screenshot
        await evaluate('''(() => {
            const dialog = document.querySelector('[role=\"dialog\"]');
            if (dialog) {
                dialog.scrollTop = 2100;
                const rawBtn = Array.from(dialog.querySelectorAll('button')).find(b => b.innerText.includes('原始分析数据'));
                if (rawBtn) rawBtn.click();
            }
        })()''')
        await asyncio.sleep(1.0)
        await capture_screenshot("/tmp/demo_screenshots/11_raw_json_collapsed_verified.png")

asyncio.run(capture_all())
