# Weekly Morning Brief — Omaha Inversiones

## Purpose
Automated weekly equity research brief for 16 portfolio positions.
Sent every Monday at 6:30 AM PET via Gmail SMTP.

## Architecture
- `weekly_brief.py` → prices (yfinance) + news headlines (Google News RSS) → JSON
- Claude → reads JSON, filters/verifies news, formats HTML email, writes to file
- `send_email.py` → reads HTML file, sends via Gmail SMTP

## Workflow

### Step 1: Run the data collection script
```bash
pip install -r requirements.txt --break-system-packages
python weekly_brief.py --debug 2>/tmp/brief_log.txt | tee /tmp/brief_data.json
```

### Step 2: Parse the JSON output from /tmp/brief_data.json
The JSON now contains:
- `prices`: each ticker with current_price, chg_7d_pct, chg_30d_pct, chg_6m_pct
- `news_1w`: last-7-day headlines per ticker (for all tickers)
- `news_6m`: broader headlines per ticker (for all tickers)
- `delayed_prices`: tickers where price is from previous close
- `movers`: tickers with >5% move in 1W or 1M

### Step 3: Build the price table
Columns: `Ticker | Company | Today | 1W Chg | 1M Chg | 6M Chg`
- **"Today"**: current price with currency symbol ($, CHF, £, €)
- **Sort by 1W Chg descending** (most positive first, most negative last)
- Show % changes with +/- sign and one decimal
- Highlight movers (>5% in 1W or 1M) with yellow background row
- If `price_delayed: true`, add asterisk (*) to price in Today column

### Step 4: News research for EVERY ticker

**4a. 1W News (last 7 days):**
- Review headlines from `news_1w` in the JSON
- Verify accuracy of every fact before including it (cross-check corporate structures, causality)
- If a headline explains a price driver, include the ROOT CAUSE (e.g. not "coal rallied" but "coal rallied because a major Chinese mine disaster reduced global supply")
- If no fundamental news found in the last 7 days, write: "No material fundamental news this week."
- Write 1 bullet (or 2 if genuinely warranted)

**4b. 6M Context (last 6 months):**
- Review headlines from `news_6m` in the JSON PLUS your own knowledge of recent events
- Focus on structural/fundamental developments: earnings trends, M&A, management changes, regulatory shifts, capital structure events, sector dynamics
- There should almost always be something to write here — dig into the broader picture
- Write 1-3 bullets depending on how much material exists. Group related items.

**4c. What to include (both sections):**
- Earnings, revenue, guidance changes
- M&A activity, divestitures, spin-offs (verify current corporate structure)
- Regulatory actions, legal rulings
- Management changes, proxy fights, activist investors
- Debt issuance, refinancing, capital structure changes
- Industry events (mine disasters, drug approvals, permits, supply disruptions)
- Commodity movements WITH root cause
- Macro factors directly affecting the company

**4d. What to exclude (both sections):**
- Technical analysis, chart patterns
- Analyst price targets (unless with fundamental reasoning)
- "Stock is up/down X%" without explanation
- Momentum, options activity, short interest speculation
- Listicles, generic AI-generated summaries
- News about DIFFERENT companies with similar tickers (e.g. AML = Aston Martin, NOT "AML investigation" about other companies; CNR = Core Natural Resources, NOT Canadian National Railway; JACK = Jack in the Box, NOT Jack Henry or Jack Dorsey)

**4e. Do NOT force bullets.** If 1W has one real item, write one. If 6M has three, write three. Never write filler.

### Step 5: Format the email as HTML

Subject: 📊 Weekly Morning Brief — [DATE in "Month DD, YYYY" format]

