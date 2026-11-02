"""
FreqX Radar - browser UI for the crypto agent, in the "ChainPulse" design language
(dark luxury, neumorphic cards, gold/silver/bronze top-3, XP + streak for READING news).

Run:  streamlit run app.py
"""

import asyncio
import html
import json
import warnings
from datetime import date, datetime, timedelta
from pathlib import Path

import streamlit as st
from autogen_agentchat.messages import ToolCallExecutionEvent, ToolCallRequestEvent
from autogen_ext.models.openai import OpenAIChatCompletionClient

from weather_news import FRECX_TOKEN, build_agent, get_json

warnings.filterwarnings("ignore", message="Pydantic serializer warnings")
st.set_page_config(page_title="FreqX Radar", page_icon="📡", layout="centered")

# ---------------------------------------------------------------- design tokens (from the spec)
TOKENS = {
    "Dark": dict(bg="#0B0B0D", surface="#16161A", raised="#1E1E24", text="#F5F5F7", text2="#9A9AA5",
                 gold="#D4AF6A", silver="#C0C4CC", bronze="#B5794A", bull="#3DDC97", bear="#FF6B6B",
                 neutral="#8AA4FF", line="rgba(255,255,255,0.06)",
                 shadow="0 8px 24px rgba(0,0,0,0.6), inset 0 1px 0 rgba(255,255,255,0.04)"),
    "Light": dict(bg="#F6F5F2", surface="#FFFFFF", raised="#EFEDE8", text="#111114", text2="#5E5E68",
                  gold="#A8833E", silver="#7D828C", bronze="#8C5A33", bull="#159A63", bear="#D64545",
                  neutral="#4C6FE0", line="rgba(17,17,20,0.08)", shadow="0 4px 16px rgba(17,17,20,0.08)"),
}
LEVELS = [(0, "Genesis"), (100, "Node"), (250, "Validator"), (500, "Block Explorer"),
          (900, "Chain Scholar"), (1400, "Protocol Sage")]
XP = {"search": 5, "read": 15, "quest": 50}
DAILY_XP_CAP = 200  # rewards reading quality, not endless scrolling
TRENDING = ["FreqX coin rate today", "What is Frequency Chain?", "Today's crypto news",
            "Ethereum ETF", "RBI crypto tax", "Bitcoin price"]

# ---------------------------------------------------------------- progress (saved in a small local file)
# kept in your home folder, outside iCloud-synced Documents, so reads never stall
PROGRESS_FILE = Path.home() / ".freqx_radar" / "progress.json"
DEFAULT = {"xp": 0, "xp_by_day": {}, "read_urls": [], "reads": 0, "searches": 0, "saved": [],
           "quest_days": [], "queries": [], "early_bird": False, "theme": "Dark"}


def load_progress() -> dict:
    try:
        return {**DEFAULT, **json.loads(PROGRESS_FILE.read_text())}
    except (OSError, ValueError):
        return dict(DEFAULT)


def save_progress() -> None:
    try:
        PROGRESS_FILE.parent.mkdir(exist_ok=True)
        PROGRESS_FILE.write_text(json.dumps(P, indent=1))
    except OSError:
        pass  # disk full etc. - progress still lives in this browser session


if "p" not in st.session_state:
    st.session_state.p = load_progress()
P = st.session_state.p
TODAY = date.today().isoformat()


def add_xp(amount: int) -> int:
    """Give XP, but never more than the daily cap. Returns what was actually given."""
    today_xp = P["xp_by_day"].get(TODAY, 0)
    gained = max(0, min(amount, DAILY_XP_CAP - today_xp))
    P["xp"] += gained
    P["xp_by_day"][TODAY] = today_xp + gained
    save_progress()
    return gained


def level_info(xp: int):
    idx = max(i for i, (need, _) in enumerate(LEVELS) if xp >= need)
    start = LEVELS[idx][0]
    end = LEVELS[idx + 1][0] if idx + 1 < len(LEVELS) else start + 600
    return idx + 1, LEVELS[idx][1], (xp - start) / (end - start), end


