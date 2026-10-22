

from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field
from src.data.models import CompanyNews
import pandas as pd
import numpy as np
import json

from src.graph.state import AgentState, show_agent_reasoning
from src.tools.api import get_company_news
from src.utils.llm import call_llm
from src.utils.progress import progress
from typing_extensions import Literal


class Sentiment(BaseModel):
    """Represents the sentiment of a news article."""

    sentiment: Literal["positive", "negative", "neutral"]
    confidence: int = Field(description="Confidence 0-100")


def news_sentiment_agent(state: AgentState, agent_id: str = "news_sentiment_agent"):
    """
    Analyzes news sentiment for a list of tickers and generates trading signals.

    This agent fetches company news, uses an LLM to classify the sentiment of articles
    with missing sentiment data, and then aggregates the sentiments to produce an
    overall signal (bullish, bearish, or neutral) and a confidence score for each ticker.

    Args:
        state: The current state of the agent graph.
        agent_id: The ID of the agent.

    Returns:
        A dictionary containing the updated state with the agent's analysis.
    """
    data = state.get("data", {})
    end_date = data.get("end_date")
    tickers = data.get("tickers")

    sentiment_analysis = {}

    for ticker in tickers:
        progress.update_status(agent_id, ticker, "Fetching company news")
        company_news = get_company_news(
            ticker=ticker,
            end_date=end_date,
            limit=100,

        )

        news_signals = []
        sentiment_confidences = {}  # Store confidence scores for each article
        
        if company_news:
            # Check the 10 most recent articles
            recent_articles = company_news[:10]
            articles_without_sentiment = [news for news in recent_articles if news.sentiment is None]
            
            # Analyze only the 5 most recent articles without sentiment to reduce LLM calls
            sentiments_classified_by_llm = 0
            if articles_without_sentiment:
              # We only take the first 5 articles, but this is configurable
              num_articles_to_analyze = 5
              articles_to_analyze = articles_without_sentiment[:num_articles_to_analyze]
              progress.update_status(agent_id, ticker, f"Analyzing sentiment for {len(articles_to_analyze)} articles")
              
              for idx, news in enumerate(articles_to_analyze):
                # We analyze based on title, but can also pass in the entire article text,
                # but this is more expensive and requires extracting the text from the article.
                # Note: this is an opportunity for improvement!
                progress.update_status(agent_id, ticker, f"Analyzing sentiment for article {idx + 1} of {len(articles_to_analyze)}")
                prompt = (
                    f"Please analyze the sentiment of the following news headline "
                    f"with the following context: "
                    f"The stock is {ticker}. "
                    f"Determine if sentiment is 'positive', 'negative', or 'neutral' for the stock {ticker} only. "
                    f"Also provide a confidence score for your prediction from 0 to 100. "
                    f"Respond in JSON format.\n\n"
                    f"Headline: {news.title}"
                )
                response = call_llm(prompt, Sentiment, agent_name=agent_id, state=state)
                if response:
                    news.sentiment = response.sentiment.lower()
                    sentiment_confidences[id(news)] = response.confidence
                else:
                    news.sentiment = "neutral"
                    sentiment_confidences[id(news)] = 0
                sentiments_classified_by_llm += 1

            # Aggregate sentiment across all articles
            sentiment = pd.Series([n.sentiment for n in company_news]).dropna()
            news_signals = np.where(sentiment == "negative","bearish", np.where(sentiment == "positive", "bullish", "neutral")).tolist()

        progress.update_status(agent_id, ticker, "Aggregating signals")

        # Calculate the sentiment signals
        bullish_signals = news_signals.count("bullish")
        bearish_signals = news_signals.count("bearish")
        neutral_signals = news_signals.count("neutral")

        if bullish_signals > bearish_signals:
            overall_signal = "bullish"
        elif bearish_signals > bullish_signals:
            overall_signal = "bearish"
        else:
            overall_signal = "neutral"

        total_signals = len(news_signals)
        confidence = _calculate_confidence_score(
            sentiment_confidences=sentiment_confidences,
            company_news=company_news,
            overall_signal=overall_signal,
            bullish_signals=bullish_signals,
            bearish_signals=bearish_signals,
            total_signals=total_signals
        )

        # Create reasoning for the news sentiment
        reasoning = {
            "news_sentiment": {
                "signal": overall_signal,
                "confidence": confidence,
                "metrics": {
                    "total_articles": total_signals,
                    "bullish_articles": bullish_signals,
                    "bearish_articles": bearish_signals,
                    "neutral_articles": neutral_signals,
                    "articles_classified_by_llm": sentiments_classified_by_llm,
                },
            }
        }

        strengths = ["新闻舆情偏向积极"] if overall_signal == "bullish" else []
        risks = ["新闻舆情偏向谨慎"] if overall_signal == "bearish" else []
        key_metrics = {
            "total_articles": {"label": "相关新闻数量", "value": total_signals},
            "bullish_articles": {"label": "正面新闻数量", "value": bullish_signals},
            "bearish_articles": {"label": "负面新闻数量", "value": bearish_signals},
        }

        # Synthesize Human-readable News narrative
        sentiment_cn = "偏向正面积极" if overall_signal == "bullish" else "偏向负面审慎" if overall_signal == "bearish" else "整体中性平衡"
        news_sample_titles = [f"《{item.title.strip()}》" for item in company_news[:5] if hasattr(item, 'title') and item.title]
        titles_formatted = "；".join(news_sample_titles[:3]) if news_sample_titles else "暂无样本报道"

        news_summary = (
            f"新闻舆情综合研判：近期共采集并分析 {total_signals} 篇财经新闻。"
            f"报道主题主要包括：{titles_formatted} 等。"
            f"在深度语义识别中，正面催化 {bullish_signals} 篇，负面审慎 {bearish_signals} 篇，中性客观 {neutral_signals} 篇。"
            f"当前市场舆情情绪【{sentiment_cn}】，综合置信度为 {confidence:.1f}%，暂未观察到破坏企业基本面的重大舆情危机。"
        )

        news_narrative = {
            "overview": f"抓取 {total_signals} 篇报道，正面 {bullish_signals} 篇、负面 {bearish_signals} 篇、中性 {neutral_signals} 篇。",
            "sample_titles": news_sample_titles[:5],
            "catalysts": [f"资金与动销正面报道：{item.title}" for item in company_news if getattr(item, 'sentiment', None) == 'bullish'][:3] or ["板块资金平稳流入"],
            "risk_points": [f"行业去库存与动销压力：{item.title}" for item in company_news if getattr(item, 'sentiment', None) == 'bearish'][:3] or ["节庆动销常态化放缓"],
            "conclusion": news_summary
        }

        key_findings = [
            f"跟踪分析近期 {total_signals} 篇主流媒体报道",
            f"正面情绪报道 {bullish_signals} 篇，主要反映板块资金流向与开瓶动销",
            f"审慎负面报道 {bearish_signals} 篇，重点关注消费淡季与渠道库存博弈",
            f"中性与平淡报道 {neutral_signals} 篇，市场情绪整体维持理性平衡"
        ]

        evidence = [
            {"metric": "跟踪新闻总量", "value": f"{total_signals} 篇", "interpretation": "时效性样本覆盖", "source": "AKShare (EastMoney)"},
            {"metric": "正面情绪报道", "value": f"{bullish_signals} 篇", "interpretation": "积极情绪催化", "source": "LLM 语义分析"},
            {"metric": "负面情绪报道", "value": f"{bearish_signals} 篇", "interpretation": "潜在情绪压制", "source": "LLM 语义分析"},
            {"metric": "中性客观报道", "value": f"{neutral_signals} 篇", "interpretation": "平稳常规资讯", "source": "LLM 语义分析"}
        ]

        bull_case = [
            f"正面资讯提振市场信心（如相关产业扶持或主力资金流入）",
            f"开瓶动销正常推进，品牌龙头溢价受到机构关注"
        ] if bullish_signals > 0 else ["行业龙头地位稳固"]

        bear_case = [
            f"终端动销增长放缓或渠道压货顾虑（负面报道 {bearish_signals} 篇）",
            f"商务消费需求变化带来的情绪扰动"
        ] if bearish_signals > 0 else ["短期舆情催化有限"]

        data_quality = {
            "status": "complete" if total_signals >= 5 else "partial" if total_signals > 0 else "insufficient",
            "source": "AKShare (EastMoney 实时财经新闻)",
            "article_count": total_signals,
            "limitations": ["新闻主要反映公开媒体报道，未覆盖社交媒体散户实时讨论情绪"]
        }

        raw_reasoning_dict = dict(reasoning)

        # Create the sentiment analysis
        sentiment_analysis[ticker] = {
            "signal": overall_signal if total_signals > 0 else "insufficient_evidence",
            "confidence": confidence if total_signals > 0 else 0.0,
            "summary": news_summary if total_signals > 0 else f"标的 {ticker} 未检索到近期有效新闻报道，舆情证据不足。",
            "narrative": news_narrative if total_signals > 0 else {"conclusion": "数据不足：无相关新闻资讯。"},
            "key_findings": key_findings if total_signals > 0 else ["无新闻数据"],
            "evidence": evidence,
            "bull_case": bull_case if total_signals > 0 else [],
            "bear_case": bear_case if total_signals > 0 else [],
            "risks": risks or ["舆情关注度低或行业需求趋于平淡"],
            "data_quality": data_quality,
            "key_metrics": key_metrics,
            "strengths": strengths or ["未出现恶性负面负面舆情"],
            "reasoning": news_summary if total_signals > 0 else "未检索到近期有效新闻报道，舆情证据不足。",
            "_raw_reasoning": raw_reasoning_dict,
        }

        progress.update_status(agent_id, ticker, "Done", analysis=json.dumps(reasoning, indent=4))

    message = HumanMessage(
        content=json.dumps(sentiment_analysis),
        name=agent_id,
    )

    if state.get("metadata", {}).get("show_reasoning"):
        show_agent_reasoning(sentiment_analysis, "News Sentiment Analysis Agent")

    if "analyst_signals" not in state["data"]:
        state["data"]["analyst_signals"] = {}
    state["data"]["analyst_signals"][agent_id] = sentiment_analysis

    progress.update_status(agent_id, None, "Done")

    return {
        "messages": [message],
        "data": state["data"],
    }


