import asyncio
import base64
import json
import time
import urllib.request
import websockets
from src.tools.api import get_financial_report_references, get_latest_financial_report_reference

def test_stocks_disclosure_connectivity():
    print("==================================================")
    print("=== Testing CNINFO Disclosure Connectivity ===")
    print("==================================================")
    test_tickers = ['600519', '000001', '300750']
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

    results = {}
    for t in test_tickers:
        print(f"\nTesting ticker: {t}...")
        refs = get_financial_report_references(t, limit=4)
        print(f"  Retrieved {len(refs)} filing references from CNINFO:")
        ticker_res = []
        for r in refs:
            # Check source_url
            source_ok = False
            try:
                req1 = urllib.request.Request(r.source_url, headers=headers)
                with urllib.request.urlopen(req1, timeout=8) as resp1:
                    source_ok = (resp1.status == 200)
            except Exception as e:
                source_ok = False

            # Check pdf_url
            pdf_ok = False
            if r.pdf_url:
                try:
                    req2 = urllib.request.Request(r.pdf_url, headers=headers)
                    with urllib.request.urlopen(req2, timeout=8) as resp2:
                        pdf_ok = (resp2.status == 200 and 'pdf' in resp2.headers.get('Content-Type', '').lower())
                except Exception as e:
                    pdf_ok = False

            info = {
                "title": r.title,
                "type": r.report_type,
                "publish_date": r.publish_date,
                "source_url": r.source_url,
                "source_ok": source_ok,
                "pdf_url": r.pdf_url,
                "pdf_ok": pdf_ok
            }
            ticker_res.append(info)
            print(f"    • [{r.publish_date}] ({r.report_type}) {r.title}")
            print(f"      source_url (200 OK): {source_ok} | pdf_url (PDF OK): {pdf_ok}")
        results[t] = ticker_res

    with open("docs/baselines/cninfo_filings_verification.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print("\nSaved verification data to docs/baselines/cninfo_filings_verification.json")
    return results


def run_600519_live_flow():
    print("\n==================================================")
    print("=== Running Live 600519 Analysis Flow ===")
    print("==================================================")
    req = urllib.request.urlopen("http://127.0.0.1:8000/flows/3")
    flow = json.loads(req.read().decode())
    nodes = flow["nodes"]
    edges = flow["edges"]

    payload = {
        "tickers": ["600519"],
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
    completed_event = None

    with urllib.request.urlopen(run_req, timeout=600) as response:
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
                    event_type, event_data = None, None
                    for l in part.splitlines():
                        if l.startswith("event:"):
                            event_type = l[len("event:"):].strip()
                        elif l.startswith("data:"):
                            event_data = json.loads(l[len("data:"):].strip())
                    elapsed = time.time() - start_time
                    if event_type and event_data:
                        events.append({"elapsed": elapsed, "type": event_type, "data": event_data})
                        if event_type == "complete":
                            print(f"[{elapsed:5.1f}s] [COMPLETE] Run finished with full citation links!")
                            completed_event = event_data

    total_time = time.time() - start_time
    print(f"600519 run completed in {total_time:.2f}s!")
    with open("docs/baselines/full_demo_run_600519.json", "w", encoding="utf-8") as f:
        json.dump({
            "ticker": "600519",
            "total_duration_seconds": total_time,
            "complete_result": completed_event
        }, f, ensure_ascii=False, indent=2)


async def capture_browser_screenshots():
    print("\n==================================================")
    print("=== Capturing Web UI Screenshots via CDP ===")
    print("==================================================")
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

        # Switch to Flow 3 Tab
        print("Ensuring Flow Tab is active...")
        await evaluate('''(() => {
            const tabDivs = Array.from(document.querySelectorAll('.group.relative.flex.items-center'));
            const flowTab = tabDivs.find(d => d.innerText.includes('贵州茅台'));
            if (flowTab) flowTab.click();
        })()''')
        await asyncio.sleep(1.0)

        # Trigger canvas run to sync React NodeContext
        print("Triggering Play button on canvas to sync React state...")
        await evaluate('''(() => {
            const stockNode = Array.from(document.querySelectorAll('.react-flow__node')).find(n => n.innerText.includes('股票分析器') || n.innerText.includes('Stock Analyzer'));
            if (!stockNode) return 'no stock node';
            const btns = Array.from(stockNode.querySelectorAll('button'));
            if (btns[2]) btns[2].click();
        })()''')

        # Wait for completion
        for _ in range(40):
            await asyncio.sleep(1.0)
            st = await evaluate('''(() => {
                const nodes = Array.from(document.querySelectorAll('.react-flow__node'));
                const pm = nodes.find(n => n.innerText.includes('投资组合经理') || n.innerText.includes('Portfolio Manager'));
                return pm ? pm.innerText : '';
            })()''')
            if '已完成' in st or 'Done' in st:
                print("UI execution reached COMPLETED state!")
                break

        await asyncio.sleep(2.0)

        # Click open Investment Report dialog
        print("Opening Investment Report dialog...")
        await evaluate('''(() => {
            const reportBtn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('投资综合研报') || b.innerText.includes('Investment Report'));
            if (reportBtn) reportBtn.click();
        })()''')
        await asyncio.sleep(2.0)

        # 1. Screenshot: Key Sources & Statutory Filings
        print("Scrolling to Key Sources & Filings...")
        await evaluate('''(() => {
            const dialog = document.querySelector('[role=\"dialog\"]');
            if (dialog) {
                const h3s = Array.from(dialog.querySelectorAll('h3'));
                const targetH3 = h3s.find(h => h.innerText.includes('主要资料来源') || h.innerText.includes('Official Filing Sources'));
                if (targetH3) {
                    targetH3.scrollIntoView({ behavior: 'instant', block: 'start' });
                } else {
                    dialog.scrollTop = 1300;
                }
            }
        })()''')
        await asyncio.sleep(1.0)
        await capture_screenshot("/tmp/demo_screenshots/12_recent_reports_section.png")

        # 2. Screenshot: Hover State on Filing Title
        print("Triggering Hover on Filing Title...")
        await evaluate('''(() => {
            const dialog = document.querySelector('[role=\"dialog\"]');
            if (dialog) {
                const filingLink = dialog.querySelector('a[href*=\"cninfo.com.cn\"]');
                if (filingLink) {
                    filingLink.dispatchEvent(new MouseEvent('mouseenter', { bubbles: true }));
                    filingLink.dispatchEvent(new MouseEvent('mouseover', { bubbles: true }));
                    filingLink.focus();
                }
            }
        })()''')
        await asyncio.sleep(1.0)
        await capture_screenshot("/tmp/demo_screenshots/13_report_title_hover.png")

        # 3. Screenshot: Fundamentals Analyst Citation
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

        # 4. Screenshot: Valuation Analyst Citation
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

        # 5. Screenshot: English UI
        print("Switching Language to English...")
        # Close dialog first
        await evaluate('''(() => {
            const closeBtn = document.querySelector('[role=\"dialog\"] button');
            if (closeBtn) closeBtn.click();
        })()''')
        await asyncio.sleep(1.0)

        # Click language switcher button
        await evaluate('''(() => {
            const langBtn = document.querySelector('#tour-language-switcher') || Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('中文') || b.innerText.includes('EN') || b.innerText.includes('English'));
            if (langBtn) langBtn.click();
        })()''')
        await asyncio.sleep(1.0)

        # Open Investment Report in English
        await evaluate('''(() => {
            const reportBtn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('投资综合研报') || b.innerText.includes('Investment Report'));
            if (reportBtn) reportBtn.click();
        })()''')
        await asyncio.sleep(1.5)

        # Scroll to Sources section in English
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

        print("All UI screenshots successfully captured!")


if __name__ == "__main__":
    test_stocks_disclosure_connectivity()
    run_600519_live_flow()
    asyncio.run(capture_browser_screenshots())
