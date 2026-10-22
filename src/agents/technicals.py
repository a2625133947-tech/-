import math

from langchain_core.messages import HumanMessage

from src.graph.state import AgentState, show_agent_reasoning
import json
import pandas as pd
import numpy as np

from src.tools.api import get_prices, prices_to_df
from src.utils.progress import progress


def safe_float(value, default=0.0):
    """
    Safely convert a value to float, handling NaN cases
    
    Args:
        value: The value to convert (can be pandas scalar, numpy value, etc.)
        default: Default value to return if the input is NaN or invalid
    
    Returns:
        float: The converted value or default if NaN/invalid
    """
    try:
        if pd.isna(value) or np.isnan(value):
            return default
        return float(value)
    except (ValueError, TypeError, OverflowError):
        return default


##### Technical Analyst #####
def technical_analyst_agent(state: AgentState, agent_id: str = "technical_analyst_agent"):
    """
    Sophisticated technical analysis system that combines multiple trading strategies for multiple tickers:
    1. Trend Following
    2. Mean Reversion
    3. Momentum
    4. Volatility Analysis
    5. Statistical Arbitrage Signals
    """
    data = state["data"]
    start_date = data["start_date"]
    end_date = data["end_date"]
    tickers = data["tickers"]

    # Initialize analysis for each ticker
    technical_analysis = {}

    for ticker in tickers:
        progress.update_status(agent_id, ticker, "Analyzing price data")

        # Get the historical price data
        prices = get_prices(
            ticker=ticker,
            start_date=start_date,
            end_date=end_date,

        )

        if not prices or len(prices) < 5:
            progress.update_status(agent_id, ticker, "Failed: Insufficient price data")
            technical_analysis[ticker] = {
                "signal": "insufficient_evidence",
                "confidence": 0.0,
                "summary": f"标的 {ticker} 历史K线价格数据不足（样本量小于5根），无法进行有效技术形态分析。",
                "narrative": {"conclusion": "数据不足：历史价格K线样本过少。"},
                "key_findings": ["K线样本量不足以支持均线及动量计算"],
                "evidence": [],
                "bull_case": [],
                "bear_case": [],
                "risks": ["缺少连续行情序列，无法评估价格趋势与波动"],
                "data_quality": {"status": "insufficient", "source": "BaoStock", "bars_count": len(prices) if prices else 0, "limitations": ["K线数据缺失"]},
                "key_metrics": {},
                "strengths": [],
                "reasoning": "历史K线价格数据不足，无法进行有效技术形态分析。",
                "_raw_reasoning": {}
            }
            continue

        # Convert prices to a DataFrame
        prices_df = prices_to_df(prices)

        progress.update_status(agent_id, ticker, "Calculating trend signals")
        trend_signals = calculate_trend_signals(prices_df)

        progress.update_status(agent_id, ticker, "Calculating mean reversion")
        mean_reversion_signals = calculate_mean_reversion_signals(prices_df)

        progress.update_status(agent_id, ticker, "Calculating momentum")
        momentum_signals = calculate_momentum_signals(prices_df)

        progress.update_status(agent_id, ticker, "Analyzing volatility")
        volatility_signals = calculate_volatility_signals(prices_df)

        progress.update_status(agent_id, ticker, "Statistical analysis")
        stat_arb_signals = calculate_stat_arb_signals(prices_df)

        # Combine all signals using a weighted ensemble approach
        strategy_weights = {
            "trend": 0.25,
            "mean_reversion": 0.20,
            "momentum": 0.25,
            "volatility": 0.15,
            "stat_arb": 0.15,
        }

        progress.update_status(agent_id, ticker, "Combining signals")
        combined_signal = weighted_signal_combination(
            {
                "trend": trend_signals,
                "mean_reversion": mean_reversion_signals,
                "momentum": momentum_signals,
                "volatility": volatility_signals,
                "stat_arb": stat_arb_signals,
            },
            strategy_weights,
        )

        sec_signals = [
            ("趋势", trend_signals),
            ("均值回归", mean_reversion_signals),
            ("动量", momentum_signals),
            ("波动", volatility_signals),
            ("统计套利", stat_arb_signals),
        ]
        strengths = [label for label, s in sec_signals if s.get("signal") == "bullish"]
        risks = [label for label, s in sec_signals if s.get("signal") == "bearish"]

        key_metrics = {}
        for _, s in sec_signals:
            for m_k, m_v in (s.get("metrics") or {}).items():
                if m_v is not None and not isinstance(m_v, (dict, list)):
                    key_metrics[m_k] = {"value": m_v}

        # Extract core price and indicators for human-readable synthesis
        current_price = float(prices_df["close"].iloc[-1])
        rsi_14 = float(mean_reversion_signals.get("metrics", {}).get("rsi_14", 50.0))
        adx = float(trend_signals.get("metrics", {}).get("adx", 0.0))
        hist_vol = float(volatility_signals.get("metrics", {}).get("historical_volatility", 0.0))
        sma_20 = float(prices_df["close"].rolling(20).mean().iloc[-1]) if len(prices_df) >= 20 else current_price
        upper_bb, lower_bb = calculate_bollinger_bands(prices_df)
        bb_lower_val = float(lower_bb.iloc[-1]) if not lower_bb.empty and not np.isnan(lower_bb.iloc[-1]) else current_price * 0.95
        bb_upper_val = float(upper_bb.iloc[-1]) if not upper_bb.empty and not np.isnan(upper_bb.iloc[-1]) else current_price * 1.05

        trend_desc = "空头下行排列" if trend_signals["signal"] == "bearish" else "多头上行排列" if trend_signals["signal"] == "bullish" else "区间震荡"
        rsi_desc = "处于极度超卖区（具备技术修复反弹诉求）" if rsi_14 < 30 else "处于极度超买区（需防范技术回撤）" if rsi_14 > 70 else "处于中性博弈区间"
        verdict_cn = "技术面偏多（超跌反弹驱动）" if combined_signal["signal"] == "bullish" else "技术面偏空（趋势压制主导）" if combined_signal["signal"] == "bearish" else "技术面中性（多空僵持）"

        tech_summary = (
            f"技术面综合研判：当前收盘价 ¥{current_price:.2f}。整体趋势呈现{trend_desc}，ADX强度达 {adx:.1f}；"
            f"但从均值回归维度看，14日RSI已降至 {rsi_14:.1f}，{rsi_desc}，且价格已逼近布林下轨支撑（¥{bb_lower_val:.2f}）。"
            f"多维加权信号给出【{verdict_cn}】，综合置信度为 {round(combined_signal['confidence'] * 100)}%。"
        )

        tech_narrative = {
            "trend": f"价格位于20日均线（¥{sma_20:.2f}）{'下方' if current_price < sma_20 else '上方'}，ADX趋势强度为 {adx:.1f}，中期形态呈现{trend_desc}。",
            "momentum": f"RSI(14) 录得 {rsi_14:.1f}，{rsi_desc}。近1月动量变化为 {float(momentum_signals.get('metrics', {}).get('momentum_1m', 0.0)):+.1%}。",
            "volatility": f"历史年化波动率为 {hist_vol:.1%}，布林下轨技术支撑位约 ¥{bb_lower_val:.2f}，上轨压力位约 ¥{bb_upper_val:.2f}。",
            "conclusion": tech_summary,
        }

        key_findings = [
            f"最新价格 ¥{current_price:.2f}，对比20日均线（¥{sma_20:.2f}）处于{'偏弱下方' if current_price < sma_20 else '偏强上方'}",
            f"RSI(14) 为 {rsi_14:.1f}，{'已触及深度超卖阈值，存在均值修复弹性' if rsi_14 < 30 else '处于常规常态波动区间'}",
            f"ADX趋势指标为 {adx:.1f}，反映现阶段走势以{trend_desc}为主导",
            f"布林通道区间：支撑位 ¥{bb_lower_val:.2f} ~ 阻力位 ¥{bb_upper_val:.2f}"
        ]

        evidence = [
            {"metric": "收盘价与均线", "value": f"¥{current_price:.2f} (MA20: ¥{sma_20:.2f})", "interpretation": f"价格在MA20{'下方' if current_price < sma_20 else '上方'}", "source": "BaoStock 日K线"},
            {"metric": "14日相对强弱指标 (RSI)", "value": f"{rsi_14:.1f}", "interpretation": rsi_desc, "source": "BaoStock 日K线"},
            {"metric": "ADX 趋势强度", "value": f"{adx:.1f}", "interpretation": f"主趋势为{trend_desc}", "source": "BaoStock 日K线"},
            {"metric": "布林带支撑与阻力", "value": f"下轨 ¥{bb_lower_val:.2f} / 上轨 ¥{bb_upper_val:.2f}", "interpretation": "短期震荡技术边界", "source": "BaoStock 日K线"},
            {"metric": "年化历史波动率", "value": f"{hist_vol:.1%}", "interpretation": "价格波幅水平", "source": "BaoStock 日K线"}
        ]

        bull_case = [
            f"RSI(14) 达到 {rsi_14:.1f} 的超卖低位，具备超跌均值修复空间",
            f"价格紧贴布林下轨 ¥{bb_lower_val:.2f}，技术支撑位具备防守博弈价值"
        ] if rsi_14 < 40 or combined_signal["signal"] == "bullish" else ["短期动量温和上行"]

        bear_case = [
            f"均线系统处于{trend_desc}，上方 MA20 (¥{sma_20:.2f}) 形成明显反压",
            f"ADX 为 {adx:.1f}，空头趋势未完全反转"
        ] if trend_signals["signal"] == "bearish" else ["高位获利盘回吐压力"]

        data_quality = {
            "status": "complete" if len(prices_df) >= 60 else "partial",
            "source": "BaoStock (每日未复权与复权K线)",
            "bars_count": len(prices_df),
            "limitations": ["未考虑日内高频分时与盘口委买委卖委托深度"]
        }

        raw_reasoning_dict = {
            "trend_following": {
                "signal": trend_signals["signal"],
                "confidence": round(trend_signals["confidence"] * 100),
                "metrics": normalize_pandas(trend_signals["metrics"]),
            },
            "mean_reversion": {
                "signal": mean_reversion_signals["signal"],
                "confidence": round(mean_reversion_signals["confidence"] * 100),
                "metrics": normalize_pandas(mean_reversion_signals["metrics"]),
            },
            "momentum": {
                "signal": momentum_signals["signal"],
                "confidence": round(momentum_signals["confidence"] * 100),
                "metrics": normalize_pandas(momentum_signals["metrics"]),
            },
            "volatility": {
                "signal": volatility_signals["signal"],
                "confidence": round(volatility_signals["confidence"] * 100),
                "metrics": normalize_pandas(volatility_signals["metrics"]),
            },
            "statistical_arbitrage": {
                "signal": stat_arb_signals["signal"],
                "confidence": round(stat_arb_signals["confidence"] * 100),
                "metrics": normalize_pandas(stat_arb_signals["metrics"]),
            },
        }

        # Generate detailed analysis report for this ticker
        technical_analysis[ticker] = {
            "signal": combined_signal["signal"],
            "confidence": round(combined_signal["confidence"] * 100),
            "summary": tech_summary,
            "narrative": tech_narrative,
            "key_findings": key_findings,
            "evidence": evidence,
            "bull_case": bull_case,
            "bear_case": bear_case,
            "risks": risks or ["均线空头压制与进一步破位风险"],
            "data_quality": data_quality,
            "key_metrics": key_metrics,
            "strengths": strengths or ["均值回归超卖支撑"],
            "reasoning": tech_summary,
            "_raw_reasoning": raw_reasoning_dict,
        }
        progress.update_status(agent_id, ticker, "Done", analysis=json.dumps(technical_analysis, indent=4))

    # Create the technical analyst message
    message = HumanMessage(
        content=json.dumps(technical_analysis),
        name=agent_id,
    )

    if state["metadata"]["show_reasoning"]:
        show_agent_reasoning(technical_analysis, "Technical Analyst")

    # Add the signal to the analyst_signals list
    state["data"]["analyst_signals"][agent_id] = technical_analysis

    progress.update_status(agent_id, None, "Done")

    return {
        "messages": state["messages"] + [message],
        "data": data,
    }


