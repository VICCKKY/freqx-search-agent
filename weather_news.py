"""
Week 5 Day 2 - AutoGen "Weather News" agent, adapted into a 3-line CRYPTO search engine.
Focus coin: FreCx (people also say "FreqX" / "Frequency Chain") - token of Frequency X Chain.

Run:  python weather_news.py
"""

import asyncio
import time

import requests
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.ui import Console
from autogen_ext.models.openai import OpenAIChatCompletionClient
from ddgs import DDGS
from dotenv import load_dotenv

load_dotenv()  # reads OPENAI_API_KEY from the .env file into the environment

# FreCx bridged token on Polygon + its only DEX pool (checked 2026-11-02)
FRECX_TOKEN = "0xaba6872eaae08a8dc61bd080731e8bcdcfbce6f1"
FRECX_POOL = "https://www.geckoterminal.com/polygon_pos/pools/0x70a4677ad9ec521609ec609742b44f177fda68ff77cc80641514b01a67de54a6"

_cache = {}  # url -> (time, json). Free price APIs rate-limit us, so reuse answers for 60s.


def get_json(url: str, params: dict | None = None) -> dict | None:
    """Fetch JSON from a free API. Retries when rate-limited; returns None if it still fails."""
    key = url + str(params)
    if key in _cache and time.time() - _cache[key][0] < 60:
        return _cache[key][1]
    for wait in (0, 3, 8):  # try now, then after 3s, then after 8s
        time.sleep(wait)
        resp = requests.get(url, params=params, headers={"Accept": "application/json"}, timeout=15)
        if resp.status_code == 200:
            _cache[key] = (time.time(), resp.json())
            return resp.json()
    return None


def search_crypto_news(query: str) -> str:
    """Search TODAY's live web news about cryptocurrency with DuckDuckGo.
    Use it for any crypto question: market news, a coin's latest updates, or FreCx /
    FreqX / Frequency X Chain project info. `query` is a short search phrase,
    e.g. "bitcoin news today" or "FreCx Frequency X Chain"."""
    try:
        results = DDGS().news(query=query, max_results=5)
    except Exception:
        results = []
    if not results:  # small coins like FreCx have little news -> fall back to web search
        try:
            results = DDGS().text(query=query, max_results=5)
        except Exception:
            return f"No results found for '{query}'."
    return str(results)


def get_crypto_price(coin: str) -> str:
    """Get the LIVE price (USD and INR) and 24h change of a cryptocurrency from CoinGecko.
    `coin` is a name or symbol like "bitcoin", "ETH" or "solana".
    For FreCx / FreqX / Frequency Chain use get_frecx_price instead."""
    found = get_json("https://api.coingecko.com/api/v3/search", {"query": coin})
    if found is None:
        return "PRICE UNAVAILABLE right now (CoinGecko rate limit). Ask again in a minute."
    if not found.get("coins"):
        return f"'{coin}' is not listed on CoinGecko."
    coin_id = found["coins"][0]["id"]
    price = get_json(
        "https://api.coingecko.com/api/v3/simple/price",
        {"ids": coin_id, "vs_currencies": "usd,inr", "include_24hr_change": "true"},
    )
    if not price or coin_id not in price:
        return "PRICE UNAVAILABLE right now (CoinGecko rate limit). Ask again in a minute."
    return f"{coin_id}: {price[coin_id]} | source: https://www.coingecko.com/en/coins/{coin_id}"


def get_frecx_price() -> str:
    """Get the LIVE price of FreCx (also called FreqX / Frequency Chain token) from its
    Polygon DEX pool on GeckoTerminal, with liquidity and 24h trading volume.
    FreCx is NOT listed on CoinGecko or CoinMarketCap."""
    url = f"https://api.geckoterminal.com/api/v2/networks/polygon_pos/tokens/{FRECX_TOKEN}/pools"
    data = get_json(url)
    if not data or not data.get("data"):
        return "FreCx PRICE UNAVAILABLE right now (GeckoTerminal rate limit). Ask again in a minute."
    pool = max(data["data"], key=lambda p: float(p["attributes"]["reserve_in_usd"] or 0))["attributes"]
    liquidity = float(pool["reserve_in_usd"] or 0)
    volume = float(pool["volume_usd"]["h24"] or 0)
    note = ""
    if liquidity < 50_000 or volume < 1_000:
        note = " WARNING: very low liquidity and almost no trades, so this is NOT a reliable market price."
    return (
        f"FreCx price ${float(pool['base_token_price_usd']):.4f}, 24h change "
        f"{pool['price_change_percentage']['h24']}%, liquidity ${liquidity:,.0f}, "
        f"24h volume ${volume:,.0f}.{note} source: {FRECX_POOL}"
    )


SYSTEM_MESSAGE = """You are a 3-line crypto search engine.
- Only answer questions about cryptocurrency, blockchain or crypto/finance news.
  For anything else, politely say in ONE line that you only cover crypto.
- For every crypto question, call at least one tool BEFORE answering. Never answer
  from memory, even for "what is X" questions: search for it with search_crypto_news.
- "FreqX", "FreCx" and "Frequency Chain" all mean FreCx (Frequency X Chain, a green
  Layer-1 blockchain for renewable energy). Use get_frecx_price for its price and
  search_crypto_news("FreCx Frequency X Chain") for project info and updates.
- Reply in EXACTLY 3 short lines, one fact per line, separated by line breaks.
  Put the source in brackets at the END of each line, e.g. "... (CoinDesk)".
  Never add a 4th line for sources.
- If a tool returns a price, ALWAYS report that exact price, even when it has a
  low-liquidity warning (then mention the warning too).
- If a tool says PRICE UNAVAILABLE, say that and ask the user to try again in a minute.
  NEVER invent or estimate a price.
- Never tell the user to buy, sell or hold. Only report news and prices."""


def build_agent(model_client: OpenAIChatCompletionClient) -> AssistantAgent:
    """Create the agent. Also used by the Streamlit web app (app.py)."""
    return AssistantAgent(
        name="crypto_news",
        model_client=model_client,
        tools=[search_crypto_news, get_crypto_price, get_frecx_price],
        system_message=SYSTEM_MESSAGE,
        reflect_on_tool_use=True,  # write a 3-line answer from the results, not raw output
    )


async def main():
    query = input("Ask about crypto (e.g. 'FreqX coin rate today'): ")
    model_client = OpenAIChatCompletionClient(model="gpt-4o-mini", temperature=0)  # key from OPENAI_API_KEY
    agent = build_agent(model_client)
    await Console(agent.run_stream(task=f"Answer in exactly 3 short lines: {query}"))
    await model_client.close()


if __name__ == "__main__":  # runs only with "python weather_news.py", not when app.py imports it
    asyncio.run(main())
