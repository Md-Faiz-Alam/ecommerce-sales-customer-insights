# Power BI Rebuild Guide

Rebuild the dashboard on a proper star schema so every number matches the SQL and notebooks.
Estimated time: **4–6 hours**. Canvas: 1280 × 720 (16:9).

**Files**

| File | What it is |
|---|---|
| `data/powerbi/*.csv` | 8 tables. Create them with `.\tasks.ps1 export` |
| [`measures.dax`](measures.dax) | Every DAX measure, ready to paste |
| [`olist_theme.json`](olist_theme.json) | Colour theme (same colorblind-safe palette as the notebooks) |

---

## What this fixes from the old dashboard

| Old problem | Fix |
|---|---|
| "Data through **March 2024**" (data ends 2018) | `Data Range Label` measure computed from the data, never typed |
| "vs Last Month" shows **0.00%** everywhere | Marked date table + `DATEADD`; MoM only shown when one month is selected |
| Months sorted by value, 2017 and 2018 merged into one "Aug" | X-axis = `'Date'[Month Start]` (continuous), not month name |
| Orders and revenue on one **log** axis | Separate visuals, one measure per axis |
| "Top Sellers Performance" actually plots **cities** | Seller scorecard page using `Sellers[Seller ID]` and `Action Quadrant` |
| `$` currency | `R$` format strings (data is BRL) |
| Portuguese category names | English `Products[Category]` |
| Donut with 7 slices | Ranked bar chart |
| Revenue included canceled orders, freight-less categories | One revenue definition: delivered orders, items + freight |

---

## Step 1: Export the data

```powershell
.\tasks.ps1 pipeline
```
```powershell
.\tasks.ps1 export
```

This creates `data/powerbi/` with: Orders, Order Items, Customers, Products, Sellers, Date, Cohort Retention, Forecast.

## Step 2: Import (Power Query)

1. **Home → Get data → Text/CSV**, and load each of the 8 files (keep the file names as table names).
2. Before loading, click **Transform Data** and check the column types:
   - Every ID column (`Order ID`, `Customer ID`, `Product ID`, `Seller ID`): **Text**
   - `Purchase Date`, `Date`, `Month Start`, `Week Start`, `First Order Date`, `Cohort Month`: **Date**
   - `Purchase Timestamp`: **Date/Time**
   - `Is …` columns: **True/False**
   - Money and rate columns: **Decimal number**
   - If decimals look wrong (e.g. 1562 instead of 15.62), change the type **Using Locale → English (United States)**.
3. **Close & Apply.**

## Step 3: Model (Model view)

Create these relationships (all **one-to-many, single direction**):

| From (one side) | To (many side) |
|---|---|
| `Date[Date]` | `Orders[Purchase Date]` |
| `Customers[Customer ID]` | `Orders[Customer ID]` |
| `Orders[Order ID]` | `Order Items[Order ID]` |
| `Products[Product ID]` | `Order Items[Product ID]` |
| `Sellers[Seller ID]` | `Order Items[Seller ID]` |

```
Date ──┐
       ├──► Orders ──► Order Items ◄── Products
Customers ┘                    ▲
                            Sellers
```

`Cohort Retention` and `Forecast` stay unrelated (they are pre-aggregated).

Then:
1. **Mark `Date` as date table:** select the table → Table tools → Mark as date table → `Date`.
2. **Sort by column** (Column tools → Sort by column):
   - `Date[Month Year]` sorted by `Month Year Sort`
   - `Date[Weekday]` sorted by `Weekday Sort`
   - `Orders[Delivery Timing]` sorted by `Delivery Timing Sort`
3. **Hide** from report view: all `… Sort` columns, `Order Items[Order ID]`, `Order Items[Product ID]`, `Order Items[Seller ID]`, `Orders[Customer ID]`.
4. **Summarisation:** set `Review Score`, `Installments` and `Customer Order Number` to *Don't summarize* (use measures instead).

> **Why Order Items carries revenue:** category and seller filters reach `Order Items`, not `Orders`. Revenue is
> summed from items, so it responds to every slicer. For order-level metrics (late %, reviews) by category,
> use `Orders[Main Category]`.

## Step 4: Measures

1. **Home → Enter data** → name the table `_Measures` → Load.
2. Paste each measure from [`measures.dax`](measures.dax) with **New measure** (one at a time).
3. Set format strings:
   - `Revenue`, `Revenue PM`, `Revenue PY`, `Revenue 3M Avg`: Custom `R$ #,0`
   - `AOV`: `R$ #,0.00`
   - All `%` measures: Percentage, 1 decimal
   - `Avg Review`: 2 decimals · day measures: 1 decimal
