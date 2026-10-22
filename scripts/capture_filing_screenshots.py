import asyncio
import base64
import json
import time
import urllib.request
import websockets

async def capture_filing_dialog():
    tabs = json.loads(urllib.request.urlopen("http://127.0.0.1:9222/json").read().decode())
    target = [t for t in tabs if "5173" in t.get("url", "")][0]
    print(f"Connecting to Chrome tab: {target['title']}")

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
                    with open(path, "wb") as f:
                        f.write(base64.b64decode(msg["result"]["data"]))
                    print(f"Saved screenshot: {path}")
                    break

        # 1. Click '投资综合研报' button
        print("Clicking '投资综合研报' button...")
        open_res = await evaluate('''(() => {
            const pmNode = Array.from(document.querySelectorAll('.react-flow__node')).find(n => n.innerText.includes('投资组合经理') || n.innerText.includes('Portfolio Manager'));
            if (!pmNode) return 'no-pm-node';
            const btn = Array.from(pmNode.querySelectorAll('button')).find(b => b.innerText.includes('投资综合研报') || b.innerText.includes('Investment Report'));
            if (btn) {
                btn.click();
                return 'clicked-report-btn';
            }
            return 'no-report-btn';
        })()''')
        print(open_res)
        await asyncio.sleep(2.0)

        # 2. Screenshot 12: Scroll to Key Sources & Filings
        print("Capturing 12_recent_reports_section.png...")
        await evaluate('''(() => {
            const dialog = document.querySelector('[role=\"dialog\"]');
            if (dialog) {
                const h3s = Array.from(dialog.querySelectorAll('h3'));
                const targetH3 = h3s.find(h => h.innerText.includes('主要资料来源') || h.innerText.includes('Official Filing Sources'));
                if (targetH3) {
                    targetH3.scrollIntoView({ behavior: 'instant', block: 'start' });
                } else {
                    dialog.scrollTop = 1200;
                }
            }
        })()''')
        await asyncio.sleep(1.0)
        await capture_screenshot("/tmp/demo_screenshots/12_recent_reports_section.png")

        # 3. Screenshot 13: Hover on Filing Title
        print("Capturing 13_report_title_hover.png...")
        await evaluate('''(() => {
            const dialog = document.querySelector('[role=\"dialog\"]');
            if (dialog) {
                const link = dialog.querySelector('a[href*=\"cninfo.com.cn\"]');
                if (link) {
                    link.dispatchEvent(new MouseEvent('mouseenter', { bubbles: true }));
                    link.dispatchEvent(new MouseEvent('mouseover', { bubbles: true }));
                    link.focus();
                }
            }
        })()''')
        await asyncio.sleep(1.0)
        await capture_screenshot("/tmp/demo_screenshots/13_report_title_hover.png")

        # 4. Screenshot 14: Fundamentals Analyst Dossier
        print("Capturing 14_fundamentals_analyst_citation.png...")
        await evaluate('''(() => {
            const dialog = document.querySelector('[role=\"dialog\"]');
            if (dialog) {
                const cards = Array.from(dialog.querySelectorAll('.border'));
                const fundCard = cards.find(c => c.innerText.includes('Fundamentals Analyst'));
                if (fundCard) {
                    fundCard.scrollIntoView({ behavior: 'instant', block: 'start' });
                }
            }
        })()''')
        await asyncio.sleep(1.0)
        await capture_screenshot("/tmp/demo_screenshots/14_fundamentals_analyst_citation.png")

        # 5. Screenshot 15: Valuation Analyst Dossier
        print("Capturing 15_valuation_analyst_citation.png...")
        await evaluate('''(() => {
            const dialog = document.querySelector('[role=\"dialog\"]');
            if (dialog) {
                const cards = Array.from(dialog.querySelectorAll('.border'));
                const valCard = cards.find(c => c.innerText.includes('Valuation Analyst'));
                if (valCard) {
                    valCard.scrollIntoView({ behavior: 'instant', block: 'start' });
                }
            }
        })()''')
        await asyncio.sleep(1.0)
        await capture_screenshot("/tmp/demo_screenshots/15_valuation_analyst_citation.png")

        # 6. Screenshot 16: English UI
        print("Capturing 16_english_ui_citations.png in English...")
        # Close dialog
        await evaluate('''(() => {
            const closeBtn = document.querySelector('[role=\"dialog\"] button');
            if (closeBtn) closeBtn.click();
        })()''')
        await asyncio.sleep(1.0)

        # Toggle to English
        await evaluate('''(() => {
            const langBtn = document.querySelector('#tour-language-switcher') || Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('中文') || b.innerText.includes('EN') || b.innerText.includes('English'));
            if (langBtn) langBtn.click();
        })()''')
        await asyncio.sleep(1.0)

        # Open in English
        await evaluate('''(() => {
            const pmNode = Array.from(document.querySelectorAll('.react-flow__node')).find(n => n.innerText.includes('投资组合经理') || n.innerText.includes('Portfolio Manager'));
            if (!pmNode) return;
            const btn = Array.from(pmNode.querySelectorAll('button')).find(b => b.innerText.includes('投资综合研报') || b.innerText.includes('Investment Report'));
            if (btn) btn.click();
        })()''')
        await asyncio.sleep(1.5)

        # Scroll to Sources
        await evaluate('''(() => {
            const dialog = document.querySelector('[role=\"dialog\"]');
            if (dialog) {
                const h3s = Array.from(dialog.querySelectorAll('h3'));
                const targetH3 = h3s.find(h => h.innerText.includes('主要资料来源') || h.innerText.includes('Official Filing Sources'));
                if (targetH3) targetH3.scrollIntoView({ behavior: 'instant', block: 'start' });
            }
        })()''')
        await asyncio.sleep(1.0)
        await capture_screenshot("/tmp/demo_screenshots/16_english_ui_citations.png")

        # Switch back to Chinese
        await evaluate('''(() => {
            const closeBtn = document.querySelector('[role=\"dialog\"] button');
            if (closeBtn) closeBtn.click();
        })()''')
        await asyncio.sleep(0.5)
        await evaluate('''(() => {
            const langBtn = document.querySelector('#tour-language-switcher') || Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('中文') || b.innerText.includes('EN') || b.innerText.includes('English'));
            if (langBtn) langBtn.click();
        })()''')

        print("Done capturing filing screenshots!")

asyncio.run(capture_filing_dialog())
