# Format And Ratio

## Table Of Contents

1. Purpose
2. Read When
3. Core Principle
4. Ratio Selection
5. Default Ratio Families
6. Text And Ratio
7. Subject Count And Zones
8. Cropping Pressure
9. Ratio-Sensitive Patterns
10. Safe Defaults
11. When To Mention Ratio
12. Failure Modes
13. What This File Must Not Do

## 1. Purpose

This reference controls aspect ratio, orientation, carrier format, crop pressure, and format-sensitive composition.

## 2. Read When

Read this file when:

- format or ratio is specified;
- story, carousel, poster, slide, banner, cover, thumbnail, or infographic format matters;
- text needs space;
- crop pressure could damage the result;
- the frame shape changes reading path or subject placement.

## 3. Core Principle

Aspect ratio is not cosmetic.

It changes:

- composition;
- cropping;
- subject placement;
- text space;
- reading path;
- number of zones;
- stability of multi-object layouts.

Choose format by function, not habit.

## 4. Ratio Selection

Base ratio choice on:

1. where the image will live;
2. vertical vs horizontal information needs;
3. text amount and hierarchy;
4. number of zones or panels;
5. one subject vs multiple sections;
6. crop risk.

If ratio materially affects success, mention it explicitly in the prompt.

## 5. Default Ratio Families

`1:1 square`

- good for social posts, balanced product shots, centered compositions, simple cards;
- risk: cramped for long text or many zones.

`4:5 / 5:4`

- good for social portraits, posters, product + headline visuals;
- risk: crowded if too many zones are added.

`3:4 / 4:3`

- good for editorial portrait, balanced poster, product-in-context, flexible framing.

`2:3 / 3:2`

- good for photo-like scenes, print-friendly visuals, editorial images.

`16:9`

- good for presentation covers, hero banners, thumbnails, wide UI/product strips;
- risk: weak for stacked text and small subjects.

`9:16`

- good for stories, reels, mobile-first visuals, vertical stacked hierarchy;
- risk: limited side detail and lateral complexity.

`21:9`

- good for cinematic panoramas and wide environmental storytelling;
- risk: weak for dense typography and focal clarity.

Extreme ratios:

- include `1:4`, `1:8`, `4:1`, and `8:1`;
- use only with intentional reading path and simplified structure;
- the more extreme the ratio, the stronger the zone logic must be.
- confirm that the target model supports the requested ratio before presenting
  it as an exact generation setting.

`1:4` or `1:8`:

- use for a deliberate single-column flow, elongated process, or tall
  infographic;
- reduce side-by-side elements;
- define section count and top-to-bottom reading order;
- treat `1:8` as exceptional because ordinary scenes become unstable.

`4:1` or `8:1`:

- use for intentional banners, panoramic environments, or lateral sequences;
- define a clear focal anchor and text-versus-subject balance;
- treat `8:1` as exceptional because focal clarity and text density degrade
  quickly.

## 6. Text And Ratio

If text matters, format choice affects readability.

Safer for stacked text:

- `9:16`;
- `4:5`;
- `3:4`;
- `2:3`.

Safer for horizontal title + subject:

- `16:9`;
- `21:9`;
- `4:3`.

Less forgiving:

- square with too many zones;
- ultra-wide with stacked text;
- extreme formats without simplified structure.

## 7. Subject Count And Zones

One dominant subject:

- square, portrait, or moderate landscape can work.

Subject plus environment:

- wider ratios may help if environment carries meaning.

Several sections or panels:

- use structured zone language;
- avoid forcing too many panels into a cramped ratio.

If zones matter, name them.

## 8. Cropping Pressure

Common crop failures:

- face cut too tightly;
- product clipped;
- text pushed into unsafe margins;
- subject too small in wide frame;
- empty dead space dominates;
- side details collapse in vertical frame.

Prevent by:

- choosing ratio after subject priority;
- defining safe text zones;
- preserving margins;
- reducing secondary elements in narrow frames;
- widening only when environment matters.

## 9. Ratio-Sensitive Patterns

Vertical stack:

- good for `9:16`, `4:5`, `1:4`;
- title/top zone, hero middle, support/CTA lower.

Wide split:

- good for `16:9`, `21:9`, `4:1`;
- text one side, subject other side, or subject offset in environment.

Centered hero:

- good for `1:1`, `4:5`, `3:4`;
- central subject, minimal support, optional top/bottom text band.

Panel strip:

- good for `16:9`, `4:3`, `1:4`, `4:1`;
- repeated sections, equal spacing, clear reading order.

## 10. Safe Defaults

If the user does not specify format and uncertainty is minor:

- square social visual -> `1:1`;
- portrait/social visual -> `4:5`;
- mobile story -> `9:16`;
- presentation/hero/thumbnail -> `16:9`;
- cover/print-like portrait -> `2:3`;
- editorial image -> `3:2` or `3:4`;
- infographic -> `9:16` or `1:4` depending on density.

If ratio changes the whole structure, ask.

## 11. When To Mention Ratio

Mention ratio when:

- platform depends on it;
- layout hierarchy depends on it;
- poster/slide/infographic structure depends on it;
- mobile-first or banner logic is required;
- crop safety matters;
- extreme format is intended.

Connect ratio to composition:

- "vertical 9:16 composition for a mobile-first story layout";
- "wide 16:9 hero banner with title-left and subject-right structure";
- "square 1:1 carousel card with centered hierarchy".

## 12. Failure Modes

Subject too small in wide frame:

- define focal priority and subject scale.

Vertical frame cramped:

- reduce side elements and simplify zones.

Text does not fit:

- choose a safer text ratio or simplify text structure.

Banner feels empty:

- add lateral logic or offset subject with purposeful negative space.

Infographic unstable:

- define section count, reading path, and zone structure.

## 13. What This File Must Not Do

This file must not:

- force ratio discussion into simple requests;
- choose dramatic ratios for effect;
- replace subject logic with format obsession;
- force extreme ratios when standard ratios work;
- promise an exact ratio that the chosen model does not support.