4. Delete the dummy column in `_Measures`; it then shows as a measures folder at the top of the Fields pane.

## Step 5: Theme

**View → Themes → Browse for themes** → `dashboard/olist_theme.json`.

---

## Step 6: Pages

Design rules (the same rules as the notebook charts):
- **Every visual title is the takeaway**, not the field name ("Late deliveries triple in peak months", not "Late % by Month").
- One measure per axis. **No dual axes, no donuts, no 3D.**
- Orange is for the thing that needs attention; everything else stays blue or grey.
- Slicers in one row at the top. Page navigation buttons on every page (**Insert → Buttons → Navigator → Page navigator**).

### Page 1: Executive Overview

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ Olist Marketplace: Executive Overview          [Date range][State][Category] │
│ <Data Range Label>                                                           │
├──────────┬──────────┬──────────┬──────────┬──────────┬──────────────────────┤
│ Revenue  │ Orders   │Customers │ AOV      │ Late %   │ Avg Review           │
│ R$15.4M  │ 99.1K    │ 95.8K    │ R$159.78 │ 6.8%     │ 4.09                 │
│<MoM Label>                                                                   │
├──────────────────────────────────────┬───────────────────────────────────────┤
│ Revenue grew 143% YoY, then          │ 18 of 74 categories make up 81% of    │
│ plateaued in 2018 (line)             │ revenue (bar, top 10)                 │
├──────────────────────────────────────┼───────────────────────────────────────┤
│ Peak months break delivery (line)    │ SP, RJ and MG are 63% of revenue (bar)│
└──────────────────────────────────────┴───────────────────────────────────────┘
```

| Visual | Fields | Settings |
|---|---|---|
| 6 KPI cards (Card, new) | `Revenue`, `Orders`, `Customers`, `AOV`, `Late %`, `Avg Review` | Reference label: `MoM Label` on the Revenue card |
| Line chart | X: `Date[Month Start]`, Y: `Revenue`, `Revenue 3M Avg` | X-axis type **Continuous**, date format `MMM yy`; 3M avg dashed |
| Bar chart | Y: `Products[Category]`, X: `Revenue` | Filter: Top N = 10 by `Revenue`; data labels on |
| Line chart | X: `Date[Month Start]`, Y: `Late %` | Constant line at 6.8% labelled "average" |
| Bar chart | Y: `Orders[Customer State]`, X: `Revenue` | Top 10 |
| Slicers | `Date[Date]` (Between), `Orders[Customer State]`, `Products[Category]` | Dropdown style |
| Text box | `Data Range Label` (as a card with no category label) | Small, grey |

### Page 2: Delivery & Satisfaction (the flagship page)

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ Late delivery is the #1 driver of bad reviews                                │
├────────────┬────────────┬────────────┬────────────┬─────────────────────────┤
│ Late %     │ Avg deliv. │ Avg promise│ Buffer     │ Negative review %       │
│ 6.8%       │ 12.5 d     │ 23.6 d     │ 11.1 d     │ 14.6%                   │
├────────────────────────────────────────┬─────────────────────────────────────┤
│ HERO: One day late doubles bad reviews │ Late % by customer state, vs Brazil │
│ (column: Negative Review % by          │ average (bar, sorted desc)          │
│  Delivery Timing)                      │                                     │
├────────────────────────────────────────┴─────────────────────────────────────┤
│ Late % by month: Black Friday 12%, Feb–Mar 2018 14–19% (line)                │
└──────────────────────────────────────────────────────────────────────────────┘
```

| Visual | Fields | Settings |
|---|---|---|
| Hero column chart | X: `Orders[Delivery Timing]`, Y: `Negative Review %` | Visual filter: exclude "Not delivered". Data labels on. **Conditional colour**: Columns → fx → Rules on `Delivery Timing Sort`: ≥ 4 → orange `#EB6834`, else blue `#2A78D6` |
| Bar chart | Y: `Orders[Customer State]`, X: `Late %` | Sort descending; constant line = `Late % (All States)`; conditional colour: value > 0.068 → orange |
| Line chart | X: `Date[Month Start]`, Y: `Late %` | Continuous axis |
| 5 cards | `Late %`, `Avg Delivery Days`, `Avg Promised Days`, `Promise Buffer Days`, `Negative Review %` | |
| Text box | "Early delivery earns no credit; customers judge against the promise. Fix: per-route promises (ML model, notebook 06) and a day-0 alert for at-risk orders (notebook 07)." | |

### Page 3: Customers & Retention

