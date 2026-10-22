import sys
import os
import logging

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langgraph.graph import END, StateGraph
from colorama import Fore, Style, init
import questionary
from src.agents.portfolio_manager import portfolio_management_agent
from src.agents.risk_manager import risk_management_agent
from src.graph.state import AgentState
from src.cli.logging import configure_logging, quiet_runtime
from src.cli.presentation import build_analysis_result
from src.cli.renderer import render_analysis
from src.cli.metadata import stock_names
from src.data.availability import DataAvailabilityReport
from src.data.pipeline import capture_data_availability
from src.utils.analysts import ANALYST_CONFIG, ANALYST_ORDER, get_analyst_nodes
from src.utils.progress import progress
from src.utils.visualize import save_graph_as_png
from src.cli.input import (
    parse_cli_inputs,
)

import argparse
from datetime import datetime
from dateutil.relativedelta import relativedelta
import json

# Load environment variables from .env file
load_dotenv()

init(autoreset=True)


def parse_hedge_fund_response(response):
    """Parses a JSON string and returns a dictionary."""
    try:
        return json.loads(response)
    except json.JSONDecodeError as e:
        print(f"JSON decoding error: {e}\nResponse: {repr(response)}")
        return None
    except TypeError as e:
        print(f"Invalid response type (expected string, got {type(response).__name__}): {e}")
        return None
    except Exception as e:
        print(f"Unexpected error while parsing response: {e}\nResponse: {repr(response)}")
        return None


##### Run the Hedge Fund #####
def run_hedge_fund(
    tickers: list[str],
    start_date: str,
    end_date: str,
    portfolio: dict,
    show_reasoning: bool = False,
    selected_analysts: list[str] = [],
    model_name: str = "gpt-4.1",
    model_provider: str = "OpenAI",
    progress_display: bool = True,
    investor_mode: str | None = None,
):
    # Start progress tracking
    if progress_display:
        progress.start()

    try:
        # Build workflow (default to all analysts when none provided)
        workflow = create_workflow(selected_analysts if selected_analysts else None)
        agent = workflow.compile()

        with capture_data_availability() as data_outcomes:
            final_state = agent.invoke(
                {
                    "messages": [
                        HumanMessage(content="Make trading decisions based on the provided data.")
                    ],
                    "data": {
                        "tickers": tickers,
                        "portfolio": portfolio,
                        "start_date": start_date,
                        "end_date": end_date,
                        "analyst_signals": {},
                    },
                    "metadata": {
                        "show_reasoning": show_reasoning,
                        "model_name": model_name,
                        "model_provider": model_provider,
                        **({"investor_mode": investor_mode} if investor_mode else {}),
                    },
                },
            )

        response = {
            "decisions": parse_hedge_fund_response(final_state["messages"][-1].content),
            "analyst_signals": final_state["data"]["analyst_signals"],
            "data_availability": DataAvailabilityReport.from_outcomes(data_outcomes).model_dump(mode="json"),
            "research_contexts": final_state["data"].get("research_contexts", {}),
        }
        if "investor_shadow" in final_state["data"]:
            response["investor_shadow"] = final_state["data"]["investor_shadow"]
        return response
    finally:
        # Stop progress tracking
        if progress_display:
            progress.stop()


def start(state: AgentState):
    """Initialize the workflow with the input message."""
    from src.research.context import attach_cached_research
    return attach_cached_research(state)


def create_workflow(selected_analysts=None):
    """Create the workflow with selected analysts."""
    workflow = StateGraph(AgentState)
    workflow.add_node("start_node", start)

    # Get analyst nodes from the configuration
    analyst_nodes = get_analyst_nodes()

    # Default to all analysts if none selected
    if selected_analysts is None:
        selected_analysts = list(analyst_nodes.keys())
    # Add selected analyst nodes
    for analyst_key in selected_analysts:
        node_name, node_func = analyst_nodes[analyst_key]
        workflow.add_node(node_name, node_func)
        workflow.add_edge("start_node", node_name)

    # Always add risk and portfolio management
    workflow.add_node("risk_management_agent", risk_management_agent)
    workflow.add_node("portfolio_manager", portfolio_management_agent)

    # Connect selected analysts to risk management
    for analyst_key in selected_analysts:
        node_name = analyst_nodes[analyst_key][0]
        workflow.add_edge(node_name, "risk_management_agent")

    workflow.add_edge("risk_management_agent", "portfolio_manager")
    workflow.add_edge("portfolio_manager", END)

    workflow.set_entry_point("start_node")
    return workflow


if __name__ == "__main__":
    debug_requested = "--debug" in sys.argv[1:]
    configure_logging(debug_requested)
    inputs = parse_cli_inputs(
        description="Run the hedge fund trading system",
        require_tickers=True,
        default_months_back=None,
        include_graph_flag=True,
        include_reasoning_flag=True,
    )

    tickers = inputs.tickers
    selected_analysts = inputs.selected_analysts

    # Construct portfolio here
    portfolio = {
        "cash": inputs.initial_cash,
        "margin_requirement": inputs.margin_requirement,
        "margin_used": 0.0,
        "positions": {
            ticker: {
                "long": 0,
                "short": 0,
                "long_cost_basis": 0.0,
                "short_cost_basis": 0.0,
                "short_margin_used": 0.0,
            }
            for ticker in tickers
        },
        "realized_gains": {
            ticker: {
                "long": 0.0,
                "short": 0.0,
            }
            for ticker in tickers
        },
    }

    statuses = {}

    def collect_progress(agent_name, _ticker, status, _analysis, _timestamp):
        if status.lower() == "done":
            statuses[agent_name] = "Done"
        elif status.lower().startswith(("failed", "warning", "error")):
            statuses[agent_name] = "数据不足，未完成"

    progress.register_handler(collect_progress)
    investor_mode = os.getenv("A_SHARE_INVESTOR_MODE", "legacy").lower()
    try:
        with quiet_runtime(inputs.debug):
            result = run_hedge_fund(
                tickers=tickers,
                start_date=inputs.start_date,
                end_date=inputs.end_date,
                portfolio=portfolio,
                show_reasoning=False,
                selected_analysts=inputs.selected_analysts,
                model_name=inputs.model_name,
                model_provider=inputs.model_provider,
                progress_display=False,
                investor_mode=investor_mode,
            )
            names = stock_names(tickers)
    except KeyboardInterrupt:
        print("分析已中断。", file=sys.stderr)
        raise SystemExit(130)
    except Exception:
        if inputs.debug:
            logging.getLogger(__name__).exception("Analysis failed")
        else:
            print("分析未完成，请检查股票代码、日期和数据可用性；使用 --debug 查看详情。", file=sys.stderr)
        raise SystemExit(1)
    finally:
        progress.unregister_handler(collect_progress)

    display_names = {
        name: "Risk Management" if name.startswith("risk_management_agent") else
        "Portfolio Manager" if name.startswith("portfolio_manager") else
        ANALYST_CONFIG.get(name.removesuffix("_agent"), {}).get("display_name", name.replace("_", " ").title())
        for name in statuses
    }
    presentation = build_analysis_result(
        result,
        {display_names[name]: status for name, status in statuses.items()},
        names,
        investor_mode=investor_mode,
        show_reasoning=inputs.show_reasoning,
        debug_state=inputs.debug_state,
    )
    render_analysis(presentation)
    if inputs.debug_state:
        from rich.console import Console
        Console().print_json(data=result)
