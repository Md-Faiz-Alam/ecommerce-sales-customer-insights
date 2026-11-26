# Project Review & Standout Plan

Target roles: **Data Analyst / Data Scientist** · Python **3.13** · Dataset: Olist Brazilian E-commerce (Sep 2016 – Oct 2018)

---

## Part 1 — Review: what's wrong today

### Critical (a recruiter will notice these)

| # | Issue | Where | Why it matters |
|---|-------|-------|----------------|
| 1 | `eda.ipynb` is **0 bytes (empty)**, but the README advertises an EDA | `python/eda.ipynb` | Recruiters who open it will assume the README claims aren't backed up |
| 2 | Hardcoded `E:/...` absolute paths (project now lives on `F:`) | `data_cleaning.ipynb` cells 36, 45 | The notebook can't be re-run, so it isn't reproducible |
| 3 | `venv/` is broken (points to `C:\Program Files\Python313`, which no longer exists) | `venv/` | Can't run anything |
| 4 | `CREATE DATABASE ecommerce; USE ecommerce; DROP DATABASE ecommerce;` | `data_preparation.sql` line 7–9 | Running the script top to bottom deletes the database |
| 5 | Dashboard says **"Data through March 2024"**, but the data ends **Oct 2018** | Power BI | Factual error on the first screen |
| 6 | Trend chart: months sorted by value, not by time; 2017 and 2018 merged into the same "Aug"; orders and revenue on one log axis | Power BI | Shows the trend wrongly |
| 7 | All "vs Last Month" KPIs show **0.00%** | Power BI | The DAX measure is broken |
| 8 | "Top Sellers Performance" actually plots **cities** sorted alphabetically (xaxim, xanxere…) | Power BI | The chart doesn't show what its title says |
| 9 | Category names in Portuguese (`cama_mesa_banho`); the translation file is in `data/raw` but never used | Everywhere | Unpolished |
| 10 | Currency shown as **$**, but Olist revenue is **BRL (R$)** | Power BI / README | Domain error |

### Analytical correctness issues

- **Revenue definition is inconsistent:** total revenue = `SUM(payment_value)` over *all* orders, including canceled and unavailable ones (R$16.01M vs **R$15.42M delivered only**). Category revenue = `SUM(price)`, which excludes freight. The two can't be reconciled.
- **AOV in the CLV query** = `AVG(payment_value)`, which is per payment row, not per order (orders with several payments/vouchers skew it).
- **"Total customers"** should use `customer_unique_id` (96,096), not `customer_id` (99,441). The README says 99,441.
- **Product cleaning fills missing weight/dimensions with 0.** A product weighing 0 g is false data. Use NaN plus a flag, or impute by category median.
- **`review_score.fillna(0)`** would create fake 0-star reviews (the scale is 1–5).
- **Reviews:** 814 duplicate `review_id`s and 551 orders with several reviews, deduplicated with no rule.
- **Cleaning output is inconsistent:** orders saved with `\N` for nulls, other tables not; SQL declares `NOT NULL` on columns that were filled with placeholder text ("No Title").
- **Customer segmentation thresholds** (R$500 / R$1000) are arbitrary and not justified with data.
- Unused imports (`seaborn`, `matplotlib`) in the cleaning notebook; typo `-- Revenuse`; ~70 trailing blank lines in the SQL.
- `sellers` and `geolocation` tables are never used, so seller and geo analysis is missing.

### Repo hygiene

- **182 MB of CSVs committed** (geolocation alone is 61 MB; GitHub warns above 50 MB). `.git` is already 112 MB. Raw data shouldn't live in Git; use a download script.
- 36 MB `.pbix` in Git (put it in a GitHub Release or Git LFS).
- Empty `presentation/` folder.
- `requirements.txt` is unpinned and lists `sqlalchemy`/`openpyxl`, which aren't used.
- README project tree lists `powerbi_dashboard.pbix`, but the real file name is different.
- No tests, no license, no `src/` code; everything lives in notebook cells.

### What's good (keep it)

Clear business framing, a real multi-table dataset, SQL + Python + Power BI coverage, and a dashboard with a decent visual layout.

---

## Part 2 — Headline findings already in the data (build the story around these)

I verified these on the raw data:

| Finding | Number | Story |
|---|---|---|
| Repeat-customer rate | **3.1%** of 96,096 customers ever reorder | Retention is the #1 business problem |
| Late deliveries | **6.8%** of delivered orders (arrived on a later calendar day than promised) | — |
| Review score: on-time vs late | **4.29 vs 2.27** | Lateness costs about 2 stars, which is the strongest lever |
| Avg delivery time | **12.1 days** | — |
| Revenue delivered vs booked | R$15.42M vs R$16.01M | ~R$590K leakage from canceled/unavailable orders |
| Data tail | Sep–Oct 2018 has only 20 orders | Must be cut off, or forecasts and trends break |

Generic projects stop at "revenue is 16M". You'll stand out by turning the chain **late delivery → bad review → no repeat purchase** into the project's central story and putting a number on it.

---

