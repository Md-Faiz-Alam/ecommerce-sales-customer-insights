"""Daily order forecast (28 days ahead) for capacity planning.

Notebook 02 showed peaks break logistics (late rate 3-6% -> 12-19%). Carriers and warehouses
need a volume forecast to book capacity ahead. Models are compared with rolling-origin
backtesting (4 folds x 28 days, never training on the future) against naive baselines:
a model that can't beat "same weekday last week" isn't worth deploying.
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
from statsmodels.tsa.exponential_smoothing.ets import ETSModel

from ecom.db import query

HORIZON = 28
FOLDS = 4
SEASON = 7

# Daily volume is normal until 21 Aug 2018, then decays to 1 order/day by 31 Aug. That is a
# data-extraction cut-off, not real demand, so the series ends here.
LAST_COMPLETE_DAY = pd.Timestamp("2018-08-21")

# Known external shocks, shown on charts and excluded from nothing (honest backtest):
EVENTS = {
    pd.Timestamp("2017-11-24"): "Black Friday",
    pd.Timestamp("2018-05-21"): "Truckers' strike",
}


def daily_orders() -> pd.Series:
    df = query(
        """
        SELECT purchase_date AS day, count(*) AS orders
        FROM marts.fact_orders WHERE in_analysis_window
        GROUP BY 1 ORDER BY 1
        """
    )
    s = df.set_index(pd.DatetimeIndex(df["day"]))["orders"].astype(float)
    return s.asfreq("D", fill_value=0.0).loc[:LAST_COMPLETE_DAY]


# ----------------------------------------------------------------------------- models
def seasonal_naive(train: pd.Series, h: int) -> np.ndarray:
    """Repeat the last observed week."""
    return np.resize(train.iloc[-SEASON:].to_numpy(), h)


def seasonal_mean_4w(train: pd.Series, h: int) -> np.ndarray:
    """Average of the last 4 same weekdays: a sturdier naive baseline."""
    last = train.iloc[-4 * SEASON :].to_numpy().reshape(4, SEASON).mean(axis=0)
    return np.resize(last, h)


def _ets(train: pd.Series) -> ETSModel:
    return ETSModel(
        np.log1p(train),  # multiplicative weekly pattern -> additive on log scale
        error="add",
        trend="add",
        damped_trend=True,
        seasonal="add",
        seasonal_periods=SEASON,
    )


def ets(train: pd.Series, h: int) -> np.ndarray:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        fit = _ets(train).fit(disp=False)
    return np.expm1(fit.forecast(h).to_numpy())


def ensemble(train: pd.Series, h: int) -> np.ndarray:
    """ETS reacts fast (great in calm periods, overreacts after shocks); the 4-week mean is
    sturdy (survives shocks, slow on rebounds). Averaging hedges the two failure modes."""
    return (ets(train, h) + seasonal_mean_4w(train, h)) / 2


MODELS = {
    "Seasonal naive (last week)": seasonal_naive,
    "Seasonal mean (last 4 weeks)": seasonal_mean_4w,
    "ETS (damped trend + weekly, log)": ets,
    "Ensemble (ETS + 4-week mean)": ensemble,
}


# ----------------------------------------------------------------------------- evaluation
def backtest(series: pd.Series) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Rolling-origin backtest. Returns (per-fold metrics, all forecasts)."""
    rows, preds = [], []
    n = len(series)
    for fold in range(FOLDS):
        cut = n - (FOLDS - fold) * HORIZON
        train, test = series.iloc[:cut], series.iloc[cut : cut + HORIZON]
        # MASE scale: in-sample MAE of the seasonal-naive forecast.
        scale = np.mean(np.abs(train.to_numpy()[SEASON:] - train.to_numpy()[:-SEASON]))
        for name, fn in MODELS.items():
            p = fn(train, HORIZON)
            err = test.to_numpy() - p
            rows.append(
                {
                    "fold": fold + 1,
                    "test_start": test.index[0].date(),
                    "model": name,
                    "mae": np.mean(np.abs(err)),
                    "mape_pct": np.mean(np.abs(err) / test.to_numpy()) * 100,
                    "mase": np.mean(np.abs(err)) / scale if scale > 0 else np.nan,
                }
            )
            preds.append(pd.DataFrame({"day": test.index, "model": name, "forecast": p}))
    return pd.DataFrame(rows), pd.concat(preds, ignore_index=True)


def summarise(folds: pd.DataFrame, preds: pd.DataFrame, series: pd.Series) -> pd.DataFrame:
    """Daily accuracy + the error on each fold's 28-day total (what capacity planning books)."""
    p = preds.assign(actual=series.reindex(preds["day"]).to_numpy())
    p["fold"] = p.groupby("model").cumcount() // HORIZON + 1
    totals = p.groupby(["model", "fold"])[["forecast", "actual"]].sum()
    total_err = (
        (totals["forecast"] / totals["actual"] - 1).abs().groupby("model").agg(["mean", "max"])
    )
    out = folds.groupby("model")[["mae", "mape_pct", "mase"]].mean()
    out["total_28d_abs_err_pct"] = total_err["mean"] * 100
    out["total_28d_worst_err_pct"] = total_err["max"] * 100
    return out.sort_values("total_28d_abs_err_pct").round(2)


def forecast_future(series: pd.Series, h: int = HORIZON) -> pd.DataFrame:
    """Ensemble forecast from all data, with an 80% interval from the ETS component."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        fit = _ets(series).fit(disp=False)
        frame = fit.get_prediction(start=len(series), end=len(series) + h - 1).summary_frame(
            alpha=0.2
        )
    ets_mean = np.expm1(frame["mean"].to_numpy())
    shift = (ets_mean + seasonal_mean_4w(series, h)) / 2 - ets_mean  # centre band on ensemble
    idx = pd.date_range(series.index[-1] + pd.Timedelta(days=1), periods=h, freq="D")
    return pd.DataFrame(
        {
            "forecast": ets_mean + shift,
            "low_80": np.expm1(frame["pi_lower"].to_numpy()) + shift,
            "high_80": np.expm1(frame["pi_upper"].to_numpy()) + shift,
        },
        index=idx,
    )
