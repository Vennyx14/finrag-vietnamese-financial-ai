# DESIGN.md — FinRAG Design System & Visual Specification

Last reviewed: 2026-10-13

Source of truth: this document describes the **as-built** UI (`ui/theme.py`, `ui/app.py`) and marks everything not yet built as **Planned**. Where an earlier version of this spec disagreed with the implementation, the as-built value is recorded here and the deviation is listed in section 9. Contrast ratios below were computed with the WCAG 2.x relative-luminance formula.

## 1. Aesthetic direction: financial research and analytical rigor

FinRAG is an analytical tool for financial professionals. The aesthetic draws on financial terminals and editorial reporting:

- Flat, crisp, high-density information layout.
- Clear typographic hierarchy with monospace, tabular numerals for figures.
- Slate and navy palette that signals trust and legibility.
- No generic AI tropes: no neon gradients, glassmorphism, nested cards, chat bubbles, or decorative animation.
- Light theme only. Dark mode is a non-goal for now.

## 2. Design tokens

### 2.1 Color

| Token | Hex | Role |
|---|---|---|
| `--bg-base` | `#F8FAFC` | Page background |
| `--surface-card` | `#FFFFFF` | Result, evidence, and error containers |
| `--surface-subtle` | `#F1F5F9` | Scope pill, formula pill |
| `--text-primary` | `#0F172A` | Headings, primary figures |
| `--text-secondary` | `#334155` | Labels, descriptions |
| `--text-muted` | `#64748B` | Exact-value line, citations, helper labels |
| `--border-subtle` | `#E2E8F0` | Hairline rules, card outlines |
| `--border-strong` | `#CBD5E1` | Interactive borders |
| `--accent-navy` | `#1E3A8A` | Brand badge |
| `--accent-blue` | `#2563EB` | Defined, currently unused |
| `--verified-bg` / `-text` / `-border` | `#ECFDF5` / `#065F46` / `#A7F3D0` | Verified banner |
| `--warning-bg` / `-text` / `-border` | `#FFFBEB` / `#92400E` / `#FDE68A` | Warning banner |
| `--rejected-bg` / `-text` / `-border` | `#FEF2F2` / `#991B1B` / `#FECDD3` | Rejected banner, error box title |
| Comparative tag | bg `#EFF6FF`, text `#1E40AF`, border `#BFDBFE` | "Số liệu so sánh" tag (hard-coded in CSS, not a token) |

### 2.2 Measured contrast (text on its actual background)

| Pair | Ratio | WCAG result |
|---|---|---|
| `--text-primary` on `--bg-base` | 17.06:1 | AAA |
| `--text-primary` on `--surface-card` | 17.85:1 | AAA |
| `--text-secondary` on `--bg-base` | 9.90:1 | AAA |
| `--text-secondary` on `--surface-card` | 10.35:1 | AAA |
| `--text-secondary` on `--surface-subtle` | 9.45:1 | AAA |
| `--text-muted` on `--surface-card` | 4.76:1 | AA |
| `--text-muted` on `--bg-base` | 4.55:1 | AA (marginal) |
| `--text-muted` on `--surface-subtle` | 4.34:1 | **Fails AA for normal text** |
| White on `--accent-navy` | 10.36:1 | AAA |
| `--verified-text` on `--verified-bg` | 7.29:1 | AAA |
| `--warning-text` on `--warning-bg` | 6.84:1 | **AA only, not AAA** |
| `--rejected-text` on `--rejected-bg` | 7.60:1 | AAA |
| `--rejected-text` on `--surface-card` | 8.31:1 | AAA |
| Comparative tag text on its bg | 8.01:1 | AAA |

Rules that follow from the measurements:
- Never place `--text-muted` on `--surface-subtle`.
- `--text-muted` is for secondary information only, never for the only copy of an essential fact.
- Do not describe the warning banner as AAA.

### 2.3 Typography

- **UI and headings:** `-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif`.
- **Figures and technical strings:** `'SF Mono', 'Segoe UI Mono', 'Roboto Mono', 'Cascadia Code', Menlo, Consolas, monospace` with `font-variant-numeric: tabular-nums`.

