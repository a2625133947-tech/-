import asyncio
import base64
import json
import urllib.request
import websockets

async def main():
    resp = urllib.request.urlopen("http://localhost:9222/json")
    tabs = json.loads(resp.read().decode())
    target = [t for t in tabs if "5173" in t.get("url", "")][0]
    print(f"Connecting to Chrome tab: {target['title']} ({target['id']})")
    
    async with websockets.connect(target["webSocketDebuggerUrl"], max_size=20_000_000) as ws:
        async def evaluate(expression):
            msg_id = int(asyncio.get_event_loop().time() * 1000) % 1000000
            await ws.send(json.dumps({
                "id": msg_id,
                "method": "Runtime.evaluate",
                "params": {"expression": expression, "returnByValue": True, "awaitPromise": True}
            }))
            res = json.loads(await ws.recv())
            return res.get("result", {}).get("result", {}).get("value")

        async def screenshot(filepath):
            msg_id = int(asyncio.get_event_loop().time() * 1000) % 1000000
            await ws.send(json.dumps({
                "id": msg_id,
                "method": "Page.captureScreenshot",
                "params": {"format": "png"}
            }))
            res = json.loads(await ws.recv())
            data = res["result"]["data"]
            with open(filepath, "wb") as f:
                f.write(base64.b64decode(data))
            print(f"Saved screenshot: {filepath}")

        # Step 1: Click on Flow 3 tab or sidebar item if not active
        print("Ensuring Flow 3 is opened and active...")
        switch_res = await evaluate('''(() => {
            const flowItems = Array.from(document.querySelectorAll('#tour-left-flows span, #tour-left-flows button, div[role=\"button\"]'));
            const targetFlow = flowItems.find(el => el.innerText.includes('贵州茅台完整投资研究演示'));
            if (targetFlow) {
                targetFlow.click();
                return 'clicked-flow-item';
            }
            return 'not-found';
        })()''')
        print("Switch flow result:", switch_res)
        await asyncio.sleep(1)

        # Step 2: Test Undo/Redo/Duplicate/Delete interaction
        print("Testing Undo / Redo / Duplicate / Delete on Canvas...")
        edit_test_res = await evaluate('''(() => {
            // Find undo and redo buttons
            const undoBtn = document.querySelector('button[aria-label=\"Undo\"]');
            const redoBtn = document.querySelector('button[aria-label=\"Redo\"]');
            const autoLayoutBtn = document.querySelector('button[title*=\"自动布局\"]') || Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('自动布局'));
            return {
                undoEnabled: undoBtn ? !undoBtn.disabled : false,
                redoEnabled: redoBtn ? !redoBtn.disabled : false,
                hasAutoLayout: !!autoLayoutBtn
            };
        })()''')
        print("Editor buttons test:", edit_test_res)

        # Step 3: Populate formal Demo Workflow nodes & edges for Flow 3
        # Nodes: 1 Stock Input, 7 Analysts, 1 Portfolio Manager
        print("Configuring formal Demo Workflow nodes and edges...")
        nodes_and_edges = {
            "nodes": [
                {
                    "id": "stock-analyzer-node_demo01",
                    "type": "stock-analyzer-node",
                    "position": {"x": 50, "y": 300},
                    "data": {
                        "name": "Stock Input",
                        "description": "Enter individual stocks and connect this node to Analysts to generate insights.",
                        "status": "Idle",
                        "tickers": "600519",
                        "startDate": "2025-09-25",
                        "endDate": "2026-09-25",
                        "initialCash": "100000"
                    }
                },
                {
                    "id": "fundamentals_analyst_demo02",
                    "type": "agent-node",
                    "position": {"x": 420, "y": 50},
                    "data": {
                        "name": "Fundamentals Analyst",
                        "description": "Analyzes financial statements and fundamental strength.",
                        "status": "Idle"
                    }
                },
                {
                    "id": "valuation_analyst_demo03",
                    "type": "agent-node",
                    "position": {"x": 420, "y": 180},
                    "data": {
                        "name": "Valuation Analyst",
                        "description": "Analyzes company valuation using financial metrics.",
                        "status": "Idle"
                    }
                },
                {
                    "id": "technical_analyst_demo04",
                    "type": "agent-node",
                    "position": {"x": 420, "y": 310},
                    "data": {
                        "name": "Technical Analyst",
                        "description": "Analyzes chart patterns, trends and price action.",
                        "status": "Idle"
                    }
                },
                {
                    "id": "news_sentiment_analyst_demo05",
                    "type": "agent-node",
                    "position": {"x": 420, "y": 440},
                    "data": {
                        "name": "News Sentiment Analyst",
                        "description": "Analyzes available company news sentiment.",
                        "status": "Idle"
                    }
                },
                {
                    "id": "duan_yongping_demo06",
                    "type": "agent-node",
                    "position": {"x": 420, "y": 570},
                    "data": {
                        "name": "段永平",
                        "description": "商业模式护城河与现金流创造策略原型",
                        "status": "Idle"
                    }
                },
                {
                    "id": "feng_liu_demo07",
                    "type": "agent-node",
                    "position": {"x": 420, "y": 700},
                    "data": {
                        "name": "冯柳",
                        "description": "低估值和价格压制代理加经营改善策略原型",
                        "status": "Idle"
                    }
                },
                {
                    "id": "fu_pengbo_demo08",
                    "type": "agent-node",
                    "position": {"x": 420, "y": 830},
                    "data": {
                        "name": "傅鹏博",
                        "description": "成长持续性、经营质量与估值匹配策略原型",
                        "status": "Idle"
                    }
                },
                {
                    "id": "portfolio_manager_demo09",
                    "type": "portfolio-manager-node",
                    "position": {"x": 800, "y": 440},
                    "data": {
                        "name": "Portfolio Manager",
                        "description": "Generates investment decisions based on input from Analysts.",
                        "status": "Idle"
                    }
                }
            ],
            "edges": [
                # Stock input -> 7 Analysts
                {"id": "e_in_fund", "source": "stock-analyzer-node_demo01", "target": "fundamentals_analyst_demo02", "markerEnd": {"type": "arrowclosed"}},
                {"id": "e_in_val", "source": "stock-analyzer-node_demo01", "target": "valuation_analyst_demo03", "markerEnd": {"type": "arrowclosed"}},
                {"id": "e_in_tech", "source": "stock-analyzer-node_demo01", "target": "technical_analyst_demo04", "markerEnd": {"type": "arrowclosed"}},
                {"id": "e_in_news", "source": "stock-analyzer-node_demo01", "target": "news_sentiment_analyst_demo05", "markerEnd": {"type": "arrowclosed"}},
                {"id": "e_in_duan", "source": "stock-analyzer-node_demo01", "target": "duan_yongping_demo06", "markerEnd": {"type": "arrowclosed"}},
                {"id": "e_in_feng", "source": "stock-analyzer-node_demo01", "target": "feng_liu_demo07", "markerEnd": {"type": "arrowclosed"}},
                {"id": "e_in_fu", "source": "stock-analyzer-node_demo01", "target": "fu_pengbo_demo08", "markerEnd": {"type": "arrowclosed"}},

                # 7 Analysts -> Portfolio Manager
                {"id": "e_fund_pm", "source": "fundamentals_analyst_demo02", "target": "portfolio_manager_demo09", "markerEnd": {"type": "arrowclosed"}},
                {"id": "e_val_pm", "source": "valuation_analyst_demo03", "target": "portfolio_manager_demo09", "markerEnd": {"type": "arrowclosed"}},
                {"id": "e_tech_pm", "source": "technical_analyst_demo04", "target": "portfolio_manager_demo09", "markerEnd": {"type": "arrowclosed"}},
                {"id": "e_news_pm", "source": "news_sentiment_analyst_demo05", "target": "portfolio_manager_demo09", "markerEnd": {"type": "arrowclosed"}},
                {"id": "e_duan_pm", "source": "duan_yongping_demo06", "target": "portfolio_manager_demo09", "markerEnd": {"type": "arrowclosed"}},
                {"id": "e_feng_pm", "source": "feng_liu_demo07", "target": "portfolio_manager_demo09", "markerEnd": {"type": "arrowclosed"}},
                {"id": "e_fu_pm", "source": "fu_pengbo_demo08", "target": "portfolio_manager_demo09", "markerEnd": {"type": "arrowclosed"}}
            ]
        }

        # Save to database via PUT /flows/3
        req_data = json.dumps({
            "name": "贵州茅台完整投资研究演示",
            "description": "600519全链路多风格投资研究Demo：段永平、冯柳、傅鹏博、基本面、估值、技术面、新闻舆情协同与风控组合决策",
            "nodes": nodes_and_edges["nodes"],
            "edges": nodes_and_edges["edges"]
        }).encode("utf-8")
        put_req = urllib.request.Request("http://localhost:8000/flows/3", data=req_data, headers={"Content-Type": "application/json"}, method="PUT")
        urllib.request.urlopen(put_req)
        print("Updated Flow 3 in backend successfully!")

        # Reload tab in browser to load the nodes & edges
        await evaluate("window.location.reload()")
        await asyncio.sleep(2.5)

        # Trigger auto layout and fit view in React Flow
        print("Triggering Auto Layout and Fit View...")
        layout_res = await evaluate('''(() => {
            const autoLayoutBtn = document.querySelector('button[title*=\"自动布局\"]') || Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('自动布局'));
            if (autoLayoutBtn) {
                autoLayoutBtn.click();
                return 'clicked-auto-layout';
            }
            return 'auto-layout-btn-not-found';
        })()''')
        print("Auto Layout Trigger:", layout_res)
        await asyncio.sleep(1.5)

        # Fit view
        await evaluate('''(() => {
            const fitViewBtn = document.querySelector('button[title*=\"适应屏幕\"]') || document.querySelector('button[title*=\"自适应\"]') || Array.from(document.querySelectorAll('button')).find(b => b.querySelector('svg.lucide-maximize-2'));
            if (fitViewBtn) {
                fitViewBtn.click();
                return 'clicked-fit-view';
            }
            return 'fit-view-btn-not-found';
        })()''')
        await asyncio.sleep(1)

        # Take screenshot of Workflow canvas
        await screenshot("/tmp/demo_screenshots/02_workflow_canvas.png")

asyncio.run(main())
