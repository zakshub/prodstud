# Vision QC Controlled Evaluation Audit

**Audit Date:** 2026-11-21
**Branch / Baseline:** `feat/mvp-foundation-and-roadmap` (PR #1 Pre-Merge Baseline)
**Harness:** [`scripts/audit_vision_qc.py`](../scripts/audit_vision_qc.py)
**External API Spend Incurred:** `$0.00` (`live_vision_api_invoked = false`)

> **Advisory Disclaimer:** Production Studio NEVER claims objective quality certification. Both deterministic media forensics (`backend/src/prodstud/engine/quality_reviewer.py`) and optional multimodal Vision QC (`backend/src/prodstud/engine/vision_qc.py` via `backend/src/prodstud/providers/google_vision_qc.py`) produce strictly advisory signals to support — never replace — human visual inspection and full-clip playback.

---

## 1. Evaluation Methodology & Scope

To audit both deterministic media forensics and the multimodal Vision QC orchestration pipeline without incurring paid provider spend, [`scripts/audit_vision_qc.py`](../scripts/audit_vision_qc.py) constructs a reproducible **13-case synthetic evaluation dataset** (10 PNG images + 3 H.264 MP4 clips built with Pillow and `ffmpeg`) designed explicitly to stress-test:

1. **Baseline compliance (True Negatives)** on both images and video.
2. **Known technical defects (True Positives)** including wrong aspect ratio, blown highlights, soft/plastic low edge energy, midpoint video flash, and multimodal source-preservation failure.
3. **Adversarial False Positive triggers** where valid artistic or commercial assets violate naive global pixel heuristics or suffer an LLM hallucinated alarm.
4. **Adversarial False Negative blind spots** where real semantic defects or inter-frame video corruption evade automated detection entirely.

### Scope Boundary (What Is NOT Verified Live Yet)

- All deterministic cases (`IMG-01`–`IMG-07`, `VID-00`, `VID-01`) execute the **real production Pillow and `ffprobe`/`ffmpeg` pipelines** unmodified.
- All multimodal cases (`IMG-08`–`IMG-10`, `VID-02`) execute the **real `VisionQCService` framing, ffmpeg keyframe extraction, JSON parsing, dimension-weight normalization, critical-gate verdict logic, and coverage disclosures**, using a deterministic provider-neutral `ControlledVisionTransport` mock rather than live Google Gemini Vision inference.
- **Live Gemini Vision real-world precision/recall** on natural photographic skin pores, hands, subtle micro-text, and real Veo video frames remains **unverified pending owner credentials (`P2-7`)**.

---

## 2. Controlled Dataset Empirical Results (13 Cases)

Executed via `.venv/bin/python scripts/audit_vision_qc.py`:
- **Summary Confusion Breakdown (Stress Dataset):** `TP = 5`, `TN = 2`, `FP = 3`, `FN = 3` (intentionally balanced to expose failure modes rather than inflate headline accuracy).

| Case ID | Media | Mode | Ground Truth Defect | Scenario | Observed Verdict | Score | Confidence | Result | Triggered Dimensions |
| :--- | :--- | :--- | :---: | :--- | :--- | :---: | :---: | :---: | :--- |
| `IMG-01` | Image | Deterministic | No | Clean balanced `3:2` studio frame (`900×600`) | `pass_advisory` | `4.54` | `0.64` | **TN** | — |
| `IMG-02` | Image | Deterministic | Yes | Aspect ratio mismatch (`1:1` delivered vs `3:2` planned) | `rework_recommended` | `3.54` | `0.64` | **TP** | `technical_spec` |
| `IMG-03` | Image | Deterministic | Yes | Severely blown highlights (`>35%` pixels `>=251`) | `review_recommended` | `3.68` | `0.64` | **TP** | `lighting_exposure`, `detail_texture` |
| `IMG-04` | Image | Deterministic | Yes | Over-smoothed low-detail plastic/blurry frame (`edge_energy < 4.5`) | `review_recommended` | `3.79` | `0.64` | **TP** | `lighting_exposure`, `detail_texture` |
| `IMG-05` | Image | Deterministic | **No** | Valid low-key chiaroscuro studio frame (`>30%` intentional deep black void) | `review_recommended` | `3.68` | `0.64` | **FP** | `lighting_exposure`, `detail_texture` |
| `IMG-06` | Image | Deterministic | **No** | Valid e-commerce product on pure-white seamless backdrop (`>40%` white cyclorama) | `review_recommended` | `3.68` | `0.64` | **FP** | `lighting_exposure`, `detail_texture` |
| `IMG-07` | Image | Deterministic | **Yes** | Garbled brand label (`X9#Q!Z` instead of hard-locked `SOLA`) on crisp `3:2` image | `pass_advisory` | `4.54` | `0.64` | **FN** | — |
| `IMG-08` | Image | Multimodal (Mock) | Yes | Vision model compares garbled label (`X9#Q!Z`) vs source ref (`SOLA`), scores `1.6` | `rework_recommended` | `3.97` | `0.80` | **TP** | `vision_source_preservation` |
| `IMG-09` | Image | Multimodal (Mock) | **No** | Hallucinated LLM preservation alarm (`score = 1.9`) on an intact asset | `rework_recommended` | `4.09` | `0.80` | **FP** | `vision_source_preservation` |
| `IMG-10` | Image | Multimodal (Mock) | **Yes** | Lenient vision LLM overlooks corrupted label (`scores 4.3–4.5`) | `pass_advisory` | `4.48` | `0.80` | **FN** | — |
| `VID-00` | Video | Deterministic | No | Clean steady `6.0s` `16:9` MP4 matching plan duration and lighting | `pass_advisory` | `4.65` | `0.60` | **TN** | — |
| `VID-01` | Video | Deterministic | Yes | `6.0s` MP4 with bright white flash spanning midpoint `t = 3.0s` | `review_recommended` | `4.15` | `0.60` | **TP** | `lighting_continuity` |
| `VID-02` | Video | Multimodal (Mock) | **Yes** | `6.0s` MP4 with severe full-frame RED corruption glitch strictly at `1.2s–1.8s` | `pass_advisory` | `4.59` | `0.71` | **FN** | — |

---

## 3. Documented False Positives (Over-Flagging Risks)

1. **Intentional Low-Key / Chiaroscuro Photography (`IMG-05`)**:
   - **Mechanism:** `quality_reviewer.py` flags `shadow_clip_pct > 18.0` on `lighting_exposure` AND low whole-frame mean `edge_energy < 4.5` on `detail_texture`. A legitimate dark-studio portrait or luxury watch shot surrounded by >20% matte black void trips both thresholds simultaneously and returns `review_recommended` (`3.68`).
   - **Operational Risk:** Unnecessary revision churn if users treat `review_recommended` as an error rather than checking whether the dark background was intentional.
2. **E-Commerce High-Key Pure-White Seamless Backdrops (`IMG-06`)**:
   - **Mechanism:** `highlight_clip_pct > 12.0` + uniform seamless white cyclorama lowers global edge energy, firing `review_recommended` (`3.68`) on completely compliant Amazon/editorial packshots.
   - **Future Mitigation (Phase 3+):** Condition histogram thresholds on planned lighting key / backdrop class or compute subject-mask ROI statistics instead of global full-frame histograms.
3. **Strong Motivated Color Casts (Warm Tungsten / Neon Night Scenes)**:
   - **Mechanism:** `color_cast_spread > 55.0` lowers `color_balance` to `3.3` with an `info` finding even when warm tungsten or sodium-vapor night lighting was explicitly specified in the brief.
4. **Multimodal Vision LLM Hallucinated Critical Defect (`IMG-09`)**:
   - **Mechanism:** Because `VisionQCService` applies a fail-closed critical gate (`score <= 2.0` on `vision_brief_adherence` or `vision_source_preservation` forces `rework_recommended`), a single hallucinated `1.9` score from the vision model overrides an otherwise `4.09` weighted score and recommends rework.
   - **Operational Guardrail:** Rework is NEVER auto-submitted; the operator inspects the finding evidence side-by-side against the asset before deciding whether to spend credits on a revision.

---

## 4. Documented False Negatives (Blind Spots)

1. **Deterministic Semantic Blindness (`IMG-07`)**:
   - **Empirical Result:** A technically sharp, balanced `900×600` frame whose brand label is completely garbled (`X9#Q!Z` instead of `SOLA`) receives **`pass_advisory` (`4.54`) with zero findings** in deterministic mode.
   - **Coverage Scope:** Deterministic pixel statistics CANNOT inspect brand typography, facial/product identity preservation, anatomical plausibility (fingers/hands), impossible reflections, or subject drift.
2. **Video Inter-Frame Structural Blind Spot (`VID-02`)**:
   - **Empirical Result:** A `6.0s` MP4 containing a severe full-frame bright-red corrupted flash strictly from `t = 1.2s` to `t = 1.8s` receives **`pass_advisory` (`4.59`, `confidence = 0.71`) with zero findings** under **BOTH** deterministic forensics AND 3-frame multimodal Vision QC!
   - **Root Cause:** Both pipelines sample strictly 3 keyframes (`[0.2s, duration * 0.5, duration - 0.3s]` -> `0.20s`, `3.00s`, `5.70s`). Not a single pixel between `0.20s` and `3.00s` (or `3.00s` and `5.70s`) is inspected.
   - **Disclosure Verified:** `inspection_coverage` explicitly prints `"ffprobe_stream_metadata_plus_3_sampled_frames_multimodal_vision (...) — NOT full frame-by-frame playback"`.
3. **Lenient Multimodal Vision Model (`IMG-10`)**:
   - **Empirical Result:** If the multimodal vision model overlooks a 1-character typo, subtle 6-finger artifact, or slight garment seam drift and scores `4.3–4.5`, the pipeline emits `pass_advisory` with `confidence = 0.80`.
4. **Audio / Sync Blind Spot**:
   - Video QC inspects container metadata and silent visual keyframes only; audio artifacts, clipping, or lip-sync drift are completely outside automated inspection scope.

---

## 5. Confidence Limitations

The `confidence` field returned in `QualityReviewRecord` is a **static structural coverage ceiling**, NOT an empirically calibrated probability of correctness:

| Review Mode | Reported `confidence` | Meaning & Limitation |
| :--- | :---: | :--- |
| Deterministic Video (`ffprobe` + 3 frames) | `0.60` | Metadata + 3 luminance points only; zero semantic or inter-frame motion coverage. |
| Deterministic Image (Pillow stats) | `0.64` | Full-frame pixel geometry/histogram/edge proxies only; zero semantic coverage. |
| Multimodal Video (3 sampled frames) | `0.71` | Semantic review of 3 still keyframes ONLY; zero inter-frame flicker/morphing coverage. |
| Multimodal Image (single image) | `0.76` | Single-image LLM inspection without source reference comparison. |
| Multimodal Image (with source ref) | `0.80` | LLM side-by-side comparison; still subject to vision model hallucinations & micro-detail misses. |

Confidence is intentionally capped `<= 0.80` to reinforce visually and programmatically that automated QC never reaches certification certainty (`1.0`).

---

## 6. Mandatory Human Review Requirements

Before any generated asset is marked **Accepted** or shipped externally, a human operator MUST perform the following checks:

1. **Images (Always Required):**
   - Visually inspect 100% zoom for Studio Brain AI tells (`T01` pore-less plastic skin, `T03` hands/fingers, `T06` floating shadows, `T08` conflicting light directions, `T09` warped architecture, `T10` garbled micro-text/logos).
   - Compare side-by-side against all attached source references whenever `hard_locks` are declared.
   - Verify whether any deterministic `lighting_exposure` or `detail_texture` warning is a false positive caused by intentional high-key white seamless or low-key chiaroscuro styling before spending credits on revision.
2. **Videos (Always Required):**
   - Watch **100% full-duration playback** from `0.0s` to end (never rely on 3-frame sampled QC scores) to detect inter-frame flashes (`VID-02`), morphing, camera jitter, subject drift, or extension seam breaks.
   - Verify continuity across extended video chains (`extended_from_asset_id`) before final delivery.
3. **Human Feedback Recording:**
   - Record final acceptance or rejection via `POST /api/reviews/{review_id}/feedback` (`accepted` / `needs_revision` / `rejected` + note), which persists human disposition alongside the immutable advisory review record and audit trail.