def calculate_trend_signals(prices_df):
    """
    Advanced trend following strategy using multiple timeframes and indicators
    """
    # Calculate EMAs for multiple timeframes
    ema_8 = calculate_ema(prices_df, 8)
    ema_21 = calculate_ema(prices_df, 21)
    ema_55 = calculate_ema(prices_df, 55)

    # Calculate ADX for trend strength
    adx = calculate_adx(prices_df, 14)

    # Determine trend direction and strength
    short_trend = ema_8 > ema_21
    medium_trend = ema_21 > ema_55

    # Combine signals with confidence weighting
    trend_strength = adx["adx"].iloc[-1] / 100.0

    if short_trend.iloc[-1] and medium_trend.iloc[-1]:
        signal = "bullish"
        confidence = trend_strength
    elif not short_trend.iloc[-1] and not medium_trend.iloc[-1]:
        signal = "bearish"
        confidence = trend_strength
    else:
        signal = "neutral"
        confidence = 0.5

    return {
        "signal": signal,
        "confidence": confidence,
        "metrics": {
            "adx": safe_float(adx["adx"].iloc[-1]),
            "trend_strength": safe_float(trend_strength),
        },
    }


def calculate_mean_reversion_signals(prices_df):
    """
    Mean reversion strategy using statistical measures and Bollinger Bands
    """
    # Calculate z-score of price relative to moving average
    ma_50 = prices_df["close"].rolling(window=50).mean()
    std_50 = prices_df["close"].rolling(window=50).std()
    z_score = (prices_df["close"] - ma_50) / std_50

    # Calculate Bollinger Bands
    bb_upper, bb_lower = calculate_bollinger_bands(prices_df)

    # Calculate RSI with multiple timeframes
    rsi_14 = calculate_rsi(prices_df, 14)
    rsi_28 = calculate_rsi(prices_df, 28)

    # Mean reversion signals
    price_vs_bb = (prices_df["close"].iloc[-1] - bb_lower.iloc[-1]) / (bb_upper.iloc[-1] - bb_lower.iloc[-1])

    # Combine signals
    if z_score.iloc[-1] < -2 and price_vs_bb < 0.2:
        signal = "bullish"
        confidence = min(abs(z_score.iloc[-1]) / 4, 1.0)
    elif z_score.iloc[-1] > 2 and price_vs_bb > 0.8:
        signal = "bearish"
        confidence = min(abs(z_score.iloc[-1]) / 4, 1.0)
    else:
        signal = "neutral"
        confidence = 0.5

    return {
        "signal": signal,
        "confidence": confidence,
        "metrics": {
            "z_score": safe_float(z_score.iloc[-1]),
            "price_vs_bb": safe_float(price_vs_bb),
            "rsi_14": safe_float(rsi_14.iloc[-1]),
            "rsi_28": safe_float(rsi_28.iloc[-1]),
        },
    }


