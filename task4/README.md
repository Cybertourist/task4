# Task 4 — Bookstore data dashboard

Loads `orders.parquet`, `users.csv` and `books.yaml` for every store in `data/`, cleans them with pandas
and shows the metrics in a Streamlit dashboard with an AI chat.

Cleaning:
- `timestamp` comes in ~10 formats (ISO, `dd.mm.yyyy`, `mm/dd/yy`, `dd-Mon-yyyy`, ctime, AM/PM variants) — only the date is extracted;
- `unit_price` comes as `$ 35`, `30.0USD`, `EUR37.50`, `€22¢25`, `46$99¢`… — converted to dollars (€1 = $1.2);
- book `year` values like `''`, `'-'`, `'\t'` become missing; empty and `NULL` shipping addresses become missing;
- phones are normalized to digits; users that differ in at most one of name/address/phone/email are merged into one real user;
- authors are stored as an unordered set, so `A, B` and `B, A` are the same set.

AI chat (`tools.py`): Gemini answers questions by calling Python functions that compute exact values with pandas;
the functions used are shown under every answer.

Run locally:

    pip install -r requirements.txt
    streamlit run app.py

The chat needs `GEMINI_API_KEY = "..."` in `.streamlit/secrets.toml` (locally) or in the app Secrets (Streamlit Cloud).