def streak_days() -> int:
    days = set(d for d, v in P["xp_by_day"].items() if v > 0)
    day, count = date.today(), 0
    if day.isoformat() not in days:
        day -= timedelta(days=1)  # streak is still alive if you read yesterday
    while day.isoformat() in days:
        count, day = count + 1, day - timedelta(days=1)
    return count


def reads_today() -> int:
    return sum(1 for u in P["read_urls"] if u.startswith(TODAY + "|"))


# ---------------------------------------------------------------- theme CSS
T = TOKENS[P["theme"]]
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700;800&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@500;700&display=swap');
:root {{ --bg:{T['bg']}; --surface:{T['surface']}; --raised:{T['raised']}; --text:{T['text']};
  --text2:{T['text2']}; --gold:{T['gold']}; --silver:{T['silver']}; --bronze:{T['bronze']};
  --bull:{T['bull']}; --bear:{T['bear']}; --neutral:{T['neutral']}; --line:{T['line']}; --shadow:{T['shadow']}; }}
.stApp, [data-testid="stAppViewContainer"] {{ background: var(--bg); color: var(--text); font-family: 'Inter', sans-serif; }}
[data-testid="stHeader"], [data-testid="stToolbar"], #MainMenu, footer {{ display: none; }}
.block-container {{ max-width: 480px; padding: 16px 16px 48px; }}
p, li, label, span, div {{ color: var(--text); }}
h1, h2, h3, .serif {{ font-family: 'Playfair Display', serif; color: var(--text); letter-spacing: -0.01em; }}
.mono {{ font-family: 'JetBrains Mono', monospace; font-variant-numeric: tabular-nums; }}
.muted {{ color: var(--text2) !important; }}

/* widgets */
[data-testid="stTextInput"] input {{ background: var(--surface); color: var(--text); border: 1px solid var(--line);
  border-radius: 16px; padding: 14px 16px; font-size: 15px; box-shadow: var(--shadow); }}
[data-testid="stTextInput"] input::placeholder {{ color: var(--text2); }}
.stButton button, .stFormSubmitButton button, .stLinkButton a {{ background: var(--raised); color: var(--text);
  border: 1px solid var(--line); border-radius: 14px; font-weight: 600; transition: transform .15s; }}
