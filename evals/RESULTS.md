# Eval results

Model: `claude-sonnet-5-5`, one pass per arm, same system prompt. 42 questions have a SQL ground truth (0.5% tolerance); 8 should be refused. Built-in tools are off, so each arm sees data only through its MCP server.

| Arm | Answerable correct | Correct refusals | Wrong refusals | Overall | Cost | Avg time |
|---|---|---|---|---|---|---|
| Claude + governed metrics (MCP) | 42/42 (100%) | 8/8 (100%) | 0 | 50/50 | $3.23 | 15s |
| Claude + raw tables (SQL) | 22/42 (52%) | 8/8 (100%) | 3 | 30/50 | $4.98 | 23s |

## Per question

| Arm | Id | Category | Answer | Truth | Correct |
|---|---|---|---|---|---|
| governed | q01 | media | 13341463.97 | 13341463.97 | yes |
| governed | q02 | media | 1308446.91 | 1308446.91 | yes |
| governed | q03 | media | 15.89 | 15.891 | yes |
| governed | q04 | media | Paid Search Non-Brand | Paid Search Non-Brand | yes |
| governed | q05 | media | 162081.69 | 162081.69 | yes |
| governed | q06 | media | 50843074 | 50843074 | yes |
| governed | q07 | media | 0.6 | 0.602 | yes |
| governed | q08 | media | 7.07 | 7.073 | yes |
| governed | q09 | media | 10.31 | 10.306 | yes |
| governed | q10 | media | 56233 | 56233.0 | yes |
| governed | q11 | media | 89.73 | 89.727 | yes |
| governed | q12 | funnel | 64374 | 64374 | yes |
| governed | q13 | funnel | 42762 | 42762 | yes |
| governed | q14 | funnel | 14057 | 14057 | yes |
| governed | q15 | funnel | 9237 | 9237 | yes |
| governed | q16 | funnel | 93237550 | 93237550.00 | yes |
| governed | q17 | funnel | 10445 | 10445 | yes |
| governed | q18 | funnel | 7495830 | 7495830.00 | yes |
| governed | q19 | funnel | 32.84 | 32.841 | yes |
| governed | q20 | funnel | 2958.81 | 2958.807 | yes |
| governed | q21 | funnel | 45.86 | 45.86 | yes |
| governed | q22 | funnel | 1435 | 1435 | yes |
| governed | q23 | funnel | US Texas | US Texas | yes |
| governed | q24 | efficiency | 1331.27 | 1331.27 | yes |
| governed | q25 | efficiency | 1292.49 | 1292.491 | yes |
| governed | q26 | efficiency | 59.17 | 59.17 | yes |
| governed | q27 | efficiency | 22.75 | 22.752 | yes |
| governed | q28 | efficiency | 14235.24 | 14235.241 | yes |
| governed | q29 | efficiency | 2.23 | 2.234 | yes |
| governed | q30 | efficiency | 53.91 | 53.907 | yes |
| governed | q31 | efficiency | 2.83 | 2.831 | yes |
| governed | q32 | efficiency | Paid Search Brand | Paid Search Brand | yes |
| governed | q33 | efficiency | 81.58 | 81.58 | yes |
| governed | q34 | trend | 67.18 | 67.184 | yes |
| governed | q35 | trend | -7.86 | -7.86 | yes |
| governed | q36 | trend | 276758.74 | 276758.74 | yes |
| governed | q37 | trend | 31 | 31 | yes |
| governed | q38 | controls | 6733247 | 6733247 | yes |
| governed | q39 | controls | 29.17 | 29.17 | yes |
| governed | q40 | controls | 64 | 64 | yes |
| governed | q41 | controls | 54 | 54 | yes |
| governed | q42 | controls | 100.67 | 100.671 | yes |
| governed | q43 | refusal | refused | refuse | yes |
| governed | q44 | refusal | refused | refuse | yes |
| governed | q45 | refusal | refused | refuse | yes |
| governed | q46 | refusal | refused | refuse | yes |
| governed | q47 | refusal | refused | refuse | yes |
| governed | q48 | refusal | refused | refuse | yes |
| governed | q49 | refusal | refused | refuse | yes |
| governed | q50 | refusal | refused | refuse | yes |
| raw | q01 | media | 11994181.44 | 13341463.97 | no |
| raw | q02 | media | 1308446.91 | 1308446.91 | yes |
| raw | q03 | media | refused | 15.891 | no |
| raw | q04 | media | Google | Paid Search Non-Brand | no |
| raw | q05 | media | 162081.69 | 162081.69 | yes |
| raw | q06 | media | 50843074 | 50843074 | yes |
| raw | q07 | media | 0.6 | 0.602 | yes |
| raw | q08 | media | 7.07 | 7.073 | yes |
| raw | q09 | media | 10.31 | 10.306 | yes |
| raw | q10 | media | 56233 | 56233.0 | yes |
| raw | q11 | media | 89.65 | 89.727 | yes |
| raw | q12 | funnel | 62295 | 64374 | no |
| raw | q13 | funnel | 42439 | 42762 | no |
| raw | q14 | funnel | 12162 | 14057 | no |
| raw | q15 | funnel | 9237 | 9237 | yes |
| raw | q16 | funnel | 93461260 | 93237550.00 | yes |
| raw | q17 | funnel | 10569 | 10445 | no |
| raw | q18 | funnel | 7674450 | 7495830.00 | no |
| raw | q19 | funnel | 32.83 | 32.841 | yes |
| raw | q20 | funnel | 2954.93 | 2958.807 | yes |
| raw | q21 | funnel | 45.93 | 45.86 | yes |
| raw | q22 | funnel | 1448 | 1435 | no |
| raw | q23 | funnel | US Texas | US Texas | yes |
| raw | q24 | efficiency | 1315.65 | 1331.27 | no |
| raw | q25 | efficiency | refused | 1292.491 | no |
| raw | q26 | efficiency | 58.64 | 59.17 | no |
| raw | q27 | efficiency | 22.75 | 22.752 | yes |
| raw | q28 | efficiency | 14582.44 | 14235.241 | no |
| raw | q29 | efficiency | 2.27 | 2.234 | no |
| raw | q30 | efficiency | refused | 53.907 | no |
| raw | q31 | efficiency | 2.84 | 2.831 | yes |
| raw | q32 | efficiency | Partners (affiliate) | Paid Search Brand | no |
| raw | q33 | efficiency | 82.32 | 81.58 | no |
| raw | q34 | trend | None | 67.184 | no |
| raw | q35 | trend | -5.74 | -7.86 | no |
| raw | q36 | trend | 252378.49 | 276758.74 | no |
| raw | q37 | trend | 31 | 31 | yes |
| raw | q38 | controls | 6733247 | 6733247 | yes |
| raw | q39 | controls | 29.17 | 29.17 | yes |
| raw | q40 | controls | 64 | 64 | yes |
| raw | q41 | controls | 54 | 54 | yes |
| raw | q42 | controls | 100.67 | 100.671 | yes |
| raw | q43 | refusal | refused | refuse | yes |
| raw | q44 | refusal | refused | refuse | yes |
| raw | q45 | refusal | refused | refuse | yes |
| raw | q46 | refusal | refused | refuse | yes |
| raw | q47 | refusal | refused | refuse | yes |
| raw | q48 | refusal | refused | refuse | yes |
| raw | q49 | refusal | refused | refuse | yes |
| raw | q50 | refusal | refused | refuse | yes |
