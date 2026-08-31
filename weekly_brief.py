#!/usr/bin/env python3
"""
Weekly Morning Brief — News Collector + FiscalAI Key Map + TAVHY fallback
===========================================================================
ARCHITECTURE CHANGE (July 2026): yfinance was blocked at the network-egress
level in the Claude Code cloud sandbox used by the Routine (confirmed 403 /
rate-limit on Yahoo AND stooq). FiscalAI MCP tools run server-side, outside
that egress policy, so price data for every ticker EXCEPT TAVHY is now
fetched by Claude DIRECTLY from FiscalAI MCP during the Routine step, using
the exact `fiscal_key` values below.

WEIGHTS CHANGE (August 2026): Table 1 is no longer sorted by 1W price change.
It is now sorted by CONSOLIDATED PORTFOLIO WEIGHT, descending, using the
SLEEVES config below. A "sleeve" is either a single ticker (AUNA, CTT, ...)
or a consolidated group (COAL = HCC+AMR+CNR, SAAS = PAR+TOST+WKL+INTU+ADBE,
APPAREL = NKE+LULU+ONON). Edit weights ONLY in SLEEVES — everything else
(sort order, the merged weight cell, the group colors) is derived from it.
Within a group, tickers are still ordered by 1W % descending, so the
short-term signal survives inside each block.

DO NOT re-derive or guess fiscal_key values. Each one was hand-verified
against the live FiscalAI API (company_profile + company_stock_prices):
  - AML must be "LSE_AML" (returns exchangeCode XLON, currency GBX)
  - CNR must be "NYSE_CNR" — NOT "TSX_CNR" (that's Canadian National Railway,
    a different company that also trades under ticker CNR)
  - UHR must be "XSWX_UHR" — "SIX_UHR"/"SWX_UHR" resolve but return NO price
    data from the API
  - DGE must be "NYSE_DEO" — FiscalAI has NO LSE/GBP listing for Diageo,
    only the NYSE ADR (ticker DEO, USD). Cost basis was converted from GBP
    to the USD-equivalent (14.72) to match.
  - BUR must be "NYSE_BUR" (Burford Capital Limited, USD, Financials /
    Specialized Finance). Note "LSE_BUR" ALSO resolves but silently returns
    the same NYSE listing — always pass NYSE_BUR explicitly.

TAVHY (TAV Havalimanlari) is confirmed NOT present in FiscalAI's company
universe (scanned all 11,963 companies / 12 pages, zero matches on ticker
"TAVHL" or name "Havalimanlari"). Its price is fetched here via yfinance
using the Istanbul-listed ticker TAVHL.IS (TRY), which matches the
TRY-denominated cost basis (278.64). This is the ONLY ticker still using
yfinance — if Yahoo blocks this specific request in the Routine's sandbox,
the "error" field will say so and the Routine should show "—" for TAVHY
prices rather than guessing.

This script now only handles:
  1. TAVHY price fetch (yfinance, single ticker, best-effort)
  2. Google News RSS headlines (1W + 6M) for all portfolio tickers
  3. Emits portfolio/watchlist metadata + fiscal_key map + sleeve weights as
     JSON, so the Routine has a single source of truth for which FiscalAI key
     to call and in what order to render the table

Usage:
    python weekly_brief.py              # Full run
    python weekly_brief.py --prices     # Skip news (TAVHY price + metadata only)
    python weekly_brief.py --debug      # Verbose logging
"""

import json
import math
import sys
import argparse
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

import yfinance as yf

