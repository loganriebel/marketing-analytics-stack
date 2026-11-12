"""Governed access to Fernhook's metrics through the MetricFlow semantic layer.

Every number comes from a metric defined once in warehouse/models/semantic/.
Callers pick metrics, a grain, allow-listed dimensions and simple filters; they
never write SQL. Unknown metrics and dimensions are refused with a list of what
does exist.
"""

from __future__ import annotations

import datetime as dt
import decimal
import os
import re
import threading
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
WAREHOUSE = REPO / "warehouse"

# Friendly dimension name -> MetricFlow group-by name.
DIMENSIONS = {
    "channel": ("channel__channel_name", "Lead source or media channel, e.g. Meta, Paid Search Brand"),
    "channel_group": ("channel__channel_group", "search, paid_social, video, ctv, display, partners, events, owned, organic"),
    "marketing_role": ("channel__marketing_role", "performance, brand, events, owned, unpaid"),
    "is_paid": ("channel__is_paid", "true for the nine paid channels"),
    "region": ("region__region_name", "One of 20 Midwest metro markets, e.g. Chicago, Fargo"),
    "sales_area": ("region__sales_area", "Illinois and Iowa, Ohio, Wisconsin or Upper Midwest"),
}
GRAINS = ("week", "month", "quarter", "year")
OPERATORS = ("=", "!=", "in", "not in")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MAX_ROWS = 500

CONVENTIONS = [
    "Weeks start on Monday. A week belongs to the month, quarter and year that contain its Monday.",
    "Data covers the weeks of 2023-01-02 through 2025-12-22.",
    "start_date and end_date select weeks whose Monday falls in the range, inclusive.",
    "Grouping a funnel or efficiency metric by channel uses the CRM's last-touch source.",
    "The latest weeks undercount deals because recent leads have not had time to close.",
]


class QueryError(ValueError):
    """A request the semantic layer will not run, with a message the caller can act on."""


