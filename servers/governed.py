"""MCP server: Claude gets Fernhook's numbers only through the governed metrics.

Run with: python -m servers.governed
"""

from __future__ import annotations

from typing import Any, Literal

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import BaseModel, Field

from .semantic_layer import QueryError, SemanticLayer

layer = SemanticLayer()
server = MCPServer(
    name="fernhook-metrics",
    instructions=(
        "Fernhook's governed marketing metrics. Call list_metrics first to see what is defined, then "
        "query_metric. Only defined metrics can be queried; if a question needs anything else, say it "
        "cannot be answered with the governed metrics."
    ),
)


class Filter(BaseModel):
    dimension: str = Field(description="A dimension name from list_metrics, e.g. channel or sales_area.")
    operator: Literal["=", "!=", "in", "not in"] = "="
    values: list[str] = Field(description="One value for = and !=, one or more for in and not in.")


@server.tool()
def list_metrics() -> dict[str, Any]:
    """List every defined metric with its definition, plus the dimensions, grains and conventions."""
    return layer.catalog()


@server.tool()
def query_metric(
    metrics: list[str],
    dimensions: list[str] | None = None,
    grain: Literal["week", "month", "quarter", "year"] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    filters: list[Filter] | None = None,
    order_by: list[str] | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    """Query governed metrics.

    metrics: metric names from list_metrics. dimensions: optional group-bys (channel, channel_group,
    marketing_role, is_paid, region, sales_area). grain: optional time grain for a period column.
    start_date / end_date: YYYY-MM-DD, selecting weeks whose Monday is in range. filters: dimension
    filters. order_by: metric, dimension or 'period', prefix '-' for descending. limit: max rows (500).
    """
    try:
        return layer.query(metrics, dimensions, grain, start_date, end_date,
                           [f.model_dump() for f in filters or []], order_by, limit)
    except QueryError as exc:
        raise ToolError(str(exc)) from exc


if __name__ == "__main__":
    server.run()
