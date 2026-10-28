from functools import lru_cache, wraps
from pathlib import Path

import pandas as pd

from analysis import compute_metrics, load_store, real_user_map

DATA_DIR = Path(__file__).parent / "data"


@lru_cache
def _store(store):
    orders, users, books = load_store(DATA_DIR / store)
    real = real_user_map(users)
    orders["real_user"] = orders["user_id"].map(real)
    sold = orders.merge(books[["id", "authors"]], left_on="book_id", right_on="id")
    return orders, sold, real


def _check(store):
    store = store.upper().replace(" ", "")
    if store not in list_stores():
        raise ValueError(f"Unknown store {store!r}. Available: {list_stores()}")
    return store


def list_stores() -> list[str]:
    """Return the names of all stores that have data, e.g. ['STORE1', 'STORE2']."""
    return sorted(p.name for p in DATA_DIR.iterdir() if p.is_dir())


def get_summary(store: str) -> dict:
    """Main metrics of a store: number of real unique users, number of unique author
    sets, the most popular author set by sold books and the best buyer with all of
    their user ids and total spending in USD."""
    m = compute_metrics(DATA_DIR / _check(store))
    return {
        "unique_users": m["unique_users"],
        "unique_author_sets": int(m["unique_author_sets"]),
        "most_popular_authors": m["most_popular_authors"],
        "most_popular_books_sold": m["most_popular_sold"],
        "best_buyer_ids": [int(i) for i in m["best_buyer_ids"]],
        "best_buyer_total_usd": float(m["best_buyer_total"]),
    }


def get_top_days(store: str, n: int) -> list[dict]:
    """Top n days of a store by revenue in USD, best first. Dates are YYYY-MM-DD."""
    orders, _, _ = _store(_check(store))
    daily = orders.groupby("date")["paid_price"].sum().nlargest(n)
    return [{"date": d.strftime("%Y-%m-%d"), "revenue_usd": round(float(v), 2)} for d, v in daily.items()]


def get_revenue(store: str, start_date: str, end_date: str) -> dict:
    """Total revenue in USD and number of orders of a store between start_date and
    end_date inclusive (YYYY-MM-DD). For a single day pass the same date twice."""
    orders, _, _ = _store(_check(store))
    part = orders[orders["date"].between(pd.Timestamp(start_date), pd.Timestamp(end_date))]
    return {"revenue_usd": round(float(part["paid_price"].sum()), 2), "orders": len(part),
            "first_day_with_data": orders["date"].min().strftime("%Y-%m-%d"),
            "last_day_with_data": orders["date"].max().strftime("%Y-%m-%d")}


def get_author_sales(store: str, author: str) -> list[dict]:
    """Books sold in a store for every author set whose names contain the given text
    (case-insensitive, e.g. 'Metz'). Solo and co-authored books are listed separately."""
    _, sold, _ = _store(_check(store))
    hit = sold[sold["authors"].map(lambda s: any(author.lower() in a.lower() for a in s))]
    totals = hit.groupby("authors")["quantity"].sum().sort_values(ascending=False)
    return [{"authors": sorted(s), "books_sold": int(q)} for s, q in totals.items()]


def get_top_authors(store: str, n: int) -> list[dict]:
    """Top n author sets of a store by number of sold books."""
    _, sold, _ = _store(_check(store))
    totals = sold.groupby("authors")["quantity"].sum().nlargest(n)
    return [{"authors": sorted(s), "books_sold": int(q)} for s, q in totals.items()]


def get_customer(store: str, user_id: int) -> dict:
    """The real customer behind a user id: all of their ids (aliases, other
    addresses/phones/e-mails), number of orders and total spending in USD."""
    store = _check(store)
    orders, _, real = _store(store)
    if user_id not in real:
        raise ValueError(f"No user with id {user_id} in {store}")
    ids = sorted(i for i, r in real.items() if r == real[user_id])
    mine = orders[orders["user_id"].isin(ids)]
    return {"user_ids": [int(i) for i in ids], "orders": len(mine),
            "total_spent_usd": round(float(mine["paid_price"].sum()), 2)}


def _safe(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            return {"error": str(e)}
    return wrapper


TOOLS = [_safe(f) for f in (list_stores, get_summary, get_top_days, get_revenue,
                            get_author_sales, get_top_authors, get_customer)]
