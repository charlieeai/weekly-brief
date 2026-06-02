# Weekly Morning Brief — Omaha Inversiones

## Purpose
This repo powers a weekly automated equity research brief for 16 portfolio positions.
The brief is sent every Monday morning via Gmail.

## Architecture
- `weekly_brief.py` → Python script that fetches prices (yfinance) and news headlines (Google News RSS)
- Claude Code Routine → runs the script, applies fundamental news judgment, formats the brief, sends via Gmail MCP

## Workflow

### Step 1: Install dependencies and run the script
```bash
pip install -r requirements.txt
python weekly_brief.py --debug 2>/tmp/brief_log.txt | tee /tmp/brief_data.json
```

### Step 2: Parse the JSON output from /tmp/brief_data.json

### Step 3: Build the price table
Format: `Ticker | Company | Price Chg. 1W | Price Chg. 1M`
- Sort by sector, then by ticker alphabetically
- Show % changes with +/- sign and one decimal place
- Include currency symbol for non-USD tickers (CHF, GBP, EUR)
- If a ticker has an error, show "N/A — [reason]" in its row

### Step 4: Filter news for movers (>5% change in 1W or 1M)
For each mover, review the raw headlines from the JSON.

**ONLY include news about fundamentals:**
- Earnings, revenue, guidance changes
- M&A activity, divestitures
- Regulatory actions, legal rulings
- Management changes (CEO, CFO, board)
- Debt issuance, refinancing, capital structure changes
- Industry-specific material events (mine permits, drug approvals, etc.)
- Macro factors directly affecting the company (tariffs on their products, etc.)

**EXCLUDE all of the following:**
- Technical analysis, chart patterns, support/resistance levels
- Analyst price targets or rating changes (unless accompanied by fundamental reasoning)
- "Stock is up/down X%" without explanation
- Momentum, options activity, short interest speculation
- Listicles ("10 stocks to buy now")

Write 2-3 concise bullet points per mover. If no fundamental news exists, state:
"No material fundamental news identified in the past 7 days."

### Step 5: Format the email exactly as follows

Subject: 📊 Weekly Morning Brief — [DATE in "Month DD, YYYY" format]

Body (plain text):

```
📊 WEEKLY MORNING BRIEF — [DATE]
Omaha Inversiones — Equity Portfolio

Ticker | Company                    | 1W Chg  | 1M Chg
-------|----------------------------|---------|--------
UHR    | Swatch Group               | +X.X%   | +X.X%
...    | ...                        | ...     | ...

---

MOVERS COMMENTARY (+/- 5%)

[TICKER] — [Company Name]
• 1W Change: X.X% | 1M Change: X.X%
• [Fundamental explanation 1]
• [Fundamental explanation 2, if relevant]

---

Tickers with data issues: [list any errors, or "None"]
```

No executive summary. No footer. No closing remarks. No sign-off.
Tone: professional, institutional, English.

### Step 6: Send via Gmail
- To: dante@omaha.pe
- From: charlieai@omaha.pe
- Subject: 📊 Weekly Morning Brief — [DATE]
- Body: the formatted brief above
- Send immediately. Do not ask for confirmation.

## Critical Notes
- **TAVHY** = TAV Havalimanlari Holding A.S. (Turkish airport operator). NOT Tabcorp.
- **CNR** = Core Natural Resources. NOT Canadian National Railway.
- **AVIO** = Avio S.p.A. (Italian aerospace, Milan: AVIO.MI). NOT AVGO.
- **DGE** = Diageo (London: DGE.L). Prices in GBP pence.
- **AML** = Aston Martin Lagonda (London: AML.L). Prices in GBP pence.
- **UHR** = Swatch Group (SIX: UHR.SW). Prices in CHF.
- **CTT** = CTT Correios de Portugal (Euronext: CTT.LS). Prices in EUR.
- **AVIO** = Avio S.p.A. (Borsa Italiana: AVIO.MI). Prices in EUR.
- Do NOT use FMP tools. All data comes from the Python script.
- If the script fails, check /tmp/brief_log.txt for errors.
