# Production Studio — Designer Brain UX Acceptance Report (Phase 1 & Phase 2)

**Review Date:** 2026-11-20  
**Reference Standard:** `zakshub/designer` (Visual Brief, Anti-Monotony 6-Axis Audit, WCAG 2.2 `2.5.3` Label in Name, `3.3.2` Labels/Instructions, Independently Calibrated Dark & Light Modes)  
**Verification Method:** Live headless Chromium E2E across all Phase 1 & Phase 2 workflows + programmatic DOM WCAG 2.2 audit + visual screenshot review across `1440×900` and `768×1024` in both **Calibrated Studio Dark** and **Archival Proofing Light** themes.

---

## 1. Workflow Acceptance Matrix

| Workflow | Status | Verified Behavior & Evidence |
|---|---|---|
| **Image workflow (brief → finished asset)** | **PASS** | Plain-language brief -> contextual 170-protocol activation (`28/170`, zero questionnaire spam) -> multi-output variations (`1–4` selector) -> explicit pre-billing approval modal (`unit × count = total`) -> real `1200×800px` PNG preview + **Variation Contact Sheet** thumbnails -> Pillow pixel forensics Advisory QC -> ZIP + sanitized provenance sidecar export. |
| **Video workflow (brief → finished asset + extension)** | **PASS** | Dedicated **Timed Shot Storyboard** (`SHOT-01`, `SHOT-02` with timestamps, framing, camera move, lens, continuity invariants, feasibility badge) -> inline video shot plan editor (`Edit Plan Controls`) with immediate capability re-validation -> real playable H.264 MP4 preview -> **Multi-Turn Video Extension** (`+3–10s`, up to `30s` cumulative) generating linked `10.0s` MP4 with `EXTENSION +4s` badge. |
| **Production plan readability** | **PASS** | Concise plain-language summary + explainable key decisions (`USER SPECIFIED` vs `INFERRED` badges + protocol codes) shown first; technical camera/optics/lighting deck and 170-protocol activation trace kept progressively disclosed; provider feasibility warnings surfaced visibly at top of plan. |
| **Approval & spending clarity** | **PASS** | Persistent topbar `Spend $0.00 / $0.00` pill; **Explicit Generation Approval Gate** for single/variation requests AND **Combined Batch Generation Approval Gate** itemized table for multi-plan batches; explicit Spend Guard (`ALLOWED`/`BLOCKED`) and Server Credential (`READY`/`MISSING`) badges; optional Multimodal Vision QC also requires explicit quote + confirmation and disables execution at `$0.00` cap. |
| **Revision experience** | **PASS** | Controlled Targeted Revision panel isolates requested deltas (including optional video target shot selector), surfaces explicit `changed_fields` vs `preserved_fields` delta banner, re-validates capability feasibility, and preserves full parent-child version lineage. |
| **Asset library & side-by-side comparison** | **PASS** | Fixed prop synchronization bug (`useEffect` on `initialComparePair` in `LibraryCompareView.tsx`) so `Compare Latest Two Versions` and `Compare First & Last Variation` reliably open directly into Side-by-Side Compare with visual previews, advisory QC scores, and structural `Production Decision Differences` table. Bulk ZIP export and keyword/media/favorite filters verified. |
| **Dark & Light themes** | **PASS** | Independently calibrated **Calibrated Studio Dark** (`#0F1114` canvas, `#171A1F` surface, warm tungsten `#D98C2B` primary accent) and **Archival Proofing Light** (`#F6F7F9` neutral matte paper canvas, `#A86414` high-contrast accent, crisp neutral borders) verified visually with zero muddy contrast or generic AI purple gradients. |
| **Responsive behavior (`1440×900` & `768×1024`)** | **PASS** | 3-zone desktop workbench collapses cleanly at `<= 1160px` and `<= 780px`; **0px horizontal overflow** across Auth, Projects, Workspace, Compare, and Settings at both `1440×900` and `768×1024`. Tightened modal `.kv-grid` spacing so 9-field video extension approval modals fit cleanly above the fold. |
| **Accessibility & usability (WCAG 2.2 AA)** | **PASS** | Automated DOM audit across 7 screens/viewports confirmed: **0 unlabeled visible inputs/selects/textareas** (`3.3.2`), **0 unlabeled visible buttons**, **0 Label-in-Name violations** (`2.5.3`), semantic `role="dialog" aria-modal="true"` with `Escape` close on modals, visible `:focus-visible` outlines, and **0 browser console/page errors**. |

---

## 2. Targeted UX Fixes Applied During Acceptance Review (No Novelty Redesign)

1. **`LibraryCompareView.tsx` Compare Pair Sync:** Added `useEffect([initialComparePair])` so triggering comparison from Workspace reliably switches tabs and updates both asset selectors.
2. **`PlanView.tsx` Inline Video Plan Editor & Feasibility Alerts:** Added inline edit controls for timed video plans (`total_duration_s`, `aspect_ratio`, `resolution`, per-shot `subject_action` & `camera_movement`) wired to server-side capability re-validation, plus visible top-level feasibility warning banner.
3. **`ApprovalModal.tsx` Density Polish:** Tightened `.modal-dialog .kv-grid` spacing so multi-field video extension and combined batch quotes remain comfortable above the fold on `1440×900` viewports.
4. **`QualityPanel.tsx` Honest Optional Vision QC Gate:** Surfaced opt-in multimodal Vision QC inline with model name (`gemini-3.5-flash-lite`), exact frame count, source comparison indicator, estimated USD cost, Spend Guard / Credential gates, and explicit advisory-only limitations.
