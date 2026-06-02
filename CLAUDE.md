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

### Step 5: Format the email as HTML

Subject: 📊 Weekly Morning Brief — [DATE in "Month DD, YYYY" format]

Body must be **HTML** (not plain text). Use this template structure:

```html
<div style="font-family: Arial, Helvetica, sans-serif; color: #1a1a1a; max-width: 720px;">

  <h2 style="margin: 0 0 4px 0; font-size: 18px;">📊 Weekly Morning Brief — [DATE]</h2>
  <p style="margin: 0 0 20px 0; color: #666; font-size: 13px;">Omaha Inversiones — Equity Portfolio</p>

  <table style="border-collapse: collapse; width: 100%; font-size: 13px; margin-bottom: 24px;">
    <thead>
      <tr style="background: #f5f5f5; text-align: left;">
        <th style="padding: 8px 12px; border-bottom: 2px solid #ddd;">Ticker</th>
        <th style="padding: 8px 12px; border-bottom: 2px solid #ddd;">Company</th>
        <th style="padding: 8px 12px; border-bottom: 2px solid #ddd; text-align: right;">1W Chg</th>
        <th style="padding: 8px 12px; border-bottom: 2px solid #ddd; text-align: right;">1M Chg</th>
      </tr>
    </thead>
    <tbody>
      <!-- One row per ticker, sorted by sector then ticker -->
      <tr>
        <td style="padding: 6px 12px; border-bottom: 1px solid #eee; font-weight: bold;">UHR</td>
        <td style="padding: 6px 12px; border-bottom: 1px solid #eee;">Swatch Group</td>
        <td style="padding: 6px 12px; border-bottom: 1px solid #eee; text-align: right; color: #16a34a;">+X.X%</td>
        <td style="padding: 6px 12px; border-bottom: 1px solid #eee; text-align: right; color: #dc2626;">-X.X%</td>
      </tr>
      <!-- ... repeat for all 16 tickers ... -->
    </tbody>
  </table>

  <!-- Only if there are movers (>5% change) -->
  <h3 style="font-size: 15px; margin: 24px 0 12px 0; border-top: 1px solid #ddd; padding-top: 16px;">Movers commentary (+/- 5%)</h3>

  <p style="margin: 0 0 4px 0; font-size: 14px; font-weight: bold;">[TICKER] — [Company Name]</p>
  <p style="margin: 0 0 4px 0; font-size: 13px; color: #666;">1W: X.X% | 1M: X.X%</p>
  <ul style="margin: 4px 0 16px 0; padding-left: 20px; font-size: 13px;">
    <li>[Fundamental explanation 1]</li>
    <li>[Fundamental explanation 2, if relevant]</li>
  </ul>

  <!-- If tickers had errors -->
  <p style="font-size: 12px; color: #999; margin-top: 20px;">Data issues: [list or "None"]</p>

</div>
```

**Color rules for % changes:**
- Positive changes: use `color: #16a34a` (green)
- Negative changes: use `color: #dc2626` (red)
- Zero or N/A: use `color: #666` (gray)

**Rows with >5% change** (movers): add `background: #fffbeb` (light yellow) to highlight them in the table.

No executive summary. No footer. No closing remarks. No sign-off.
Tone: professional, institutional, English.

### Step 6: Send via Gmail as HTML
- To: dante@omaha.pe
- From: charlieai@omaha.pe
- Subject: 📊 Weekly Morning Brief — [DATE]
- Body: the HTML formatted brief above. Send as **HTML email**, not plain text.
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
