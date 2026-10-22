# AI Hedge Fund

This is a proof of concept for an AI-powered hedge fund.  The goal of this project is to explore the use of AI to make trading decisions.  This project is for **educational** purposes only and is not intended for real trading or investment.

This system offers twelve A-share investor-inspired strategy prototypes:

1. 段永平 — long-term business quality and reasonable valuation
2. 邓晓峰 — value and earnings recovery
3. 冯柳 — low expectations and fundamental improvement
4. 傅鹏博 — growth and business quality
5. 朱少醒 — balanced quality, growth, and valuation
6. 张坤 — durable profitability and cash generation
7. 刘彦春 — earnings quality and growth
8. 谢治宇 — growth relative to valuation
9. 董承非 — valuation discipline and financial resilience
10. 王亚伟 — valuation, earnings change, and price trend
11. 陈光明 — quality value and cash flow
12. 林园 — durable profitability, growth, and cash generation

These are project-defined models inspired by public investment ideas. Their factor weights and reports are not the investors' own methods, holdings, or advice. Six functional analysts cover technicals, fundamentals, growth, news sentiment, market sentiment, and valuation. Risk management and portfolio management combine the resulting signals.

<img width="1042" alt="Screenshot 2025-03-22 at 6 19 07 PM" src="https://github.com/user-attachments/assets/cbae3dcf-b571-490d-b0ad-3f0f035ac0d4" />

Note: the system does not actually make any trades.

[![Twitter Follow](https://img.shields.io/twitter/follow/virattt?style=social)](https://twitter.com/virattt)

## Disclaimer

This project is for **educational and research purposes only**.

- Not intended for real trading or investment
- No investment advice or guarantees provided
- Creator assumes no liability for financial losses
- Consult a financial advisor for investment decisions
- Past performance does not indicate future results

By using this software, you agree to use it solely for learning purposes.

## Table of Contents
- [How to Install](#how-to-install)
- [How to Run](#how-to-run)
  - [⌨️ Command Line Interface](#️-command-line-interface)
  - [🖥️ Web Application (NEW!)](#️-web-application)
- [Contributing](#contributing)
- [Feature Requests](#feature-requests)
- [License](#license)

## How to Install

Before you can run the AI Hedge Fund, you'll need to install it and set up your API keys. These steps are common to both the full-stack web application and command line interface.

### 1. Clone the Repository

```bash
git clone https://github.com/virattt/ai-hedge-fund.git
cd ai-hedge-fund
```

### 2. Set Up Your API Keys

Create a `.env` file for your API keys:
```bash
# Create .env file for your API keys (in the root directory)
cp .env.example .env
```

Open and edit the `.env` file to add your API keys:
```bash
# For running LLMs hosted by openai (gpt-4o, gpt-4o-mini, etc.)
OPENAI_API_KEY=your-openai-api-key

# A-share market data uses BaoStock and AKShare; no financial-data API key is needed.
```

**Important**: You must set at least one LLM API key (e.g. `OPENAI_API_KEY`, `GROQ_API_KEY`, `ANTHROPIC_API_KEY`, or `DEEPSEEK_API_KEY`) for the hedge fund to work. 

**Financial Data**: BaoStock provides Shanghai/Shenzhen A-share daily prices and PE/PB/PS; AKShare reads Sina financial statements. Use six-digit A-share codes such as `600519,000001`. No market-data API key is required.

BaoStock prices are unadjusted. Historical financial reports are filtered by Sina announcement date. Market capitalization uses BaoStock close and dated total shares from AKShare's Eastmoney share-capital endpoint; it stays null when either value is unavailable. Insider-trade data is unavailable. See the root README for data coverage details.

## How to Run

### ⌨️ Command Line Interface

For users who prefer working with command line tools, you can run the AI Hedge Fund directly via terminal. This approach offers more granular control and is useful for automation, scripting, and integration purposes.

<img width="992" alt="Screenshot 2025-01-06 at 5 50 17 PM" src="https://github.com/user-attachments/assets/e8ca04bf-9989-4a7d-a8b4-34e04666663b" />

#### Using Docker

1. Make sure you have Docker installed on your system. If not, you can download it from [Docker's official website](https://www.docker.com/get-started).

2. Navigate to the docker directory:
```bash
cd docker
```

3. Build the Docker image:
```bash
# On Linux/Mac:
./run.sh build

# On Windows:
run.bat build
```

#### Running the AI Hedge Fund (with Docker)
```bash
# Navigate to the docker directory first
cd docker

# On Linux/Mac:
./run.sh --ticker 600519,000001 main

# On Windows:
run.bat --ticker 600519,000001 main
```

You can also specify a `--ollama` flag to run the AI hedge fund using local LLMs.

```bash
# With Docker (from docker/ directory):
# On Linux/Mac:
./run.sh --ticker 600519,000001 --ollama main

# On Windows:
run.bat --ticker 600519,000001 --ollama main
```

If you already have an Ollama server running (locally or on your network), point the containers at it instead of starting the bundled instance. You can either pass an explicit base URL or export `OLLAMA_BASE_URL` before running the scripts.

```bash
# Linux / macOS
./run.sh --ticker 600519,000001 --ollama --ollama-base-url http://localhost:11434 main

# Windows
run.bat --ticker 600519,000001 --ollama --ollama-base-url http://localhost:11434 main
```

When `OLLAMA_BASE_URL` is provided, the Docker compose services reuse that endpoint and the Ollama container is not started. To launch the embedded Ollama service manually with Docker Compose, add the `embedded-ollama` profile (e.g. `docker compose --profile embedded-ollama up`).

You can optionally specify the start and end dates to make decisions for a specific time period.

```bash
# With Docker (from docker/ directory):
# On Linux/Mac:
./run.sh --ticker 600519,000001 --start-date 2024-01-01 --end-date 2024-03-01 main

# On Windows:
run.bat --ticker 600519,000001 --start-date 2024-01-01 --end-date 2024-03-01 main
```

#### Running the Backtester (with Docker)
```bash
# Navigate to the docker directory first
cd docker

# On Linux/Mac:
./run.sh --ticker 600519,000001 backtest

# On Windows:
run.bat --ticker 600519,000001 backtest
```

**Example Output:**
<img width="941" alt="Screenshot 2025-01-06 at 5 47 52 PM" src="https://github.com/user-attachments/assets/00e794ea-8628-44e6-9a84-8f8a31ad3b47" />


You can optionally specify the start and end dates to backtest over a specific time period.

```bash
# With Docker (from docker/ directory):
# On Linux/Mac:
./run.sh --ticker 600519,000001 --start-date 2024-01-01 --end-date 2024-03-01 backtest

# On Windows:
run.bat --ticker 600519,000001 --start-date 2024-01-01 --end-date 2024-03-01 backtest
```

You can also specify a `--ollama` flag to run the backtester using local LLMs.
```bash
# With Docker (from docker/ directory):
# On Linux/Mac:
./run.sh --ticker 600519,000001 --ollama backtest

# On Windows:
run.bat --ticker 600519,000001 --ollama backtest
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

**Important**: Please keep your pull requests small and focused.  This will make it easier to review and merge.

## Feature Requests

If you have a feature request, please open an [issue](https://github.com/virattt/ai-hedge-fund/issues) and make sure it is tagged with `enhancement`.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