| Visual | Fields | Settings |
|---|---|---|
| Cards | `Customers`, `Repeat Customer %` | |
| Matrix (cohort heatmap) | Rows: `Cohort Retention[Cohort]`, Columns: `Months Since First Order`, Values: `Retention Rate` | Filter months 1–12. Cell elements → Background colour → gradient (theme min → max). Format 0.0% |
| Clustered bar | Y: `Customers[RFM Segment]`, X: `Customer Share`, `Revenue Share` | Filter out "No delivered order". Title: "At-risk big spenders: 15% of customers, 27% of revenue" |
| Table | `RFM Segment`, `Customers`, `Revenue`, `Revenue Share` | Sorted by Revenue |
| Text box | Recommended actions per segment (from notebook 03) | |

### Page 4: Seller Performance

| Visual | Fields | Settings |
|---|---|---|
| Cards | `Active Sellers`, `Top 10% Seller Revenue Share`, `Fix-First Sellers`, `Fix-First Revenue Share` | |
| Scatter | X: `Sellers[Revenue (window)]` (log scale), Y: `Sellers[Negative Review Rate]`, Values: `Seller ID`, Legend: `Action Quadrant` | Filter out "Low volume" and "No orders in window". Colours: "fix first" orange, others grey |
| Table | `Seller ID`, `State`, `Orders (window)`, `Revenue (window)`, `Late Rate`, `Negative Review Rate`, `Action Quadrant` | Filter: Action Quadrant = fix first; sort by revenue; data bars on revenue |
| **Drill-through** (advanced) | New page "Seller Detail" with drill-through field `Sellers[Seller ID]`: cards plus a monthly revenue line | Right-click any seller → Drill through |

### Page 5 (optional): Planning (ML)

| Visual | Fields | Settings |
|---|---|---|
| Line chart | X: `Forecast[Date]`, Y: `Actual Orders`, `Forecast Orders` | Error bars (Analytics pane) on `Forecast Orders`: upper `Forecast High (80%)`, lower `Forecast Low (80%)` |
| Text box | Promise-model result: "Late deliveries 3.6% → 1.7% with promises 1.1 days shorter (test months). See notebook 06." | |

---

## Step 7: Check your numbers

With **no slicers applied**, your visuals should show exactly these values (computed from the same CSVs).
If a number differs, check the relationships and the `Is Delivered` filter in `Revenue`.

| Measure / visual | Expected |
|---|---|
| Revenue | **R$15,371,741** (card: R$15.37M) |
| Orders | 99,092 |
| Delivered Orders | 96,203 |
| Customers | 95,774 |
| AOV | R$159.78 |
| Late % | 6.79% |
| Avg Review | 4.09 |
| Negative Review % | 14.63% |
| Avg Delivery Days / Avg Promised Days | 12.5 / 23.6 |
| Repeat Customer % | 3.13% |
| Lost Order % | 1.19% |
| Revenue, Nov 2017 · MoM | R$1,153,229 · +53.5% |
| Revenue, Aug 2018 · YoY | R$985,492 · +52.6% (August is partial, see note) |
| Negative Review % by Delivery Timing | 8+ early 9.0% · 1–7 early 10.2% · on day 12.4% · 1–3 late 32.1% · 4–7 late 67.7% · 8+ late 79.3% |
| Top 10% Seller Revenue Share | 66.2% (295 of 2,945 sellers) |
| Fix-First Sellers · revenue share | 164 · 33.9% |
| RFM revenue share: New high-value / At-risk big spenders | 28.2% / 27.5% |

## Step 8: Publish

1. Save as `dashboard/Olist_Insights.pbix` (it's git-ignored because of its size; attach it to a GitHub Release).
2. **Screenshots:** File → Export → PDF, or Windows `Win + Shift + S`, one PNG per page → save to `images/`
   (`dashboard_overview.png`, `dashboard_delivery.png`, `dashboard_customers.png`, `dashboard_sellers.png`).
3. **GIF:** record a 15–20 s walkthrough with [ScreenToGif](https://www.screentogif.com/) (free): click a slicer,
   select one month to show the MoM label, drill through to a seller. Save as `images/dashboard.gif` (keep it under 5 MB).
4. Delete the old `images/dashboard.png` if you no longer use it.
5. Optional: **Publish to web** from Power BI Service and put the link in the README.

## Interview talking points

- "I rebuilt the model as a **star schema** with a marked date table. That fixed broken MoM measures and month sorting."
- "Revenue is summed from the item fact, so product and seller filters work; order-level KPIs come from the order fact."
- "`Top 10% Seller Revenue Share` uses `ADDCOLUMNS` + `TOPN` to rank sellers inside the current filter context."
- "Every number reconciles with the SQL warehouse; I kept a checklist of expected values."