def calculate_momentum_signals(prices_df):
    """
    Multi-factor momentum strategy
    """
    # Price momentum
    returns = prices_df["close"].pct_change()
    mom_1m = returns.rolling(21).sum()
    mom_3m = returns.rolling(63).sum()
    mom_6m = returns.rolling(126).sum()

    # Volume momentum
    volume_ma = prices_df["volume"].rolling(21).mean()
    volume_momentum = prices_df["volume"] / volume_ma

    # Relative strength
    # (would compare to market/sector in real implementation)

    # Calculate momentum score
    momentum_score = (0.4 * mom_1m + 0.3 * mom_3m + 0.3 * mom_6m).iloc[-1]

    # Volume confirmation
    volume_confirmation = volume_momentum.iloc[-1] > 1.0

    if momentum_score > 0.05 and volume_confirmation:
        signal = "bullish"
        confidence = min(abs(momentum_score) * 5, 1.0)
    elif momentum_score < -0.05 and volume_confirmation:
        signal = "bearish"
        confidence = min(abs(momentum_score) * 5, 1.0)
    else:
        signal = "neutral"
        confidence = 0.5

    return {
        "signal": signal,
        "confidence": confidence,
        "metrics": {
            "momentum_1m": safe_float(mom_1m.iloc[-1]),
            "momentum_3m": safe_float(mom_3m.iloc[-1]),
            "momentum_6m": safe_float(mom_6m.iloc[-1]),
            "volume_momentum": safe_float(volume_momentum.iloc[-1]),
        },
    }


