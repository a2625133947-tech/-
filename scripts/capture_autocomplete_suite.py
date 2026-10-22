import asyncio
import base64
import json
import os
import time
import urllib.request
import websockets

async def capture_autocomplete_suite():
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
                    data = msg["result"]["data"]
                    os.makedirs(os.path.dirname(path), exist_ok=True)
                    with open(path, "wb") as f:
                        f.write(base64.b64decode(data))
                    print(f"Saved screenshot: {path}")
                    break

        # 1. Close any open dialogs / welcome modals
        print("Closing any open dialogs or welcome modals...")
        await evaluate('''(() => {
            const btns = Array.from(document.querySelectorAll('button'));
            const skipBtn = btns.find(b => b.innerText.includes('暂时跳过') || b.innerText.includes('Skip'));
            if (skipBtn) skipBtn.click();
            const closeBtn = document.querySelector('[role=\"dialog\"] button');
            if (closeBtn) closeBtn.click();
        })()''')
        await asyncio.sleep(1.0)

        # 2. Switch to Flow 3 tab
        print("Ensuring Flow 3 tab is selected...")
        await evaluate('''(() => {
            const tabDivs = Array.from(document.querySelectorAll('.group.relative.flex.items-center'));
            const flowTab = tabDivs.find(d => d.innerText.includes('贵州茅台'));
            if (flowTab) flowTab.click();
        })()''')
        await asyncio.sleep(1.0)

        # 3. Focus and scroll Stock Analyzer Node into view
        print("Focusing Stock Analyzer Node...")
        await evaluate('''(() => {
            const stockNode = Array.from(document.querySelectorAll('.react-flow__node')).find(n => n.innerText.includes('股票分析器') || n.innerText.includes('Stock Analyzer'));
            if (stockNode) {
                stockNode.scrollIntoView({ behavior: 'instant', block: 'center', inline: 'center' });
            }
        })()''')
        await asyncio.sleep(0.5)

        # Helper to set combobox input value
        async def set_search_query(q):
            await evaluate(f'''(() => {{
                const input = document.querySelector('.react-flow__node input[role="combobox"]');
                if (input) {{
                    input.focus();
                    const valueSetter = Object.getOwnPropertyDescriptor(input, 'value').set;
                    const prototype = Object.getPrototypeOf(input);
                    const prototypeValueSetter = Object.getOwnPropertyDescriptor(prototype, 'value').set;
                    if (prototypeValueSetter && valueSetter !== prototypeValueSetter) {{
                        prototypeValueSetter.call(input, '{q}');
                    }} else {{
                        valueSetter.call(input, '{q}');
                    }}
                    input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                }}
            }})()''')
            await asyncio.sleep(0.6) # wait for debounce & fetch

        # --- Test 1: Type '6005' and capture dropdown ---
        print("Test 1: Type '6005'...")
        await set_search_query('6005')
        await capture_screenshot("/tmp/demo_screenshots/17_search_6005_dropdown.png")

        # --- Test 2: Type '贵州' and capture dropdown ---
        print("Test 2: Type '贵州'...")
        await set_search_query('贵州')
        await capture_screenshot("/tmp/demo_screenshots/18_search_guizhou_dropdown.png")

        # --- Test 3: Type '宁德时代' and capture dropdown ---
        print("Test 3: Type '宁德时代'...")
        await set_search_query('宁德时代')
        await capture_screenshot("/tmp/demo_screenshots/19_search_ningde_dropdown.png")

        # --- Test 4: Select 600519 and capture selected state ---
        print("Test 4: Select '600519'...")
        await set_search_query('600519')
        # Click the dropdown option
        await evaluate('''(() => {
            const opt = document.querySelector('li[role=\"option\"]');
            if (opt) opt.click();
        })()''')
        await asyncio.sleep(0.5)
        await capture_screenshot("/tmp/demo_screenshots/20_selected_moutai_node.png")

        # --- Test 5: Keyboard navigation ArrowDown highlight ---
        print("Test 5: Keyboard navigation...")
        await set_search_query('银行')
        # Press ArrowDown twice to highlight second item
        await evaluate('''(() => {
            const input = document.querySelector('.react-flow__node input[role=\"combobox\"]');
            if (input) {
                input.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true }));
                input.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true }));
            }
        })()''')
        await asyncio.sleep(0.5)
        await capture_screenshot("/tmp/demo_screenshots/21_keyboard_highlight_dropdown.png")

        # --- Test 6: Search no results state ---
        print("Test 6: Search no match...")
        await set_search_query('999999xyz')
        await capture_screenshot("/tmp/demo_screenshots/22_search_no_results.png")

        # --- Test 7: English UI search ---
        print("Test 7: English UI...")
        # Toggle language to English
        await evaluate('''(() => {
            const langBtn = document.querySelector('#tour-language-switcher') || Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('中文') || b.innerText.includes('EN') || b.innerText.includes('English'));
            if (langBtn) langBtn.click();
        })()''')
        await asyncio.sleep(1.0)

        # Type '600' in English UI
        await set_search_query('600')
        await capture_screenshot("/tmp/demo_screenshots/23_english_ui_search.png")

        # Switch back to Chinese and reset input to 600519
        await evaluate('''(() => {
            const langBtn = document.querySelector('#tour-language-switcher') || Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('中文') || b.innerText.includes('EN') || b.innerText.includes('English'));
            if (langBtn) langBtn.click();
        })()''')
        await asyncio.sleep(0.5)
        await set_search_query('600519')

        print("All screenshots successfully captured!")

asyncio.run(capture_autocomplete_suite())
