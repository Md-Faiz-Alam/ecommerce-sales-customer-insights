"""One chart style for the whole project (notebooks, report figures).

Colours come from a CVD-validated palette: categorical slots are used in fixed order,
sequential data uses a single blue ramp, status colours are reserved for good/bad states.
Rules: no dual axes, thin marks, recessive grid, selective direct labels.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.ticker import FuncFormatter

from ecom.config import REPORTS_DIR

# Categorical slots, light mode. Use in this order, never cycled past what the chart needs.
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
BLUE, ORANGE, AQUA = SERIES[:3]

# Sequential blue ramp (light -> dark) for magnitude (heatmaps).
SEQ_BLUE = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
SEQ_CMAP = LinearSegmentedColormap.from_list("seq_blue", SEQ_BLUE)

# Status (reserved; always paired with a text label).
GOOD, WARNING, SERIOUS, CRITICAL = "#0ca30c", "#fab219", "#ec835a", "#d03b3b"

# Ink and chrome.
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
NEUTRAL = "#c3c2b7"  # de-emphasised marks ("everything else")

FIG_DIR = REPORTS_DIR / "figures"


def set_style() -> None:
    mpl.rcParams.update(
        {
            "figure.facecolor": SURFACE,
            "axes.facecolor": SURFACE,
            "savefig.facecolor": SURFACE,
            "figure.dpi": 110,
            "figure.figsize": (9, 4.2),
            "font.family": ["Segoe UI", "DejaVu Sans", "sans-serif"],
            "font.size": 10,
            "text.color": INK,
            "axes.labelcolor": INK_2,
            "axes.titlesize": 13,
            "axes.titleweight": "bold",
            "axes.titlelocation": "left",
            "axes.titlepad": 26,
            "text.parse_math": False,  # 'R$' must stay literal, not trigger mathtext
            "axes.edgecolor": AXIS,
            "axes.linewidth": 0.8,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "axes.grid.axis": "y",
            "axes.axisbelow": True,
            "axes.prop_cycle": mpl.cycler(color=SERIES),
            "grid.color": GRID,
            "grid.linewidth": 0.6,
            "xtick.color": MUTED,
            "ytick.color": MUTED,
            "xtick.labelcolor": INK_2,
            "ytick.labelcolor": INK_2,
            "lines.linewidth": 2,
            "lines.markersize": 6,
            "legend.frameon": False,
            "legend.fontsize": 9,
        }
    )


def subtitle(ax: plt.Axes, text: str) -> None:
    """Grey one-line takeaway under the title."""
    ax.annotate(
        text,
        xy=(0, 1),
        xycoords="axes fraction",
        xytext=(0, 8),
        textcoords="offset points",
        color=INK_2,
        fontsize=9.5,
        va="bottom",
    )


def brl(x: float, _pos: int | None = None) -> str:
    """Compact BRL formatter: R$1.2M, R$350K, R$90."""
    if abs(x) >= 1e6:
        return f"R${x / 1e6:.1f}M"
    if abs(x) >= 1e3:
        return f"R${x / 1e3:.0f}K"
    return f"R${x:.0f}"


BRL = FuncFormatter(brl)
PCT = FuncFormatter(lambda x, _: f"{x:.0f}%")


def save(fig: plt.Figure, name: str) -> Path:
    """Save to reports/figures/<name>.png (used by the README)."""
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    path = FIG_DIR / f"{name}.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    return path