def calculate_volatility_signals(prices_df):
    """
    Volatility-based trading strategy
    """
    # Calculate various volatility metrics
    returns = prices_df["close"].pct_change()

    # Historical volatility
    hist_vol = returns.rolling(21).std() * math.sqrt(252)

    # Volatility regime detection
    vol_ma = hist_vol.rolling(63).mean()
    vol_regime = hist_vol / vol_ma

    # Volatility mean reversion
    vol_z_score = (hist_vol - vol_ma) / hist_vol.rolling(63).std()

    # ATR ratio
    atr = calculate_atr(prices_df)
    atr_ratio = atr / prices_df["close"]

    # Generate signal based on volatility regime
    current_vol_regime = vol_regime.iloc[-1]
    vol_z = vol_z_score.iloc[-1]

    if current_vol_regime < 0.8 and vol_z < -1:
        signal = "bullish"  # Low vol regime, potential for expansion
        confidence = min(abs(vol_z) / 3, 1.0)
    elif current_vol_regime > 1.2 and vol_z > 1:
        signal = "bearish"  # High vol regime, potential for contraction
        confidence = min(abs(vol_z) / 3, 1.0)
    else:
        signal = "neutral"
        confidence = 0.5

    return {
        "signal": signal,
        "confidence": confidence,
        "metrics": {
            "historical_volatility": safe_float(hist_vol.iloc[-1]),
            "volatility_regime": safe_float(current_vol_regime),
            "volatility_z_score": safe_float(vol_z),
            "atr_ratio": safe_float(atr_ratio.iloc[-1]),
        },
    }


