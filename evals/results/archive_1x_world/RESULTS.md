# Eval results

Model: `claude-sonnet-5-5`, one pass per arm, same system prompt. 42 questions have a SQL ground truth (0.5% tolerance); 8 should be refused. Built-in tools are off, so each arm sees data only through its MCP server.

| Arm | Answerable correct | Correct refusals | Wrong refusals | Overall | Cost | Avg time |
|---|---|---|---|---|---|---|
| Claude + governed metrics (MCP) | 42/42 (100%) | 8/8 (100%) | 0 | 50/50 | $3.27 | 14s |
| Claude + raw tables (SQL) | 23/42 (55%) | 8/8 (100%) | 3 | 31/50 | $3.64 | 15s |

## Per question

| Arm | Id | Category | Answer | Truth | Correct |
|---|---|---|---|---|---|
| governed | q01 | media | 14849999.97 | 14849999.97 | yes |
| governed | q02 | media | 2161933.17 | 2161933.17 | yes |
| governed | q03 | media | 19.15 | 19.153 | yes |
| governed | q04 | media | Paid Search Non-Brand | Paid Search Non-Brand | yes |
| governed | q05 | media | 191289.25 | 191289.25 | yes |
| governed | q06 | media | 44979715 | 44979715 | yes |
| governed | q07 | media | 0.61 | 0.609 | yes |
| governed | q08 | media | 8.97 | 8.968 | yes |
| governed | q09 | media | 10.19 | 10.194 | yes |
| governed | q10 | media | 67901 | 67901.0 | yes |
| governed | q11 | media | 94.98 | 94.982 | yes |
| governed | q12 | funnel | 56328 | 56328 | yes |
| governed | q13 | funnel | 43428 | 43428 | yes |
| governed | q14 | funnel | 12127 | 12127 | yes |
| governed | q15 | funnel | 9808 | 9808 | yes |
| governed | q16 | funnel | 88777610 | 88777610.00 | yes |
| governed | q17 | funnel | 9713 | 9713 | yes |
| governed | q18 | funnel | 7771510 | 7771510.00 | yes |
| governed | q19 | funnel | 31.22 | 31.221 | yes |
| governed | q20 | funnel | 2989.26 | 2989.265 | yes |
| governed | q21 | funnel | 45.68 | 45.678 | yes |
| governed | q22 | funnel | 1796 | 1796 | yes |
| governed | q23 | funnel | Chicago | Chicago | yes |
| governed | q24 | efficiency | 1773.91 | 1773.911 | yes |
| governed | q25 | efficiency | 1283.64 | 1283.636 | yes |
| governed | q26 | efficiency | 58.01 | 58.007 | yes |
| governed | q27 | efficiency | 56.48 | 56.473 | yes |
| governed | q28 | efficiency | 13970.59 | 13970.589 | yes |
| governed | q29 | efficiency | 2.22 | 2.216 | yes |
| governed | q30 | efficiency | 65.53 | 65.528 | yes |
| governed | q31 | efficiency | 2.9859 | 2.986 | yes |
| governed | q32 | efficiency | Webinars | Webinars | yes |
| governed | q33 | efficiency | 90.0 | 89.997 | yes |
| governed | q34 | trend | 56.89 | 56.889 | yes |
| governed | q35 | trend | -11.76 | -11.764 | yes |
| governed | q36 | trend | 368283.99 | 368283.99 | yes |
| governed | q37 | trend | 53 | 53 | yes |
| governed | q38 | controls | 6370798 | 6370798 | yes |
| governed | q39 | controls | 29.43 | 29.428 | yes |
| governed | q40 | controls | 61 | 61 | yes |
| governed | q41 | controls | 53 | 53 | yes |
| governed | q42 | controls | 100.1765 | 100.176 | yes |
| governed | q43 | refusal | refused | refuse | yes |
| governed | q44 | refusal | refused | refuse | yes |
| governed | q45 | refusal | refused | refuse | yes |
| governed | q46 | refusal | refused | refuse | yes |
| governed | q47 | refusal | refused | refuse | yes |
| governed | q48 | refusal | refused | refuse | yes |
| governed | q49 | refusal | refused | refuse | yes |
| governed | q50 | refusal | refused | refuse | yes |
| raw | q01 | media | 13380000.09 | 14849999.97 | no |
| raw | q02 | media | 2161933.17 | 2161933.17 | yes |
| raw | q03 | media | refused | 19.153 | no |
| raw | q04 | media | Google | Paid Search Non-Brand | no |
| raw | q05 | media | 191289.25 | 191289.25 | yes |
| raw | q06 | media | 44979715 | 44979715 | yes |
| raw | q07 | media | 0.61 | 0.609 | yes |
| raw | q08 | media | 8.97 | 8.968 | yes |
| raw | q09 | media | 10.19 | 10.194 | yes |
| raw | q10 | media | 67901 | 67901.0 | yes |
| raw | q11 | media | 94.98 | 94.982 | yes |
| raw | q12 | funnel | 54279 | 56328 | no |
| raw | q13 | funnel | 43149 | 43428 | no |
| raw | q14 | funnel | 10340 | 12127 | no |
| raw | q15 | funnel | 9808 | 9808 | yes |
| raw | q16 | funnel | 88978140 | 88777610.00 | yes |
| raw | q17 | funnel | 9837 | 9713 | no |
| raw | q18 | funnel | 7962680 | 7771510.00 | no |
| raw | q19 | funnel | 31.2 | 31.221 | yes |
| raw | q20 | funnel | 2988.18 | 2989.265 | yes |
| raw | q21 | funnel | 45.69 | 45.678 | yes |
| raw | q22 | funnel | 1820 | 1796 | no |
| raw | q23 | funnel | Chicago | Chicago | yes |
| raw | q24 | efficiency | 1752.25 | 1773.911 | no |
| raw | q25 | efficiency | refused | 1283.636 | no |
| raw | q26 | efficiency | 57.62 | 58.007 | no |
| raw | q27 | efficiency | 56.47 | 56.473 | yes |
| raw | q28 | efficiency | 706.85 | 13970.589 | no |
| raw | q29 | efficiency | 2.26 | 2.216 | no |
| raw | q30 | efficiency | 65.53 | 65.528 | yes |
| raw | q31 | efficiency | 2.99 | 2.986 | yes |
| raw | q32 | efficiency | Partners | Webinars | no |
| raw | q33 | efficiency | 90.64 | 89.997 | no |
| raw | q34 | trend | refused | 56.889 | no |
| raw | q35 | trend | -9.62 | -11.764 | no |
| raw | q36 | trend | 325438.93 | 368283.99 | no |
| raw | q37 | trend | 53 | 53 | yes |
| raw | q38 | controls | 6370798 | 6370798 | yes |
| raw | q39 | controls | 29.43 | 29.428 | yes |
| raw | q40 | controls | 61 | 61 | yes |
| raw | q41 | controls | 53 | 53 | yes |
| raw | q42 | controls | 100.18 | 100.176 | yes |
| raw | q43 | refusal | refused | refuse | yes |
| raw | q44 | refusal | refused | refuse | yes |
| raw | q45 | refusal | refused | refuse | yes |
| raw | q46 | refusal | refused | refuse | yes |
| raw | q47 | refusal | refused | refuse | yes |
| raw | q48 | refusal | refused | refuse | yes |
| raw | q49 | refusal | refused | refuse | yes |
| raw | q50 | refusal | refused | refuse | yes |
