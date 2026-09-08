---
name: "explain"
description: "Produce a polished, standalone single-file HTML or visual explainer with Claude-owned aesthetic direction and automatic light/dark mode. Use only when the user requests an HTML page, visual explanation, designed explainer, or similar artifact; an ordinary ‘Hey Claude, explain…’ chat question belongs to claude:claude."
---

# Explain Visually

A one-shot recipe for turning a topic into a polished standalone HTML explainer.

## Host scope

This skill's nested Claude visual-direction pass is Codex-hosted. In Claude
Code, do not spawn another Claude CLI; produce the requested explainer directly,
or use the `design` skill when the user wants the artifact stored and
edited in Claude Design. The shared host helper refuses nested execution when
`$CLAUDECODE` is set.

The user invokes this when they want something **explained as a designed artifact** — not as chat prose, not as markdown, not as a tutorial repo. One HTML file, opens in a browser, looks intentional, works in light and dark mode.

## The contract

Every explainer must:

1. Be a **single self-contained HTML file**. No external JS frameworks. Google Fonts is fine. No build step.
2. Use the **Claude plugin workflow** for aesthetic direction. Claude should own the visual-artifact judgment; Codex remains the steward for scope, saving, opening, and final verification. Do not default to a generic "docs page" look.
3. **Support both light and dark mode** via `@media (prefers-color-scheme: dark)`. No JS toggle, no asking the user which mode they want, no separate files.
4. Be written for **a reader who wants to learn**, not a reader scanning for a reference. Prose can be opinionated. Examples should be worked, not abstract.
5. Save to `/tmp/<slug>-explainer.html` (kebab-case the topic) and `open` it.

## Workflow

1. **Read the topic.** If the user gave one sentence, you have enough — don't over-clarify. If genuinely ambiguous (could be one of two different things), ask once.

2. **Get Claude's design direction.** Use the Claude plugin's visual-direction workflow or `scripts/run_design_pass.py` when available. Pass the topic and ask for a committed visual direction for a standalone educational HTML explainer. Follow that direction unless it conflicts with this skill's contract.

3. **Plan the content before writing CSS.** A good explainer has:
   - A masthead / hero that names the thing
   - A "what this actually is" section in plain prose
   - An **anatomy** or **dissection** section if the topic has structure (a string, a syntax, a flow, a config). Annotate parts visually.
   - **Worked examples** with concrete inputs and outputs. Visual where possible (grids, timelines, diagrams).
   - **Comparison** to adjacent concepts the reader probably knows.
   - **Recipes / cookbook** of copy-pasteable patterns.
   - **Pitfalls / foot-guns** the reader will hit.
   - A colophon or footer with sources/spec references.
   - Skip sections that don't apply. Don't force all of them.

4. **Implement dark mode correctly from the start.** Do not retrofit. The rules:

   - Define every color as a CSS variable in `:root`.
   - Override variables in `@media (prefers-color-scheme: dark) { :root { ... } }`.
   - For any "inverted" section (dark slab with light text used as a callout — code panels, headers, marquees), introduce `--invert-bg` and `--invert-fg` vars so those sections stay dark-with-light-text in **both** modes. Otherwise they flash bright white in dark mode and the page looks broken.
   - Variabilize grain/noise color AND blend mode. Light mode uses `mix-blend-mode: multiply`; dark mode uses `screen`. Same pattern for vignettes (opacity differs).
   - Dashed/soft borders need a `--rule-soft` (rgba) variant, not a hardcoded `rgba(26,20,16,...)`. Hardcoded ink colors vanish into the dark background.
   - Accent colors usually need to be **lifted and slightly desaturated** in dark mode. A saturated accent that reads confident on a light background reads alarming on near-black; shift it lighter and softer.
   - **Never use inline `style="color: ..."` attributes.** They can't be overridden by dark-mode CSS without `!important`. Use classes.

5. **Aesthetic guardrails** (in addition to Claude's direction):
   - **There is no house style.** Decide a fresh design system per explainer — palette, type pairing, layout language — chosen for the topic, not inherited from previous explainers. Warm-paper editorial with a serif display is one direction among many, not the default; if the last explainer looked like that, go somewhere else.
   - Skip Inter, Roboto, Arial, generic system stacks. Pair a distinctive display face with a refined body face.
   - Avoid the purple-gradient-on-white default. If the design direction calls for accent colors, commit.
   - Asymmetry, generous negative space OR controlled density. Avoid the centered-card-on-white look.
   - One well-orchestrated page-load reveal beats scattered micro-interactions.

6. **Save and open.**
   - Path: `/tmp/<topic-slug>-explainer.html`
   - Open with `open <path>` (macOS).

7. **Narrate briefly.** One short paragraph: what the aesthetic direction was, what sections you included, where it's saved. Don't recap the topic content — the user can read it in the file.

## Dark-mode template (copy this scaffolding)

```css
:root {
  /* base */
  --paper: #...;        /* page background */
  --paper-2: #...;      /* raised surface */
  --ink: #...;          /* primary text */
  --ink-soft: #...;
  --muted: #...;
  --rule: #...;         /* solid borders */
  --rule-soft: rgba(..., 0.3);  /* dashed/soft borders */
  --accent: #...;
  --highlight: #...;

  /* inverted callouts — dark-on-cream slabs that stay dark in BOTH modes */
  --invert-bg: var(--ink);
  --invert-fg: var(--paper);

  /* grain */
  --grain-color: rgba(..., 0.05);
  --grain-blend: multiply;
  --grain-opacity: 0.7;

  /* vignette */
  --vignette: rgba(..., 0.10);
}

@media (prefers-color-scheme: dark) {
  :root {
    --paper: #...;        /* near-black tinted to match the palette, not pure black */
    --paper-2: #...;      /* slightly raised dark */
    --ink: #...;          /* light ink tinted to match the palette, not pure white */
    --ink-soft: #...;
    --muted: #...;
    --rule: #...;
    --rule-soft: rgba(..., 0.18);
    --accent: #...;       /* lifted/desaturated from light mode */
    --highlight: #...;

    --invert-bg: var(--paper-2);   /* still a dark slab */
    --invert-fg: var(--ink);       /* still cream text */

    --grain-color: rgba(..., 0.06);
    --grain-blend: screen;
    --grain-opacity: 0.5;

    --vignette: rgba(0, 0, 0, 0.45);
  }
}
```

## What this skill is not

- Not a tutorial generator. It produces one polished page, not a multi-page site or course.
- Not for application UI.
- Not for documents the user wants to edit (use Markdown instead).
- Not for slide decks (use a different skill or HTML deck framework).

## Anti-patterns to refuse

- "Just give me a quick page" -> still get Claude's visual direction, still support dark mode. The whole point of this skill is that the user doesn't have to keep specifying those.
- Inline `style="color: ..."` for colors. Always classes.
- A `<button>` to toggle theme. The OS preference is the source of truth.
- Two separate files for light and dark. One file, one media query.