```html
<div style="font-family: Arial, Helvetica, sans-serif; color: #1a1a1a; max-width: 720px;">

  <h2 style="margin: 0 0 4px 0; font-size: 18px;">📊 Weekly Morning Brief — [DATE]</h2>
  <p style="margin: 0 0 20px 0; color: #666; font-size: 13px;">Omaha Inversiones — Equity Portfolio</p>

  <table style="border-collapse: collapse; width: 100%; font-size: 13px; margin-bottom: 8px;">
    <thead>
      <tr style="background: #f5f5f5; text-align: left;">
        <th style="padding: 8px 10px; border-bottom: 2px solid #ddd;">Ticker</th>
        <th style="padding: 8px 10px; border-bottom: 2px solid #ddd;">Company</th>
        <th style="padding: 8px 10px; border-bottom: 2px solid #ddd; text-align: right;">Today</th>
        <th style="padding: 8px 10px; border-bottom: 2px solid #ddd; text-align: right;">1W</th>
        <th style="padding: 8px 10px; border-bottom: 2px solid #ddd; text-align: right;">1M</th>
        <th style="padding: 8px 10px; border-bottom: 2px solid #ddd; text-align: right;">6M</th>
      </tr>
    </thead>
    <tbody>
      <!-- SORTED BY 1W Chg DESCENDING -->
      <tr style="background: #fffbeb;"><!-- yellow = mover row -->
        <td style="padding: 6px 10px; border-bottom: 1px solid #eee; font-weight: bold;">HCC</td>
        <td style="padding: 6px 10px; border-bottom: 1px solid #eee;">Warrior Met Coal</td>
        <td style="padding: 6px 10px; border-bottom: 1px solid #eee; text-align: right;">$110.28</td>
        <td style="padding: 6px 10px; border-bottom: 1px solid #eee; text-align: right; color: #16a34a;">+18.5%</td>
        <td style="padding: 6px 10px; border-bottom: 1px solid #eee; text-align: right; color: #16a34a;">+27.9%</td>
        <td style="padding: 6px 10px; border-bottom: 1px solid #eee; text-align: right; color: #16a34a;">+45.2%</td>
      </tr>
    </tbody>
  </table>

  <!-- Delayed price footnote (only if applicable) -->
  <p style="font-size: 11px; color: #999; margin: 0 0 20px 0;">* UHR, AVIO: price as of [date] (latest available close)</p>

  <!-- COMMENTARY FOR EVERY TICKER (sorted same as table: 1W desc) -->
  <h3 style="font-size: 15px; margin: 24px 0 16px 0; border-top: 1px solid #ddd; padding-top: 16px;">Portfolio commentary</h3>

  <!-- Repeat this block for EACH ticker -->
  <div style="margin-bottom: 20px;">
    <p style="margin: 0 0 4px 0; font-size: 14px; font-weight: bold;">[TICKER] — [Company Name]</p>
    <p style="margin: 0 0 8px 0; font-size: 13px;">
      1W: <span style="color: #16a34a;">+X.X%</span> |
      1M: <span style="color: #dc2626;">-X.X%</span> |
      6M: <span style="color: #16a34a;">+X.X%</span>
    </p>

    <p style="margin: 0 0 2px 0; font-size: 12px; font-weight: bold; color: #444;">Last week</p>
    <ul style="margin: 2px 0 8px 0; padding-left: 20px; font-size: 13px;">
      <li>[1W fundamental news with root cause]</li>
      <!-- OR: <li style="color: #999;">No material fundamental news this week.</li> -->
    </ul>

    <p style="margin: 0 0 2px 0; font-size: 12px; font-weight: bold; color: #444;">6M context</p>
    <ul style="margin: 2px 0 0 0; padding-left: 20px; font-size: 13px;">
      <li>[Structural development or trend over last 6 months]</li>
      <li>[Additional item if material exists]</li>
    </ul>
  </div>
  <!-- End repeat -->

  <p style="font-size: 12px; color: #999; margin-top: 20px;">Data issues: [list or "None"]</p>

</div>
```

**Color rules (table AND commentary):**
- Positive: `color: #16a34a` (green)
- Negative: `color: #dc2626` (red)
- Zero/N/A: `color: #666` (gray)

**Mover rows** in table: `background: #fffbeb` (yellow).

No executive summary. No footer. No closing. No sign-off.
Tone: professional, institutional, English.

### Step 6: Write the HTML to file
```bash
# Claude writes the formatted HTML to this file:
cat > /tmp/brief_email.html << 'EOF'
[THE FULL HTML HERE]
EOF
```

### Step 7: Send the email via n8n webhook
```bash
python send_brief_webhook.py
```
This POSTs the HTML to the n8n webhook, which sends the email via Gmail.

If the webhook fails, log the error. The HTML file is preserved at /tmp/brief_email.html for manual review.

## Critical Notes
- **TAVHY** = TAV Havalimanlari Holding A.S. (Turkish airports). NOT Tabcorp.
- **CNR** = Core Natural Resources. NOT Canadian National Railway. Headlines about TSX:CNR are WRONG company.
- **AML** = Aston Martin Lagonda. NOT "AML investigation" (anti-money laundering). Filter out unrelated AML news.
- **JACK** = Jack in the Box. Jack sold Del Taco in 2024 — Del Taco is NOT a subsidiary. Jack Henry (JKHY) is a DIFFERENT company. Block/Jack Dorsey is IRRELEVANT.
- **HCC** = Warrior Met Coal. NOT hepatocellular carcinoma (HCC cancer). Filter out medical HCC news.
- **AVIO** = Avio S.p.A. (Italian aerospace, AVIO.MI). NOT AVGO.
- **DGE** = Diageo (DGE.L). Prices in GBP pence.
- **AML** = Aston Martin (AML.L). Prices in GBP pence.
- **UHR** = Swatch Group (UHR.SW). Prices in CHF.
- **CTT** / **AVIO** = Prices in EUR.
- Do NOT use FMP tools. All data comes from the Python scripts.
