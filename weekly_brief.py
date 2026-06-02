#!/usr/bin/env python3
"""
Weekly Morning Brief — Price & News Data Collector
===================================================
Fetches price data via yfinance and recent news headlines via Google News RSS.
Outputs structured JSON for Claude to filter (fundamental-only) and format.

Usage:
    python weekly_brief.py              # Full run
    python weekly_brief.py --prices     # Prices only (skip news)
    python weekly_brief.py --debug      # Verbose logging
"""

import json
import sys
import argparse
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

import yfinance as yf

# ──────────────────────────────────────────────────────────────
# PORTFOLIO CONFIGURATION
# Edit this dict to add/remove positions.
# Keys = display ticker, values = yfinance symbol + metadata.
# ──────────────────────────────────────────────────────────────
PORTFOLIO = {
    "UHR":   {"yf": "UHR.SW",  "name": "Swatch Group",                "sector": "Consumer Discretionary", "ccy": "CHF"},
    "AML":   {"yf": "AML.L",   "name": "Aston Martin Lagonda",        "sector": "Consumer Discretionary", "ccy": "GBP"},
    "NKE":   {"yf": "NKE",     "name": "Nike",                        "sector": "Consumer Discretionary", "ccy": "USD"},
    "LULU":  {"yf": "LULU",    "name": "Lululemon Athletica",         "sector": "Consumer Discretionary", "ccy": "USD"},
    "LEN":   {"yf": "LEN",     "name": "Lennar",                      "sector": "Consumer Discretionary", "ccy": "USD"},
    "LMND":  {"yf": "LMND",    "name": "Lemonade",                    "sector": "Financials",             "ccy": "USD"},
    "AUNA":  {"yf": "AUNA",    "name": "Auna S.A.",                   "sector": "Health Care",            "ccy": "USD"},
    "JACK":  {"yf": "JACK",    "name": "Jack in the Box",             "sector": "Consumer Discretionary", "ccy": "USD"},
    "AVIO":  {"yf": "AVIO.MI", "name": "Avio S.p.A.",                 "sector": "Industrials",            "ccy": "EUR"},
    "HCC":   {"yf": "HCC",     "name": "Warrior Met Coal",            "sector": "Energy",                 "ccy": "USD"},
    "AMR":   {"yf": "AMR",     "name": "Alpha Metallurgical Resources","sector": "Energy",                "ccy": "USD"},
    "CNR":   {"yf": "CNR",     "name": "Core Natural Resources",      "sector": "Energy",                 "ccy": "USD"},
    "CTT":   {"yf": "CTT.LS",  "name": "CTT Correios de Portugal",    "sector": "Industrials",            "ccy": "EUR"},
    "DGE":   {"yf": "DGE.L",   "name": "Diageo",                      "sector": "Consumer Staples",       "ccy": "GBP"},
    "PAR":   {"yf": "PAR",     "name": "PAR Technology",              "sector": "Technology",             "ccy": "USD"},
    "TAVHY": {"yf": "TAVHY",   "name": "TAV Havalimanlari Holding",   "sector": "Industrials",            "ccy": "USD"},
}

MOVER_THRESHOLD = 5.0  # % change to qualify as a mover


def log(msg, debug=False):
    """Print to stderr so stdout stays clean JSON."""
    if debug:
        print(f"[DEBUG] {msg}", file=sys.stderr)
    else:
        print(msg, file=sys.stderr)


