# SQL layer (DuckDB)

Built automatically by `.\tasks.ps1 pipeline`. Files run in lexical order.

| Layer | Folder | What it holds |
|---|---|---|
| `staging` | loaded from Python (`src/ecom/warehouse.py`) | cleaned, validated source tables |
| `marts` | [`01_marts/`](01_marts) | star schema: `fact_orders`, `fact_order_items`, `dim_customer`, `dim_product`, `dim_seller`, `dim_date` |
| `analysis` | [`02_analysis/`](02_analysis) | business views: KPIs, cohorts, RFM, Pareto, seller scorecard, delivery |
| tests | [`tests/`](tests) | each query returns the rows that break a rule; the pipeline fails if any row comes back |

```
                 dim_date
                    │
dim_customer ── fact_orders ── (1:N) ── fact_order_items ── dim_product
                                               │
                                           dim_seller
```

## Analysis views

| View | Business question | Techniques |
|---|---|---|
| `kpi_monthly` | Are we growing, and is quality keeping up? | `LAG` (MoM, YoY), running total, 3-month moving average, `FILTER` |
| `cohort_retention` | Do customers come back? | cohort indexing with `date_diff`, self-referencing cohort size |
| `repeat_purchase_summary` | How many repeat, and how fast? | conditional aggregates, `median` |
| `customer_rfm`, `rfm_segment_summary` | Who are our customers worth targeting? | `NTILE`, rule-based segments, share-of-total windows |
| `category_pareto` | Which categories drive revenue? | cumulative `SUM() OVER`, ABC classification |
| `seller_scorecard` | Which sellers need action? | `DENSE_RANK`, median benchmarks, action quadrant |
| `state_delivery` | Where is delivery slow, late and expensive? | grouped KPIs, haversine distance from the marts |
| `delivery_vs_review` | How much does lateness hurt ratings? | delay buckets, share of total |

Query it yourself:

```powershell
.venv\Scripts\python.exe -c "import duckdb; print(duckdb.connect('data/warehouse.duckdb').sql('SELECT * FROM analysis.delivery_vs_review'))"
```

Metric definitions: [`reports/metrics.md`](../reports/metrics.md).
