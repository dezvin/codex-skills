# Text And Layout

## Table Of Contents

1. Purpose
2. Read When
3. Core Principle
4. Text Priority Rule
5. Minimum Text Specification
6. Hierarchy
7. Typography Direction
8. Placement And Zones
9. Negative Space And Margins
10. Text Length And Typography Baseline
11. Posters, Slides, Infographics, UI, And Mobile Formats
12. Text Replacement And Localization
13. Layout In Sets
14. Exact Spelling
15. Failure Modes
16. What This File Must Not Do

## 1. Purpose

This reference controls text inside images, typography-aware prompts, readable layout, zones, poster and slide structure, infographics, UI-like visuals, and text replacement.

## 2. Read When

Read this file when:

- requested text must appear inside the image;
- exact text must appear in the image;
- text replacement or localization is requested;
- the task is a poster, slide, thumbnail, title card, frame, card,
  infographic, diagram, or UI-like visual;
- hierarchy, zones, margins, labels, or readability materially affect success.

## 3. Core Principle

When an image contains important text, the task becomes a layout problem.

Control:

- text hierarchy;
- placement;
- negative space;
- background complexity;
- spacing;
- reading path;
- legibility.

Layout control outranks decorative scene density when text readability matters.

## 4. Text Priority Rule

When text matters, prioritize:

1. legibility;
2. hierarchy;
3. placement;
4. spacing and negative space;
5. visual harmony;
6. decorative richness.

Do not sacrifice readable text for atmosphere.

## 5. Minimum Text Specification

For each important text block, define:

- exact text in double quotes;
- language;
- role;
- approximate placement;
- relative priority;
- whether full legibility is mission-critical.

Common roles:

- headline;
- subheadline;
- body copy;
- caption;
- label;
- CTA;
- footer;
- badge;
- button text;
- axis label;
- annotation.

Exact user-provided in-image text must be preserved.

## 6. Hierarchy

Text-heavy visuals fail when all text blocks compete equally.

Define:

- primary text;
- secondary text;
- tertiary/support text;
- what must dominate first glance;
- what may be smaller or quieter.

Useful wording:

- "The headline is the dominant visual text element."
- "The subheadline is smaller and placed directly below."
- "The footer is discreet and aligned to the bottom margin."

## 7. Typography Direction

Specify a type direction when it improves the result:

- serif, sans-serif, script, or monospaced;
- bold, regular, condensed, or expanded;
- editorial, corporate, elegant, industrial, playful, or technical.

Typography must fit the use case, not merely the mood. Avoid exact font-family
claims unless the font is known, available, and important.

## 8. Placement And Zones

Use concrete placement language:

- upper third;
- lower third;
- top-left;
- top-right;
- centered;
- left-aligned block;
- right sidebar;
- center column;
- full-width banner;
- left half / right half;
- header area;
- footer strip.

Avoid vague placement:

- somewhere near the top;
- around the center;
- floating nearby.

For structured visuals, define zones:

- title zone;
- hero zone;
- support zone;
- label zone;
- CTA zone;
- footer;
- panel 1 / panel 2 / panel 3.

## 9. Negative Space And Margins

Protect text with:

- generous margins;
- clean separation from image edges;
- low-detail background behind text;
- spacing between text blocks;
- no collision with hair, hands, products, reflections, foliage, architecture detail, or decorative texture.

Useful wording:

- "Keep the background behind the headline visually simple."
- "Preserve clean negative space around every text element."
- "Do not allow props or product edges to intersect the text."

## 10. Text Length And Typography Baseline

Modern multimodal image models (the 2025–2026 baseline including GPT Image 2 / 2.5) natively understand text structure and render multilingual typography, including Russian Cyrillic, with high precision across headlines, subheadlines, bullet points, multi-line cards, and full-screen editorial copy.

Do not fall back to legacy 2023–2024 diffusion workarounds (such as cutting approved text, refusing to render copy, or moving text outside the image).

### Graphic Typography Overlay Vs. Diegetic Props

