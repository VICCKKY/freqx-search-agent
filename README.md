# FreqX Radar: 3-line crypto search agent (AutoGen)

This is the Week 5 Day 2 assignment ("Build an AutoGen Weather News Agent"), adapted for crypto.
Instead of a city's weather, you type a crypto question. The agent searches the live web and
price APIs and answers in **exactly 3 short lines**, each with its source.

The main coin is **FreCx**. People also call it "FreqX" or "Frequency Chain". FreCx is the token of
**Frequency X Chain**, a green Layer-1 blockchain for renewable energy
([frequencychain.org](https://frequencychain.org)).

## Setup (run once)

```bash
cd freqx-search-agent
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # open .env and paste your OpenAI key
```

## Run

```bash
python weather_news.py
```

```
Ask about crypto (e.g. 'FreqX coin rate today'): FreqX coin rate today
---------- ToolCallRequestEvent (crypto_news) ----------
[FunctionCall(... name='get_frecx_price')]
---------- ToolCallExecutionEvent (crypto_news) ----------
[FunctionExecutionResult(content='FreCx price $15.1846 ... WARNING: very low liquidity ...')]
---------- TextMessage (crypto_news) ----------
FreCx is priced at $15.1846 today.
It has low liquidity with only $3,726 and virtually no trades.
This market price is not considered reliable due to these conditions. (GeckoTerminal)
```

The full demo for 4 questions is in [`demo_run.txt`](demo_run.txt). It covers the FreqX rate,
"what is Frequency Chain", today's crypto news, and a weather question that the agent politely
refuses.

## The tools (plain Python functions with type hints and docstrings)

| Tool | Data source | Key needed? |
|---|---|---|
| `search_crypto_news(query)` | **ddgs** (DuckDuckGo) news, falling back to web search | No |
| `get_crypto_price(coin)` | CoinGecko (BTC, ETH, SOL …) | No |
| `get_frecx_price()` | GeckoTerminal, FreCx's Polygon DEX pool | No |

The only key in the project is the OpenAI key, which the LLM needs.

## How this meets the assignment PDF

| PDF requirement | Where it is done |
|---|---|
| Keep all code in a single file named `weather_news.py` | `weather_news.py` is the only code file |
| Install `ddgs` for search, no API key | `search_crypto_news` uses `DDGS().news(...)`; `ddgs` is in `requirements.txt` |
| Search function with type hints and a docstring | All 3 tools have `(x: str) -> str` hints and docstrings that say *when* to use them |
| Pass it to the agent in `tools=[...]` | `tools=[search_crypto_news, get_crypto_price, get_frecx_price]` |
| `reflect_on_tool_use=True` | Set on the `AssistantAgent`, so the agent writes 3 lines instead of dumping raw JSON |
| Ask the user with `input()`, reply in exactly 3 short lines | `input("Ask about crypto ...")` plus the system message rule "EXACTLY 3 short lines" |
| Close the model client, keep the API key in an env variable | `await model_client.close()`; the key is `OPENAI_API_KEY` in `.env` (git-ignored) |
| Use `Console(agent.run_stream(...))` | Used in `main()`, so the tool call is visible in the output |
| Final output shows the tool call and changes per input | See `demo_run.txt`: each question calls a different tool and gets different lines |

**Adaptation:** "city" became "crypto question". Two price tools were added next to the ddgs
search, because news search alone can't give a live coin price.

## Agent rules (system message)

- It only covers crypto, blockchain and finance news. Anything else gets one polite line.
- It always calls a tool before answering and never answers from memory.
- "FreqX", "FreCx" and "Frequency Chain" all map to FreCx.
- It never says buy, sell or hold. It only reports news and prices.

## Honest notes on FreCx data (checked 2026-11-02)

- FreCx is **not listed on CoinGecko or CoinMarketCap**.
- The only live price comes from a small Polygon DEX pool: about $3.7k liquidity and roughly
  zero trades a day. So the ~$15 quote is **not a reliable market price**, and the agent says so.
- Very few news sites cover FreCx, so the agent falls back to DuckDuckGo web search
  (frequencychain.org and its docs).
- FreCx is a different project from **Frequency (FRQCY)**, the Polkadot social-media chain.

## What to submit (from the PDF)

1. A screenshot showing the tool call and the 3-line reply (run `python weather_news.py`).
2. `weather_news.py` pushed to GitHub, with the link shared in WhatsApp. `.env` is git-ignored,
   so your key stays private.
3. A screen-recorded video of the agent running, posted in the community.
