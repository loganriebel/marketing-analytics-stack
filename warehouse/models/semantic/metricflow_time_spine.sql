-- Daily calendar MetricFlow uses to roll weeks into months, quarters and years.
select cast(unnest(generate_series(timestamp '2022-01-01', timestamp '2026-12-31', interval 1 day)) as date) as date_day