## Part 3 — Target architecture

```
ecommerce-insights/
├── README.md                  # executive summary first, then details
├── pyproject.toml             # deps pinned for Python 3.13 (or requirements.txt + requirements.lock)
├── Makefile / tasks.ps1       # one command: setup, data, pipeline, test, app
├── .pre-commit-config.yaml    # ruff + nbstripout
├── .github/workflows/ci.yml   # lint + tests on every push
├── data/
│   ├── raw/        (gitignored; filled by scripts/download_data.py via Kaggle API)
│   └── processed/  (gitignored; parquet)
├── sql/
│   ├── 01_staging/            # typed, cleaned views
│   ├── 02_marts/              # star schema: fact_orders, fact_order_items, dim_customer, dim_product, dim_seller, dim_date
│   └── 03_analysis/           # cohort, RFM, pareto, MoM growth, seller scorecard (window functions, CTEs)
├── src/ecom/
│   ├── config.py              # paths via pathlib, no hardcoded drives
│   ├── ingest.py
│   ├── clean.py               # documented cleaning rules
│   ├── validate.py            # pandera data contracts
│   ├── build_warehouse.py     # loads into DuckDB, runs sql/
│   ├── features.py
│   └── models/ (late_delivery.py, review_risk.py, forecast.py, segmentation.py)
├── notebooks/                 # numbered, story-driven, import from src/
│   ├── 01_data_quality_report.ipynb
│   ├── 02_business_overview.ipynb
│   ├── 03_customer_retention_cohorts.ipynb
│   ├── 04_delivery_vs_satisfaction.ipynb
│   ├── 05_seller_and_geo_analysis.ipynb
│   ├── 06_rfm_segmentation.ipynb
│   ├── 07_review_risk_model.ipynb
│   └── 08_demand_forecast.ipynb
├── app/streamlit_app.py       # live, deployed dashboard + model demo
├── dashboard/                 # .pbix via Release/LFS + screenshots
├── reports/
│   ├── executive_summary.pdf  # 1-page memo for a manager
│   └── figures/
└── tests/                     # pytest: cleaning rules, SQL row-count reconciliation, feature leakage checks
```

**Why DuckDB instead of MySQL:** a reviewer can reproduce everything with `pip install` (no server, no `LOAD DATA INFILE` path setup). It's widely used in modern analytics. Keep the SQL ANSI-style so the MySQL skill still shows.

---

## Part 4 — Implementation plan (in order)

### Phase 0: Cleanup & foundation (½ day)
- [ ] Delete the broken `venv/`, empty `presentation/`, and empty `python/eda.ipynb` (commands below)
- [ ] New venv on Python 3.13; `pyproject.toml` with pinned versions
- [ ] Move raw data out of Git; add `scripts/download_data.py` (Kaggle API, with a manual-download fallback in the README)
- [ ] `.gitignore`: `data/`, `*.parquet`, `*.duckdb`, `.ruff_cache`, `mlruns/`
- [ ] `ruff`, `nbstripout`, pre-commit
- [ ] MIT `LICENSE`

### Phase 1: Reproducible data pipeline (1–2 days)
- [ ] `src/ecom/clean.py` with an explicit rule per table:
  - translate categories to English; keep `unknown` as an explicit category
  - product dims: NaN + `is_missing_dims` flag (no fake 0s)
  - reviews: keep the latest review per order; document the 814 duplicates
  - order status: keep everything in staging; define `is_completed = status == 'delivered'`
  - trim the time window to **2017-01-01 → 2018-08-31** (sparse head/tail), documented
- [ ] `validate.py` (pandera): PK uniqueness, FK integrity, `review_score ∈ [1,5]`, `price > 0`, delivery date ≥ purchase date
- [ ] Output parquet + a `warehouse.duckdb`
- [ ] **One command** rebuilds everything: `python -m ecom.pipeline`

### Phase 2: SQL analytics layer (1–2 days) — the DA skill showcase
- [ ] Star schema marts with a single **metric definitions** doc (Revenue = delivered items `price + freight`; GMV vs net; AOV per order)
- [ ] Advanced queries (window functions are what interviewers look for):
  - MoM / YoY growth with `LAG()`
  - Monthly **cohort retention matrix**
  - **RFM** scores with `NTILE()`
  - **Pareto**: % of revenue from top 20% of categories/sellers (running `SUM() OVER`)
  - **Seller scorecard**: revenue, late %, avg rating, cancellation rate, rank with `DENSE_RANK()`
  - State-level delivery time vs freight cost (uses `sellers` + `geolocation`)
- [ ] SQL data-quality tests (row-count reconciliation raw vs mart, orphan keys)

