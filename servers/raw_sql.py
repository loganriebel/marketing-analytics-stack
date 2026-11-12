"""MCP server for the eval baseline: read-only SQL over the raw source exports.

This is "Claude on raw tables": the same CSVs the warehouse reads, with no
semantic layer and no metric definitions. Files are loaded into an in-memory
DuckDB at startup; external file access is then switched off, so queries can
only touch these tables.

Run with: python -m servers.raw_sql
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import duckdb
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

REPO = Path(__file__).resolve().parents[1]
RAW_DIR = REPO / "data" / "raw"
MAX_ROWS = 500
WRITE_WORDS = re.compile(r"\b(insert|update|delete|create|drop|alter|attach|copy|export|install|load|pragma|set|call)\b", re.I)

_con: duckdb.DuckDBPyConnection | None = None


def connection() -> duckdb.DuckDBPyConnection:
    global _con
    if _con is None:
        con = duckdb.connect(":memory:")
        for path in sorted(RAW_DIR.glob("*.csv")):
            con.execute(f"create table {path.stem} as select * from read_csv('{path.as_posix()}', header = true)")
        con.execute("set enable_external_access = false")
        con.execute("set lock_configuration = true")
        _con = con
    return _con


server = MCPServer(
    name="fernhook-raw-sql",
    instructions="Read-only SQL (DuckDB dialect) over Fernhook's raw source exports. Call list_tables first.",
)


@server.tool()
def list_tables() -> dict[str, Any]:
    """List the raw tables with their columns, types and row counts."""
    con = connection()
    out = {}
    for (name,) in con.execute("select table_name from information_schema.tables order by 1").fetchall():
        cols = con.execute(
            "select column_name, data_type from information_schema.columns where table_name = ? order by ordinal_position",
            [name]).fetchall()
        rows = con.execute(f"select count(*) from {name}").fetchone()[0]
        out[name] = {"rows": rows, "columns": {c: t for c, t in cols}}
    return out


@server.tool()
def run_sql(query: str) -> dict[str, Any]:
    """Run one read-only SELECT (or WITH ... SELECT) query and return up to 500 rows."""
    q = query.strip().rstrip(";")
    if ";" in q or not re.match(r"^(select|with)\b", q, re.I) or WRITE_WORDS.search(q):
        raise ToolError("Only a single read-only SELECT or WITH query is allowed.")
    try:
        cur = connection().execute(q)
        cols = [d[0] for d in cur.description]
        rows = cur.fetchmany(MAX_ROWS + 1)
    except duckdb.Error as exc:
        raise ToolError(str(exc).splitlines()[0][:500]) from exc
    truncated = len(rows) > MAX_ROWS
    rows = [[v if isinstance(v, (int, float, str, bool)) or v is None else str(v) for v in r] for r in rows[:MAX_ROWS]]
    return {"columns": cols, "rows": rows, "row_count": len(rows), "truncated": truncated}


if __name__ == "__main__":
    server.run()