# ──────────────────────────────────────────────────────────────
# PORTFOLIO CONFIGURATION
#
# fiscal_key: exact FiscalAI companyKey for the Routine to call directly.
#             None only for TAVHY (not covered by FiscalAI's API — see yf field).
# cost: cost per share, in the currency given by "ccy"
# purchase_date: "YYYY-MM-DD" — used to compute holding period in months
#                None => Holding (mo) cell is left BLANK, never guessed
#
# NOTE: portfolio WEIGHTS are NOT set here — they live in SLEEVES below.
# ──────────────────────────────────────────────────────────────
PORTFOLIO = {
    "UHR":   {"fiscal_key": "XSWX_UHR",   "name": "Swatch Group",                 "sector": "Consumer Discretionary", "ccy": "CHF", "cost": 169.48, "purchase_date": "2025-12-03"},
    "AML":   {"fiscal_key": "LSE_AML",    "name": "Aston Martin Lagonda",         "sector": "Consumer Discretionary", "ccy": "GBX", "cost": 5.52,   "purchase_date": "2021-03-22"},
    "NKE":   {"fiscal_key": "NYSE_NKE",   "name": "Nike",                         "sector": "Consumer Discretionary", "ccy": "USD", "cost": 44.94,  "purchase_date": "2026-04-24"},
    "LULU":  {"fiscal_key": "NASDAQ_LULU","name": "Lululemon Athletica",          "sector": "Consumer Discretionary", "ccy": "USD", "cost": 133.65, "purchase_date": "2026-04-24"},
    "LEN":   {"fiscal_key": "NYSE_LEN",   "name": "Lennar",                       "sector": "Consumer Discretionary", "ccy": "USD", "cost": 90.19,  "purchase_date": "2026-04-14"},
    "AUNA":  {"fiscal_key": "NYSE_AUNA",  "name": "Auna S.A.",                    "sector": "Health Care",            "ccy": "USD", "cost": 4.93,   "purchase_date": "2025-12-01"},
    "AVIO":  {"fiscal_key": "MIL_AVIO",   "name": "Avio S.p.A.",                  "sector": "Industrials",            "ccy": "EUR", "cost": 36.05,  "purchase_date": "2026-03-11"},
    "HCC":   {"fiscal_key": "NYSE_HCC",   "name": "Warrior Met Coal",             "sector": "Energy",                 "ccy": "USD", "cost": 55.63,  "purchase_date": "2023-12-15"},
    "AMR":   {"fiscal_key": "NYSE_AMR",   "name": "Alpha Metallurgical Resources","sector": "Energy",                 "ccy": "USD", "cost": 269.37, "purchase_date": "2023-12-04"},
    "CNR":   {"fiscal_key": "NYSE_CNR",   "name": "Core Natural Resources",       "sector": "Energy",                 "ccy": "USD", "cost": 132.51, "purchase_date": "2024-11-25"},
    "CTT":   {"fiscal_key": "LIS_CTT",    "name": "CTT Correios de Portugal",     "sector": "Industrials",            "ccy": "EUR", "cost": 3.79,   "purchase_date": "2018-04-24"},
    "DGE":   {"fiscal_key": "NYSE_DEO",   "name": "Diageo",                       "sector": "Consumer Staples",       "ccy": "USD", "cost": 14.72,  "purchase_date": "2025-12-19"},
    "PAR":   {"fiscal_key": "NYSE_PAR",   "name": "PAR Technology",               "sector": "Technology",             "ccy": "USD", "cost": 40.32,  "purchase_date": "2021-12-20"},
    "TAVHY": {"fiscal_key": None, "yf": "TAVHL.IS", "name": "TAV Havalimanlari Holding", "sector": "Industrials",      "ccy": "TRY", "cost": 278.64, "purchase_date": "2026-05-28"},
    "ONON":  {"fiscal_key": "NYSE_ONON",  "name": "On Holding AG",                "sector": "Consumer Cyclical",      "ccy": "USD", "cost": 37.85,  "purchase_date": "2026-06-08"},
    "ADBE":  {"fiscal_key": "NASDAQ_ADBE","name": "Adobe Inc",                    "sector": "Technology",             "ccy": "USD", "cost": 229.82, "purchase_date": "2026-07-13"},
    "INTU":  {"fiscal_key": "NASDAQ_INTU","name": "Intuit Inc",                   "sector": "Technology",             "ccy": "USD", "cost": 288.01, "purchase_date": "2026-07-13"},
    "TOST":  {"fiscal_key": "NYSE_TOST",  "name": "Toast Inc",                    "sector": "Technology",             "ccy": "USD", "cost": 29.97,  "purchase_date": "2026-07-14"},
    "WKL":   {"fiscal_key": "AMS_WKL",    "name": "Wolters Kluwer N.V.",          "sector": "Technology",             "ccy": "EUR", "cost": 61.95,  "purchase_date": "2026-07-14"},
    # TODO: set purchase_date for BUR. Left as None on purpose — the Routine
    # renders a BLANK "Holding (mo)" cell rather than guessing a date.
    "BUR":   {"fiscal_key": "NYSE_BUR",   "name": "Burford Capital",              "sector": "Financials",             "ccy": "USD", "cost": 4.25,   "purchase_date": "2026-08-11"},
}