.stButton button:hover, .stLinkButton a:hover {{ border-color: var(--gold); color: var(--text); transform: translateY(-1px); }}
.stFormSubmitButton button {{ background: var(--gold); color: #111114; border: none; }}
.stFormSubmitButton button p {{ color: #111114; }}
[data-testid="stForm"] {{ border: none; padding: 0; }}
/* keep card action buttons side by side on phones (Streamlit stacks columns below 640px) */
[data-testid="stHorizontalBlock"] {{ flex-wrap: nowrap !important; gap: 8px; }}
[data-testid="stColumn"], [data-testid="column"] {{ min-width: 0 !important; width: auto !important; flex: 1 1 0 !important; }}
.stButton button p, .stLinkButton a p {{ font-size: 13px; white-space: nowrap; }}
/* nav fits one row on a 375px phone */
.st-key-tab [data-testid="stButtonGroup"] > div {{ flex-wrap: nowrap; gap: 4px; }}
.st-key-tab button {{ flex: 1 1 0; min-width: 0; padding: 4px 6px; min-height: 36px; }}
.st-key-tab button p {{ font-size: 12px; white-space: nowrap; }}
[data-testid="stExpander"] {{ background: var(--surface); border: 1px solid var(--line); border-radius: 16px; }}
[data-testid="stExpander"] summary p {{ color: var(--text2); }}
[data-testid="stPills"] button, [data-testid="stButtonGroup"] button {{ background: var(--surface); color: var(--text);
  border: 1px solid var(--line); border-radius: 999px; }}
[data-testid="stButtonGroup"] button[aria-checked="true"], [data-testid="stButtonGroup"] button[kind*="Active"] {{
  border-color: var(--gold); color: var(--gold); }}

/* cards */
.card {{ background: var(--surface); border: 1px solid var(--line); border-radius: 20px; padding: 16px;
  box-shadow: var(--shadow); margin-bottom: 8px; }}
.topbar {{ display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 16px; }}
.avatar {{ width: 44px; height: 44px; border-radius: 50%; display: grid; place-items: center; }}
.avatar span {{ width: 36px; height: 36px; border-radius: 50%; background: var(--raised); display: grid;
  place-items: center; font-weight: 700; font-family: 'JetBrains Mono', monospace; }}
.stat {{ background: var(--surface); border: 1px solid var(--line); border-radius: 999px; padding: 6px 12px;
  font-family: 'JetBrains Mono', monospace; font-size: 13px; }}
.flame {{ display: inline-block; animation: pulse 1.6s ease-in-out infinite; }}
@keyframes pulse {{ 50% {{ transform: scale(1.18); }} }}
.hero {{ font-family: 'Playfair Display', serif; font-size: 28px; font-weight: 800; line-height: 1.15; margin: 4px 0 4px; }}
.hero em {{ color: var(--gold); font-style: normal; }}
.ticker {{ display: flex; gap: 8px; overflow-x: auto; margin: 8px 0 16px; }}
.tick {{ flex: 0 0 auto; background: var(--surface); border: 1px solid var(--line); border-radius: 12px;
  padding: 8px 12px; font-family: 'JetBrains Mono', monospace; font-size: 12px; }}
.up {{ color: var(--bull) !important; }} .down {{ color: var(--bear) !important; }}
.bar {{ height: 6px; border-radius: 99px; background: var(--raised); overflow: hidden; }}
.bar i {{ display: block; height: 100%; background: var(--gold); border-radius: 99px; }}

/* top-3 rank cards */
.rank {{ position: relative; border-left: 4px solid var(--edge); animation: flip .38s ease-out both; }}
.rank.r1 {{ --edge: var(--gold); padding: 20px 16px; }}
.rank.r2 {{ --edge: var(--silver); animation-delay: .12s; }}
.rank.r3 {{ --edge: var(--bronze); animation-delay: .24s; }}
@keyframes flip {{ from {{ opacity: 0; transform: perspective(600px) rotateX(-70deg); }} to {{ opacity: 1; transform: none; }} }}
.badge-rank {{ font-family: 'JetBrains Mono', monospace; font-weight: 700; color: var(--edge); font-size: 13px; }}
.headline {{ font-weight: 700; font-size: 16px; line-height: 1.35; margin: 6px 0; }}
.r1 .headline {{ font-family: 'Playfair Display', serif; font-size: 20px; }}
.meta {{ font-size: 12px; color: var(--text2); display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }}
.meta img {{ width: 14px; height: 14px; border-radius: 3px; }}
.summary {{ font-size: 14px; color: var(--text2); margin: 8px 0; display: -webkit-box; -webkit-line-clamp: 3;
  -webkit-box-orient: vertical; overflow: hidden; }}
.tag {{ font-size: 11px; font-weight: 700; padding: 2px 8px; border-radius: 999px; border: 1px solid currentColor; }}
.Bullish {{ color: var(--bull) !important; }} .Bearish {{ color: var(--bear) !important; }} .Neutral {{ color: var(--neutral) !important; }}

/* loader */
.loader {{ text-align: center; padding: 32px 0; }}
.chain {{ display: flex; justify-content: center; gap: 6px; margin-bottom: 12px; }}
.chain i {{ width: 18px; height: 18px; border-radius: 5px; background: var(--gold); opacity: .25; animation: link 1.2s infinite; }}
.chain i:nth-child(2) {{ animation-delay: .2s; }} .chain i:nth-child(3) {{ animation-delay: .4s; }} .chain i:nth-child(4) {{ animation-delay: .6s; }}
@keyframes link {{ 40% {{ opacity: 1; transform: translateY(-4px); }} }}
.status::after {{ content: 'Scanning sources…'; color: var(--text2); animation: status 3.6s steps(1) infinite; }}
@keyframes status {{ 33% {{ content: 'Ranking relevance…'; }} 66% {{ content: 'Picking top 3…'; }} }}

/* rewards */
.ring {{ width: 92px; height: 92px; border-radius: 50%; display: grid; place-items: center; }}
.ring span {{ width: 76px; height: 76px; border-radius: 50%; background: var(--surface); display: grid; place-items: center;
  font-family: 'JetBrains Mono', monospace; font-weight: 700; font-size: 20px; }}
.badges {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }}
.bdg {{ text-align: center; padding: 12px 6px; font-size: 12px; font-weight: 600; }}
.bdg b {{ display: block; font-size: 26px; margin-bottom: 4px; }}
.bdg.locked {{ opacity: .35; filter: grayscale(1); }}
.heat {{ display: grid; grid-template-columns: repeat(7, 1fr); gap: 4px; }}
.heat i {{ aspect-ratio: 1; border-radius: 4px; background: var(--raised); }}
.disclaimer {{ text-align: center; font-size: 12px; color: var(--text2) !important; margin-top: 24px; }}
</style>
""", unsafe_allow_html=True)


def esc(text: str) -> str:
    """Escape text for HTML; '&#36;' stops Streamlit reading $...$ as a math formula."""
    return html.escape(str(text)).replace("$", "&#36;")


def ui(markup: str) -> None:
    # strip indentation so Markdown doesn't turn indented HTML into a code block
    st.markdown("\n".join(line.strip() for line in markup.splitlines()), unsafe_allow_html=True)


# ---------------------------------------------------------------- top bar: level ring, XP, streak
lvl, lvl_name, lvl_pct, _ = level_info(P["xp"])
ui(f"""
<div class="topbar">
  <div style="display:flex;align-items:center;gap:10px">
    <div class="avatar" style="background:conic-gradient(var(--gold) {lvl_pct*360:.0f}deg, var(--raised) 0)"><span>L{lvl}</span></div>
    <div><div class="serif" style="font-size:18px;font-weight:800">FreqX Radar</div>
    <div class="muted" style="font-size:12px">Level {lvl} · {lvl_name}</div></div>
  </div>
  <div style="display:flex;gap:6px">
    <span class="stat">✦ {P['xp']} XP</span><span class="stat"><span class="flame">🔥</span> {streak_days()}</span>
  </div>
</div>""")

tab = st.segmented_control("nav", ["Search", "Saved", "Rewards", "Profile"],
                           default="Search", label_visibility="collapsed", key="tab", width="stretch") or "Search"


# ---------------------------------------------------------------- live data helpers
@st.cache_data(ttl=60)
def ticker_data():
    coins = get_json("https://api.coingecko.com/api/v3/simple/price",
                     {"ids": "bitcoin,ethereum,solana", "vs_currencies": "usd", "include_24hr_change": "true"}) or {}
    rows = [(sym, coins[cid]["usd"], coins[cid].get("usd_24h_change") or 0)
            for sym, cid in [("BTC", "bitcoin"), ("ETH", "ethereum"), ("SOL", "solana")] if cid in coins]
    pools = get_json(f"https://api.geckoterminal.com/api/v2/networks/polygon_pos/tokens/{FRECX_TOKEN}/pools")
    if pools and pools.get("data"):
        a = max(pools["data"], key=lambda p: float(p["attributes"]["reserve_in_usd"] or 0))["attributes"]
        rows.append(("FRECX*", float(a["base_token_price_usd"]), float(a["price_change_percentage"]["h24"] or 0)))
    return rows


async def run_search(question: str):
    """Ask the AutoGen agent for 3 cards. Returns (result, tool calls, cards dropped as unverified)."""
    model_client = OpenAIChatCompletionClient(model="gpt-4o-mini", temperature=0)
    agent = build_agent(model_client, top3_cards=True)
    result = await agent.run(task=question)
    await model_client.close()

    calls, tool_text = [], ""
    for msg in result.messages:
        if isinstance(msg, ToolCallRequestEvent):
            calls += [f"{c.name}({c.arguments})" for c in msg.content]
        if isinstance(msg, ToolCallExecutionEvent):
            tool_text += " ".join(r.content for r in msg.content)

    answer = result.messages[-1].content
    if isinstance(answer, str):  # model answered without the card format
        return {"on_topic": False, "message": answer, "cards": []}, calls, 0
    answer = answer.model_dump()
    # never show a fake result: keep only cards whose link really came from a tool
    real = [c for c in answer["cards"] if c["url"] and c["url"] in tool_text][:3]
    dropped = len(answer["cards"][:3]) - len(real)
    answer["cards"] = real
    return answer, calls, dropped


def do_search(question: str) -> None:
    holder = st.empty()
    with holder.container():
        ui('<div class="card loader"><div class="chain"><i></i><i></i><i></i><i></i></div><div class="status"></div></div>')
    try:
        answer, calls, dropped = asyncio.run(run_search(question))
        st.session_state.results = {"q": question, "answer": answer, "calls": calls, "dropped": dropped,
                                    "error": None}
        if answer["on_topic"]:
            P["searches"] += 1
            P["queries"] = (P["queries"] + [question.lower()])[-50:]
            add_xp(XP["search"])
    except Exception as exc:  # network error card - never a fake result
        st.session_state.results = {"q": question, "error": str(exc)[:160]}
    holder.empty()


def favicon(url: str) -> str:
    host = url.split("/")[2] if url.startswith("http") else ""
    return f'<img src="https://www.google.com/s2/favicons?domain={host}&sz=32" alt="">' if host else ""


def render_card(card: dict, rank: int, key: str) -> None:
    labels = {1: "#1 · TOP STORY", 2: "#2", 3: "#3"}
    ui(f"""
    <div class="card rank r{rank}">
      <div style="display:flex;justify-content:space-between;align-items:center">
        <span class="badge-rank">{labels[rank]}</span>
        <span class="tag {card['sentiment']}">{card['sentiment']}</span>
      </div>
      <div class="headline">{esc(card['headline'])}</div>
      <div class="meta">{favicon(card['url'])}<b>{esc(card['source'])}</b><span>·</span><span class="mono">{esc(card['published'][:16])}</span></div>
      <div class="summary">{esc(card['summary'])}</div>
      <div class="meta" style="justify-content:space-between"><span>Relevance</span><span class="mono">{card['relevance']}%</span></div>
      <div class="bar"><i style="width:{max(0, min(card['relevance'], 100))}%"></i></div>
    </div>""")
    c1, c2, c3 = st.columns([1.3, 1.2, 1])
    c1.link_button("Read source ↗", card["url"], use_container_width=True)
    already = any(u.endswith("|" + card["url"]) for u in P["read_urls"])
    if c2.button("✓ Read" if already else "✓ I read it", key=f"r{key}", disabled=already, use_container_width=True):
        P["read_urls"].append(f"{TODAY}|{card['url']}")
        P["reads"] += 1
        if datetime.now().hour < 8:
            P["early_bird"] = True
        gained = add_xp(XP["read"])
        if reads_today() >= 3 and TODAY not in P["quest_days"]:
            P["quest_days"].append(TODAY)
            gained += add_xp(XP["quest"])
            st.balloons()
        save_progress()
        st.toast(f"+{gained} XP · Story read" if gained else "Daily XP cap reached - nice reading!")
        st.rerun()
    saved = any(s["url"] == card["url"] for s in P["saved"])
    if c3.button("★" if saved else "☆ Save", key=f"s{key}", use_container_width=True):
        P["saved"] = [s for s in P["saved"] if s["url"] != card["url"]] if saved else P["saved"] + [card]
        save_progress()
        st.rerun()


# ================================================================ SEARCH
if tab == "Search":
    ui('<div class="hero">Only the <em>3 stories</em><br>that matter.</div>'
       '<div class="muted" style="font-size:14px;margin-bottom:12px">Live crypto search · focus on FreCx (FreqX / Frequency X Chain)</div>')

    with st.form("search", clear_on_submit=False, border=False):
        q = st.text_input("q", placeholder="Ask anything about crypto…", label_visibility="collapsed")
        submitted = st.form_submit_button("Search  ✦", use_container_width=True)

    def pick_trending():
        st.session_state.pending = st.session_state.trend
        st.session_state.trend = None

    st.pills("Trending", TRENDING, key="trend", on_change=pick_trending, label_visibility="collapsed")

    question = q.strip() if submitted else st.session_state.pop("pending", None)
    if question:
        do_search(question)
        st.rerun()  # redraw so the top bar shows the new XP

    res = st.session_state.get("results")
    if res:
        st.markdown(f"<div class='muted' style='font-size:13px;margin:12px 0 8px'>Top results for "
                    f"<b>“{esc(res['q'])}”</b></div>", unsafe_allow_html=True)
        if res.get("error"):
            ui(f'<div class="card"><b>Network error</b><div class="muted" style="font-size:13px">{esc(res["error"])}</div></div>')
            if st.button("↻ Retry"):
                st.session_state.pending = res["q"]
                st.rerun()
        elif not res["answer"]["on_topic"] or not res["answer"]["cards"]:
            ui(f'<div class="card" style="text-align:center"><div style="font-size:32px">🧭</div>'
               f'<b>{esc(res["answer"]["message"] or "No verified results found.")}</b>'
               f'<div class="muted" style="font-size:13px">Try a coin name or topic, like the chips above.</div></div>')
        else:
            for i, card in enumerate(res["answer"]["cards"], start=1):
                render_card(card, i, f"{res['q']}{i}")
            if res["dropped"]:
                st.caption(f"{res['dropped']} result(s) hidden because their source link could not be verified.")
            with st.expander("Show why these results"):
                st.markdown("The AutoGen agent called these tools, then ranked what they returned by relevance:")
                for call in res["calls"]:
                    st.code(call, language=None)

    # daily quest
    done = min(reads_today(), 3)
    ui(f"""
    <div class="card" style="margin-top:16px">
      <div style="display:flex;justify-content:space-between"><b>🎯 Daily Quest</b><span class="mono" style="color:var(--gold)">+50 XP</span></div>
      <div class="muted" style="font-size:13px;margin:4px 0 8px">Read 3 stories today</div>
      <div class="bar"><i style="width:{done/3*100:.0f}%"></i></div>
      <div class="mono muted" style="font-size:12px;margin-top:6px">{done}/3 {'· complete ✓' if TODAY in P['quest_days'] else ''}</div>
    </div>""")

    # market ticker - information only, no buy/sell buttons
    rows = ticker_data()
    if rows:
        ticks = "".join(
            f'<div class="tick"><b>{sym}</b> &#36;{price:,.2f} <span class="{"up" if ch >= 0 else "down"}">{ch:+.1f}%</span></div>'
            for sym, price, ch in rows)
        ui(f'<div class="ticker">{ticks}</div>')
        st.caption("*FRECX: tiny Polygon pool with almost no trades — not a reliable market price.")

# ================================================================ SAVED
elif tab == "Saved":
    ui('<div class="hero" style="font-size:24px">Saved stories</div>')
    if not P["saved"]:
        ui('<div class="card" style="text-align:center"><div style="font-size:32px">☆</div>'
           '<b>Nothing saved yet</b><div class="muted" style="font-size:13px">Tap ☆ Save on any result.</div></div>')
    for i, card in enumerate(reversed(P["saved"])):
        ui(f"""<div class="card"><div class="headline">{esc(card['headline'])}</div>
        <div class="meta">{favicon(card['url'])}<b>{esc(card['source'])}</b><span>·</span><span class="mono">{esc(card['published'][:16])}</span></div>
        <div class="summary">{esc(card['summary'])}</div></div>""")
        a, b = st.columns(2)
        a.link_button("Read source ↗", card["url"], use_container_width=True)
        if b.button("Remove", key=f"rm{i}", use_container_width=True):
            P["saved"] = [s for s in P["saved"] if s["url"] != card["url"]]
            save_progress()
            st.rerun()

# ================================================================ REWARDS
elif tab == "Rewards":
    lvl, lvl_name, pct, nxt = level_info(P["xp"])
    ui(f"""
    <div class="card" style="display:flex;gap:16px;align-items:center">
      <div class="ring" style="background:conic-gradient(var(--gold) {pct*360:.0f}deg, var(--raised) 0)"><span>L{lvl}</span></div>
      <div><div class="muted" style="font-size:12px">LEVEL {lvl}</div>
      <div class="serif" style="font-size:22px;font-weight:800">{lvl_name}</div>
      <div class="mono muted" style="font-size:12px">{P['xp']} / {nxt} XP · today {P['xp_by_day'].get(TODAY, 0)}/{DAILY_XP_CAP}</div></div>
    </div>""")

    qs = " ".join(P["queries"])
    badges = [
        ("🔥", "7-Day Streak", streak_days() >= 7),
        ("🔍", "Fact Checker", P["reads"] >= 10),
        ("⚖️", "Regulation Watcher", any(w in qs for w in ["regulation", "tax", "rbi", "sec ", "law", "ban"])),
        ("🧪", "DeFi Scholar", "defi" in qs),
        ("🌅", "Early Bird", P["early_bird"]),
        ("⛓", "Genesis Search", P["searches"] >= 1),
    ]
    cells = "".join(f'<div class="card bdg {"" if ok else "locked"}"><b>{icon if ok else "🔒"}</b>{name}</div>'
                    for icon, name, ok in badges)
    ui(f'<h3 style="font-size:18px;margin:16px 0 8px">Badges</h3><div class="badges">{cells}</div>')

    # streak heatmap: last 28 days, darker gold = more XP that day
    days = [date.today() - timedelta(days=27 - i) for i in range(28)]
    cells = "".join(
        f'<i title="{d} · {P["xp_by_day"].get(d.isoformat(), 0)} XP" style="background:'
        f'{"var(--gold)" if P["xp_by_day"].get(d.isoformat(), 0) else "var(--raised)"};'
        f'opacity:{0.35 + 0.65 * min(P["xp_by_day"].get(d.isoformat(), 0), 100) / 100 if P["xp_by_day"].get(d.isoformat(), 0) else 1}"></i>'
        for d in days)
    ui(f'<h3 style="font-size:18px;margin:16px 0 8px">Streak · <span class="mono">🔥 {streak_days()} days</span></h3>'
       f'<div class="card"><div class="heat">{cells}</div></div>')
    st.caption(f"XP rules: search +{XP['search']} · story read +{XP['read']} · daily quest +{XP['quest']} · "
               f"max {DAILY_XP_CAP} XP a day. Rewards are for reading, never trading.")

# ================================================================ PROFILE
else:
    ui('<div class="hero" style="font-size:24px">Profile & settings</div>')
    theme = st.segmented_control("Theme", ["Dark", "Light"], default=P["theme"], key="theme_pick")
    if theme and theme != P["theme"]:
        P["theme"] = theme
        save_progress()
        st.rerun()
    ui(f"""<div class="card"><b>Your stats</b>
    <div class="mono muted" style="font-size:13px;margin-top:6px">Searches {P['searches']} · Stories read {P['reads']} ·
    Saved {len(P['saved'])} · Quests {len(P['quest_days'])}</div></div>""")
    if st.button("Reset my progress"):
        st.session_state.p = dict(DEFAULT, theme=P["theme"])
        P = st.session_state.p
        save_progress()
        st.rerun()

ui('<div class="disclaimer">News summaries for information only. Not financial advice.<br>'
   'Built with AutoGen · ddgs · CoinGecko · GeckoTerminal</div>')
