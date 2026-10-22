import asyncio
import base64
import json
import time
import urllib.request
import websockets

async def expand_report():
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

        print("Clicking expand on 600519 analyst details...")
        click_res = await evaluate('''(() => {
            const accordion = Array.from(document.querySelectorAll('div, button')).find(el => el.innerText && el.innerText.includes('600519 — hold 0 shares') || el.innerText.includes('600519 - hold 0 shares'));
            if (accordion) {
                accordion.click();
                return 'clicked-accordion';
            }
            return 'not-found';
        })()''')
        print("Accordion click:", click_res)
        await asyncio.sleep(1.0)
        await capture_screenshot("/tmp/demo_screenshots/09_investment_report_expanded.png")

asyncio.run(expand_report())