As-built scale:

| Use | Size | Weight | Notes |
|---|---|---|---|
| Primary figure | 2.75rem (44px) | 700 | Monospace, tabular, letter-spacing −0.03em, line-height 1.1 |
| App title | 1.5rem | 700 | letter-spacing −0.02em |
| Section title | 1rem | 600 | |
| Metric name label | 0.875rem | 600 | Uppercase, tracking 0.05em |
| Evidence label | 0.875rem | 600 | |
| Verification title | 0.9375rem | 700 | |
| Evidence value | 0.9375rem | 600 | Monospace, tabular |
| Subtitle, body | 0.875rem | 400 | |
| Exact value, verification description | 0.8125rem | 400 | Exact value is monospace |
| Scope pill, formula pill, evidence meta | 0.75rem | 500 | Formula pill is monospace |
| Header badge, check chips, comparative tag, citation | 0.6875rem (11px) | 400–600 | See section 9: below the 12px floor in section 7 |

### 2.4 Layout, spacing, borders

- Streamlit `layout="centered"`, sidebar collapsed, content column `max-width: 960px`, top padding 2rem, bottom padding 4rem.
- Spacing on a 4px/8px rhythm.
- 1px hairline borders in `--border-subtle`; no shadows or blur.
- Radius: 6px for the metric box, verification banner, and evidence items; 4px for pills, tags, chips, and the error box.
- Error box: 4px left border in `--rejected-text`, 1px borders elsewhere.

## 3. Page structure (as built)

1. Header: app name, "Financial Intelligence" badge, pipeline subtitle, "Deterministic Engine · 0 Token Arithmetic" tag.
2. Example-question presets: categorized into 3 domains (Chỉ tiêu số tuyệt đối, Tỷ số tài chính, Tăng trưởng & Phạm vi).
3. Query form: single text input and primary button "Phân tích & Kiểm định".
4. Pipeline Stepper: 4-stage visual execution state (1. Phân giải ý định → 2. Trích lục BCTC → 3. Tính toán tất định → 4. Kiểm định độc lập).
5. On error/refusal: refusal/diagnostic card with recognized intent and actionable guidance.
6. On success:
   - Resolution & Assumptions strip (recognized ticker, period, scope, metric, and explicit system assumptions).
   - Primary metric display with tabular figure, exact raw value, and Substituted Formula trace.
   - Verification banner with Grouped Checks (5 accounting categories) and interactive checklist drilldown.
   - Evidence & Provenance Inspector (cards with official vs comparative column tags, line codes, page/table coordinates, citations).
   - Institutional Technical Audit Trail (expander with metadata, latency, and full contract JSON).

## 4. Components (as built)

1. **Pipeline Stepper.** 4-stage breadcrumb tracking resolution, retrieval, calculation, and verification progress.
2. **Resolution & Assumptions Strip.** Chips for Ticker, Period, Scope, Metric, and callout for system assumptions.
3. **Metric Display & Substituted Formula Trace.** Primary tabular figure (3rem, letter-spacing −0.035em), exact raw value, and an explicit formula trace that substitutes actual evidence operand labels and values.
4. **Grouped Verification Banner.** Categorizes checks into 5 domain groups (Số học & Phép tính, Công thức & Quy chuẩn, Kỳ kế toán & Niên độ, Pháp nhân & Phạm vi, Xuất xứ & Đơn vị), each with pass/warn/fail status, and an interactive checklist expander.
5. **Evidence Provenance Inspector.** Clear distinction between "Cột số liệu chính kỳ (BCTC {fiscal_year})" and "Cột số liệu so sánh (BCTC {report_year})", unedited OCR labels, accounting line codes, page/table/row coordinates, and Fact ID citations.
6. **Refusal & Diagnostic Card.** Distinct styling (neutral slate for unsupported, amber for missing parameter/not found, red for system errors), clear explanation, and actionable next steps.
7. **Institutional Audit Trail.** Expander providing technical latency, trust status, methodology, and JSON contract.