class SemanticLayer:
    def __init__(self) -> None:
        self._cfg = None
        self._lock = threading.Lock()
        self._metrics: dict[str, dict[str, str]] | None = None

    def _engine(self):
        with self._lock:
            if self._cfg is None:
                os.chdir(REPO)  # the dbt profile's DuckDB path is relative to the repo root
                from dbt_metricflow.cli.cli_configuration import CLIConfiguration

                cfg = CLIConfiguration()
                cfg.setup(dbt_profiles_path=WAREHOUSE, dbt_project_path=WAREHOUSE, configure_file_logging=False)
                self._cfg = cfg
            return self._cfg.mf

    def metrics(self) -> dict[str, dict[str, str]]:
        if self._metrics is None:
            engine = self._engine()
            self._metrics = {
                m.name: {"label": getattr(m, "label", None) or m.name, "description": (m.description or "").strip()}
                for m in sorted(engine.list_metrics(include_dimensions=False), key=lambda m: m.name)
            }
        return self._metrics

    def catalog(self) -> dict[str, Any]:
        return {
            "metrics": [{"name": k, **v} for k, v in self.metrics().items()],
            "dimensions": {k: v[1] for k, v in DIMENSIONS.items()},
            "grains": list(GRAINS),
            "filter_operators": list(OPERATORS),
            "conventions": CONVENTIONS,
        }

    def query(self, metrics: list[str], dimensions: list[str] | None = None, grain: str | None = None,
              start_date: str | None = None, end_date: str | None = None,
              filters: list[dict[str, Any]] | None = None, order_by: list[str] | None = None,
              limit: int | None = None) -> dict[str, Any]:
        known = self.metrics()
        if not metrics:
            raise QueryError("Ask for at least one metric.")
        unknown = [m for m in metrics if m not in known]
        if unknown:
            raise QueryError(f"Not defined in the semantic layer: {', '.join(unknown)}. "
                             f"Defined metrics: {', '.join(known)}. If none fits, the question cannot be answered here.")
        dimensions = dimensions or []
        bad_dims = [d for d in dimensions if d not in DIMENSIONS]
        if bad_dims:
            raise QueryError(f"Unknown dimensions: {', '.join(bad_dims)}. Available: {', '.join(DIMENSIONS)}.")
        if grain is not None and grain not in GRAINS:
            raise QueryError(f"grain must be one of {', '.join(GRAINS)}.")

        group_by = ([f"metric_time__{grain}"] if grain else []) + [DIMENSIONS[d][0] for d in dimensions]
        where = []
        for label, value, op in (("start_date", start_date, ">="), ("end_date", end_date, "<=")):
            if value is not None:
                if not DATE_RE.match(value):
                    raise QueryError(f"{label} must look like YYYY-MM-DD.")
                where.append(f"{{{{ TimeDimension('metric_time', 'week') }}}} {op} '{value}'")
        for f in filters or []:
            where.append(_filter_sql(f))

        order = []
        for o in order_by or []:
            desc, name = (o.startswith("-"), o.lstrip("-"))
            if name in known:
                mf_name = name
            elif name in DIMENSIONS:
                mf_name = DIMENSIONS[name][0]
            elif name == "period" and grain:
                mf_name = f"metric_time__{grain}"
            else:
                raise QueryError(f"Cannot order by {name!r}; use a requested metric, dimension, or 'period'.")
            order.append(("-" if desc else "") + mf_name)

        from metricflow.engine.metricflow_engine import MetricFlowQueryRequest

        request = MetricFlowQueryRequest.create(
            metric_names=metrics, group_by_names=group_by or None, where_constraints=where or None,
            order_by_names=order or None, limit=min(limit or MAX_ROWS, MAX_ROWS))
        try:
            result = self._engine().query(request)
        except Exception as exc:  # MetricFlow explains invalid combinations; pass the first line back
            raise QueryError(str(exc).strip().splitlines()[0][:500]) from exc

        table = result.result_df
        rename = {f"metric_time__{g}": "period" for g in GRAINS}
        rename.update({v[0]: k for k, v in DIMENSIONS.items()})
        columns = [rename.get(c, c) for c in table.column_names]
        rows = [[_clean(v) for v in row] for row in table.rows]
        return {"columns": columns, "rows": rows, "row_count": len(rows),
                "definitions": {m: known[m]["description"] for m in metrics}}


def _quote(value: Any) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _filter_sql(f: dict[str, Any]) -> str:
    dim, op = f.get("dimension"), str(f.get("operator", "=")).lower()
    values = f.get("values", f.get("value"))
    if dim not in DIMENSIONS:
        raise QueryError(f"Cannot filter on {dim!r}. Filterable dimensions: {', '.join(DIMENSIONS)}.")
    if op not in OPERATORS:
        raise QueryError(f"operator must be one of {', '.join(OPERATORS)}.")
    vals = values if isinstance(values, list) else [values]
    if not vals or any(v is None for v in vals):
        raise QueryError("Filters need at least one value.")
    ref = f"{{{{ Dimension('{DIMENSIONS[dim][0]}') }}}}"
    if dim == "is_paid":
        lits = ["true" if str(v).lower() in ("true", "1", "yes") else "false" for v in vals]
    else:
        lits = [_quote(v) for v in vals]
    if op in ("in", "not in"):
        return f"{ref} {op.upper()} ({', '.join(lits)})"
    if len(lits) != 1:
        raise QueryError("Use 'in' or 'not in' for more than one value.")
    return f"{ref} {op} {lits[0]}"


def _clean(v: Any) -> Any:
    if isinstance(v, (dt.datetime, dt.date)):
        return v.date().isoformat() if isinstance(v, dt.datetime) else v.isoformat()
    if isinstance(v, decimal.Decimal):
        v = float(v)
    if isinstance(v, float):
        return None if v != v else round(v, 4)
    return v
