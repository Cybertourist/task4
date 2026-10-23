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

overview, top_days, revenue = st.tabs(["Overview", "Top 5 days", "Daily revenue"])

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
