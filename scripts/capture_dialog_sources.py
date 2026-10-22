import asyncio
import base64
import json
import time
import urllib.request
import websockets

async def run_and_capture_dialog():
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
                    with open(path, "wb") as f:
                        f.write(base64.b64decode(msg["result"]["data"]))
                    print(f"Saved screenshot: {path}")
                    break

        # 1. Trigger Play button on canvas
        print("Clicking Play button on Stock Analyzer Node...")
        click_play = await evaluate('''(() => {
            const stockNode = Array.from(document.querySelectorAll('.react-flow__node')).find(n => n.innerText.includes('股票分析器') || n.innerText.includes('Stock Analyzer'));
            if (!stockNode) return 'no stock node';
            const btns = Array.from(stockNode.querySelectorAll('button'));
            if (btns[2]) {
                btns[2].click();
                return 'play-clicked';
            }
            return 'no-btn';
        })()''')
        print("Play click result:", click_play)

        # 2. Wait until Portfolio Manager has "投资综合研报" button
        print("Waiting for full workflow execution to complete in UI...")
        for i in range(45):
            await asyncio.sleep(1.0)
            status = await evaluate('''(() => {
                const reportBtn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('投资综合研报') || b.innerText.includes('Investment Report'));
                const nodes = Array.from(document.querySelectorAll('.react-flow__node'));
                const pm = nodes.find(n => n.innerText.includes('投资组合经理') || n.innerText.includes('Portfolio Manager'));
                return {
                    hasReportBtn: !!reportBtn,
                    pmText: pm ? pm.innerText.substring(0, 80) : ''
                };
            })()''')
            print(f"  [{i+1}s] Report button ready: {status.get('hasReportBtn')}")
            if status.get('hasReportBtn'):
                break

        await asyncio.sleep(1.5)

        # 3. Click '投资综合研报' button
        print("Clicking '投资综合研报' button...")
        open_res = await evaluate('''(() => {
            const reportBtn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('投资综合研报') || b.innerText.includes('Investment Report'));
            if (reportBtn) {
                reportBtn.click();
                return 'opened-dialog';
            }
            return 'btn-not-found';
        })()''')
        print("Open dialog result:", open_res)
        await asyncio.sleep(2.0)

        # Verify dialog is open
        dialog_ready = await evaluate('''(() => {
            const d = document.querySelector('[role=\"dialog\"]');
            return d ? d.innerText.substring(0, 100) : null;
        })()''')
        print("Dialog text preview:", dialog_ready)

        # 4. Screenshot 12: Scroll to Key Sources & Filings
        print("Scrolling to '主要资料来源与法定财报原文'...")
        await evaluate('''(() => {
            const dialog = document.querySelector('[role=\"dialog\"]');
            if (dialog) {
                const h3s = Array.from(dialog.querySelectorAll('h3'));
                const targetH3 = h3s.find(h => h.innerText.includes('主要资料来源') || h.innerText.includes('Official Filing Sources'));
                if (targetH3) {
                    targetH3.scrollIntoView({ behavior: 'instant', block: 'start' });
                } else {
                    dialog.scrollTop = 1400;
                }
            }
        })()''')
        await asyncio.sleep(1.0)
        await capture_screenshot("/tmp/demo_screenshots/12_recent_reports_section.png")

        # 5. Screenshot 13: Hover on Filing Title
        print("Triggering hover on filing title...")
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

        # 6. Screenshot 14: Fundamentals Analyst Dossier
        print("Scrolling to Fundamentals Analyst Dossier...")
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

        # 7. Screenshot 15: Valuation Analyst Dossier
        print("Scrolling to Valuation Analyst Dossier...")
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

        # 8. Screenshot 16: English UI
        print("Switching Language to English...")
        # Close dialog
        await evaluate('''(() => {
            const closeBtn = document.querySelector('[role=\"dialog\"] button');
            if (closeBtn) closeBtn.click();
        })()''')
        await asyncio.sleep(1.0)

        # Toggle language
        await evaluate('''(() => {
            const langBtn = document.querySelector('#tour-language-switcher') || Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('中文') || b.innerText.includes('EN') || b.innerText.includes('English'));
            if (langBtn) langBtn.click();
        })()''')
        await asyncio.sleep(1.0)

        # Re-open dialog in English
        await evaluate('''(() => {
            const reportBtn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('投资综合研报') || b.innerText.includes('Investment Report'));
            if (reportBtn) reportBtn.click();
        })()''')
        await asyncio.sleep(1.5)

        # Scroll to sources in English
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

        print("All screenshots successfully captured!")

asyncio.run(run_and_capture_dialog())
