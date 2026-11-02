"""
Browser UI for the 3-line crypto agent.

Run:  streamlit run app.py
"""

import asyncio

import streamlit as st
from autogen_agentchat.messages import ToolCallRequestEvent
from autogen_ext.models.openai import OpenAIChatCompletionClient

from weather_news import build_agent

st.set_page_config(page_title="FreqX Radar", page_icon="📡")
st.title("📡 FreqX Radar")
st.caption("3-line live crypto search · focus on FreCx (FreqX / Frequency X Chain) · AutoGen + ddgs")


async def ask(question: str):
    """Run the agent once and return (tools it called, final 3-line answer)."""
    model_client = OpenAIChatCompletionClient(model="gpt-4o-mini")
    agent = build_agent(model_client)
    result = await agent.run(task=f"Answer in exactly 3 short lines: {question}")
    await model_client.close()

    tools_used = [
        f"{call.name}({call.arguments})"
        for msg in result.messages
        if isinstance(msg, ToolCallRequestEvent)
        for call in msg.content
    ]
    return tools_used, result.messages[-1].content


examples = ["FreqX coin rate today", "What is Frequency Chain?", "Today's crypto news", "Bitcoin price"]
cols = st.columns(len(examples))
for col, example in zip(cols, examples):
    if col.button(example, use_container_width=True):
        st.session_state.question = example

question = st.text_input("Ask about crypto", key="question", placeholder="e.g. FreqX coin rate today")

if st.button("Search", type="primary") or (question and st.session_state.get("last") != question):
    st.session_state.last = question
    if question:
        with st.spinner("Searching live web + price data..."):
            tools_used, answer = asyncio.run(ask(question))

        if tools_used:
            st.info("🔧 Tool call: " + ", ".join(tools_used))
        # "\$" stops Streamlit reading $...$ as a math formula; "  \n" keeps the 3 line breaks
        st.success(answer.replace("$", "\\$").replace("\n", "  \n"))

st.divider()
st.caption("Only news and prices. Not investment advice. FreCx has very low liquidity, so its price is not reliable.")