# ══════════════════════════════════════════════════════════════
# PORTFOLIO WEIGHTS — ★ EDIT WEIGHTS HERE AND ONLY HERE ★
# ══════════════════════════════════════════════════════════════
# A "sleeve" is one row-block in Table 1: either a single ticker or a
# consolidated group. `weight_pct` is the CONSOLIDATED weight of the whole
# sleeve, expressed in percent (9.0 == 9%).
#
# Table 1 renders sleeves in DESCENDING weight_pct order. For a group, the
# weight cell is rendered ONCE as a vertically-merged (rowspan) cell, centred,
# filled with `color`. Tickers inside a group are ordered by 1W % descending.
#
# `color`: background of the merged weight cell. None => default styling
#          (used for single-ticker sleeves). Keep group colors distinct from
#          the yellow mover highlight (#FFF3B0) so both signals stay readable.
#
# To re-weight: change weight_pct. To move a ticker between sleeves: move its
# symbol between `tickers` lists. Every PORTFOLIO ticker must appear in exactly
# one sleeve — the validator below will flag it in the JSON if it doesn't.
# ══════════════════════════════════════════════════════════════
SLEEVES = [
    {"id": "AUNA",    "label": "Auna",            "tickers": ["AUNA"],                              "weight_pct": 8.2, "color": None},
    {"id": "COAL",    "label": "Coal",            "tickers": ["HCC", "AMR", "CNR"],                 "weight_pct": 7.6, "color": "#DDE3E9"},
    {"id": "AVIO",    "label": "Avio",            "tickers": ["AVIO"],                              "weight_pct": 5.1, "color": None},
    {"id": "SAAS",    "label": "SaaS",            "tickers": ["PAR", "TOST", "WKL", "INTU", "ADBE"],"weight_pct": 5.3, "color": "#D6EAE6"},
    {"id": "CTT",     "label": "CTT",             "tickers": ["CTT"],                               "weight_pct": 5.3, "color": None},
    {"id": "DGE",     "label": "Diageo",          "tickers": ["DGE"],                               "weight_pct": 4.2, "color": None},
    {"id": "APPAREL", "label": "Sports Apparel",  "tickers": ["NKE", "LULU", "ONON"],               "weight_pct": 3.6, "color": "#E6DFF1"},
    {"id": "LEN",     "label": "Lennar",          "tickers": ["LEN"],                               "weight_pct": 3.1, "color": None},
    {"id": "UHR",     "label": "Swatch Group",    "tickers": ["UHR"],                               "weight_pct": 2.7, "color": None},
    {"id": "TAVHY",   "label": "TAV Havalimanlari","tickers": ["TAVHY"],                            "weight_pct": 1.6, "color": None},
    {"id": "AML",     "label": "Aston Martin",    "tickers": ["AML"],                               "weight_pct": 0.4, "color": None},
    {"id": "BUR",     "label": "Burford Capital", "tickers": ["BUR"],                               "weight_pct": 0.2, "color": None},
]

# ──────────────────────────────────────────────────────────────
# WATCHLIST — price-only tracking via FiscalAI (no cost, no weight, no news)
# Mag 7 + SpaceX + Micron. All confirmed live on FiscalAI.
# Watchlist table stays sorted by 1W DESCENDING.
# ──────────────────────────────────────────────────────────────
WATCHLIST = {
    "NVDA": {"fiscal_key": "NASDAQ_NVDA", "name": "NVIDIA",            "sector": "Technology",             "ccy": "USD"},
    "AAPL": {"fiscal_key": "NASDAQ_AAPL", "name": "Apple",             "sector": "Technology",             "ccy": "USD"},
    "GOOG": {"fiscal_key": "NASDAQ_GOOG", "name": "Alphabet",          "sector": "Technology",             "ccy": "USD"},
    "MSFT": {"fiscal_key": "NASDAQ_MSFT", "name": "Microsoft",         "sector": "Technology",             "ccy": "USD"},
    "AMZN": {"fiscal_key": "NASDAQ_AMZN", "name": "Amazon",            "sector": "Consumer Discretionary", "ccy": "USD"},
    "META": {"fiscal_key": "NASDAQ_META", "name": "Meta Platforms",    "sector": "Technology",             "ccy": "USD"},
    "TSLA": {"fiscal_key": "NASDAQ_TSLA", "name": "Tesla",             "sector": "Consumer Discretionary", "ccy": "USD"},
    "SPCX": {"fiscal_key": "NASDAQ_SPCX", "name": "SpaceX",            "sector": "Industrials",            "ccy": "USD"},
    "MU":   {"fiscal_key": "NASDAQ_MU",   "name": "Micron Technology", "sector": "Technology",             "ccy": "USD"},
}

