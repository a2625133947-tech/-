import asyncio
import base64
import json
import time
import urllib.request
import websockets

async def reload_and_run():
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

        # 1. Reload page
        print("Reloading page to clear pending requests...")
        await evaluate("window.location.reload()")
        await asyncio.sleep(3.0)

        # 2. Switch to Flow 3 tab
        print("Switching to Flow 3 tab...")
        await evaluate('''(() => {
            const tabs = Array.from(document.querySelectorAll('.group.relative.flex.items-center'));
            const flowTab = tabs.find(t => t.innerText.includes('贵州茅台'));
            if (flowTab) flowTab.click();
        })()''')
        await asyncio.sleep(1.5)

        # 3. Check and set input to 600519
        print("Ensuring ticker is 600519...")
        await evaluate('''(() => {
            const stockNode = Array.from(document.querySelectorAll('.react-flow__node')).find(n => n.innerText.includes('股票分析器') || n.innerText.includes('Stock Analyzer'));
            if (!stockNode) return;
            const input = stockNode.querySelector('input');
            if (input && input.value !== '600519') {
                const valueSetter = Object.getOwnPropertyDescriptor(input, 'value').set;
                const prototype = Object.getPrototypeOf(input);
                const prototypeValueSetter = Object.getOwnPropertyDescriptor(prototype, 'value').set;
                if (prototypeValueSetter && valueSetter !== prototypeValueSetter) {
                    prototypeValueSetter.call(input, '600519');
                } else {
                    valueSetter.call(input, '600519');
                }
                input.dispatchEvent(new Event('input', { bubbles: true }));
                input.dispatchEvent(new Event('change', { bubbles: true }));
            }
        })()''')
        await asyncio.sleep(0.5)

        # 4. Click Start Analysis (Run)
        print("Clicking Start Analysis...")
        click_res = await evaluate('''(() => {
            const btn = document.querySelector('button[title*=\"开始分析\"]');
            if (btn && !btn.disabled) {
                btn.click();
                return 'run-started';
            }
            return 'not-ready';
        })()''')
        print("Click result:", click_res)

        # 5. Wait for Portfolio Manager to finish and report button to appear
        print("Waiting for full workflow execution...")
        for i in range(40):
            await asyncio.sleep(1.0)
            st = await evaluate('''(() => {
                const reportBtn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('投资综合研报') || b.innerText.includes('Investment Report'));
                return !!reportBtn;
            })()''')
            if st:
                print(f"  Finished in UI at second {i+1}!")
                break
            if (i + 1) % 5 == 0:
                print(f"  Still running... {i+1}s")

        await asyncio.sleep(2.0)

        # 6. Click '投资综合研报'
        print("Opening Investment Report dialog...")
        await evaluate('''(() => {
            const reportBtn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('投资综合研报') || b.innerText.includes('Investment Report'));
            if (reportBtn) reportBtn.click();
        })()''')
        await asyncio.sleep(2.0)

        # 7. Screenshot 12: Key Sources & Statutory Filings
        print("Capturing 12_recent_reports_section.png...")
        await evaluate('''(() => {
            const dialog = document.querySelector('[role=\"dialog\"]');
            if (dialog) {
                const h3s = Array.from(dialog.querySelectorAll('h3'));
                const targetH3 = h3s.find(h => h.innerText.includes('主要资料来源') || h.innerText.includes('Official Filing Sources'));
                if (targetH3) {
                    targetH3.scrollIntoView({ behavior: 'instant', block: 'start' });
                } else {
                    dialog.scrollTop = 1350;
                }
            }
        })()''')
        await asyncio.sleep(1.0)
        await capture_screenshot("/tmp/demo_screenshots/12_recent_reports_section.png")

        # 8. Screenshot 13: Hover on Filing Title
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

        # 9. Screenshot 14: Fundamentals Analyst Dossier
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

        # 10. Screenshot 15: Valuation Analyst Dossier
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

        # 11. Screenshot 16: English UI
        print("Capturing 16_english_ui_citations.png...")
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
            const reportBtn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('投资综合研报') || b.innerText.includes('Investment Report'));
            if (reportBtn) reportBtn.click();
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

        print("Done!")

asyncio.run(reload_and_run())