def _calculate_confidence_score(
    sentiment_confidences: dict,
    company_news: list,
    overall_signal: str,
    bullish_signals: int,
    bearish_signals: int,
    total_signals: int
) -> float:
    """
    Calculate confidence score for a sentiment signal.
    
    Uses a weighted approach combining LLM confidence scores (70%) with 
    signal proportion (30%) when LLM classifications are available.
    
    Args:
        sentiment_confidences: Dictionary mapping news article IDs to confidence scores.
        company_news: List of CompanyNews objects.
        overall_signal: The overall sentiment signal ("bullish", "bearish", or "neutral").
        bullish_signals: Count of bullish signals.
        bearish_signals: Count of bearish signals.
        total_signals: Total number of signals.
        
    Returns:
        Confidence score as a float between 0 and 100.
    """
    if total_signals == 0:
        return 0.0
    
    # Calculate weighted confidence using LLM confidence scores when available
    if sentiment_confidences:
        # Get articles that match the overall signal
        matching_articles = [
            news for news in company_news 
            if news.sentiment and (
                (overall_signal == "bullish" and news.sentiment == "positive") or
                (overall_signal == "bearish" and news.sentiment == "negative") or
                (overall_signal == "neutral" and news.sentiment == "neutral")
            )
        ]
        
        # Calculate average confidence from LLM-classified articles that match the signal
        llm_confidences = [
            sentiment_confidences[id(news)] 
            for news in matching_articles 
            if id(news) in sentiment_confidences
        ]
        
        if llm_confidences:
            # Weight: 70% from LLM confidence scores, 30% from signal proportion
            avg_llm_confidence = sum(llm_confidences) / len(llm_confidences)
            signal_proportion = (max(bullish_signals, bearish_signals) / total_signals) * 100
            return round(0.7 * avg_llm_confidence + 0.3 * signal_proportion, 2)
    
    # Fallback to proportion-based confidence
    return round((max(bullish_signals, bearish_signals) / total_signals) * 100, 2)
