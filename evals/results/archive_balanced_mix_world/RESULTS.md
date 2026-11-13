# Eval results

Model: `claude-sonnet-5-5`, one pass per arm, same system prompt. 42 questions have a SQL ground truth (0.5% tolerance); 8 should be refused. Built-in tools are off, so each arm sees data only through its MCP server.

| Arm | Answerable correct | Correct refusals | Wrong refusals | Overall | Cost | Avg time |
|---|---|---|---|---|---|---|
| Claude + governed metrics (MCP) | 42/42 (100%) | 8/8 (100%) | 0 | 50/50 | $3.24 | 14s |
| Claude + raw tables (SQL) | 23/42 (55%) | 8/8 (100%) | 2 | 31/50 | $3.78 | 14s |

## Per question

| Arm | Id | Category | Answer | Truth | Correct |
|---|---|---|---|---|---|
| governed | q01 | media | 13923580.65 | 13923580.65 | yes |
| governed | q02 | media | 1303935.84 | 1303935.84 | yes |
| governed | q03 | media | 16.21 | 16.213 | yes |
| governed | q04 | media | Paid Search Non-Brand | Paid Search Non-Brand | yes |
| governed | q05 | media | 90261.25 | 90261.25 | yes |
| governed | q06 | media | 48286556 | 48286556 | yes |
| governed | q07 | media | 0.6 | 0.601 | yes |
| governed | q08 | media | 7.12 | 7.118 | yes |
| governed | q09 | media | 10.28 | 10.277 | yes |
| governed | q10 | media | 55659 | 55659.0 | yes |
| governed | q11 | media | 91.07 | 91.073 | yes |
| governed | q12 | funnel | 54925 | 54925 | yes |
| governed | q13 | funnel | 41711 | 41711 | yes |
| governed | q14 | funnel | 11801 | 11801 | yes |
| governed | q15 | funnel | 9605 | 9605 | yes |
| governed | q16 | funnel | 91111760 | 91111760.00 | yes |
| governed | q17 | funnel | 9999 | 9999 | yes |
| governed | q18 | funnel | 7601050 | 7601050.00 | yes |
| governed | q19 | funnel | 31.96 | 31.959 | yes |
| governed | q20 | funnel | 2985.05 | 2985.048 | yes |
| governed | q21 | funnel | 45.46 | 45.463 | yes |
| governed | q22 | funnel | 1870 | 1870 | yes |
| governed | q23 | funnel | Chicago | Chicago | yes |
| governed | q24 | efficiency | 1434.72 | 1434.725 | yes |
| governed | q25 | efficiency | 1269.17 | 1269.166 | yes |
| governed | q26 | efficiency | 60.69 | 60.685 | yes |
| governed | q27 | efficiency | 24.7 | 24.704 | yes |
| governed | q28 | efficiency | 13387.25 | 13387.25 | yes |
| governed | q29 | efficiency | 2.4284 | 2.428 | yes |
| governed | q30 | efficiency | 57.1032 | 57.103 | yes |
| governed | q31 | efficiency | 2.9855 | 2.986 | yes |
| governed | q32 | efficiency | Webinars | Webinars | yes |
| governed | q33 | efficiency | 82.39 | 82.387 | yes |
| governed | q34 | trend | 67.96 | 67.96 | yes |
| governed | q35 | trend | -10.7 | -10.699 | yes |
| governed | q36 | trend | 302181.31 | 302181.31 | yes |
| governed | q37 | trend | 53 | 53 | yes |
| governed | q38 | controls | 6445219 | 6445219 | yes |
| governed | q39 | controls | 29.29 | 29.29 | yes |
| governed | q40 | controls | 62 | 62 | yes |
| governed | q41 | controls | 53 | 53 | yes |
| governed | q42 | controls | 100.01 | 100.006 | yes |
| governed | q43 | refusal | refused | refuse | yes |
| governed | q44 | refusal | refused | refuse | yes |
| governed | q45 | refusal | refused | refuse | yes |
| governed | q46 | refusal | refused | refuse | yes |
| governed | q47 | refusal | refused | refuse | yes |
| governed | q48 | refusal | refused | refuse | yes |
| governed | q49 | refusal | refused | refuse | yes |
| governed | q50 | refusal | refused | refuse | yes |
| raw | q01 | media | 12427182.04 | 13923580.65 | no |
| raw | q02 | media | 1303935.84 | 1303935.84 | yes |
| raw | q03 | media | refused | 16.213 | no |
| raw | q04 | media | Google | Paid Search Non-Brand | no |
| raw | q05 | media | 90261.25 | 90261.25 | yes |
| raw | q06 | media | 48286556 | 48286556 | yes |
| raw | q07 | media | 0.6 | 0.601 | yes |
| raw | q08 | media | 7.12 | 7.118 | yes |
| raw | q09 | media | 10.28 | 10.277 | yes |
| raw | q10 | media | 55659 | 55659.0 | yes |
| raw | q11 | media | 91.07 | 91.073 | yes |
| raw | q12 | funnel | 52780 | 54925 | no |
| raw | q13 | funnel | 41462 | 41711 | no |
| raw | q14 | funnel | 9881 | 11801 | no |
| raw | q15 | funnel | 9605 | 9605 | yes |
| raw | q16 | funnel | 91291690 | 91111760.00 | yes |
| raw | q17 | funnel | 10117 | 9999 | no |
| raw | q18 | funnel | 7741240 | 7601050.00 | no |
| raw | q19 | funnel | 31.97 | 31.959 | yes |
| raw | q20 | funnel | 2986.35 | 2985.048 | yes |
| raw | q21 | funnel | 45.43 | 45.463 | yes |
| raw | q22 | funnel | 1890 | 1870 | no |
| raw | q23 | funnel | Chicago | Chicago | yes |
| raw | q24 | efficiency | 1418.74 | 1434.725 | no |
| raw | q25 | efficiency | 1265.23 | 1269.166 | yes |
| raw | q26 | efficiency | 60.25 | 60.685 | no |
| raw | q27 | efficiency | 23.76 | 24.704 | no |
| raw | q28 | efficiency | 719.44 | 13387.25 | no |
| raw | q29 | efficiency | 2.45 | 2.428 | no |
| raw | q30 | efficiency | 57.1 | 57.103 | yes |
| raw | q31 | efficiency | 2.99 | 2.986 | yes |
| raw | q32 | efficiency | Partners (affiliate) | Webinars | no |
| raw | q33 | efficiency | 83.02 | 82.387 | no |
| raw | q34 | trend | refused | 67.96 | no |
| raw | q35 | trend | -8.68 | -10.699 | no |
| raw | q36 | trend | 282273.06 | 302181.31 | no |
| raw | q37 | trend | 53 | 53 | yes |
| raw | q38 | controls | 6445219 | 6445219 | yes |
| raw | q39 | controls | 29.29 | 29.29 | yes |
| raw | q40 | controls | 62 | 62 | yes |
| raw | q41 | controls | 53 | 53 | yes |
| raw | q42 | controls | 100.01 | 100.006 | yes |
| raw | q43 | refusal | refused | refuse | yes |
| raw | q44 | refusal | refused | refuse | yes |
| raw | q45 | refusal | refused | refuse | yes |
| raw | q46 | refusal | refused | refuse | yes |
| raw | q47 | refusal | refused | refuse | yes |
| raw | q48 | refusal | refused | refuse | yes |
| raw | q49 | refusal | refused | refuse | yes |
| raw | q50 | refusal | refused | refuse | yes |
