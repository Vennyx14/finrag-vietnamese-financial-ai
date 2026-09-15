# DESIGN.md — FinRAG Design System & Visual Specification

## 1. Aesthetic Direction: Financial Research & Analytical Rigor

FinRAG is an analytical tool built for financial professionals. The aesthetic draws from high-end financial terminals and editorial reporting:
- Flat, crisp, and high-density information architecture.
- Intentional typography hierarchy with monospace/tabular numerics.
- Semantic slate/navy color scheme emphasizing trust and legibility.
- Strict avoidance of generic AI tropes: no neon gradients, no glassmorphism, no nested cards, no conversational chat bubbles.

## 2. Design Tokens

### 2.1 Color Palette (WCAG AA/AAA Compliant)

| Token | Hex | Role | Contrast vs Background |
|-------|-----|------|------------------------|
| `--bg-base` | `#F8FAFC` (Slate 50) | Main background | 1.0 (base) |
| `--surface-card` | `#FFFFFF` (White) | Primary container surface | 1.05 |
| `--surface-subtle` | `#F1F5F9` (Slate 100) | Secondary panels, tags, code | 1.15 |
| `--text-primary` | `#0F172A` (Slate 900) | Headings, primary metrics, table data | 15.8:1 (AAA) |
| `--text-secondary` | `#334155` (Slate 700) | Subheadings, labels, secondary descriptions | 10.2:1 (AAA) |
| `--text-muted` | `#64748B` (Slate 500) | Metadata timestamps, table footers | 4.8:1 (AA) |
| `--border-subtle` | `#E2E8F0` (Slate 200) | Divider rules, card outlines | Visual separator |
| `--border-strong` | `#CBD5E1` (Slate 300) | Interactive borders, table cell boundaries | Visual separator |
| `--accent-navy` | `#1E3A8A` (Blue 900) | Brand accents, active selection chips | 11.2:1 (AAA) |
| `--verified-bg` | `#ECFDF5` (Emerald 50) | Verification success container | 1.05 |
| `--verified-text` | `#065F46` (Emerald 800) | Verification success text | 7.6:1 (AAA) |
| `--verified-border` | `#A7F3D0` (Emerald 200) | Verification success border | Visual separator |
| `--warning-bg` | `#FFFBEB` (Amber 50) | Methodology caveat container | 1.05 |
| `--warning-text` | `#92400E` (Amber 800) | Methodology caveat text | 7.1:1 (AAA) |
| `--warning-border` | `#FDE68A` (Amber 200) | Methodology caveat border | Visual separator |
| `--rejected-bg` | `#FEF2F2` (Rose 50) | Verification rejection container | 1.05 |
| `--rejected-text` | `#991B1B` (Rose 800) | Verification rejection text | 7.8:1 (AAA) |
| `--rejected-border` | `#FECDD3` (Rose 200) | Verification rejection border | Visual separator |

### 2.2 Typography Stack

- **Primary UI & Headings**: System Grotesque Sans (`-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif`).
- **Financial Figures & Metrics**: Monospace & Tabular figures (`'SF Mono', 'Segoe UI Mono', 'Roboto Mono', 'Cascadia Code', Menlo, Consolas, monospace` with `font-variant-numeric: tabular-nums`).
- **Scale**:
  - Primary Metric Display: `2.25rem` (`36px`), bold (`700`), tabular.
  - Section Headings: `1.25rem` (`20px`), semi-bold (`600`).
  - Metric Labels & Subheaders: `0.875rem` (`14px`), medium (`500`), uppercase tracked (`letter-spacing: 0.05em`).
  - Body & Provenance Data: `0.875rem` (`14px`), regular (`400`).
  - Technical Citations & Metadata: `0.75rem` (`12px`), regular (`400`).

### 2.3 Spatial Rhythm & Borders

- **Grid Base**: 4px / 8px incremental scale (`p-2: 8px`, `p-4: 16px`, `p-6: 24px`).
- **Borders**: 1px solid hairline rules (`--border-subtle`). No heavy shadows or blurred drop-shadows.
- **Border Radius**: Subtle `6px` to `8px` for interactive inputs and cards. Zero pill-shaped circular containers for content.

## 3. Component Design Patterns

1. **Analytical Result Header**:
   - Displays canonical metric title and Vietnamese statutory translation.
   - Primary figure displayed prominently with exact magnitude suffix (`₫62.85T`, `15.00%`, `+19.44%`).
   - Formula box immediately beneath the figure explaining the arithmetic breakdown.
2. **Verification Banner**:
   - Flat banner with semantic icon (`✓`, `⚠`, `✕`) and distinct textual status (`VERIFIED`, `WARNING`, `REJECTED`).
   - Accompanied by a concise plain-language explanation and individual check pills (`Formula`, `Numerical`, `Fiscal Period`, `Scope`, `Provenance`, `Unit`).
3. **Comparative Period Provenance Card**:
   - Shows the exact period semantics:
     - `Fiscal Year`: observation period.
     - `Report Year`: filing year.
     - `Comparative`: `YES` badge with explanatory caption (`Số liệu năm trước trên BCTC năm sau`).
   - Statutory accounting line code and Vietnamese table label unedited.
   - Page and table ID citations with collapsible technical path.
4. **Input Error Diagnostics**:
   - Clear classification: `Input Error` vs `Data Unavailable` vs `Verification Rejection`.
   - Helpful suggestions for valid ticker symbols or metric queries.
