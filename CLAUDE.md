# Weekly Morning Brief — Omaha Inversiones

## Purpose
This repo powers a weekly automated equity research brief for 16 portfolio positions.
The brief is created as a Gmail draft every Monday morning.

## Architecture
- `weekly_brief.py` → Python script that fetches prices (yfinance) and news headlines (Google News RSS)
- Claude Code Routine → runs the script, applies fundamental news judgment, formats the brief, creates Gmail draft

## Workflow

### Step 1: Install dependencies and run the script
```bash
pip install -r requirements.txt --break-system-packages
python weekly_brief.py --debug 2>/tmp/brief_log.txt | tee /tmp/brief_data.json
```

### Step 2: Parse the JSON output from /tmp/brief_data.json

### Step 3: Build the price table
Columns: `Ticker | Company | Today | 1W Chg | 1M Chg`
- **"Today" column**: shows the current price from the JSON, with currency symbol (e.g. $43.73, CHF 192.40, £12.55, €4.32)
- **Sort by 1W Chg descending** (largest positive first, most negative last)
- Show % changes with +/- sign and one decimal place
- If a ticker has an error, show "N/A" in the price columns

### Step 4: News research for movers (>5% change in 1W or 1M)

**4a. Review the raw headlines from the JSON first.**

**4b. Verify accuracy of every headline before including it.** Cross-check facts:
- If a headline says "company X is a subsidiary of Y", verify that is CURRENTLY true (not outdated info from a past corporate structure)
- If a headline describes a price driver, explain the ROOT CAUSE, not just the surface event. Example: don't just say "hard coking coal prices rallied" — explain WHY (e.g. supply disruption from a mine disaster in China reducing global supply)
- If a headline seems generic or vague, discard it

**4c. If the script's headlines are insufficient for a mover with >5% change, you MUST search harder:**
- Search for the company name + "news" in the last 7-14 days
- Search for the industry/commodity + recent events
- Check if there were earnings releases, M&A announcements, regulatory actions
- A >5% move almost always has a fundamental explanation — find it

**4d. What to include:**
- Earnings, revenue, guidance changes
- M&A activity, divestitures, spin-offs (verify current corporate structure)
- Regulatory actions, legal rulings
- Management changes (CEO, CFO, board)
- Debt issuance, refinancing, capital structure changes
- Industry-specific material events (mine disasters, drug approvals, permits, supply disruptions)
- Commodity price movements WITH their root cause
- Macro factors directly affecting the company (tariffs, sanctions, policy changes)

**4e. What to exclude:**
- Technical analysis, chart patterns, support/resistance levels
- Analyst price targets or rating changes (unless with fundamental reasoning)
- "Stock is up/down X%" without explanation
- Momentum, options activity, short interest speculation
- Listicles ("10 stocks to buy now")