def closest_price(hist, target_date):
    """Return (price, date_str) for the trading day on or before target_date."""
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
    """Fetch current, 7d-ago, and 30d-ago prices for all tickers."""
    today = datetime.now()
    start = (today - timedelta(days=45)).strftime("%Y-%m-%d")
    results = {}

    for ticker, info in PORTFOLIO.items():
        try:
            log(f"Fetching {ticker} ({info['yf']})...", debug)
            stock = yf.Ticker(info["yf"])
            hist = stock.history(start=start)

            if hist.empty:
                results[ticker] = {
                    "name": info["name"],
                    "sector": info["sector"],
                    "ccy": info["ccy"],
                    "error": "No price data available from yfinance",
                }
                continue

            current_price = float(hist["Close"].iloc[-1])
            current_date = hist.index[-1].strftime("%Y-%m-%d")

            target_7d = today - timedelta(days=7)
            price_7d, date_7d = closest_price(hist, target_7d)

            target_30d = today - timedelta(days=30)
            price_30d, date_30d = closest_price(hist, target_30d)

            chg_7d = round((current_price - price_7d) / price_7d * 100, 2) if price_7d else None
            chg_30d = round((current_price - price_30d) / price_30d * 100, 2) if price_30d else None

            is_mover = (abs(chg_7d) >= MOVER_THRESHOLD if chg_7d is not None else False) or \
                       (abs(chg_30d) >= MOVER_THRESHOLD if chg_30d is not None else False)

            results[ticker] = {
                "name": info["name"],
                "sector": info["sector"],
                "ccy": info["ccy"],
                "current_price": round(current_price, 2),
                "current_date": current_date,
                "price_7d": round(price_7d, 2) if price_7d else None,
                "date_7d": date_7d,
                "price_30d": round(price_30d, 2) if price_30d else None,
                "date_30d": date_30d,
                "chg_7d_pct": chg_7d,
                "chg_30d_pct": chg_30d,
                "is_mover": is_mover,
            }
            log(f"  {ticker}: {info['ccy']} {current_price} | 7d: {chg_7d}% | 30d: {chg_30d}%", debug)

        except Exception as e:
            log(f"  ERROR on {ticker}: {e}", debug)
            results[ticker] = {
                "name": info["name"],
                "sector": info["sector"],
                "ccy": info["ccy"],
                "error": str(e),
            }

    return results


def fetch_google_news(query, max_results=5):
    """Fetch headlines from Google News RSS (no API key needed)."""
    try:
        encoded = urllib.parse.quote(query)
        url = f"https://news.google.com/rss/search?q={encoded}+when:7d&hl=en-US&gl=US&ceid=US:en"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            xml_data = resp.read()
        root = ET.fromstring(xml_data)
        items = root.findall(".//item")
        headlines = []
        for item in items[:max_results]:
            title = item.findtext("title", "")
            link = item.findtext("link", "")
            pub_date = item.findtext("pubDate", "")
            source = item.findtext("source", "")
            headlines.append({
                "title": title,
                "link": link,
                "published": pub_date,
                "source": source,
            })
        return headlines
    except Exception as e:
        return [{"error": str(e)}]


def fetch_news_for_movers(prices, debug=False):
    """Fetch news only for tickers that moved >=5%."""
    movers = {k: v for k, v in prices.items() if v.get("is_mover")}
    log(f"Found {len(movers)} movers (>{MOVER_THRESHOLD}% change). Fetching news...", debug)

    news = {}
    for ticker, data in movers.items():
        company = data["name"]
        log(f"  News for {ticker} ({company})...", debug)

        # Primary: Google News RSS
        headlines = fetch_google_news(f'"{company}" OR "{ticker}" stock')

        # Fallback: yfinance news property
        if not headlines or (len(headlines) == 1 and "error" in headlines[0]):
            try:
                stock = yf.Ticker(PORTFOLIO[ticker]["yf"])
                yf_news = stock.news or []
                headlines = [
                    {
                        "title": n.get("title", ""),
                        "link": n.get("link", ""),
                        "published": str(n.get("providerPublishTime", "")),
                        "source": n.get("publisher", ""),
                    }
                    for n in yf_news[:5]
                ]
            except Exception:
                pass

        news[ticker] = headlines
        log(f"    Got {len(headlines)} headlines", debug)

    return news


def main():
    parser = argparse.ArgumentParser(description="Weekly Morning Brief data collector")
    parser.add_argument("--prices", action="store_true", help="Fetch prices only, skip news")
    parser.add_argument("--debug", action="store_true", help="Verbose logging to stderr")
    args = parser.parse_args()

    log("=" * 50)
    log("Weekly Morning Brief — Data Collection")
    log(f"Run at: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    log("=" * 50)

    prices = fetch_prices(debug=args.debug)

    news = {}
    if not args.prices:
        news = fetch_news_for_movers(prices, debug=args.debug)

    output = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "date_display": datetime.now().strftime("%B %d, %Y"),
        "mover_threshold_pct": MOVER_THRESHOLD,
        "prices": prices,
        "news": news,
        "movers": [k for k, v in prices.items() if v.get("is_mover")],
        "errors": [k for k, v in prices.items() if "error" in v],
    }

    print(json.dumps(output, indent=2))
    log(f"\nDone. {len(prices)} tickers processed, {len(news)} with news.")


if __name__ == "__main__":
    main()
