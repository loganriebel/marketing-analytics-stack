# Step 5: the funding memo

An agent turns the MMM's outputs into a one-page funding memo for the CFO, and a script fails the run if the memo holds any number the model did not produce.

**Sample run ([memo](outputs/funding_memo.md)):** the memo asks for a free 8-week market test first, then a same-budget reallocation of $1.5M a year, with $336K a year more for YouTube as the new-money alternative. All 49 numbers in it match the facts pack. Graded afterward against the hidden answer key, the reallocation's claim holds and the YouTube claim is too low.

| Variant | Memo claims, extra deals a year (90% range) | True | Covered |
|---|---:|---:|---|
| Same-budget reallocation | 166 (10 to 334) | 194 | yes |
| YouTube +50% (new money) | 128 (75 to 172) | 221 | no |

- **The reallocation holds.** The true gain is 14% above the memo's middle estimate and inside its range.
- **The YouTube claim is too low.** The MMM's cost per extra deal for YouTube is too high (its 90% range misses the truth in the [MMM grade](../mmm/grading/grade_holdout.md)), so the memo understates the gain. It errs on the safe side, but the range is still wrong.
- **The test is weak, and the memo says so.** The model expects the cuts to cost 5.5 deals in the test markets, and the test can only see a drop of about 36. The memo states both.
- **The graded world shows why that matters.** In truth the cuts cost 395 deals a year, 2.2 times the model's 178 (LinkedIn and affiliates far more than modeled, display less). The test markets would lose about 12 deals, well under the 36 the test can see, so the test as written would miss it. The move still pays because YouTube, Meta and CTV gain more than modeled too.

## Three parts

```
mmm/outputs/  ->  memo/facts.py  ->  facts.json  ->  memo/writer.py (claude -p)  ->  funding_memo.md
                                         |                                              |
                                         +---------------> memo/grounding.py <----------+
                                                                  |
                                                            grounding.json (fails below 100%)
```

1. **Facts pack** (`memo/facts.py`, plain Python): reads `mmm/outputs/` only and writes [`facts.json`](outputs/facts.json), 108 facts, each with an id, value, unit, kind and source file. Same inputs, same bytes.
2. **Writer** (`memo/writer.py`): headless `claude -p`, default model `claude-sonnet-5-5` (same as the evals). Every built-in tool is off, no MCP servers load, and it runs from an empty folder, so the facts pack in the prompt is all it sees.
3. **Grounding check** (`memo/grounding.py`): pulls every number from the memo and matches it to a fact under the rules below. It writes [`grounding.json`](outputs/grounding.json) and exits 1 below 100%.

If grounding or the style check fails, the writer gets the failures (each number with the sentence around it) and rewrites, up to 2 times. The sample needed 2 drafts: the first was 561 words. [`writer.json`](outputs/writer.json) logs every attempt, about $0.20 each.

## Run it

From the repo root, after the MMM has written `mmm/outputs/` (no warehouse needed):

```bash
.venv\Scripts\python -m memo
.venv\Scripts\python -m memo.grounding
.venv-mmm\Scripts\python -m mmm.grade
.venv\Scripts\python -m pytest tests/test_memo.py -q
```

- `python -m memo` builds the facts, writes the memo, checks it, and exits 1 unless grounding is at 100%. `--model` and `--retries` change the writer.
- `python -m memo.facts` and `python -m memo.grounding` run one part. The grounding check takes `--memo`, `--facts` and `--out`.
- `mmm.grade` reads the memo's outputs when they exist and adds the truth check to `mmm/grading/`.
- The memo code is plain Python, so it runs in either environment. It needs the Claude CLI signed in.

## The facts pack

**A year** is the average year of the MMM window: 156 weeks, or 3 years at 2023 to 2025 spend. The MMM scores whole-window spend paths, so each per-year fact is the window number divided by 3. That is exact for means and for 90% ranges, because it rescales every posterior draw the same way.

**Point estimates:** deal changes use posterior means, because the optimizer maximizes the mean and means add up. Channel CPAs and deals use medians, as the MMM docs do.

