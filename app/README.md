# Olist Insights: Streamlit app

Seven pages: four analytics pages (Overview, Delivery & Satisfaction, Customers & Retention, Sellers)
and three ML pages (Delivery Promise Simulator, Review Risk Checker, Demand Forecast).

The app is **self-contained**. It reads only `app/data/*.parquet` and `app/models/*` (about 6 MB, committed),
so it deploys without the raw data or the DuckDB warehouse. Models ship as LightGBM **text files** (portable,
no pickles), and `tests/test_app_parity.py` checks that they reproduce the training predictions exactly.

## Run locally

```powershell
.\tasks.ps1 app
```

Refresh the app's data and models after changing the pipeline or models:

```powershell
.\tasks.ps1 export-app
```

## Deploy free on Streamlit Community Cloud

1. Push the repository to GitHub (including `app/data`, `app/models` and `.streamlit/config.toml`).
2. Go to [share.streamlit.io](https://share.streamlit.io) → sign in with GitHub → **Create app**.
3. Repository: `Md-Faiz-Alam/ecommerce-sales-customer-insights` · Branch: `main` · Main file path: `app/streamlit_app.py`.
4. **Advanced settings → Python version: 3.13** → Deploy.
5. Dependencies come from `app/requirements.txt` (next to the entry point), not the heavy root `requirements.txt`.
6. Copy the app URL into the top of the main README.
