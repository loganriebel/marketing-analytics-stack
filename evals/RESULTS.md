# Eval results

Model: `claude-sonnet-5-5`, one pass per arm, same system prompt. 42 questions have a SQL ground truth (0.5% tolerance); 8 should be refused. Built-in tools are off, so each arm sees data only through its MCP server.

| Arm | Answerable correct | Correct refusals | Wrong refusals | Overall | Cost | Avg time |
|---|---|---|---|---|---|---|
| Claude + governed metrics (MCP) | 42/42 (100%) | 8/8 (100%) | 0 | 50/50 | $3.27 | 15s |
| Claude + raw tables (SQL) | 23/42 (55%) | 8/8 (100%) | 3 | 31/50 | $3.65 | 13s |

## Per question

| Arm | Id | Category | Answer | Truth | Correct |
|---|---|---|---|---|---|
| governed | q01 | media | 37124999.89 | 37124999.89 | yes |
| governed | q02 | media | 5404832.95 | 5404832.95 | yes |
| governed | q03 | media | 19.15 | 19.153 | yes |
| governed | q04 | media | Paid Search Non-Brand | Paid Search Non-Brand | yes |
| governed | q05 | media | 478223.11 | 478223.11 | yes |
| governed | q06 | media | 112044535 | 112044535 | yes |
| governed | q07 | media | 0.6 | 0.603 | yes |
| governed | q08 | media | 8.9957 | 8.996 | yes |
| governed | q09 | media | 10.22 | 10.222 | yes |
| governed | q10 | media | 165300 | 165300.0 | yes |
| governed | q11 | media | 95.14 | 95.144 | yes |
| governed | q12 | funnel | 138880 | 138880 | yes |
| governed | q13 | funnel | 107193 | 107193 | yes |
| governed | q14 | funnel | 29947 | 29947 | yes |
| governed | q15 | funnel | 24384 | 24384 | yes |
| governed | q16 | funnel | 219826880 | 219826880.00 | yes |
| governed | q17 | funnel | 24886 | 24886 | yes |
| governed | q18 | funnel | 19158400 | 19158400.00 | yes |
| governed | q19 | funnel | 31.73 | 31.734 | yes |
| governed | q20 | funnel | 2966.47 | 2966.467 | yes |
| governed | q21 | funnel | 45.55 | 45.554 | yes |
| governed | q22 | funnel | 4967 | 4967 | yes |
| governed | q23 | funnel | Chicago | Chicago | yes |
| governed | q24 | efficiency | 1730.89 | 1730.893 | yes |
| governed | q25 | efficiency | 1267.03 | 1267.035 | yes |
| governed | q26 | efficiency | 58.51 | 58.509 | yes |
| governed | q27 | efficiency | 57.52 | 57.522 | yes |
| governed | q28 | efficiency | 17592.59 | 17592.593 | yes |
| governed | q29 | efficiency | 2.2139 | 2.214 | yes |
| governed | q30 | efficiency | 66.41 | 66.408 | yes |
| governed | q31 | efficiency | 2.96 | 2.96 | yes |
| governed | q32 | efficiency | Webinars | Webinars | yes |
| governed | q33 | efficiency | 91.65 | 91.647 | yes |
| governed | q34 | trend | 56.89 | 56.889 | yes |
| governed | q35 | trend | -10.02 | -10.022 | yes |
| governed | q36 | trend | 927784.83 | 927784.83 | yes |
| governed | q37 | trend | 53 | 53 | yes |
| governed | q38 | controls | 16088821 | 16088821 | yes |
| governed | q39 | controls | 29.46 | 29.461 | yes |
| governed | q40 | controls | 159 | 159 | yes |
| governed | q41 | controls | 131 | 131 | yes |
| governed | q42 | controls | 101.11 | 101.112 | yes |
| governed | q43 | refusal | refused | refuse | yes |
| governed | q44 | refusal | refused | refuse | yes |
| governed | q45 | refusal | refused | refuse | yes |
| governed | q46 | refusal | refused | refuse | yes |
| governed | q47 | refusal | refused | refuse | yes |
| governed | q48 | refusal | refused | refuse | yes |
| governed | q49 | refusal | refused | refuse | yes |
| governed | q50 | refusal | refused | refuse | yes |
| raw | q01 | media | 33450000 | 37124999.89 | no |
| raw | q02 | media | 5404832.95 | 5404832.95 | yes |
| raw | q03 | media | refused | 19.153 | no |
| raw | q04 | media | Google | Paid Search Non-Brand | no |
| raw | q05 | media | 478223.11 | 478223.11 | yes |
| raw | q06 | media | 112044535 | 112044535 | yes |
| raw | q07 | media | 0.6 | 0.603 | yes |
| raw | q08 | media | 9.0 | 8.996 | yes |
| raw | q09 | media | 10.22 | 10.222 | yes |
| raw | q10 | media | 165300 | 165300.0 | yes |
| raw | q11 | media | 95.14 | 95.144 | yes |
| raw | q12 | funnel | 134265 | 138880 | no |
| raw | q13 | funnel | 106475 | 107193 | no |
| raw | q14 | funnel | 25588 | 29947 | no |
| raw | q15 | funnel | 24384 | 24384 | yes |
| raw | q16 | funnel | 220204440 | 219826880.00 | yes |
| raw | q17 | funnel | 25163 | 24886 | no |
| raw | q18 | funnel | 19719110 | 19158400.00 | no |
| raw | q19 | funnel | 31.77 | 31.734 | yes |
| raw | q20 | funnel | 2964.9 | 2966.467 | yes |
| raw | q21 | funnel | 45.56 | 45.554 | yes |
| raw | q22 | funnel | 5019 | 4967 | no |
| raw | q23 | funnel | Chicago | Chicago | yes |
| raw | q24 | efficiency | 1712.52 | 1730.893 | no |
| raw | q25 | efficiency | 1264.09 | 1267.035 | yes |
| raw | q26 | efficiency | 58.11 | 58.509 | no |
| raw | q27 | efficiency | 56.63 | 57.522 | no |
| raw | q28 | efficiency | refused | 17592.593 | no |
| raw | q29 | efficiency | 2.23 | 2.214 | no |
| raw | q30 | efficiency | 66.41 | 66.408 | yes |
| raw | q31 | efficiency | 2.96 | 2.96 | yes |
| raw | q32 | efficiency | Partners (affiliate) | Webinars | no |
| raw | q33 | efficiency | 92.28 | 91.647 | no |
| raw | q34 | trend | refused | 56.889 | no |
| raw | q35 | trend | -8.1 | -10.022 | no |
| raw | q36 | trend | 820672.13 | 927784.83 | no |
| raw | q37 | trend | 53 | 53 | yes |
| raw | q38 | controls | 16088821 | 16088821 | yes |
| raw | q39 | controls | 29.46 | 29.461 | yes |
| raw | q40 | controls | 159 | 159 | yes |
| raw | q41 | controls | 131 | 131 | yes |
| raw | q42 | controls | 101.11 | 101.112 | yes |
| raw | q43 | refusal | refused | refuse | yes |
| raw | q44 | refusal | refused | refuse | yes |
| raw | q45 | refusal | refused | refuse | yes |
| raw | q46 | refusal | refused | refuse | yes |
| raw | q47 | refusal | refused | refuse | yes |
| raw | q48 | refusal | refused | refuse | yes |
| raw | q49 | refusal | refused | refuse | yes |
| raw | q50 | refusal | refused | refuse | yes |