MOVER_THRESHOLD = 5.0


def log(msg, debug=False):
    if debug:
        print(f"[DEBUG] {msg}", file=sys.stderr)
    else:
        print(msg, file=sys.stderr)


def closest_price(hist, target_date):
    try:
        filtered = hist[hist.index <= str(target_date)]
        if filtered.empty:
            return None, None
        price = float(filtered["Close"].iloc[-1])
        date_str = filtered.index[-1].strftime("%Y-%m-%d")
        return price, date_str
    except Exception:
        return None, None


def holding_period_months(purchase_date_str, as_of=None):
    """Compute holding period in whole months between purchase_date and today (or as_of).
    Returns None when purchase_date is missing — the Routine renders a blank cell."""
    if not purchase_date_str:
        return None
    try:
        purchase_date = datetime.strptime(purchase_date_str, "%Y-%m-%d")
    except Exception:
        return None
    as_of = as_of or datetime.now()
    months = (as_of.year - purchase_date.year) * 12 + (as_of.month - purchase_date.month)
    if as_of.day < purchase_date.day:
        months -= 1
    return max(months, 0)


# ──────────────────────────────────────────────────────────────
# SLEEVE / WEIGHT HELPERS
# ──────────────────────────────────────────────────────────────
def sleeves_sorted():
    """Sleeves in DESCENDING weight order. Ties broken by declaration order in
    SLEEVES so the output is always deterministic."""
    return sorted(
        enumerate(SLEEVES),
        key=lambda pair: (-pair[1]["weight_pct"], pair[0]),
    )


def ticker_to_sleeve():
    """Reverse index: ticker -> (sleeve dict, position within its sleeve)."""
    index = {}
    for sleeve in SLEEVES:
        for pos, ticker in enumerate(sleeve["tickers"]):
            index[ticker] = (sleeve, pos)
    return index


def validate_sleeves(debug=False):
    """Every PORTFOLIO ticker must sit in exactly one sleeve, and every sleeve
    ticker must exist in PORTFOLIO. Returns a dict the Routine can inspect
    instead of silently dropping a position from the table."""
    index = ticker_to_sleeve()

    unassigned = sorted(t for t in PORTFOLIO if t not in index)

    seen, duplicated = set(), []
    for sleeve in SLEEVES:
        for ticker in sleeve["tickers"]:
            if ticker in seen:
                duplicated.append(ticker)
            seen.add(ticker)

    unknown = sorted(t for t in seen if t not in PORTFOLIO)
    total = round(sum(s["weight_pct"] for s in SLEEVES), 4)

    report = {
        "weights_total_pct": total,
        "implied_cash_pct": round(100.0 - total, 4),
        "unassigned_tickers": unassigned,
        "duplicated_tickers": sorted(set(duplicated)),
        "unknown_sleeve_tickers": unknown,
        "ok": not (unassigned or duplicated or unknown),
    }

    if unassigned:
        log(f"  WARNING: tickers with no sleeve/weight: {', '.join(unassigned)}", debug)
    if duplicated:
        log(f"  WARNING: tickers in more than one sleeve: {', '.join(sorted(set(duplicated)))}", debug)
    if unknown:
        log(f"  WARNING: sleeve tickers absent from PORTFOLIO: {', '.join(unknown)}", debug)
    log(f"  Weights total {total}% (implied cash {report['implied_cash_pct']}%)", debug)

    return report


def build_sleeve_order():
    """Ordered render plan for Table 1. The Routine walks this list top to
    bottom; it only has to sort tickers WITHIN each group (by 1W desc)."""
    plan = []
    for _, sleeve in sleeves_sorted():
        tickers = [t for t in sleeve["tickers"] if t in PORTFOLIO]
        if not tickers:
            continue
        plan.append({
            "sleeve_id": sleeve["id"],
            "label": sleeve["label"],
            "weight_pct": sleeve["weight_pct"],
            "color": sleeve["color"],
            "is_group": len(tickers) > 1,
            "rowspan": len(tickers),
            "tickers": tickers,
            "sort_within": "1w_desc",
        })
    return plan


