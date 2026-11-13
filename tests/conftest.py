def pytest_collection_modifyitems(items):
    # The Tableau export tests open the warehouse in child processes. Once a test in this
    # process has queried MetricFlow (test_evals does), dbt-duckdb keeps the file open and
    # Windows locks the children out, so the export tests run first.
    items.sort(key=lambda item: not item.nodeid.startswith("tests/test_tableau_export.py"))