def calculate_stat_arb_signals(prices_df):
    """
    Statistical arbitrage signals based on price action analysis
    """
    # Calculate price distribution statistics
    returns = prices_df["close"].pct_change()

    # Skewness and kurtosis
    skew = returns.rolling(63).skew()
    kurt = returns.rolling(63).kurt()

    # Test for mean reversion using Hurst exponent
    hurst = calculate_hurst_exponent(prices_df["close"])

    # Correlation analysis
    # (would include correlation with related securities in real implementation)

    # Generate signal based on statistical properties
    if hurst < 0.4 and skew.iloc[-1] > 1:
        signal = "bullish"
        confidence = (0.5 - hurst) * 2
    elif hurst < 0.4 and skew.iloc[-1] < -1:
        signal = "bearish"
        confidence = (0.5 - hurst) * 2
    else:
        signal = "neutral"
        confidence = 0.5

    return {
        "signal": signal,
        "confidence": confidence,
        "metrics": {
            "hurst_exponent": safe_float(hurst),
            "skewness": safe_float(skew.iloc[-1]),
            "kurtosis": safe_float(kurt.iloc[-1]),
        },
    }


def weighted_signal_combination(signals, weights):
    """
    Combines multiple trading signals using a weighted approach
    """
    # Convert signals to numeric values
    signal_values = {"bullish": 1, "neutral": 0, "bearish": -1}

    weighted_sum = 0
    total_confidence = 0

    for strategy, signal in signals.items():
        numeric_signal = signal_values[signal["signal"]]
        weight = weights[strategy]
        confidence = signal["confidence"]

        weighted_sum += numeric_signal * weight * confidence
        total_confidence += weight * confidence

    # Normalize the weighted sum
    if total_confidence > 0:
        final_score = weighted_sum / total_confidence
    else:
        final_score = 0

    # Convert back to signal
    if final_score > 0.2:
        signal = "bullish"
    elif final_score < -0.2:
        signal = "bearish"
    else:
        signal = "neutral"

    return {"signal": signal, "confidence": abs(final_score)}