**Kinds:** `estimate` (an MMM output), `input` (spend or observed deals the MMM used), `derived` (arithmetic on outputs, written out in the fact's `how`), `design` (the test plan).

| Group | What | From |
|---|---|---|
| Context | Markets, window, paid spend, observed deals, blended CPA, holdout error | `channels.json`, `diagnostics_holdout.json` |
| Paid media | Deals it causes, its incremental CPA and share of deals, each with a 90% range | `channels.json` summary |
| Every channel | Spend, deals, CPA and marginal CPA with 90% ranges. Meta, YouTube and CTV include deals they create through brand search | `channels.json` |
| Revenue per deal | $2,841: the MMM values each deal at its market's average won-deal revenue. Here it is `sum(roi x spend) / sum(deals)` over the 8 channels | `channels.json` |
| Ask A: reallocation | The optimizer's plan at the same total: each channel's move, extra deals and revenue with ranges, odds of a gain, extra brand-search spend, payback | `optimizer.json` |
| Ask B: YouTube | YouTube is the channel with the lowest cost per extra deal. The ask grows it 50%, the largest step the optimizer allows (where the plan also puts it). Its range is exact: the optimizer scored that move on every draw | `optimizer.json`, `response_curves_total.csv` |
| Risks | Wide ranges, always-on channels not measured, Meta mixed with the season, paid media likely under-credited, a good fit is not proof, YouTube past what the model has seen | `docs/mmm/README.md`, numbers from outputs |
| The test | The plan's cuts in 4 markets for 8 weeks against 16 matched markets, the spend it holds back, the drop the model expects, and the smallest drop it can see | design, numbers from outputs |

**Sizing the YouTube ask on its curve.** Each 25% step costs more per extra deal, counting the brand-search spend it creates: $2,677, then $2,915, then $3,196 for the step past the optimizer's limit. The ask stops at 50%. The whole ask costs $2,791 per extra deal and pays back in 11.8 months of first-year revenue.

**Payback** is months of first-year revenue from the extra deals needed to repay the extra spend. It uses revenue, not margin, because the MMM has no cost of goods. The reallocation adds no budget, so its only new cost is the $69K a year of brand search that follows the extra searches.

**Derived ranges.** Revenue, payback and cost per extra deal map the deal range through a fixed formula. Each holds the same 90% of draws as the deal range, but it is not always the narrowest such range.

**The test.** The MMM's limits call for a budget test of an always-on channel in a few markets at 50% to 70% of plan for 6 to 8 weeks. Here it tests the plan's own cuts (LinkedIn, display and affiliates at 50% to 60% of today), because every cut lands on channels the model cannot see. The smallest drop it can see is 2 times the square root of the test markets' deals, which ignores noise in the matched markets, so the real bar is a little higher.

**Prose carries no numbers.** The risks, test and recommendation text in the pack hold no digits or number words (a test checks this), so the writer cannot pass along an unchecked number.

## Grounding rules

**What counts as a number:** dollars ($2,841, $1.5M, $472K, 2 million dollars), percents (5.4%, 30 percent), multipliers (1.5x), counts (166 deals, 4 markets), durations (8 weeks, an 8-week test, 12 months), ranges (10 to 334, $29K to $948K, 6-8 weeks, between 6 and 8), and number words (two to ninety, hundred, thousand, million, billion, dozen, zero, half, double, twice, triple).

**Exempt:** years (a bare 1990 to 2099 with no comma, $, % or scale), ISO dates (2025-12-22), month-day dates (June 1), section and list numbering at the start of a line, digits glued to letters (Q1, B2B), ordinals (3rd), and the word "one".

**Units must agree.** `$` or "dollars" matches only USD facts, `%` only percent facts, `x` only multipliers. A count or duration takes the unit of the next word (deals, markets, channels, weeks, months, years), skipping filler like "more" or "extra". A bare number with no unit word may match any fact that is not USD or percent.

**Rounding.** A number matches a fact when the fact, rounded to the digits the memo shows, equals it, and the memo keeps at least two significant figures.

| Fact | Passes | Fails |
|---|---|---|
| 1,491,623 USD | $1.5M, $1.49M, $1,491,623 | $1M, $2M, $1.4M |
| 472,478 USD | $472K, $470K, $0.47M | $473K |
| 166.3 deals | 166, 170, 166.3 | 200 |
| 8 weeks | 8 weeks, an 8-week test, eight weeks | 9 weeks, 8%, $8 |

Trailing zeros in a whole number are not significant ($500K means $495K to $505K). Signs are ignored, because the words carry the direction: "cut $540K" matches a -540,098 fact.

**Ranges** must match one fact's own low and high, in either order. Ends from two facts fail: "$2,677 to $2,915" is two steps of the YouTube curve, not a range, and the check caught a draft that wrote it that way. A single number may match a fact's value, low or high.

## What grounding does not check

- **Meaning.** It checks that each number exists in the pack with the right unit, not that the sentence uses it correctly. "128 deals" passes whether it describes the YouTube ask or the YouTube row of the reallocation, which are the same number here.
- **Bare numbers** match any count-type fact by value. "3 risks" would pass on the 3-year window.
- **Words without digits.** "Most of the gain" or "a strong lean" are claims, not numbers. The writer's prompt and the pack's risks keep them tied to the model, but no script checks them.

## Boundaries

- `memo/` reads `mmm/outputs/` and its own outputs, nothing else. It never reads the answer key in `sim/` or the MMM's grading folder. Tests check the source text and record every file the facts pack and grounding check open.
- `mmm/grade.py` stays the only reader of the answer key. Its new `grade_memo` reads `memo/outputs/facts.json` for each variant's channel multipliers and claimed range, runs the moves through the true, noise-free response curves (total curves for Meta, YouTube and CTV), divides by the window's years, and reports whether the claimed range covered the true gain. It reads `grounding.json` to report whether the memo stated that range. It writes to `mmm/grading/` only.

## Tests

`tests/test_memo.py`, 69 tests, under a second:

- An invented number fails grounding: added dollars, deals, months, percents and number words, and one changed digit.
- Allowed rounding passes, and wrong rounding, too few significant figures and wrong units fail.
- A range passes only on one fact's own ends.
- Dates, years, numbering and labels are exempt.
- `memo/` never reads the answer key or grading output.
- The facts pack is deterministic and equals the committed file.
- The committed memo passes grounding and style, and matches the committed `grounding.json`.

## Limits

- **The YouTube range misses.** The memo can be only as right as the MMM. The fix is upstream: a test of YouTube's scale, or a lift test from its flights.
- **The test is small.** It can tell the cuts cost more than the model thinks only if the drop is about 6.6 times what the model expects. A sharper read needs more markets, more weeks, or deeper cuts, each with a cost the CFO should see.
- **One sample.** The memo is one draw from the writer. Wording changes run to run, and grounding is the only gate on the numbers.

## Disclosures

- The first truth check printed each channel's true deal change under the plan, which showed the cuts cost more than the model expects. After that, the test's power facts (`test_detectable_drop`, `test_detectable_multiple`) were added to the pack. They use no truth, only observed deals and the model's own expected drop, but the choice to add them came after seeing the grade.
- Other changes after the first grade fixed bugs and limits found by tests and drafts: a range parser bug, a `channels` unit, clearer failure messages, the word limit. None touched the variants, the test design or the claimed ranges.
