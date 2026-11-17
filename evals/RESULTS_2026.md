# Eval results: 2026 questions

Model: `claude-sonnet-5-5`, one pass per arm, same system prompt. 8 questions have a SQL ground truth (0.5% tolerance); 1 should be refused. Built-in tools are off, so each arm sees data only through its MCP server. Data: the `data/cut_2027-01-03` cut, weeks 2023-01-02 to 2026-12-28.

| Arm | Answerable correct | Correct refusals | Wrong refusals | Overall | Cost | Avg time |
|---|---|---|---|---|---|---|
| Claude + governed metrics (MCP) | 8/8 (100%) | 0/1 (0%) | 0 | 8/9 | $0.69 | 17s |
| Claude + raw tables (SQL) | 6/8 (75%) | 0/1 (0%) | 1 | 6/9 | $1.47 | 27s |

## Per question

| Arm | Id | Category | Answer | Truth | Correct |
|---|---|---|---|---|---|
| governed | t01 | test | 3741 | 3741 | yes |
| governed | t02 | test | 861835.37 | 861835.37 | yes |
| governed | t03 | test | 1038896.83 | 1038896.83 | yes |
| governed | t04 | test | 1543.48 | 1543.483 | yes |
| governed | t05 | test | search only | search only | yes |
| governed | t06 | refusal | 386 | refuse | no |
| governed | t07 | year | 28054 | 28054 | yes |
| governed | t08 | year | 26232155.93 | 26232155.93 | yes |
| governed | t09 | year | 1435.98 | 1435.98 | yes |
| raw | t01 | test | 3741 | 3741 | yes |
| raw | t02 | test | 861835.37 | 861835.37 | yes |
| raw | t03 | test | 1038896.83 | 1038896.83 | yes |
| raw | t04 | test | refused | 1543.483 | no |
| raw | t05 | test | search only | search only | yes |
| raw | t06 | refusal | 399 | refuse | no |
| raw | t07 | year | 28083 | 28054 | yes |
| raw | t08 | year | 23725926.41 | 26232155.93 | no |
| raw | t09 | year | 1435.98 | 1435.98 | yes |