Distinguish two fundamentally different approaches:

1. **Graphic Typography Overlay:**
   - Intentional typography layer over full-bleed artwork across any format (posters, slides, infographics, flyers, booklets, business cards, covers, mobile stories, social cards).
   - Requires full-bleed composition across the selected medium with organic negative space (shadow, blur, quiet areas) for high-contrast, legible text.
   - Strictly NO artificial split-screens: never split the frame into flat solid-color blocks or banner strips unless a modular UI wireframe is specifically requested.
   - Copy rules: preserve exact user-provided in-image text in full; enforce clear typographic hierarchy (Headline > Subhead/Bullets > CTA) and generous margins; never strip approved text for external overlay.

2. **Diegetic Scene Props:**
   - Text physically embedded in 3D scene objects (signboard, book page, engraving).
   - Use ONLY when the brief explicitly requests physical text on an object.
   - **Failure rule:** Never demote graphic headlines, story text, or slide copy into tiny handwriting in notebooks, tags, or desktop props.

## 11. Posters, Slides, Infographics, UI, And Mobile Formats

Poster:

- strong headline zone;
- one main visual;
- clean support area;
- high contrast and hierarchy.

Slide:

- title zone;
- restrained subtitle;
- one dominant illustration or diagram area;
- presentation-friendly spacing.

Infographic:

- section logic;
- labels;
- reading path;
- grouping;
- clarity over cinematic mood.

UI-like visual:

- clean zones;
- alignment;
- button hierarchy;
- card/panel spacing;
- readable labels;
- modular structure.

## 12. Text Replacement And Localization

For replacement or localization, preserve by default:

- typography tone;
- placement;
- alignment;
- spacing;
- hierarchy;
- margins;
- composition.

Useful instruction:

```text
Replace the existing text with "[new text]" while preserving the original typography tone, placement, spacing, hierarchy, and layout.
```

If the new text is much longer, state whether resizing, line breaks, or hierarchy changes are allowed.

## 13. Layout In Sets

For prompt sets and sequences, layout-first protects readability inside each
item.

Preserve:

- typography direction;
- cleanliness;
- margin discipline;
- hierarchy quality;
- practical utility.

Vary when not explicitly template-based:

- text placement;
- zone structure;
- composition family;
- relationship between text and hero visual;
- meaning carrier.

Do not freeze one layout skeleton across the whole series unless requested.

## 14. Exact Spelling

When exact spelling matters:

- quote the text exactly;
- name the language;
- say not to alter wording;
- preserve punctuation;
- use letter-by-letter fallback only for rare, brand-sensitive, or repeatedly drifting words.

Do not use letter-by-letter mode for ordinary short text by default.

## 15. Failure Modes

Text unreadable:

- strengthen legibility;
- simplify background;
- increase contrast;
- add negative space;
- shorten only if allowed.

Hierarchy collapse:

- define primary/secondary/tertiary text;
- reduce competing objects.

Layout drift:

- use zones;
- preserve margins and spacing;
- define alignment.

Decorative interference:

- lower texture density behind text;
- restrain effects around text areas.

Repeated layout skeleton in series:

- preserve typography standards;
- vary placement, zones, composition family, and text-image relationship.

Prop demotion:

- replacing graphic typography overlay with microscopic handwriting in scene notebooks or desktop props; response: restore graphic typography overlay over the composition.

Artificial split-screen drift:

- dividing the image into flat color blocks and cropped visuals; response: restore full-bleed artwork with organic contrast and negative space.

Legacy text omission:

- refusing or omitting approved copy under legacy generative assumptions; response: render the exact quoted text using modern typography controls.

## 16. What This File Must Not Do

This file must not:

- rewrite or truncate exact approved text;
- force infographic structure on a simple caption task;
- add layout complexity where text is minor;
- demote graphic typography into tiny in-scene props;
- force artificial split-screen color blocks where full-bleed art is required;
- assume text cannot be rendered and must be omitted;
- override exact user text or item-level constraints.