def fetch_tavhy_price(debug=False):
    """Best-effort fetch of TAVHY price via yfinance (Istanbul listing, TRY).
    This is the ONLY ticker still using yfinance — FiscalAI has no coverage."""
    info = PORTFOLIO["TAVHY"]
    yf_ticker = info["yf"]
    today = datetime.now()
    start = (today - timedelta(days=200)).strftime("%Y-%m-%d")

    try:
        log(f"Fetching TAVHY via yfinance ({yf_ticker})...", debug)
        stock = yf.Ticker(yf_ticker)
        hist = stock.history(start=start)
        if hist.empty:
            hist = stock.history(period="9mo")

        if hist.empty:
            return {"error": "No price data available from yfinance for TAVHL.IS"}

        current_price = float(hist["Close"].iloc[-1])
        current_date = hist.index[-1].strftime("%Y-%m-%d")
        price_delayed = False

        if math.isnan(current_price):
            valid_closes = hist["Close"].dropna()
            if valid_closes.empty:
                return {"error": "All TAVHY close prices are NaN"}
            current_price = float(valid_closes.iloc[-1])
            current_date = valid_closes.index[-1].strftime("%Y-%m-%d")
            price_delayed = True

        target_7d = today - timedelta(days=7)
        price_7d, date_7d = closest_price(hist, target_7d)
        target_30d = today - timedelta(days=30)
        price_30d, date_30d = closest_price(hist, target_30d)
        target_6m = today - timedelta(days=182)
        price_6m, date_6m = closest_price(hist, target_6m)

        chg_7d = round((current_price - price_7d) / price_7d * 100, 2) if price_7d else None
        chg_30d = round((current_price - price_30d) / price_30d * 100, 2) if price_30d else None
        chg_6m = round((current_price - price_6m) / price_6m * 100, 2) if price_6m else None

        cost = info.get("cost")
        chg_since_cost = round((current_price - cost) / cost * 100, 2) if cost else None
        is_mover = (abs(chg_7d) >= MOVER_THRESHOLD if chg_7d is not None else False) or \
                   (abs(chg_30d) >= MOVER_THRESHOLD if chg_30d is not None else False)

        result = {
            "current_price": round(current_price, 2), "current_date": current_date,
            "price_delayed": price_delayed,
            "price_7d": round(price_7d, 2) if price_7d else None, "date_7d": date_7d,
            "price_30d": round(price_30d, 2) if price_30d else None, "date_30d": date_30d,
            "price_6m": round(price_6m, 2) if price_6m else None, "date_6m": date_6m,
            "chg_7d_pct": chg_7d, "chg_30d_pct": chg_30d, "chg_6m_pct": chg_6m,
            "chg_since_cost_pct": chg_since_cost,
            "is_mover": is_mover,
        }
        log(f"  TAVHY: TRY {current_price} | 7d:{chg_7d}% | 30d:{chg_30d}% | 6m:{chg_6m}%", debug)
        return result

    except Exception as e:
        log(f"  ERROR fetching TAVHY: {e}", debug)
        return {"error": str(e)}


def fetch_google_news(query, time_filter="when:7d", max_results=5):
    """Fetch headlines from Google News RSS. time_filter can be 'when:7d', 'when:6m', or '' for no filter."""
    try:
        search = f"{query} {time_filter}".strip()
        encoded = urllib.parse.quote(search)
        url = f"https://news.google.com/rss/search?q={encoded}&hl=en-US&gl=US&ceid=US:en"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            xml_data = resp.read()
        root = ET.fromstring(xml_data)
        items = root.findall(".//item")
        headlines = []
        for item in items[:max_results]:
            headlines.append({
                "title": item.findtext("title", ""),
                "link": item.findtext("link", ""),
                "published": item.findtext("pubDate", ""),
                "source": item.findtext("source", ""),
            })
        return headlines
    except Exception as e:
        return [{"error": str(e)}]


def fetch_news_all_tickers(debug=False):
    """Fetch 1W and 6M news for ALL portfolio tickers (watchlist gets no news)."""
    news_1w = {}
    news_6m = {}

    for ticker, info in PORTFOLIO.items():
        company = info["name"]
        log(f"  News for {ticker} ({company})...", debug)

        query = f'"{company}" OR "{ticker}" stock'
        news_1w[ticker] = fetch_google_news(query, time_filter="when:7d", max_results=5)
        news_6m[ticker] = fetch_google_news(query, time_filter="", max_results=5)

        log(f"    1W: {len(news_1w[ticker])} | 6M: {len(news_6m[ticker])} headlines", debug)

    return news_1w, news_6m