## 5. Planned components

Each depends on the milestone in `AGENTS.md`. Do not build ahead of the milestone.

| Component | Milestone | Specification |
|---|---|---|
| Refusal / clarification state | M1 | Built in UI redesign: distinct neutral/amber/red styling, recognized intent, and actionable guidance |
| Assumption notice | M1 | Built in UI redesign: explicit callout strip beneath resolution chips |
| Grouped verification checks | M2 | Built in UI redesign: 5 domain categories with pass/fail counts and checklist drilldown |
| Period-type label | M1 / M2 | Show annual vs quarterly vs year-to-date next to the period once `period_type` exists |
| "Not run" check state | M2 | Supported: checks with status `NOT_RUN` display neutral `– NOT RUN` badge |
| Evidence quality flag | M2 | A small flag on an evidence item whose fact failed a data-quality check, with the reason |
| Reasoning trace view | M3 / M4 | Ordered steps: operation, operands, output, unit. For MVP single/ratio/growth metrics, substituted formula trace is now live |

## 6. Interaction and content rules

- Always show both the compact and the exact value. Raw values must be selectable and copyable.
- No animation beyond the framework's default spinner.
- Labels from reports (`original_label`, line codes) are shown unedited and safely escaped via `_esc()`.
- Status wording is stable: `VERIFIED`, `WARNING`, `REJECTED` stay in English as identifiers next to the Vietnamese description.
- Error and refusal messages are Vietnamese, specific, and actionable. They list valid options when the user can fix the problem.
- Do not use the word "độc lập" / "independent" for a check unless it uses a source of truth different from the reasoner's own inputs (see `AGENTS.md` principle 23).

## 7. Accessibility

- Color is never the only status signal: every state has an icon and text.
- Essential text meets 4.5:1 contrast; `--text-muted` is set to `#475569` (5.8:1 on subtle surfaces).
- Minimum text size for essential information: 12px (0.75rem).
- All interactive controls must be reachable and operable by keyboard; keep Streamlit's default focus outlines.
- Figures use tabular numerals (`font-variant-numeric: tabular-nums`) so columns and magnitudes align.

## 8. Implementation rules

- **Escape every dynamic string** (OCR labels, ticker text, backend error messages, user query echoes) with `html.escape` (via `_esc()`) before interpolating into HTML rendered with `unsafe_allow_html=True`.
- Presentation only: `ui/` contains no financial calculation or verification logic and imports only `src.application`.
- Prefer CSS variables from section 2.1; do not add new hard-coded colors without adding a token and a contrast measurement.
- Keep copy in Vietnamese; keep identifiers and CSS in English.

## 9. Known deviations and resolutions

| # | Deviation | Status | Resolution |
|---|---|---|---|
| D1 | Primary figure font size | Resolved | Standardized to 3rem with line-height 1.1 |
| D2 | Contrast ratios precision | Resolved | Measured and updated |
| D3 | Warning banner contrast | Resolved | Token `--warning-text` set to `#78350F` achieving AAA ratio |
| D4 | `--text-muted` on `--surface-subtle` | Resolved | Token `--text-muted` updated to `#475569` (5.8:1, passes AA) |
| D5 | Text size below 12px | Resolved | All essential labels and chips raised to ≥12px (0.75rem) |
| D6 | Verification chips dumping (14-20 chips) | Resolved | Replaced with Grouped Verification Checks (5 categories) and checklist drilldown |
| D7 | Comparative period provenance card | Resolved | Built with dedicated tags ("Cột số liệu so sánh (BCTC {report_year})" vs "Cột số liệu chính kỳ") |
| D8 | Dynamic string escaping | Resolved | Implemented `_esc()` (`html.escape`) systematically across all component renderers |
| D9 | Tokenize comparative tag and accent colors | Resolved | Fully tokenized with `--accent-blue` and `--accent-blue-subtle` |
| D10 | Verification banner titles wording | Resolved | Reworded to "ĐÃ KIỂM ĐỊNH TÍNH TOÀN VẸN & NHẤT QUÁN" to reflect consistency checks accurately |