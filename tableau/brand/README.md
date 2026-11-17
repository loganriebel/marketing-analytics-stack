# Fernhook brand pack for Tableau

Everything needed to make the four dashboards in [`../LAYOUT.md`](../LAYOUT.md) look like one company's work: the logo, the colors, the fonts, the dashboard frame and the words. Fernhook Software is fictional, and so is this brand.

| File | What it is |
|---|---|
| `logo/fernhook-lockup.png` | Mark plus "Fernhook" and the tagline, for light backgrounds. Transparent. |
| `logo/fernhook-lockup-reversed.png` | The same in white and mint, for the dark green header bar. Transparent. |
| `logo/fernhook-mark-{32,64,128,256,512}.png` | The mark alone, square, transparent. |
| `logo/fernhook-mark-reversed-{...}.png` | The mark alone in white and mint. |
| `logo/source-fal-nano-banana-2.png` | The original generated image the others are cut from. |
| `Preferences.tps` | Tableau color palettes: roles, views, test vs control, a blue ramp and a red-blue diverging ramp. |

## The logo

A fern frond whose stem ends in a tow hook: fern for growth, hook for the trucks and vans Fernhook's customers keep running.

- **On the green header bar:** `fernhook-lockup-reversed.png`, 48 px tall.
- **On light backgrounds:** `fernhook-lockup.png`, or the mark alone when space is tight.
- **Clear space:** at least the width of one leaflet on every side.
- **Don't:** stretch it, recolor it, put it on a busy background, or add effects.
- **Smallest size:** 32 px for the mark, 40 px tall for the lockup.

## Colors

### Brand frame

| Name | Hex | Use |
|---|---|---|
| Fern Deep | `#1E4D3B` | Header bar, logo stem, the one brand color in the frame |
| Fern Leaf | `#489261` | Logo leaflets only |
| Mint | `#CFE3D8` | Text on the header bar next to the logo |
| Canvas | `#F6F5F0` | Dashboard background |
| Card | `#FFFFFF` | Background of every sheet container |
| Ink | `#1F2421` | Titles, numbers, body text |
| Slate | `#5B625E` | Subtitles, axis titles, legends |
| Muted | `#7C827E` | Footer, notes, axis tick labels |
| Rule | `#E7E5DE` | Gridlines and dividers |

Fern Deep stays in the frame. It is never a data color, so no one reads the header as a series.

### Data colors