**4f. Bullet point rules:**
- Write 1-3 bullet points per mover, as many as there are REAL fundamental items to report
- Do NOT force a second or third bullet point if there is only one real piece of news
- Do NOT write filler like "No company-specific fundamental news identified" — if you have one solid bullet, that's enough
- Each bullet must contain a specific, verifiable fact with its root cause

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
        <th style="padding: 8px 12px; border-bottom: 2px solid #ddd; text-align: right;">Today</th>
        <th style="padding: 8px 12px; border-bottom: 2px solid #ddd; text-align: right;">1W Chg</th>
        <th style="padding: 8px 12px; border-bottom: 2px solid #ddd; text-align: right;">1M Chg</th>
      </tr>
    </thead>
    <tbody>
      <!-- SORTED BY 1W CHG DESCENDING (most positive first) -->
      <tr style="background: #fffbeb;"><!-- yellow highlight = mover -->
        <td style="padding: 6px 12px; border-bottom: 1px solid #eee; font-weight: bold;">AVIO</td>
        <td style="padding: 6px 12px; border-bottom: 1px solid #eee;">Avio S.p.A.</td>
        <td style="padding: 6px 12px; border-bottom: 1px solid #eee; text-align: right;">€43.07</td>
        <td style="padding: 6px 12px; border-bottom: 1px solid #eee; text-align: right; color: #16a34a;">+25.1%</td>
        <td style="padding: 6px 12px; border-bottom: 1px solid #eee; text-align: right; color: #16a34a;">+38.5%</td>
      </tr>
      <tr><!-- normal row, not a mover -->
        <td style="padding: 6px 12px; border-bottom: 1px solid #eee; font-weight: bold;">NKE</td>
        <td style="padding: 6px 12px; border-bottom: 1px solid #eee;">Nike</td>
        <td style="padding: 6px 12px; border-bottom: 1px solid #eee; text-align: right;">$43.73</td>
        <td style="padding: 6px 12px; border-bottom: 1px solid #eee; text-align: right; color: #dc2626;">-2.1%</td>
        <td style="padding: 6px 12px; border-bottom: 1px solid #eee; text-align: right; color: #16a34a;">+1.5%</td>
      </tr>
      <!-- ... repeat for all 16 tickers, sorted by 1W Chg desc ... -->
    </tbody>
  </table>

  <!-- Only for movers with >5% change in 1W or 1M -->
  <h3 style="font-size: 15px; margin: 24px 0 12px 0; border-top: 1px solid #ddd; padding-top: 16px;">Movers commentary</h3>

  <p style="margin: 0 0 4px 0; font-size: 14px; font-weight: bold;">[TICKER] — [Company Name]</p>
  <p style="margin: 0 0 4px 0; font-size: 13px;">
    1W: <span style="color: #16a34a;">+X.X%</span> | 1M: <span style="color: #dc2626;">-X.X%</span>
  </p>
  <!-- Color each % individually: green if positive, red if negative -->
  <ul style="margin: 4px 0 16px 0; padding-left: 20px; font-size: 13px;">
    <li>[Verified fundamental explanation with root cause]</li>
    <!-- Only add more bullets if there are MORE real fundamental items -->
  </ul>

  <!-- If tickers had errors -->
  <p style="font-size: 12px; color: #999; margin-top: 20px;">Data issues: [list or "None"]</p>

  <!-- If any tickers have price_delayed: true in the JSON -->
  <!-- Add footnote below the table (before movers section) like: -->
  <!-- <p style="font-size: 11px; color: #999; margin: -16px 0 20px 0;">* UHR, AVIO: price as of [date] (latest available close)</p> -->

</div>
```

**Color rules for % changes (apply everywhere: table AND commentary):**
- Positive: `color: #16a34a` (green)
- Negative: `color: #dc2626` (red)
- Zero or N/A: `color: #666` (gray)

**Mover rows** in the table: add `background: #fffbeb` (light yellow).

**Delayed prices:** If the JSON has `"price_delayed": true` for any ticker, add an asterisk (*) next to the price in the Today column, and include a footnote below the table: `"* [TICKER(s)]: price as of [date] (latest available close)"`. Place this footnote between the table and the movers commentary.

No executive summary. No footer. No closing remarks. No sign-off.
Tone: professional, institutional, English.

### Step 6: Create Gmail DRAFT (do NOT send)
- To: dante@omaha.pe
- Subject: 📊 Weekly Morning Brief — [DATE]
- Body: the HTML formatted brief above. Create as **HTML draft**, not plain text.
- **CREATE DRAFT ONLY. Do NOT send the email.** The user will review and send manually.

## Critical Notes
- **TAVHY** = TAV Havalimanlari Holding A.S. (Turkish airport operator). NOT Tabcorp. NOT Tabcorp Holdings.
- **CNR** = Core Natural Resources. NOT Canadian National Railway. NOT any Canadian company.
- **AVIO** = Avio S.p.A. (Italian aerospace, Borsa Italiana: AVIO.MI). NOT AVGO.
- **DGE** = Diageo (London: DGE.L). Prices in GBP pence.
- **AML** = Aston Martin Lagonda (London: AML.L). Prices in GBP pence.
- **UHR** = Swatch Group (SIX: UHR.SW). Prices in CHF.
- **CTT** = CTT Correios de Portugal (Euronext: CTT.LS). Prices in EUR.
- **AVIO** = Avio S.p.A. (Borsa Italiana: AVIO.MI). Prices in EUR.
- **JACK** = Jack in the Box. Note: Jack sold Del Taco in 2024. Del Taco is NO LONGER a subsidiary.
- Do NOT use FMP tools. All data comes from the Python script.
- If the script fails, check /tmp/brief_log.txt for errors.
