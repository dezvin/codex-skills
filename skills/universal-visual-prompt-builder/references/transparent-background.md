# Transparent Background

## 1. Purpose & Modes

Controls native transparent-background prompts, isolated assets, cutouts, and transparent compositions. Do not use for ordinary opaque scenes.

Modes:
- `opaque_scene`: standard environment; no transparency constraints.
- `transparent_isolated_asset`: one isolated subject/group; all surrounding space transparent; no ground, panel, or floor.
- `transparent_composition`: multi-part foreground artwork; intentional gaps and unused space remain transparent; no connecting panels or filler haze.

## 2. Surface Routing

- `chatgpt_images`: natural language only; request true transparent background early. Never insert API parameters (`alpha=0`, `output_format="png"`, `background="transparent"`).
- `api_or_named_model`: verify technical transparency support; keep API parameters outside the image prompt.
- `other_or_unknown`: request transparency in portable natural language; do not falsely guarantee technical alpha.

## 3. Subject Boundary & Local Effects

Foreground artwork includes: primary subject, attached elements, and subject-owned effects (local glow, steam, particles, contact shadow). Anything outside stays transparent.
- Placement context (slide, web, packaging) is used ONLY for contrast; never render the placement surface or color.
- Keep shadows compact/attached. Keep effects local to subject contours; never let glow/smoke expand into an atmospheric background field.

## 4. Prompt Construction

Primary pattern for isolated asset:
```text
Create [subject] as isolated foreground artwork on a true transparent background. Render only [subject boundary]; keep all surrounding space transparent.
```

Multi-part composition addition:
```text
Keep all unused space and intentional gaps between separate parts transparent.
```

Placement context contrast check (without rendering background):
```text
The image will be placed on [placement context]. Use this only for foreground contrast; do not render this color, surface, or any background.
```

Targeted exclusions (apply only on recurring failure):
```text
Do not add a visible backdrop, scene, wall, floor, horizon, rectangular panel, checkerboard pattern, vignette, or atmospheric field.
```

## 5. Editing, Preservation & Repair

When editing a transparent image:
- Follow Two-Line Rule: Line 1 specifies target change; Line 2 explicitly locks transparent regions and subject contours.
- Never fill transparent gaps with inferred scenery. Localize new effects strictly to the edited region.

Repair checklist:
- Visible panel / floor / checkerboard: preserve subject, restate boundary, strip background, mandate transparent empty space.
- Floating haze / expanding shadow: trim to subject contact footprint; eliminate surrounding ground plane.