### Phase 3: Analysis notebooks — insight, not charts (2–3 days)
Every notebook follows **Question → Method → Finding → Business impact → Recommendation**.
- [ ] **01 Data quality report:** what was wrong, what you did, how many rows were affected
- [ ] **02 Business overview:** GMV trend, seasonality (Black Friday Nov-2017 spike), category Pareto
- [ ] **03 Retention:** cohort heatmap; 3.1% repeat rate; time-to-second-order
- [ ] **04 Delivery → satisfaction (flagship):** late vs on-time ratings, **Mann-Whitney U test + effect size**, rating vs days-late curve; **impact estimate**, e.g. "halving late deliveries in the worst 5 states would move X orders from ≤2★ to ≥4★"
- [ ] **05 Seller & geo:** seller scorecard quadrant (volume vs quality); delivery time by state on a choropleth (plotly)
- [ ] Use plotly or a consistent matplotlib style; export key figures to `reports/figures/`

### Phase 4: Data science (3–4 days): pick these 3, do them well
1. **Negative-review risk model** (flagship DS piece)
   - Target: `review_score ≤ 2`. Features use **only information known at purchase/shipping time** (estimated delivery days, freight ratio, seller history, distance from customer to seller via geolocation, category, installments, item count)
   - **Time-based split** (train ≤ Apr-2018, test after), with no random split
   - Baseline logistic regression → LightGBM; metrics: PR-AUC, recall at top-10% flagged
   - **SHAP** explanations; translate into a business action ("proactive voucher for top-risk orders; cost vs saved-rating tradeoff")
   - Leakage test in `tests/` (no post-delivery columns in features)
2. **Customer segmentation:** RFM + KMeans (silhouette/elbow), named personas with a recommended action and revenue share per segment. Note honestly that with a 3% repeat rate, classic CLV models (BG/NBD) are weak. Saying this shows maturity.
3. **Demand forecast:** weekly orders, total and top-5 categories; `statsforecast` (AutoETS/AutoARIMA) vs seasonal-naive baseline; backtesting with MAPE/MASE.
- Optional bonus: **Review NLP**: TF-IDF + logistic regression on Portuguese review text to find the topics behind 1★ reviews (delivery, wrong item, quality).

### Phase 5: Make it live (1–2 days): the biggest differentiator
- [ ] **Streamlit app** deployed free on Streamlit Community Cloud (reads a small parquet sample/aggregates committed to the repo):
  - Page 1: KPI overview with filters (date, state, category)
  - Page 2: Cohort and RFM explorer
  - Page 3: Seller scorecard
  - Page 4: "Score an order": the review-risk model with SHAP explanation
- [ ] Live link at the top of the README and on your resume

### Phase 6: Power BI fixes (½–1 day)
- [ ] Proper star schema + a **Date table** (mark as date table) → fixes month sorting and the 0% MoM
- [ ] DAX: `Revenue`, `Revenue PM = CALCULATE([Revenue], DATEADD('Date'[Date], -1, MONTH))`, `MoM %`, `Late %`, `Repeat Rate`
- [ ] Fix title date, R$ currency, English categories, a real top-sellers visual, line chart for the trend (no log scale, no mixed units)
- [ ] Add a page: **Delivery & Satisfaction** (the flagship story)
- [ ] Publish to web (if allowed) or upload a GIF + PDF export

### Phase 7: Engineering quality (½ day)
- [ ] `pytest` tests: cleaning rules, metric definitions (revenue reconciles between SQL and pandas), no leakage
- [ ] GitHub Actions: ruff + pytest on a small fixture sample
- [ ] Type hints and docstrings in `src/`

### Phase 8: Storytelling & packaging (1 day)
- [ ] README rewrite: **TL;DR with 3 numbers**, live app link, architecture diagram, key findings with $ impact, model results table, how to reproduce (3 commands), limitations, next steps
- [ ] `reports/executive_summary.pdf`: one page, written for a manager
- [ ] Remove the emoji-heavy template style; write in a crisp, business tone
- [ ] Short LinkedIn post / Medium write-up of the delivery → rating finding

**Total: ~12–16 focused days.** If short on time, do Phases 0 → 1 → 3(04) → 4(1) → 5 → 8 first. That is the minimum standout version.

---

## Part 5 — Python 3.13 dependency set (all support 3.13)

```
pandas>=2.2.3  numpy>=2.1  pyarrow>=18  duckdb>=1.1
matplotlib>=3.9  seaborn>=0.13  plotly>=5.24
scipy>=1.14  scikit-learn>=1.5  lightgbm>=4.5  shap>=0.46
statsforecast>=2.0  pandera>=0.21
streamlit>=1.40  kaggle>=1.6
jupyterlab  ipykernel  pytest  ruff  pre-commit  nbstripout
```
Avoid `lifetimes` (unmaintained, breaks on new pandas) and `prophet` (painful build on Windows/3.13).
After installing, freeze exact versions: `pip freeze > requirements.lock`.

---

## Part 6 — Resume bullet you're building toward

> Built an end-to-end analytics & ML pipeline on 100K Olist e-commerce orders (Python, DuckDB SQL, Power BI, Streamlit). Found that late deliveries (8% of orders) cut ratings from 4.3★ to 2.6★, and built a LightGBM model that flags high-risk orders at shipping time (PR-AUC X, top-decile recall Y%); deployed as a live Streamlit app with cohort, RFM and seller-scorecard views.