def build_portfolio_meta():
    """Metadata for every portfolio ticker: fiscal_key, cost, holding period,
    sleeve + weight. The Routine reads this directly instead of re-deriving
    anything."""
    index = ticker_to_sleeve()
    meta = {}
    for ticker, info in PORTFOLIO.items():
        sleeve, pos = index.get(ticker, (None, None))
        meta[ticker] = {
            "name": info["name"],
            "sector": info["sector"],
            "ccy": info["ccy"],
            "cost": info.get("cost"),
            "purchase_date": info.get("purchase_date"),
            "holding_period_months": holding_period_months(info.get("purchase_date")),
            "fiscal_key": info.get("fiscal_key"),
            "sleeve_id": sleeve["id"] if sleeve else None,
            "sleeve_label": sleeve["label"] if sleeve else None,
            "weight_pct": sleeve["weight_pct"] if sleeve else None,
            "sleeve_color": sleeve["color"] if sleeve else None,
            "sleeve_size": len(sleeve["tickers"]) if sleeve else None,
            "is_group_member": (len(sleeve["tickers"]) > 1) if sleeve else None,
        }
    return meta


def build_watchlist_meta():
    meta = {}
    for ticker, info in WATCHLIST.items():
        meta[ticker] = {
            "name": info["name"],
            "sector": info["sector"],
            "ccy": info["ccy"],
            "fiscal_key": info["fiscal_key"],
        }
    return meta


def main():
    parser = argparse.ArgumentParser(description="Weekly Morning Brief data collector")
    parser.add_argument("--prices", action="store_true", help="Skip news (TAVHY price + metadata only)")
    parser.add_argument("--debug", action="store_true", help="Verbose logging")
    args = parser.parse_args()

    log("=" * 50)
    log("Weekly Morning Brief — Data Collection")
    log(f"Run at: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    log("=" * 50)

    log("Validating sleeve weights...", args.debug)
    weights_check = validate_sleeves(debug=args.debug)

    tavhy_price = fetch_tavhy_price(debug=args.debug)

    news_1w, news_6m = {}, {}
    if not args.prices:
        log(f"Fetching news for {len(PORTFOLIO)} portfolio tickers...", args.debug)
        news_1w, news_6m = fetch_news_all_tickers(debug=args.debug)

    output = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "date_display": datetime.now().strftime("%B %d, %Y"),
        "mover_threshold_pct": MOVER_THRESHOLD,
        "instructions_for_routine": (
            "Prices for every portfolio/watchlist ticker EXCEPT TAVHY must be fetched "
            "directly from FiscalAI MCP using company_stock_prices({companyKey: fiscal_key}), "
            "using the exact fiscal_key given in portfolio_meta/watchlist_meta. Do NOT guess "
            "or re-derive a fiscal_key. TAVHY has no FiscalAI coverage — use the tavhy_price "
            "block below (fetched via yfinance TAVHL.IS, TRY) instead; if it contains an "
            "'error' field, show '—' in the table for TAVHY rather than guessing a price. "
            "TABLE 1 ORDER: walk sleeve_order top to bottom (already sorted by consolidated "
            "weight, descending). Do NOT re-sort Table 1 by 1W. Within a sleeve whose "
            "is_group is true, order its tickers by 1W % DESCENDING and render the weight "
            "once as a rowspan cell using the sleeve's rowspan and color. Table 2 "
            "(watchlist) is still sorted by 1W descending."
        ),
        "weights_check": weights_check,
        "sleeve_order": build_sleeve_order(),
        "portfolio_meta": build_portfolio_meta(),
        "watchlist_meta": build_watchlist_meta(),
        "tavhy_price": tavhy_price,
        "news_1w": news_1w,
        "news_6m": news_6m,
    }

    print(json.dumps(output, indent=2))
    log(f"\nDone. {len(PORTFOLIO)} portfolio + {len(WATCHLIST)} watchlist tickers (metadata only).")
    log(f"  Sleeves: {len(SLEEVES)} | weights OK: {weights_check['ok']}")
    log(f"  TAVHY price: {'OK' if 'error' not in tavhy_price else 'ERROR — ' + tavhy_price['error']}")
    log(f"  {len(news_1w)} with 1W news, {len(news_6m)} with 6M news.")


if __name__ == "__main__":
    main()