These replace the Okabe-Ito values the layout plan started with. Same jobs, tuned to the brand, and checked again for color-blind readers (see [Checks](#checks)).

| Job | Name | Hex | Where |
|---|---|---|---|
| Role: performance | Hook Blue | `#0072B2` | Paid search, display retargeting, affiliates |
| Role: brand | Signal Amber | `#C27800` | Meta, YouTube, CTV, LinkedIn |
| Role: events | Rose | `#CC6A8E` | Webinars |
| Role: owned | Pine | `#1B7A55` | Email |
| Role: unpaid | Stone | `#878D89` | Organic, direct, referral |
| View: CRM last touch | Slate Gray | `#6E7470` | Dashboard 2 |
| View: platform reported | Rose | `#CC6A8E` | Dashboard 2 |
| View: MMM | Pine | `#1B7A55` | Dashboard 2, with its 90% range line |
| View: answer key | Black | `#000000` | Hollow diamond, every dashboard |
| Test, rollout, measured | Hook Blue | `#0072B2` | Dashboard 4 |
| Control, holdout, forecast, last year | Stone | `#878D89` | Dashboards 1 and 4 |
| Grown | Hook Blue | `#0072B2` | Diverging bars |
| Cut | Brake Red | `#C8452F` | Diverging bars |
| Ranges and bands | Mist | `#DCDDD6` | HDI areas, reference bands |

**Deltas keep their status colors:** good `#2E7D32`, bad `#C62828`, neutral `#6B6B6B`, always with ▲ or ▼ so color is never the only signal.

**Ramps** (in `Preferences.tps`):
- Fernhook blue, for magnitude: `#93BADF` `#6A9FD0` `#3F86C1` `#0072B2` `#0B4F80`
- Fernhook red-blue, for above or below zero (the market map's `Won vs YA`): `#C8452F` `#DC8873` `#EEC5B9` `#EDECE6` `#B4CFE8` `#6A9FD0` `#0072B2`

### Install the palettes

1. Close Tableau.
2. Open `Documents\My Tableau Repository\Preferences.tps`. Tableau Public usually keeps it in `Documents\My Tableau Public Repository` instead.
3. Copy everything between `<preferences>` and `</preferences>` from this folder's `Preferences.tps` into that file, inside its own `<preferences>` tag. If the file is empty or missing, copy this one over it.
4. Reopen Tableau. Edit Colors now lists the five Fernhook palettes. Colors are saved into the workbook, so Tableau Public viewers see them too.

## Fonts

Tableau's own fonts render on Tableau Public without substitution, so use only these. Set them once under Format, Workbook.

| Element | Font | Size | Color |
|---|---|---:|---|
| Dashboard title | Tableau Semibold | 20 | Ink |
| Dashboard subtitle | Tableau Book | 11 | Slate |
| Sheet title | Tableau Semibold | 12 | Ink |
| Big number (BAN) | Tableau Semibold | 26 | Ink |
| BAN label | Tableau Book | 9 | Slate |
| Axis and header labels | Tableau Book | 9 | Slate |
| Tooltip | Tableau Book | 10 | Ink, labels in Slate |
| Header bar text | Tableau Book | 11 | Mint |
| Footer | Tableau Book | 8 | Muted |

The logo's wordmark is set in Inter SemiBold. Inter doesn't render on Tableau Public, which is why the wordmark ships as an image.

## The dashboard frame

The same frame on all four dashboards, so they read as one workbook.

1. **Size:** keep the fixed sizes from `LAYOUT.md` (1400 wide).
2. **Canvas:** Dashboard, Format, Shading: `#F6F5F0`.
3. **Header bar:** a horizontal container across the top, 64 px tall, background `#1E4D3B`, inner padding 8 left and right.
   - Left: an Image object with `fernhook-lockup-reversed.png`, fit to height, 48 px.
   - Right: a Text object, right aligned, Tableau Book 11 in Mint: `Marketing readout  |  Synthetic data`.
4. **Title block:** under the header, a Text object. Title on line 1 (Tableau Semibold 20, Ink), subtitle on line 2 (Tableau Book 11, Slate). Outer padding 16 left, 12 top.
5. **Cards:** put each sheet in its own vertical container with background `#FFFFFF`, outer padding 8, inner padding 12, and no border. The canvas showing between cards does the separating.
6. **Sheets:** Format, Workbook, Lines: gridlines `#E7E5DE`, zero lines `#C5C8C3`, no row or column dividers. Worksheet shading: none, so the card shows through.
7. **Footer:** a Text object across the bottom, Tableau Book 8 in Muted (text below).

## Words

### Names

- **Company:** Fernhook Software. Short form: Fernhook. Never "FernHook" or "Fern Hook".
- **Tagline:** Fleet maintenance software.
- **Workbook name on Tableau Public:** Fernhook marketing readout (synthetic)

### Header and footer

Header bar, right side:

```
Marketing readout  |  Synthetic data
```

Footer, every dashboard:

```
Synthetic data. Fernhook Software is a fictional company built for a portfolio project. Data and code: github.com/loganriebel/marketing-analytics-stack
```

### Dashboard titles

Use the titles and subtitles in `LAYOUT.md`. They follow the rules below.

| Dashboard | Title |
|---|---|
| 1 | Fernhook weekly readout |
| 2 | Three views of the same spend |
| 3 | Where the next dollar goes |
| 4 | What the test and the rollout showed |

### Tableau Public description

```
A marketing readout for Fernhook, a made-up fleet software company: weekly performance, three ways to count the same spend, MMM response curves, and a pre-registered market test and rollout. All data is synthetic and every number rebuilds from code: github.com/loganriebel/marketing-analytics-stack
```

### Tooltips

First line bold, naming the thing. Then one fact per line, label in Slate, value in Ink.

```
<Channel Name>
Spend         <SUM(Spend)>
Won deals     <SUM(Won Deals)>
Cost per deal <CPA>
```

### Number formats

| Measure | Format | Example |
|---|---|---|
| Spend, large | Currency (custom), 1 decimal, display units Millions (M) | $43.1M |
| Spend, weekly | `$#,##0` | $691,741 |
| Cost per lead, cost per deal | `$#,##0` | $1,205 |
| Deals, leads | `#,##0` | 24,886 |
| Rates | `0.0%` | 33.8% |
| Deltas | `▲0.0%;▼0.0%;0.0%` | ▲11.9% |
| Ranges | `+#,##0;-#,##0` with "to" between | +246 to +679 |

### Voice

- Sentence case for every title, label and button. No Title Case.
- The subtitle says what to take away, not what the chart is.
- Short sentences and plain words. No em dashes.
- Every range says what it is the first time: "90% range".
- The answer key is always labeled "answer key" and always a hollow black diamond.

## Checks

Run with the dataviz palette validator (OKLab color distance, protan and deutan simulation):

- **Roles** (Hook Blue, Signal Amber, Rose, Pine) pass every pair on white and on Canvas: color-blind separation 8.6 at worst (target 8), normal-vision separation 15.5 (floor 15), every color at least 3:1 against the background. The Okabe-Ito set it replaces had amber at 2.25:1 and a 7.6 color-blind pair.
- **Views** (Rose, Pine) and **grown vs cut** (Hook Blue, Brake Red) pass.
- **Fernhook blue** is one hue, steps evenly from light to dark, and its lightest step clears 2:1 on white.
- **Text:** Ink on Canvas 14.4:1, Slate on Card 6.3:1, Muted on Card 3.9:1, white on Fern Deep 9.6:1, Mint on Fern Deep 7.2:1.

## How the logo was made

- **Model:** fal `fal-ai/nano-banana-2`, 1024 x 1024, 4 options, option 3 kept. Generated 2026-11-17.
- **Prompt:** "A simple, flat, geometric logo mark for Fernhook, a fleet-maintenance software company. The mark is a single stylized fern frond whose stem curls at the bottom into a clean J-shaped hook, like a tow hook. Built from a few bold, smooth shapes with even stroke weight, like a modern app icon. Exactly two colors: deep fern green #1E4D3B for the hook and stem, and lighter leaf green #3E8E63 for the frond leaflets. Solid flat fills only, no gradients, no shadows, no outlines, no 3D, no texture. Centered on a plain pure white background with generous empty margin. No text, no letters, no circle or badge around it. Must read clearly at 32 pixels."
- **After:** the white background was turned into transparency, both greens were snapped to the brand hex values, and the reversed and lockup versions were drawn from the same shapes.
