"""Single registry for selectable analyst nodes."""

from src.agents.a_share_investors import AGENTS, PROFILES
from src.agents.fundamentals import fundamentals_analyst_agent
from src.agents.growth_agent import growth_analyst_agent
from src.agents.news_sentiment import news_sentiment_agent
from src.agents.sentiment import sentiment_analyst_agent
from src.agents.technicals import technical_analyst_agent
from src.agents.valuation import valuation_analyst_agent


# Each named node is an independently weighted strategy prototype. The name
# identifies its inspiration, not a statement from or endorsement by the person.
ANALYST_CONFIG = {
    key: {
        "display_name": profile.name,
        "description": "A股投资理念启发的策略原型",
        "investing_style": f"{profile.lens}。由公开理念启发的项目模型，并非本人观点。",
        "agent_func": AGENTS[key],
        "type": "analyst",
        "order": order,
    }
    for order, (key, profile) in enumerate(PROFILES.items())
}


ANALYST_CONFIG.update({
    "technical_analyst": {
        "display_name": "Technical Analyst",
        "description": "Chart Pattern Specialist",
        "investing_style": "Analyzes chart patterns, trends and price action.",
        "agent_func": technical_analyst_agent,
        "type": "analyst",
        "order": 12,
    },
    "fundamentals_analyst": {
        "display_name": "Fundamentals Analyst",
        "description": "Financial Statement Specialist",
        "investing_style": "Analyzes financial statements and fundamental strength.",
        "agent_func": fundamentals_analyst_agent,
        "type": "analyst",
        "order": 13,
    },
    "growth_analyst": {
        "display_name": "Growth Analyst",
        "description": "Growth Specialist",
        "investing_style": "Analyzes revenue, earnings and valuation growth.",
        "agent_func": growth_analyst_agent,
        "type": "analyst",
        "order": 14,
    },
    "news_sentiment_analyst": {
        "display_name": "News Sentiment Analyst",
        "description": "News Sentiment Specialist",
        "investing_style": "Analyzes available company news sentiment.",
        "agent_func": news_sentiment_agent,
        "type": "analyst",
        "order": 15,
    },
    "sentiment_analyst": {
        "display_name": "Sentiment Analyst",
        "description": "Market Sentiment Specialist",
        "investing_style": "Analyzes available market sentiment indicators.",
        "agent_func": sentiment_analyst_agent,
        "type": "analyst",
        "order": 16,
    },
    "valuation_analyst": {
        "display_name": "Valuation Analyst",
        "description": "Company Valuation Specialist",
        "investing_style": "Analyzes company valuation using financial metrics.",
        "agent_func": valuation_analyst_agent,
        "type": "analyst",
        "order": 17,
    },
})


ANALYST_ORDER = [
    (config["display_name"], key)
    for key, config in sorted(ANALYST_CONFIG.items(), key=lambda item: item[1]["order"])
]


def get_analyst_nodes():
    return {key: (f"{key}_agent", config["agent_func"]) for key, config in ANALYST_CONFIG.items()}


def get_agents_list():
    return [
        {
            "key": key,
            "display_name": config["display_name"],
            "description": config["description"],
            "investing_style": config["investing_style"],
            "order": config["order"],
        }
        for key, config in sorted(ANALYST_CONFIG.items(), key=lambda item: item[1]["order"])
    ]
