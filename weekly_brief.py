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
# ──────────────────────────────────────────────────────────────
PORTFOLIO = {
    "UHR":   {"yf": "UHR.SW",  "yf_alt": "SWGAY",  "name": "Swatch Group",                "sector": "Consumer Discretionary", "ccy": "CHF"},
    "AML":   {"yf": "AML.L",   "name": "Aston Martin Lagonda",        "sector": "Consumer Discretionary", "ccy": "GBP"},
    "NKE":   {"yf": "NKE",     "name": "Nike",                        "sector": "Consumer Discretionary", "ccy": "USD"},
    "LULU":  {"yf": "LULU",    "name": "Lululemon Athletica",         "sector": "Consumer Discretionary", "ccy": "USD"},
    "LEN":   {"yf": "LEN",     "name": "Lennar",                      "sector": "Consumer Discretionary", "ccy": "USD"},
    "LMND":  {"yf": "LMND",    "name": "Lemonade",                    "sector": "Financials",             "ccy": "USD"},
    "AUNA":  {"yf": "AUNA",    "name": "Auna S.A.",                   "sector": "Health Care",            "ccy": "USD"},
    "JACK":  {"yf": "JACK",    "name": "Jack in the Box",             "sector": "Consumer Discretionary", "ccy": "USD"},
    "AVIO":  {"yf": "AVIO.MI", "yf_alt": "AVVSY",  "name": "Avio S.p.A.",                 "sector": "Industrials",            "ccy": "EUR"},
    "HCC":   {"yf": "HCC",     "name": "Warrior Met Coal",            "sector": "Energy",                 "ccy": "USD"},
    "AMR":   {"yf": "AMR",     "name": "Alpha Metallurgical Resources","sector": "Energy",                "ccy": "USD"},
    "CNR":   {"yf": "CNR",     "name": "Core Natural Resources",      "sector": "Energy",                 "ccy": "USD"},
    "CTT":   {"yf": "CTT.LS",  "name": "CTT Correios de Portugal",    "sector": "Industrials",            "ccy": "EUR"},
    "DGE":   {"yf": "DGE.L",   "name": "Diageo",                      "sector": "Consumer Staples",       "ccy": "GBP"},
    "PAR":   {"yf": "PAR",     "name": "PAR Technology",              "sector": "Technology",             "ccy": "USD"},
    "TAVHY": {"yf": "TAVHY",   "name": "TAV Havalimanlari Holding",   "sector": "Industrials",            "ccy": "USD"},
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
                    "ccy": info["ccy"], "error": "No price data available",
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
                        "ccy": info["ccy"], "error": "All close prices are NaN",
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

            results[ticker] = {
                "name": info["name"], "sector": info["sector"], "ccy": info["ccy"],
                "current_price": round(current_price, 2), "current_date": current_date,
                "price_delayed": price_delayed,
                "price_7d": round(price_7d, 2) if price_7d else None, "date_7d": date_7d,
                "price_30d": round(price_30d, 2) if price_30d else None, "date_30d": date_30d,
                "price_6m": round(price_6m, 2) if price_6m else None, "date_6m": date_6m,
                "chg_7d_pct": chg_7d, "chg_30d_pct": chg_30d, "chg_6m_pct": chg_6m,
                "is_mover": is_mover,
            }
            log(f"  {ticker}: {info['ccy']} {current_price} | 7d:{chg_7d}% | 30d:{chg_30d}% | 6m:{chg_6m}%", debug)

        except Exception as e:
            log(f"  ERROR on {ticker}: {e}", debug)
            results[ticker] = {
                "name": info["name"], "sector": info["sector"],
                "ccy": info["ccy"], "error": str(e),
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
