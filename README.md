# E-commerce Sales & Customer Insights (Olist, Brazil)

End-to-end analytics on **~100K real orders** from Olist, a Brazilian marketplace (2017–2018):
a reproducible Python + SQL pipeline, a DuckDB warehouse, a Power BI dashboard, and (in progress)
retention analysis and machine-learning models.

> **Core finding:** orders that arrive after the promised date average **2.27★**, versus
> **4.29★** for on-time orders, and only **3.1%** of customers ever buy a second time.
> Delivery reliability is the biggest lever for satisfaction and retention.

## Key findings (R$15.4M revenue, 99K orders, Jan 2017 – Aug 2018)

| # | Finding | Evidence |
|---|---|---|
| 1 | **Even a short delay destroys ratings.** Negative reviews (1–2★) go from **9%** for early orders to **32%** at 1–3 days late and **68%** at 4–7 days late | `analysis.delivery_vs_review` |
| 2 | **Retention is close to zero.** Only 3.1% of customers reorder; month-1 retention averages **0.5%**. 30% of "repeat" orders are same-day split baskets, not loyalty | `analysis.cohort_retention`, `repeat_purchase_summary` |
| 3 | **Peak season breaks logistics.** Black Friday (Nov 2017) lifted orders 63% month over month, and the late rate jumped from 4% to **12%**. Feb–Mar 2018 hit **14–19%** late, with ratings falling to 3.75★ | `analysis.kpi_monthly` |
| 4 | **Delivery promises are padded.** 74% of orders arrive 8+ days early. A shorter, accurate promise could improve conversion without hurting ratings | `analysis.delivery_vs_review` |
| 5 | **Revenue is concentrated, and at risk.** 164 high-volume sellers with above-median negative reviews (19%) generate **R$5.2M (34%)** of revenue | `analysis.seller_scorecard` |
| 6 | **The North-East is underserved.** AL, MA, SE, CE: 14–21% late, 16–21% of order value spent on freight, 1,650–2,200 km average shipping distance | `analysis.state_delivery` |
| 7 | 18 of 74 categories (A class) make up **81%** of revenue | `analysis.category_pareto` |

All metric definitions: [`docs/metrics.md`](docs/metrics.md).

---

## Quickstart (Windows / PowerShell, Python 3.13)

```powershell
.\tasks.ps1 setup      # create .venv, install pinned dependencies
.\tasks.ps1 data       # download raw Olist CSVs from Kaggle into data/raw/
.\tasks.ps1 pipeline   # clean -> validate -> Parquet -> DuckDB warehouse -> quality report
.\tasks.ps1 test       # unit tests
```

The pipeline rebuilds everything from raw data in about 10 seconds:

- `data/processed/*.parquet`: cleaned tables
- `data/warehouse.duckdb`: queryable warehouse (`staging` schema)
- [`reports/data_quality_report.md`](reports/data_quality_report.md): every cleaning rule and the number of rows it affected, plus all validation results

---

## Pipeline

```
data/raw/*.csv ─► clean.py ─► validate.py ─► DuckDB staging ─► marts (star schema) ─► analysis views
   (Kaggle)       documented   pandera +        Parquet          sql/01_marts          sql/02_analysis
                  rules, flags foreign keys                          └──── sql/tests: 8 data tests ────┘
```

The SQL layer is documented in [`sql/README.md`](sql/README.md): a star schema plus 8 analysis views
using window functions (`LAG`, `NTILE`, `DENSE_RANK`, running totals), cohort indexing, and RFM/ABC
classification. The pipeline fails if any SQL data test (row counts, revenue reconciliation,
uniqueness) breaks.

### Data-cleaning decisions

| Problem found | Decision |
|---|---|
| `customer_id` is generated per order | Customer counts and retention use `customer_unique_id` (**96,096** people, not 99,441) |
| 4 products with weight/dimension = 0, 2 missing | Treated as missing (NA) and flagged; never filled with fake zeros |
| 610 products without a category; names in Portuguese | `unknown`; translated to English, including 2 categories missing from Olist's own translation file |
| 551 orders with several reviews | Keep the latest review per order (order-level grain) |
| Sparse months (Sep–Dec 2016, Sep–Oct 2018) | Kept but flagged `in_analysis_window = false`, and excluded from trends and forecasts |
| 1,359 orders handed to the carrier before payment approval; 8 "delivered" orders with no date | Flagged in `has_timestamp_anomaly`, not silently fixed |
| "Late" definition | Delivered on a calendar day after the promised date (**6.8%** of delivered orders) |
| 1M geolocation points, some outside Brazil | Out-of-country GPS noise removed; collapsed to one median centroid per zip prefix |
| Revenue definition | Completed revenue counts only orders with `is_delivered = true` (delivered status plus a delivery date) |

The full audit trail is in [`reports/data_quality_report.md`](reports/data_quality_report.md).

---

## Dashboard (Power BI)

<p align="center"><img src="images/dashboard.gif" width="800"/></p>

> A Power BI revision is planned: proper date table, MoM measures, BRL currency, and English categories.

---

## Project structure

```
├── src/ecom/            # pipeline package (config, ingest, clean, validate, warehouse, quality)
├── scripts/             # download_data.py
├── sql/                 # DuckDB: 01_marts (star schema), 02_analysis (views), tests
├── docs/                # metric definitions
├── tests/               # pytest: cleaning rules, data contracts, SQL test runner
├── reports/             # generated data-quality report, figures
├── dashboard/           # Power BI .pbix
├── images/              # dashboard screenshots
├── data/                # raw + processed (git-ignored; rebuilt by the pipeline)
├── tasks.ps1            # task runner
└── pyproject.toml       # package + tooling config
```

## Roadmap

- [x] Reproducible pipeline, data contracts, data-quality report, tests
- [x] SQL marts (star schema) + cohort retention, RFM, Pareto, seller scorecard, SQL data tests
- [ ] Analysis notebooks: delivery → satisfaction (with statistical tests), retention, seller and geography
- [ ] ML: negative-review risk model (LightGBM + SHAP), customer segmentation, demand forecast
- [ ] Live Streamlit app
- [ ] Power BI fixes + executive summary

## Tech stack

Python 3.13 · pandas 3 · DuckDB · pandera · pytest · ruff · Power BI

## Data

[Olist Brazilian E-Commerce Public Dataset](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce) (CC BY-NC-SA 4.0). Values are in Brazilian reais (BRL).
