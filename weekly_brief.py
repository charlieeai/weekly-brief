#!/usr/bin/env python3
"""
Weekly Morning Brief — Price & News Data Collector
===================================================
Fetches price data via yfinance and recent news headlines via Google News RSS.
Outputs structured JSON for Claude to format as an HTML email.

Usage:
    python weekly_brief.py              # Full run
    python weekly_brief.py --prices     # Prices only (skip news)
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
# cost: cost per share (in the position's local currency, "ccy")
# purchase_date: "YYYY-MM-DD" — used to compute holding period in months
# ──────────────────────────────────────────────────────────────
PORTFOLIO = {
    "UHR":   {"yf": "UHR.SW",  "yf_alt": "SWGAY",  "name": "Swatch Group",                "sector": "Consumer Discretionary", "ccy": "CHF", "cost": 169.48, "purchase_date": "2025-12-03"},
    "AML":   {"yf": "AML.L",   "name": "Aston Martin Lagonda",        "sector": "Consumer Discretionary", "ccy": "GBP", "cost": 5.52, "purchase_date": "2021-03-22"},
    "NKE":   {"yf": "NKE",     "name": "Nike",                        "sector": "Consumer Discretionary", "ccy": "USD", "cost": 45.06, "purchase_date": "2026-04-24"},
    "LULU":  {"yf": "LULU",    "name": "Lululemon Athletica",         "sector": "Consumer Discretionary", "ccy": "USD", "cost": 133.65, "purchase_date": "2026-04-24"},
    "LEN":   {"yf": "LEN",     "name": "Lennar",                      "sector": "Consumer Discretionary", "ccy": "USD", "cost": 90.19, "purchase_date": "2026-04-14"},
    "AUNA":  {"yf": "AUNA",    "name": "Auna S.A.",                   "sector": "Health Care",            "ccy": "USD", "cost": 4.93, "purchase_date": "2025-12-01"},
    "JACK":  {"yf": "JACK",    "name": "Jack in the Box",             "sector": "Consumer Discretionary", "ccy": "USD", "cost": 18.81, "purchase_date": "2025-12-01"},
    "AVIO":  {"yf": "AVIO.MI", "yf_alt": "AVVSY",  "name": "Avio S.p.A.",                 "sector": "Industrials",            "ccy": "EUR", "cost": 36.05, "purchase_date": "2026-03-11"},
    "HCC":   {"yf": "HCC",     "name": "Warrior Met Coal",            "sector": "Energy",                 "ccy": "USD", "cost": 55.63, "purchase_date": "2023-12-15"},
    "AMR":   {"yf": "AMR",     "name": "Alpha Metallurgical Resources","sector": "Energy",                "ccy": "USD", "cost": 269.37, "purchase_date": "2023-12-04"},
    "CNR":   {"yf": "CNR",     "name": "Core Natural Resources",      "sector": "Energy",                 "ccy": "USD", "cost": 132.51, "purchase_date": "2024-11-25"},
    "CTT":   {"yf": "CTT.LS",  "name": "CTT Correios de Portugal",    "sector": "Industrials",            "ccy": "EUR", "cost": 3.79, "purchase_date": "2018-04-24"},
    "DGE":   {"yf": "DGE.L",   "name": "Diageo",                      "sector": "Consumer Staples",       "ccy": "GBP", "cost": 15.55, "purchase_date": "2025-12-19"},
    "PAR":   {"yf": "PAR",     "name": "PAR Technology",              "sector": "Technology",             "ccy": "USD", "cost": 40.32, "purchase_date": "2021-12-20"},
    "TAVHY": {"yf": "TAVHY",   "name": "TAV Havalimanlari Holding",   "sector": "Industrials",            "ccy": "USD", "cost": 22.80, "purchase_date": "2026-05-28"},
    "ONON": {"yf": "ONON",   "name": "On Holding AG",   "sector": "Consumer Cyclical",            "ccy": "USD", "cost": 37.85, "purchase_date": "2026-06-08"},
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
    """Compute holding period in whole months between purchase_date and today (or as_of)."""
    if not purchase_date_str:
        return None
    try:
        purchase_date = datetime.strptime(purchase_date_str, "%Y-%m-%d")
    except Exception:
        return None
    as_of = as_of or datetime.now()
    months = (as_of.year - purchase_date.year) * 12 + (as_of.month - purchase_date.month)
    # Adjust down by 1 if we haven't reached the day-of-month yet
    if as_of.day < purchase_date.day:
        months -= 1
    return max(months, 0)


def fetch_prices(debug=False):
    today = datetime.now()
    start = (today - timedelta(days=200)).strftime("%Y-%m-%d")  # 200 days for 6M lookback
    results = {}

    for ticker, info in PORTFOLIO.items():
        try:
            log(f"Fetching {ticker} ({info['yf']})...", debug)
            stock = yf.Ticker(info["yf"])

            hist = stock.history(start=start)
            if hist.empty:
                log(f"  Retrying {ticker} with period='9mo'...", debug)
                hist = stock.history(period="9mo")
            if hist.empty and info.get("yf_alt"):
                log(f"  Retrying {ticker} with alt ticker {info['yf_alt']}...", debug)
                stock = yf.Ticker(info["yf_alt"])
                hist = stock.history(period="9mo")

            if hist.empty:
                results[ticker] = {
                    "name": info["name"], "sector": info["sector"],
                    "ccy": info["ccy"],
                    "cost": info.get("cost"),
                    "purchase_date": info.get("purchase_date"),
                    "holding_period_months": holding_period_months(info.get("purchase_date")),
                    "error": "No price data available",
                }
                continue

            current_price = float(hist["Close"].iloc[-1])
            current_date = hist.index[-1].strftime("%Y-%m-%d")
            price_delayed = False

            if math.isnan(current_price):
                valid_closes = hist["Close"].dropna()
                if valid_closes.empty:
                    results[ticker] = {
                        "name": info["name"], "sector": info["sector"],
                        "ccy": info["ccy"],
                        "cost": info.get("cost"),
                        "purchase_date": info.get("purchase_date"),
                        "holding_period_months": holding_period_months(info.get("purchase_date")),
                        "error": "All close prices are NaN",
                    }
                    continue
                current_price = float(valid_closes.iloc[-1])
                current_date = valid_closes.index[-1].strftime("%Y-%m-%d")
                price_delayed = True
                log(f"  {ticker}: using previous close from {current_date} (today NaN)", debug)

            target_7d = today - timedelta(days=7)
            price_7d, date_7d = closest_price(hist, target_7d)

            target_30d = today - timedelta(days=30)
            price_30d, date_30d = closest_price(hist, target_30d)

            target_6m = today - timedelta(days=182)
            price_6m, date_6m = closest_price(hist, target_6m)

            chg_7d = round((current_price - price_7d) / price_7d * 100, 2) if price_7d else None
            chg_30d = round((current_price - price_30d) / price_30d * 100, 2) if price_30d else None
            chg_6m = round((current_price - price_6m) / price_6m * 100, 2) if price_6m else None

            is_mover = (abs(chg_7d) >= MOVER_THRESHOLD if chg_7d is not None else False) or \
                       (abs(chg_30d) >= MOVER_THRESHOLD if chg_30d is not None else False)

            cost = info.get("cost")
            chg_since_cost = round((current_price - cost) / cost * 100, 2) if cost else None

            results[ticker] = {
                "name": info["name"], "sector": info["sector"], "ccy": info["ccy"],
                "cost": cost,
                "purchase_date": info.get("purchase_date"),
                "holding_period_months": holding_period_months(info.get("purchase_date")),
                "chg_since_cost_pct": chg_since_cost,
                "current_price": round(current_price, 2), "current_date": current_date,
                "price_delayed": price_delayed,
                "price_7d": round(price_7d, 2) if price_7d else None, "date_7d": date_7d,
                "price_30d": round(price_30d, 2) if price_30d else None, "date_30d": date_30d,
                "price_6m": round(price_6m, 2) if price_6m else None, "date_6m": date_6m,
                "chg_7d_pct": chg_7d, "chg_30d_pct": chg_30d, "chg_6m_pct": chg_6m,
                "is_mover": is_mover,
            }
            log(f"  {ticker}: {info['ccy']} {current_price} | cost:{cost} | hold:{holding_period_months(info.get('purchase_date'))}mo | 7d:{chg_7d}% | 30d:{chg_30d}% | 6m:{chg_6m}%", debug)

        except Exception as e:
            log(f"  ERROR on {ticker}: {e}", debug)
            results[ticker] = {
                "name": info["name"], "sector": info["sector"],
                "ccy": info["ccy"],
                "cost": info.get("cost"),
                "purchase_date": info.get("purchase_date"),
                "holding_period_months": holding_period_months(info.get("purchase_date")),
                "error": str(e),
            }

    return results


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


def fetch_news_all_tickers(prices, debug=False):
    """Fetch 1W and 6M news for ALL tickers (not just movers)."""
    news_1w = {}
    news_6m = {}

    for ticker, data in prices.items():
        if "error" in data:
            continue
        company = data["name"]
        log(f"  News for {ticker} ({company})...", debug)

        # 1W: strict last-7-days search
        query = f'"{company}" OR "{ticker}" stock'
        news_1w[ticker] = fetch_google_news(query, time_filter="when:7d", max_results=5)

        # 6M: broader search (no time filter — Google returns most relevant recent)
        news_6m[ticker] = fetch_google_news(query, time_filter="", max_results=5)

        log(f"    1W: {len(news_1w[ticker])} | 6M: {len(news_6m[ticker])} headlines", debug)

    return news_1w, news_6m


def main():
    parser = argparse.ArgumentParser(description="Weekly Morning Brief data collector")
    parser.add_argument("--prices", action="store_true", help="Fetch prices only")
    parser.add_argument("--debug", action="store_true", help="Verbose logging")
    args = parser.parse_args()

    log("=" * 50)
    log("Weekly Morning Brief — Data Collection")
    log(f"Run at: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    log("=" * 50)

    prices = fetch_prices(debug=args.debug)

    news_1w, news_6m = {}, {}
    if not args.prices:
        log(f"Fetching news for all {len(prices)} tickers...", args.debug)
        news_1w, news_6m = fetch_news_all_tickers(prices, debug=args.debug)

    output = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "date_display": datetime.now().strftime("%B %d, %Y"),
        "mover_threshold_pct": MOVER_THRESHOLD,
        "prices": prices,
        "news_1w": news_1w,
        "news_6m": news_6m,
        "movers": [k for k, v in prices.items() if v.get("is_mover")],
        "delayed_prices": [k for k, v in prices.items() if v.get("price_delayed")],
        "errors": [k for k, v in prices.items() if "error" in v],
    }

    print(json.dumps(output, indent=2))
    log(f"\nDone. {len(prices)} tickers, {len(news_1w)} with 1W news, {len(news_6m)} with 6M news.")


if __name__ == "__main__":
    main()
