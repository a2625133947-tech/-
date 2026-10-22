import asyncio
import base64
import json
import time
import urllib.request
import websockets

async def capture_analyst_dossiers():
    tabs = json.loads(urllib.request.urlopen("http://127.0.0.1:9222/json").read().decode())
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
                    with open(path, "wb") as f:
                        f.write(base64.b64decode(msg["result"]["data"]))
                    print(f"Saved screenshot: {path}")
                    break

        # Scroll to Analyst section
        scroll_res = await evaluate('''(() => {
            const dialog = document.querySelector('[role=\"dialog\"]');
            if (dialog) {
                // Find the analyst section header
                const headers = Array.from(dialog.querySelectorAll('h3'));
                const targetHeader = headers.find(h => h.innerText.includes('各分析师专业研判细则'));
                if (targetHeader) {
                    targetHeader.scrollIntoView({ behavior: 'instant', block: 'start' });
                    return 'scrolled to analyst header';
                }
                dialog.scrollTop = 2500;
                return 'scrolled by offset';
            }
            return 'no dialog';
        })()''')
        print(scroll_res)
        await asyncio.sleep(1.0)
        await capture_screenshot("/tmp/demo_screenshots/10_new_analyst_dossiers.png")

        # Now click on '原始分析数据 (Raw Analysis JSON)' on the visible analyst card
        click_raw = await evaluate('''(() => {
            const btns = Array.from(document.querySelectorAll('[role=\"dialog\"] button'));
            const rawBtn = btns.find(b => b.innerText.includes('原始分析数据'));
            if (rawBtn) {
                rawBtn.scrollIntoView({ behavior: 'instant', block: 'center' });
                rawBtn.click();
                return 'clicked raw json btn';
            }
            return 'no raw btn';
        })()''')
        print(click_raw)
        await asyncio.sleep(1.0)
        await capture_screenshot("/tmp/demo_screenshots/11_raw_json_collapsed_verified.png")

asyncio.run(capture_analyst_dossiers())
