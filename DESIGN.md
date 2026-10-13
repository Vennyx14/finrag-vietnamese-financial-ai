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

1. Header: app name, "Research Assistant" badge, one-line Vietnamese subtitle.
2. Example-question chips (six, three per row).
3. Query form: single text input and primary button "Phân tích & Kiểm định".
4. On error: diagnostic error box, then stop.
5. On success: metric display → verification banner → evidence list → technical audit trail (expander with original query, system status, methodology, full JSON).

## 4. Components (as built)

1. **Metric display.** Metric name, ticker, period, and scope pill on one line; the primary figure in monospace; the exact raw value beneath; a formula pill. Period reads "Năm {year}" or "Giai đoạn {y1 - y2}". Scope reads "Hợp nhất" or "Báo cáo riêng".
2. **Verification banner.** One flat banner with icon and Vietnamese title: `✓ ĐÃ KIỂM ĐỊNH ĐỘC LẬP (VERIFIED)`, `⚠ ĐÃ KIỂM ĐỊNH CÓ LƯU Ý (WARNING)`, `✕ TỪ CHỐI KIỂM ĐỊNH (REJECTED)`; a plain-language description; optional italic warnings; and one chip per executed check in the form `check_name: STATUS`. Note: the current titles use the phrase "độc lập" (independent); see section 9.
3. **Evidence item.** Index and original label (unedited), value, then metadata: ticker, fiscal year, line code, scope, page, table; then a monospace citation line with source path and fact ID. When the fact comes from a comparative column, a tag reads "Số liệu so sánh (BCTC {report_year})".
4. **Diagnostic error box.** Category title (Lỗi Yêu Cầu Người Dùng, Không Tìm Thấy Số Liệu, Từ Chối Kiểm Định Độc Lập, Lỗi Hệ Thống) and an actionable message.
5. **Example chips and query form.** Standard Streamlit controls styled by the page theme.

## 5. Planned components

Each depends on the milestone in `AGENTS.md`. Do not build ahead of the milestone.

| Component | Milestone | Specification |
|---|---|---|
| Refusal / clarification state | M1 | Distinct from error styling. States: unsupported, ambiguous, needs clarification. Shows what was understood, why it cannot be answered, and what the user can do (supported metrics or the missing parameter). Neutral slate or amber tone, never the rejected red |
| Assumption notice | M1 / M3 | A line under the primary figure listing any default applied (period, scope, methodology), for example "Giả định: năm tài chính gần nhất, báo cáo hợp nhất" |
| Period-type label | M1 / M2 | Show annual vs quarterly vs year-to-date next to the period once `period_type` exists |
| Grouped verification checks | M2 | Group chips by category (Công thức, Số học, Kỳ kế toán, Phạm vi, Xuất xứ, Đơn vị, Đối chiếu kế toán) instead of listing every raw check name; expandable details |
| "Not run" check state | M2 | A check that did not run is shown as "Chưa kiểm tra" with a neutral style and the reason; it is never styled as passed |
| Evidence quality flag | M2 | A small flag on an evidence item whose fact failed a data-quality check (for example an accounting identity), with the reason |
| Reasoning trace view | M3 / M4 | Ordered steps: operation, operands (each linked to its evidence item), output, unit. For a single metric this is one or two steps; for programs it is the full step list. Collapsible; monospace for expressions |
| Comparative-period row | M2 | In the evidence item, show Fiscal year, Report year, and Comparative (Có / Không) explicitly, with the caption "Số liệu năm trước trên BCTC năm sau" |

## 6. Interaction and content rules

- Always show both the compact and the exact value. Raw values must be selectable and copyable.
- No animation beyond the framework's default spinner.
- Labels from reports (`original_label`, line codes) are shown unedited.
- Status wording is stable: `VERIFIED`, `WARNING`, `REJECTED` stay in English as identifiers next to the Vietnamese description.
- Error and refusal messages are Vietnamese, specific, and actionable. They list valid options when the user can fix the problem.
- Do not use the word "độc lập" / "independent" for a check unless it uses a source of truth different from the reasoner's own inputs (see `AGENTS.md` principle 23).

## 7. Accessibility

- Color is never the only status signal: every state has an icon and text.
- Essential text must meet 4.5:1 contrast; use the pairs in section 2.2 only.
- Minimum text size for essential information: 12px (0.75rem). Decorative or redundant text may be smaller only if the same information is available elsewhere.
- All interactive controls must be reachable and operable by keyboard; keep Streamlit's default focus outlines.
- Figures use tabular numerals so columns and magnitudes align.

## 8. Implementation rules

- **Escape every dynamic string** (OCR labels, ticker text, backend error messages, user query echoes) with `html.escape` before interpolating into HTML rendered with `unsafe_allow_html=True`. Report text comes from OCR and may contain `<`, `>`, or `&`.
- Presentation only: `ui/` contains no financial calculation or verification logic and imports only `src.application`.
- Prefer CSS variables from section 2.1; do not add new hard-coded colors without adding a token and a contrast measurement.
- Keep copy in Vietnamese; keep identifiers and CSS in English.

## 9. Known deviations from this spec (as built)

| # | Deviation | Resolution |
|---|---|---|
| D1 | Previous spec listed primary figure 2.25rem and section heading 1.25rem; the implementation uses 2.75rem and 1rem | Spec updated to as-built values |
| D2 | Previous spec stated contrast ratios (for example 15.8:1, 10.2:1, 4.8:1, 11.2:1, 7.6:1, 7.1:1, 7.8:1) that do not match the computed values | Replaced with measured ratios in section 2.2 |
| D3 | Previous spec called warning text AAA; measured 6.84:1 is AA | Corrected |
| D4 | `--text-muted` on `--surface-subtle` is 4.34:1 (below AA) | Usage rule added; check the codebase for any such pairing |
| D5 | Citation line, check chips, badge, and comparative tag use 11px text, below the 12px floor; the previous spec listed citations at 12px | Open: raise to 12px or provide the same information elsewhere |
| D6 | The banner lists every raw check name as a chip (14–20 chips per result) instead of the grouped pills in the previous spec | Planned: grouped verification checks (M2) |
| D7 | The previous spec described a Comparative Period Provenance card (Fiscal Year / Report Year / Comparative row, collapsible technical path); the build shows only a tag and a metadata line | Planned: comparative-period row (M2); collapsible technical path remains in the audit-trail expander |
| D8 | Dynamic strings are interpolated into HTML without escaping | Open: fix per section 8 (tracked as K11 in `AGENTS.md`) |
| D9 | `--accent-blue` is defined but unused; comparative-tag colors are hard-coded | Open: use or remove the token; tokenize the tag colors |
| D10 | Verification banner titles say "ĐÃ KIỂM ĐỊNH ĐỘC LẬP" although several checks reuse the reasoner's own inputs | Open: reword to "ĐÃ KIỂM ĐỊNH" until M2 delivers checks against independent sources |