def normalize_pandas(obj):
    """Convert pandas Series/DataFrames to primitive Python types"""
    if isinstance(obj, pd.Series):
        return obj.tolist()
    elif isinstance(obj, pd.DataFrame):
        return obj.to_dict("records")
    elif isinstance(obj, dict):
        return {k: normalize_pandas(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [normalize_pandas(item) for item in obj]
    return obj


def calculate_rsi(prices_df: pd.DataFrame, period: int = 14) -> pd.Series:
    delta = prices_df["close"].diff()
    gain = (delta.where(delta > 0, 0)).fillna(0)
    loss = (-delta.where(delta < 0, 0)).fillna(0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def calculate_bollinger_bands(prices_df: pd.DataFrame, window: int = 20) -> tuple[pd.Series, pd.Series]:
    sma = prices_df["close"].rolling(window).mean()
    std_dev = prices_df["close"].rolling(window).std()
    upper_band = sma + (std_dev * 2)
    lower_band = sma - (std_dev * 2)
    return upper_band, lower_band


def calculate_ema(df: pd.DataFrame, window: int) -> pd.Series:
    """
    Calculate Exponential Moving Average

    Args:
        df: DataFrame with price data
        window: EMA period

    Returns:
        pd.Series: EMA values
    """
    return df["close"].ewm(span=window, adjust=False).mean()


def calculate_adx(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """
    Calculate Average Directional Index (ADX)

    Args:
        df: DataFrame with OHLC data
        period: Period for calculations

    Returns:
        DataFrame with ADX values
    """
    # Calculate True Range
    df["high_low"] = df["high"] - df["low"]
    df["high_close"] = abs(df["high"] - df["close"].shift())
    df["low_close"] = abs(df["low"] - df["close"].shift())
    df["tr"] = df[["high_low", "high_close", "low_close"]].max(axis=1)

    # Calculate Directional Movement
    df["up_move"] = df["high"] - df["high"].shift()
    df["down_move"] = df["low"].shift() - df["low"]

    df["plus_dm"] = np.where((df["up_move"] > df["down_move"]) & (df["up_move"] > 0), df["up_move"], 0)
    df["minus_dm"] = np.where((df["down_move"] > df["up_move"]) & (df["down_move"] > 0), df["down_move"], 0)

    # Calculate ADX
    df["+di"] = 100 * (df["plus_dm"].ewm(span=period).mean() / df["tr"].ewm(span=period).mean())
    df["-di"] = 100 * (df["minus_dm"].ewm(span=period).mean() / df["tr"].ewm(span=period).mean())
    df["dx"] = 100 * abs(df["+di"] - df["-di"]) / (df["+di"] + df["-di"])
    df["adx"] = df["dx"].ewm(span=period).mean()

    return df[["adx", "+di", "-di"]]


def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Calculate Average True Range

    Args:
        df: DataFrame with OHLC data
        period: Period for ATR calculation

    Returns:
        pd.Series: ATR values
    """
    high_low = df["high"] - df["low"]
    high_close = abs(df["high"] - df["close"].shift())
    low_close = abs(df["low"] - df["close"].shift())

    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)

    return true_range.rolling(period).mean()


def calculate_hurst_exponent(price_series: pd.Series, max_lag: int = 20) -> float:
    """
    Calculate Hurst Exponent to determine long-term memory of time series
    H < 0.5: Mean reverting series
    H = 0.5: Random walk
    H > 0.5: Trending series

    Args:
        price_series: Array-like price data
        max_lag: Maximum lag for R/S calculation

    Returns:
        float: Hurst exponent
    """
    lags = range(2, max_lag)
    # Add small epsilon to avoid log(0)
    tau = [max(1e-8, np.sqrt(np.std(np.subtract(price_series[lag:], price_series[:-lag])))) for lag in lags]

    # Return the Hurst exponent from linear fit
    try:
        reg = np.polyfit(np.log(lags), np.log(tau), 1)
        return reg[0]  # Hurst exponent is the slope
    except (ValueError, RuntimeWarning):
        # Return 0.5 (random walk) if calculation fails
        return 0.5
