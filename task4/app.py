from pathlib import Path

import pandas as pd
import streamlit as st

from analysis import compute_metrics

st.set_page_config(page_title="Bookstore Dashboard", page_icon="📚", layout="wide")

DATA_DIR = Path(__file__).parent / "data"
stores = sorted(p.name for p in DATA_DIR.iterdir() if p.is_dir())


@st.cache_data
def metrics_for(store):
    return compute_metrics(DATA_DIR / store)


store = st.sidebar.radio("Store", stores)
m = metrics_for(store)

st.title(f"📚 Bookstore analytics — {store}")

overview, top_days, revenue, chat_tab = st.tabs(["Overview", "Top 5 days", "Daily revenue", "AI chat"])

with overview:
    c1, c2, c3 = st.columns(3)
    c1.metric("Unique users", m["unique_users"])
    c2.metric("Unique author sets", m["unique_author_sets"])
    c3.metric("Best buyer spent", f"${m['best_buyer_total']:,.2f}")

    st.subheader("Most popular author(s)")
    for authors in m["most_popular_authors"]:
        st.markdown(f"**{', '.join(authors)}** — {m['most_popular_sold']} books sold")

    st.subheader("Best buyer (all ids)")
    st.code(str(m["best_buyer_ids"]))

with top_days:
    table = pd.DataFrame(m["top5_days"], columns=["Date", "Revenue, $"])
    table.index = range(1, len(table) + 1)
    table["Revenue, $"] = table["Revenue, $"].map("{:,.2f}".format)
    st.table(table)

with revenue:
    st.line_chart(m["daily_revenue"].rename("Revenue, $"), y_label="Revenue, $")

SYSTEM = """You are an analyst assistant for a bookstore dashboard.
Answer ONLY with numbers returned by the tools; never estimate, compute or invent figures yourself.
If the user does not name a store, use the store selected in the dashboard (given in brackets).
If a tool returns an error or the data cannot answer the question, say so plainly.
Money is in USD. Dates are YYYY-MM-DD. Answer briefly, in the user's language."""

with chat_tab:
    try:
        api_key = st.secrets["GEMINI_API_KEY"]
    except Exception:
        st.warning("Add GEMINI_API_KEY to the app secrets to enable the chat.")
        st.stop()

    from google import genai
    from google.genai import types

    from tools import TOOLS

    MODELS = [st.secrets.get("GEMINI_MODEL", "gemini-3.8-flash"), "gemini-flash-latest", "gemini-3.5-flash-lite"]
    client = genai.Client(api_key=api_key, http_options=types.HttpOptions(
        timeout=20_000, retry_options=types.HttpRetryOptions(attempts=1)))
    config = types.GenerateContentConfig(system_instruction=SYSTEM, tools=TOOLS)

    def ask(contents):
        errors = []
        for model in dict.fromkeys(MODELS):
            try:
                return client.models.generate_content(model=model, contents=contents, config=config)
            except Exception as e:
                errors.append(f"{model}: {e}")
        raise RuntimeError("all models failed — " + " | ".join(errors))

    if "messages" not in st.session_state:
        st.session_state.messages = []
        st.session_state.context = []

    history = st.container(height=450)
    for role, text in st.session_state.messages:
        history.chat_message(role).markdown(text, unsafe_allow_html=True)

    if question := st.chat_input("Ask about the data, e.g. “Who is the best buyer in STORE3?”"):
        history.chat_message("user").markdown(question)
        st.session_state.messages.append(("user", question))
        user_turn = types.Content(role="user", parts=[types.Part(text=f"[Selected store: {store}] {question}")])
        with history.chat_message("assistant"), st.spinner("Thinking..."):
            try:
                response = ask(st.session_state.context + [user_turn])
                answer = response.text or "No answer."
                st.session_state.context += [user_turn, types.Content(role="model", parts=[types.Part(text=answer)])]
                calls = [p.function_call for c in response.automatic_function_calling_history or []
                         for p in c.parts or [] if p.function_call]
                if calls:
                    answer += "\n\n<sub>Tools used: " + ", ".join(
                        f"`{c.name}({', '.join(f'{k}={v!r}' for k, v in (c.args or {}).items())})`"
                        for c in calls) + "</sub>"
            except Exception as e:
                answer = f"⚠️ Chat error: {e}"
            st.markdown(answer, unsafe_allow_html=True)
        st.session_state.messages.append(("assistant", answer))
