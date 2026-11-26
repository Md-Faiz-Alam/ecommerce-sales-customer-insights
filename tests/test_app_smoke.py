"""Smoke tests: every Streamlit page renders without an exception (Streamlit's AppTest).

Runs against the committed app/ data and models, so it works in CI without the warehouse.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP = Path(__file__).parents[1] / "app"
PAGES = sorted(p.name for p in (APP / "pages").glob("*.py"))

pytestmark = pytest.mark.skipif(
    not (APP / "models" / "meta.json").exists(), reason="run `python -m ecom.export_app` first"
)


@pytest.fixture(autouse=True)
def _app_on_path(monkeypatch):
    monkeypatch.syspath_prepend(str(APP))  # pages do `import lib`, as Streamlit does at runtime
    yield
    for mod in ("lib", "order_form"):
        sys.modules.pop(mod, None)


@pytest.mark.parametrize("page", PAGES)
def test_page_renders_without_errors(page):
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(str(APP / "pages" / page), default_timeout=60).run()
    assert not at.exception, f"{page} raised: {[e.value for e in at.exception]}"


def test_overview_kpis_match_warehouse_totals():
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(str(APP / "pages" / "overview.py"), default_timeout=60).run()
    metrics = {m.label: m.value for m in at.metric}
    assert metrics["Orders"] == "99,092"
    assert metrics["Revenue"] == "R$15.4M"
    assert metrics["Late deliveries"] == "6.8%"


def test_risk_checker_flags_a_clearly_risky_order():
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(str(APP / "pages" / "risk.py"), default_timeout=60).run()
    at.slider[1].set_value(15.0)  # very slow handoff to the carrier
    at.toggle[0].set_value(True)  # missed the shipping deadline
    at.run()
    assert not at.exception
    assert any("Flag for proactive care" in e.value for e in at.error)
