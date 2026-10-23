import re
from pathlib import Path

import pandas as pd
import yaml

EUR_TO_USD = 1.2
MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}

# Only the date part matters, so each pattern extracts year, month and day and ignores the time.
DATE_PATTERNS = [
    (r"(\d{4})-(\d{1,2})-(\d{1,2})", "ymd"),               # 2025-12-23T04:36:49, 2025-08-17 12:25
    (r"(\d{1,2})\.(\d{1,2})\.(\d{4})", "dmy"),             # 30.06.2025 11:49:49
    (r"(\d{1,2})/(\d{1,2})/(\d{2,4})", "mdy"),             # 04/29/26,13:42 (US order)
    (r"(\d{1,2})-([A-Za-z]+)-(\d{4})", "dMy"),             # 10-Dec-2025, 15-September-2025
    (r"[A-Za-z]{3} ([A-Za-z]{3})\s+(\d{1,2}) [\d:]+ (\d{4})", "Mdy"),  # Fri Apr 10 15:32:26 2026
]


def parse_date(text):
    for pattern, order in DATE_PATTERNS:
        m = re.search(pattern, text)
        if not m:
            continue
        a, b, c = m.groups()
        if order == "ymd":
            y, mo, d = a, b, c
        elif order == "dmy":
            d, mo, y = a, b, c
        elif order == "mdy":
            mo, d, y = a, b, c
        elif order == "dMy":
            d, mo, y = a, MONTHS[b[:3].lower()], c
        else:
            mo, d, y = MONTHS[a.lower()], b, c
        y = int(y)
        return pd.Timestamp(year=y + 2000 if y < 100 else y, month=int(mo), day=int(d))
    raise ValueError(f"Unknown timestamp format: {text!r}")


def parse_price_usd(text):
    """'$ 35', '30.0USD', 'EUR37.50', '29.00$', '€22¢25', '46$99¢' -> price in dollars."""
    rate = EUR_TO_USD if ("EUR" in text or "€" in text) else 1.0
    if "¢" in text:
        dollars, cents = re.findall(r"\d+", text)
        amount = int(dollars) + int(cents) / 100
    else:
        amount = float(re.search(r"\d+(?:\.\d*)?", text).group())
    return amount * rate


def load_store(folder):
    folder = Path(folder)
    orders = pd.read_parquet(folder / "orders.parquet")
    users = pd.read_csv(folder / "users.csv", dtype=str, keep_default_na=False)
    with open(folder / "books.yaml", encoding="utf-8") as f:
        books = pd.DataFrame(yaml.safe_load(f))
    books.columns = [c.lstrip(":") for c in books.columns]   # Ruby-style keys ':id' -> 'id'

    orders = orders.drop_duplicates()
    orders["date"] = orders["timestamp"].map(parse_date)
    orders["paid_price"] = (orders["quantity"] * orders["unit_price"].map(parse_price_usd)).round(2)

    users["id"] = users["id"].astype(int)
    users["phone"] = users["phone"].str.replace(r"\D", "", regex=True)  # (313) 970-1817 -> 3139701817

    books["authors"] = books["author"].map(lambda a: frozenset(x.strip() for x in a.split(",")))
    return orders, users, books


def real_user_map(users):
    """Two records belong to one person if at most one of name/address/phone/email differs."""
    parent = {uid: uid for uid in users["id"]}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    fields = ["name", "address", "phone", "email"]
    for skipped in fields:
        same = [f for f in fields if f != skipped]
        for ids in users.groupby(same)["id"]:
            ids = list(ids[1])
            for other in ids[1:]:
                parent[find(other)] = find(ids[0])
    return {uid: find(uid) for uid in users["id"]}


def compute_metrics(folder):
    orders, users, books = load_store(folder)

    daily = orders.groupby("date")["paid_price"].sum().round(2).sort_index()
    top5 = daily.sort_values(ascending=False).head(5)

    real = real_user_map(users)
    orders["real_user"] = orders["user_id"].map(real)

    sold = orders.merge(books[["id", "authors"]], left_on="book_id", right_on="id")
    by_authors = sold.groupby("authors")["quantity"].sum()
    best_authors = by_authors[by_authors == by_authors.max()].index

    spending = orders.groupby("real_user")["paid_price"].sum()
    best = spending.idxmax()

    return {
        "top5_days": [(d.strftime("%Y-%m-%d"), v) for d, v in top5.items()],
        "unique_users": len(set(real.values())),
        "unique_author_sets": books["authors"].nunique(),
        "most_popular_authors": [sorted(s) for s in best_authors],
        "most_popular_sold": int(by_authors.max()),
        "best_buyer_ids": sorted(u for u, r in real.items() if r == best),
        "best_buyer_total": round(spending.max(), 2),
        "daily_revenue": daily,
    }


if __name__ == "__main__":
    for folder in sorted(Path("data").iterdir()):
        m = compute_metrics(folder)
        print(folder.name, {k: v for k, v in m.items() if k != "daily_revenue"})
