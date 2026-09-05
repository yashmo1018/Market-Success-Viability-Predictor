# UI/UX Design Brief
## Hybrid AI Product Success Predictor

### 1. Design Goals
1. **Credibility over flash.** The product's core claim (predicting reception of unlaunched products) invites skepticism. Every design choice should make the system feel measured, evidence-backed, and honest — never like a magic 8-ball.
2. **Explanation is the product.** The viability % is the headline, but the SHAP risks/strengths and per-aspect reasoning are what founders act on. Layout must give explanation equal visual weight to the score.
3. **The iteration loop is the hero moment.** Change a spec → watch viability and aspects shift with delta indicators. Optimize the design for fast, satisfying re-runs.
4. **Demo-proof.** An examiner will see this projected. Large type, high contrast, minimal chrome, nothing that depends on hover.

### 2. Audience & Context
- Primary: non-technical founders/PMs; secondary: academic evaluators
- Context: desktop browser (Streamlit); demo on a projector; occasional mobile viewing (graceful, not optimized)
- Reading level: plain business English; no ML jargon on result screens ("what's dragging this down" not "negative SHAP contribution")

### 3. Information Architecture & Navigation
- Sidebar nav (Streamlit native): Simulator ▸ Explorer ▸ Analyzer ▸ About the Model
- Simulator is default landing; each page has one primary action visible without scrolling
- Cross-links: every Explorer/Analyzer page ends with a CTA into the Simulator (pre-filled)

### 4. Key Screens

**4.1 Simulator — Input**
- Two-column: form left (60%), live category context card right (40%: median price, top-3 priorities, #1 pain point, n_products behind the data)
- Category picker: 10 tiles with icons, grouped "Physical products" / "Apps"; selected tile highlighted
- Form fields adapt to category; price prominent; free-text description last with helper text "optional — improves the analysis"
- Primary button: **Analyze viability** (disabled until price valid)

**4.2 Simulator — Results (the screen that matters)**
- Top band: viability gauge (0-100 semicircle) + one-line verdict ("Above the success threshold for this category" / "Below typical performers")
  - Secondary metric beside it: "Aspect-driven estimate: 63%" with ⓘ popover explaining full vs aspects-only
- Middle band, two columns:
  - Left: horizontal aspect bars — bridged score (solid) overlaid on category average (ghost); click/expand reveals the bridging reasoning sentence
  - Right: Risk & Strength cards — max 3 each; card = aspect name, impact chip (−6.1 / +4.3), one plain-language sentence
- Bottom band: persistent honesty banner (muted amber): "Estimate of likely consumer reception vs. category norms, built from public review data. Not a sales forecast."
- Sticky footer actions: **Adjust specs** · Explore category · Start over
- Re-run state: delta chips animate next to gauge and any aspect that moved (▲ +2.1 in green, ▼ in red)

**4.3 Explorer**
- Header: category name + n_products + "data through Sep 2023 (Amazon) / live snapshot (Play)"
- Aspect bars with mention-rate encoded as bar opacity + small "% discussed" label — teaches users that confidence varies
- Pain point / strength cards with up to 3 short verbatim quotes styled as quotes (italic, quotation marks) — real consumer voice builds trust
- Success-score histogram with a labeled p75 line: "top-quartile threshold"

**4.4 About the Model**
- Tables over prose: metrics, benchmark, data counts
- Limitations section styled identically to the rest (not hidden fine print)

### 5. Visual Language
- Base: Streamlit default theme, light mode, with a small custom palette:
  - Primary/action: deep teal `#0E7C7B`
  - Risk: muted red `#C0392B`; Strength: green `#1E8449`; category-average ghost: 30% gray
  - Honesty banner: amber background `#FFF6E5`, dark text
- Typography: Streamlit defaults; result headline (viability %) very large (≈64px); everything else ≥14px
- Charts: matplotlib/plotly with the same palette; no 3D, no gradients, no dual axes
- Icons: emoji or lucide via markdown only where they aid scanning (⚠ risks, ✓ strengths); never decorative clutter
- Density: generous whitespace; max ~3 information bands per screen; no tables on the results screen

### 6. Content & Tone Guidelines
- Verdict lines: direct, comparative, non-absolute — "performs above most budget headphones on value" not "will succeed"
- Reasoning sentences: always reference a spec AND a category fact ("Plastic build in a category where build quality is the #1 complaint")
- Numbers: viability to 1 decimal; aspect scores to 1 decimal; impacts signed
- Never: "AI predicts", "guaranteed", "revenue", "sales forecast"
- Disclaimers are part of the voice, not legal small print

### 7. Interaction & Feedback
- Loading: staged status messages (3 steps) so the 5-15s bridging wait feels purposeful; skeleton bars where results will appear
- All state changes visible without hover (projector rule)
- Form retains values across runs; "Start over" is the only destructive action and asks nothing (specs are cheap)
- Errors: human sentence + retry button; log details to Supabase, never to the UI

### 8. Accessibility Baseline
- Contrast ≥ 4.5:1 for text; color never the sole encoding (risk/strength cards carry −/+ signs and labels)
- Charts include text summaries beneath ("Biggest risk: durability, −6.1")
- Keyboard: form fully tabbable (Streamlit native); no interaction requires drag

### 9. Out of Scope (v1)
Dark mode · custom fonts · mobile-first layouts · animations beyond delta chips · user accounts · saved sessions (predictions logged server-side only)

### 10. Definition of Visual Done
- The results screen screenshot alone communicates: the score, why, and the honesty caveat — with no one explaining it
- A first-time examiner completes spec→result→adjust→re-run without guidance in under 2 minutes
