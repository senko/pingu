# Pingu — Design Guide

## Version 1.0

Reference mockups: `pingu-dashboard-mockup.html`, `pingu-detail-mockup.html`, `pingu-form-mockup.html`, `pingu-history-mockup.html`.

---

## 1. Design Principles

1. **Dark-first**: Single dark theme. No light mode. Backgrounds use deep blue-charcoal tones (not pure black) for reduced eye strain.
2. **Information density over decoration**: This is an internal monitoring tool. Every pixel should serve a purpose — status, data, or navigation.
3. **Progressive disclosure by breakpoint**: Show the most important data at every screen size. Remove columns and secondary info on smaller screens rather than wrapping into multi-line rows.
4. **Monospace for data, sans-serif for UI**: Technical data (URLs, timestamps, status codes, numbers) uses monospace. Labels, headings, and navigation use the sans-serif.
5. **Color encodes meaning**: Green = up/success, red = down/failure, amber = warning/degraded, gray = paused/inactive, teal = interactive/accent. Never use these status colors decoratively.
6. **Minimal motion**: Only subtle transitions (0.15s ease) on hover states and focus rings. One animation: the pulse on active incidents. No page transitions, no loading spinners, no auto-refresh.

---

## 2. Color System

All colors are defined as Tailwind theme extensions. Use the semantic names, not raw hex values.

### 2.1 Surface (Backgrounds)

| Token | Hex | Usage |
|---|---|---|
| `surface-900` | `#0a0c10` | Page background (`body`) |
| `surface-800` | `#0f1218` | Card backgrounds, form inputs |
| `surface-700` | `#161a22` | Elevated cards (summary cards, active day indicator) |
| `surface-600` | `#1c2130` | Inset elements (method badges, uptime bar empty state, avatar circle) |
| `surface-500` | `#252b3b` | Scrollbar thumbs, toggle tracks (inactive) |

### 2.2 Borders

| Token | Hex | Usage |
|---|---|---|
| `border` | `#1e2433` | Primary borders on cards, dividers, inputs |
| `border-light` | `#2a3148` | Hover-state borders, secondary dividers |
| `border/50` | `rgba(30,36,51,0.5)` | Subtle row dividers within tables |

### 2.3 Text

| Token | Hex | Usage |
|---|---|---|
| `text-primary` | `#e2e8f0` | Headings, names, primary data |
| `text-secondary` | `#8896ab` | Labels, secondary info, timestamps |
| `text-muted` | `#556178` | Helper text, placeholders, captions, disabled text |

### 2.4 Accent

| Token | Value | Usage |
|---|---|---|
| `accent-teal` | `#2dd4a8` | Primary action color — buttons, links, focus rings, active states |
| `accent-tealDim` | `rgba(45,212,168,0.12)` | Accent backgrounds (active method button, primary button bg) |

### 2.5 Status Colors

Each status color has a full-opacity variant and a `Dim` background variant.

| Status | Full | Dim (background) | Meaning |
|---|---|---|---|
| `status-up` | `#22c55e` | `rgba(34,197,94,0.12)` | Up, success, healthy |
| `status-down` | `#ef4444` | `rgba(239,68,68,0.12)` | Down, failure, error |
| `status-warn` | `#f59e0b` | `rgba(245,158,11,0.12)` | Degraded, slow, minor issue |
| `status-orange` | `#f97316` | `rgba(249,115,22,0.12)` | Moderate downtime (1–5% in availability charts) |
| `status-paused` | `#6b7280` | `rgba(107,114,128,0.12)` | Paused, inactive, no data |

### 2.6 Availability Chart Thresholds

Used for coloring both 24-hour and 30-day availability bars:

| Downtime | Color | Token |
|---|---|---|
| < 0.1% | Green | `status-up` |
| 0.1% – 1% | Yellow | `status-warn` |
| 1% – 5% | Orange | `status-orange` |
| > 5% | Red | `status-down` |
| No data / paused | Gray | `surface-600` |

---

## 3. Typography

### 3.1 Font Stack

| Role | Family | Load from Google Fonts |
|---|---|---|
| UI (sans-serif) | **DM Sans** | Weights: 300, 400, 500, 600, 700 |
| Data (monospace) | **JetBrains Mono** | Weights: 400, 500 |

Tailwind config:
```js
fontFamily: {
  sans: ['DM Sans', 'sans-serif'],
  mono: ['JetBrains Mono', 'monospace'],
}
```

### 3.2 Scale

| Element | Size | Weight | Font |
|---|---|---|---|
| Page title (`h1`) | `text-lg` (1.125rem) | `font-semibold` (600) | Sans |
| Section heading | `text-sm` (0.875rem) | `font-semibold` (600) | Sans |
| Section label (uppercase) | `0.6875rem` | `font-semibold` (600) + `tracking-wider` + `uppercase` | Sans |
| Body text / labels | `text-sm` (0.875rem) | `font-normal` (400) | Sans |
| Form labels | `text-sm` (0.875rem) | `font-normal` (400) | Sans |
| Helper text | `text-xs` (0.75rem) | `font-normal` (400) | Sans |
| Badge text | `0.6875rem` | `font-medium` (500) + `tracking-wide` | Sans |
| Data values (URLs, codes, times) | `text-sm` or `text-xs` | `font-normal` (400) | Mono |
| Form inputs | `text-sm` (0.875rem) | `font-normal` (400) | Sans (or Mono for data inputs) |
| Large numbers (summary cards) | `text-2xl` (1.5rem) | `font-semibold` (600) | Sans |
| Navigation brand | `text-base` (1rem) | `font-semibold` (600) | Sans |
| Breadcrumb path | `text-xs` (0.75rem) | `font-normal` (400) | Mono |

### 3.3 When to Use Monospace

Use `font-mono` (JetBrains Mono) for:
- URLs
- Timestamps and durations
- Status codes
- Response times
- Percentages
- HTTP methods (in badges)
- Form inputs for: URL, headers (key+value), request body, timeout, interval, alert threshold, expected status codes

Use sans-serif (DM Sans) for everything else.

---

## 4. Layout

### 4.1 Page Widths

| Page type | Max width | Rationale |
|---|---|---|
| Dashboard (list page) | `max-w-7xl` (80rem) | Wide — needs room for the 12-col grid |
| Detail page | `max-w-5xl` (64rem) | Medium — single-item focus, charts need width |
| Form / edit page | `max-w-3xl` (48rem) | Narrow — forms read better in tight columns |
| Login page | `max-w-sm` (24rem) | Centered card |

All pages use: `mx-auto px-4 sm:px-6 lg:px-8`.

### 4.2 Spacing

- Page padding top/bottom: `py-6`
- Between major sections: `space-y-6` or `mb-6`/`mb-8`
- Inside cards: `px-5 py-4 sm:px-6` (horizontal padding bumps at `sm`)
- Between form fields: `space-y-5`
- Card border radius: `rounded-xl` (0.75rem)
- Button border radius: `rounded-md` (0.375rem) for small, `rounded-lg` (0.5rem) for standard

### 4.3 Cards

All content sections are wrapped in cards:
```
bg-surface-800 border border-border rounded-xl overflow-hidden
```

Cards with headers use a border-bottom divider:
```
<div class="px-5 py-3 sm:px-6 border-b border-border">
  <h2 class="text-sm font-semibold text-text-primary">Section Title</h2>
</div>
```

Elevated cards (summary stats): `bg-surface-700` instead of `surface-800`.

---

## 5. Components

### 5.1 Navigation Bar

Fixed to top with glassmorphism backdrop:
```css
border-b border-border sticky top-0 z-40
background: rgba(10,12,16,0.85)
backdrop-filter: blur(12px)
```

Height: `h-14`. Contains: logo (left), breadcrumb path (hidden below `sm`), user avatar + logout (hidden below `sm`), and primary action link ("+ New Check").

Breadcrumb uses monospace and the pattern: `/ segment / segment`. Each segment is a link with `hover:text-text-secondary`.

### 5.2 Status Badges

Pill-shaped badges for UP/DOWN/PAUSED/status codes:
```css
.badge {
  font-size: 0.6875rem;
  letter-spacing: 0.03em;
  font-weight: 500;
  padding: 0.2rem 0.55rem;
  border-radius: 9999px;
  line-height: 1;
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
}
```

Color combinations:
- UP: `bg-status-upDim text-status-up`
- DOWN: `bg-status-downDim text-status-down` (optionally with pulsing dot inside)
- PAUSED: `bg-status-pausedDim text-status-paused`
- Status code 200/201/204: same as UP
- Status code 4xx/5xx/Timeout: same as DOWN

The DOWN badge may include an animated dot:
```html
<span class="badge bg-status-downDim text-status-down">
  <span class="inline-block w-1 h-1 rounded-full bg-status-down pulse-down"></span>
  DOWN
</span>
```

### 5.3 Buttons

Four button variants. All use `font-family: 'DM Sans'`, `transition: all 0.15s ease`, `cursor: pointer`.

**Primary** (teal — main actions like "Save Changes", "Check Now"):
```css
background: rgba(45, 212, 168, 0.1);
border: 1px solid rgba(45, 212, 168, 0.25);
color: #2dd4a8;
/* hover: */
background: rgba(45, 212, 168, 0.18);
border-color: rgba(45, 212, 168, 0.4);
```

**Secondary** (neutral — "Edit", "Cancel"):
```css
background: transparent;
border: 1px solid #1e2433;
color: #8896ab;
/* hover: */
background: rgba(255,255,255,0.03);
border-color: #2a3148;
color: #e2e8f0;
```

**Danger** (red — "Delete"):
```css
background: rgba(239, 68, 68, 0.08);
border: 1px solid rgba(239, 68, 68, 0.2);
color: #ef4444;
/* hover: */
background: rgba(239, 68, 68, 0.15);
border-color: rgba(239, 68, 68, 0.35);
```

**Ghost** (dashed border — "+ Add header"):
```css
background: transparent;
border: 1px dashed #2a3148;
color: #556178;
/* hover: */
border-color: rgba(45, 212, 168, 0.3);
color: #8896ab;
background: rgba(45, 212, 168, 0.04);
```

Standard button size: `padding: 0.55rem 1.25rem; font-size: 0.875rem; border-radius: 0.5rem;`
Small button size (inline, e.g., "Check Now" on dashboard): `padding: 0.3rem 0.65rem; font-size: 0.75rem; border-radius: 0.375rem;`

### 5.4 Filter Pills

Used for toggling between views (All / Failed / Success):
```css
.filter-pill {
  font-size: 0.75rem;
  padding: 0.3rem 0.75rem;
  border-radius: 9999px;
  border: 1px solid #1e2433;
  color: #556178;
}
.filter-pill.active {
  background: rgba(45, 212, 168, 0.1);
  border-color: rgba(45, 212, 168, 0.25);
  color: #2dd4a8;
}
```

### 5.5 Form Inputs

**Base input:**
```css
.form-input {
  background: #0f1218;
  border: 1px solid #1e2433;
  border-radius: 0.5rem;
  padding: 0.55rem 0.75rem;
  color: #e2e8f0;
  font-size: 0.875rem;
}
/* focus: */
border-color: rgba(45, 212, 168, 0.4);
box-shadow: 0 0 0 3px rgba(45, 212, 168, 0.08);
/* placeholder: */
color: #556178;
```

**Monospace modifier** (for URL, headers, body, numeric inputs):
```css
.form-input-mono {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.8125rem;
}
```

**Error state:**
```css
.form-input-error {
  border-color: rgba(239, 68, 68, 0.5);
}
.form-input-error:focus {
  border-color: rgba(239, 68, 68, 0.6);
  box-shadow: 0 0 0 3px rgba(239, 68, 68, 0.1);
}
```

**Numeric inputs**: Use `type="text" inputmode="numeric" pattern="[0-9]*"` — no browser spinners, numeric keyboard on mobile, server-side validation.

**Unit suffixes** (s, min, failures): Positioned with `absolute right-3 top-1/2 -translate-y-1/2` inside a `relative` wrapper. Text: `text-xs text-text-muted font-mono`.

### 5.6 Field Error Messages

Below the input, red text with an icon:
```css
.field-error {
  color: #ef4444;
  font-size: 0.75rem;
  margin-top: 0.4rem;
  display: flex;
  align-items: center;
  gap: 0.35rem;
}
```

Icon: 12×12 SVG circle with exclamation mark, same red stroke.

### 5.7 Form-Level Error Banner

Shown at the top of the form after a failed submission:
```html
<div class="bg-status-downDim border border-status-down/20 rounded-xl px-4 py-3 flex items-start gap-3">
  <!-- 16x16 error icon -->
  <div>
    <div class="text-sm font-medium text-status-down">Please fix the errors below</div>
    <div class="text-xs text-status-down/70 mt-0.5">3 fields need your attention.</div>
  </div>
</div>
```

### 5.8 Toggle Switches

Custom toggle (not native checkbox):
```css
.toggle-track: 36×20px, border-radius: 10px, bg: #252b3b
.toggle-track.active: bg: rgba(45, 212, 168, 0.35)
.toggle-thumb: 16×16px, circle, bg: #556178, positioned 2px from edges
.toggle-track.active .toggle-thumb: left: 18px, bg: #2dd4a8
```

### 5.9 Tag / Chip Input

For multi-value fields (expected status codes):
```css
.tag {
  background: #1c2130;
  border: 1px solid #2a3148;
  border-radius: 0.375rem;
  padding: 0.25rem 0.5rem;
  font-size: 0.8125rem;
  font-family: monospace;
}
```

Container: `.form-input` base style with `flex flex-wrap items-center gap-1.5`. Inline text input for adding new values.

### 5.10 Method Selector

Button group (not dropdown). All methods visible. Selected state matches primary accent:
```
Selected:   bg-accent-tealDim text-accent-teal border-accent-teal/25
Unselected: bg-transparent text-text-muted border-border
```

Font: `text-xs font-mono font-medium`. Size: `px-3 py-1.5 rounded-md`.

### 5.11 Uptime Bars

**Dashboard (inline strip)** — seamless, no gaps, no hover:
```css
.uptime-strip {
  display: flex;
  height: 20px;
  border-radius: 3px;
  overflow: hidden;
  max-width: 180px;
}
.uptime-strip > div { flex: 1; min-width: 0; }
```

**Detail page (charts)** — with gaps and hover tooltips:
```css
/* Container: flex items-end gap-1 sm:gap-1.5, height: 64px */
.avail-bar {
  border-radius: 3px;
  height: 100%;
}
/* Tooltip on hover of .bar-wrap parent */
.bar-tooltip {
  background: #1c2130;
  border: 1px solid #2a3148;
  border-radius: 8px;
  padding: 8px 12px;
  font-size: 0.75rem;
  box-shadow: 0 8px 24px rgba(0,0,0,0.5);
}
```

Time labels below charts: `text-[0.625rem] text-text-muted font-mono`, flexed with `justify-between`.

### 5.12 Status Dot

Small indicator dot used throughout:
- Standard: `w-2 h-2 rounded-full bg-status-{up|down|paused}`
- With pulse (active down): add class `pulse-down`

```css
@keyframes pulse-down {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}
.pulse-down { animation: pulse-down 2s ease-in-out infinite; }
```

### 5.13 Section Labels (Form)

Uppercase divider labels within form sections:
```css
.section-label {
  font-size: 0.6875rem;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: #556178;
  padding-bottom: 0.75rem;
  border-bottom: 1px solid rgba(30, 36, 51, 0.6);
  margin-bottom: 1rem;
}
```

---

## 6. Row Patterns

### 6.1 Down / Error Row Tinting

Rows representing failures get a subtle red background:
```css
style="background: rgba(239,68,68,0.025);"
```

This applies to: dashboard check rows (if currently down), history result rows (if failed).

### 6.2 Paused Row Dimming

Paused check rows use: `opacity-50` on the entire `<a>` element.

### 6.3 Clickable Row Hover

Dashboard check rows are full `<a>` elements with hover effect:
```css
.check-row { transition: background 0.15s ease; }
.check-row:hover { background: rgba(45, 212, 168, 0.03); }
```

History result rows use a more subtle hover:
```css
.result-row:hover { background: rgba(255, 255, 255, 0.015); }
```

---

## 7. Responsive Strategy

Three breakpoints, using Tailwind defaults:
- **`< md` (< 768px)**: Mobile
- **`md – lg` (768px – 1023px)**: Tablet / medium
- **`≥ lg` (1024px+)**: Desktop

### 7.1 General Rules

1. Each row should remain a single visual line at every breakpoint. Never wrap a row into multiple lines — instead, hide columns.
2. Hide the least critical columns first as the viewport shrinks.
3. Summary cards and stat blocks are hidden on mobile (they duplicate info already visible in the list).
4. Navigation elements (user avatar, logout, breadcrumb) are hidden on mobile. Only the logo and primary action remain.
5. Stat/summary blocks that are inline-horizontal on desktop become stacked key-value pairs on mobile.

### 7.2 Dashboard Breakpoints

| Element | `lg` | `md` | `< md` |
|---|---|---|---|
| Summary cards | 4-col grid | 4-col grid | Hidden |
| Column headers | Shown | Hidden | Hidden |
| Service name | Name + URL | Name + URL | Name only |
| Status badge | Shown | Shown | Shown |
| Uptime bars + % | Bars + percentage | Percentage only (no bars) | Hidden |
| Last checked | Shown | Hidden | Hidden |
| Actions (Check Now) | Shown | Hidden | Hidden |

Implementation: Three separate DOM blocks per row, toggled with `hidden lg:grid`, `hidden md:flex lg:hidden`, `flex md:hidden`.

### 7.3 Detail Page Breakpoints

| Element | `sm+` | `< sm` |
|---|---|---|
| Header actions | Inline right | Stacked below name |
| Config grid | 3-col or 6-col | 2-col |
| Availability charts | Full width | Full width (bars adapt via flex) |
| Monthly stats | Inline row | Same (simple enough to not need changes) |

### 7.4 Form Breakpoints

| Element | `sm+` | `< sm` |
|---|---|---|
| Timeout + Interval | Side-by-side (2-col grid) | Stacked |
| Action buttons (Save/Cancel) | Inline row | Stacked (Save on top, Cancel below) |
| Alert email | `max-w-[360px]` | Full width |

### 7.5 History Page Breakpoints

| Element | `md+` | `< md` |
|---|---|---|
| Column headers | 4-col grid shown | Hidden |
| Result row | Grid: time, code, response time, details | Flex: time (left) + status badge (right). Response time and details hidden. |
| Day summary | Inline horizontal | Stacked key-value |
| Day nav labels | "Yesterday" / "Tomorrow" | Date strings ("Mar 19" / "Mar 21") |

---

## 8. Global Elements

### 8.1 Noise Texture Overlay

Subtle grain texture applied to the page for depth:
```css
body::before {
  content: '';
  position: fixed;
  inset: 0;
  opacity: 0.015;
  background-image: url("data:image/svg+xml,...feTurbulence...");
  pointer-events: none;
  z-index: 9999;
}
```

### 8.2 Custom Scrollbar

Webkit only (Chrome, Edge, Safari):
```css
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: #252b3b; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #2a3148; }
```

### 8.3 Footer

Simple flex row at page bottom:
```html
<div class="flex items-center justify-between text-xs text-text-muted py-6">
  <span>Pingu v1.0</span>
  <a href="#" class="text-accent-teal hover:underline">← Back to dashboard</a>
</div>
```

The right side varies: dashboard shows stats ("12 checks · 1 incident active"), sub-pages show a back link.

### 8.4 Links

- **Accent links** (navigation, action links): `text-accent-teal hover:underline`
- **Muted links** (secondary nav, breadcrumbs): `text-text-muted hover:text-text-secondary`
- **Text links within paragraphs**: `text-text-secondary hover:text-text-primary`

---

## 9. Page Templates

### 9.1 Login Page

Not yet mocked up. Guidelines:

- Center a card vertically and horizontally: `min-h-screen flex items-center justify-center`
- Card width: `max-w-sm w-full`
- Card style: `bg-surface-800 border border-border rounded-xl p-6 sm:p-8`
- Logo centered above the form
- Fields: Username (`.form-input`), Password (`.form-input`), Submit button (`.btn-primary`, full width)
- Error state: form-level error banner above the fields for "Invalid credentials"
- No registration link, no forgot-password link
- Footer below card: "Pingu v1.0" in `text-text-muted`

### 9.2 Delete Confirmation

Not a separate page — implemented as a simple confirmation page following the form card pattern:

- `max-w-3xl` layout
- Card with warning message: "Are you sure you want to delete **{check name}**? This will permanently remove all check results and incident history."
- Two buttons: "Delete" (`.btn-danger`) and "Cancel" (`.btn-secondary`)

### 9.3 Django Messages / Toasts

For success messages after actions (e.g., "Check created", "Check deleted"):

Use a banner similar to the error banner but with success styling:
```html
<div class="bg-status-upDim border border-status-up/20 rounded-xl px-4 py-3 flex items-start gap-3">
  <!-- 16x16 checkmark icon -->
  <div class="text-sm text-status-up">Check created successfully.</div>
</div>
```

Placed at the top of the main content area, above the page content.

---

## 10. Tailwind Configuration

Complete Tailwind theme extension to include in `tailwind.config.js`:

```js
module.exports = {
  content: [
    './src/**/templates/**/*.html',
    './static/js/**/*.js',
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['DM Sans', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      colors: {
        surface: {
          900: '#0a0c10',
          800: '#0f1218',
          700: '#161a22',
          600: '#1c2130',
          500: '#252b3b',
        },
        border: {
          DEFAULT: '#1e2433',
          light: '#2a3148',
        },
        accent: {
          teal: '#2dd4a8',
          tealDim: 'rgba(45,212,168,0.12)',
        },
        status: {
          up: '#22c55e',
          upDim: 'rgba(34,197,94,0.12)',
          down: '#ef4444',
          downDim: 'rgba(239,68,68,0.12)',
          paused: '#6b7280',
          pausedDim: 'rgba(107,114,128,0.12)',
          warn: '#f59e0b',
          warnDim: 'rgba(245,158,11,0.12)',
          orange: '#f97316',
          orangeDim: 'rgba(249,115,22,0.12)',
        },
        text: {
          primary: '#e2e8f0',
          secondary: '#8896ab',
          muted: '#556178',
        },
      },
    },
  },
  plugins: [],
}
```

---

## 11. CSS Classes Reference

Classes that should be defined in the global stylesheet (not inline Tailwind), as they're reused across templates:

| Class | Purpose | Defined in |
|---|---|---|
| `.badge` | Status pill badges | `base.css` |
| `.form-input` | Base form input | `base.css` |
| `.form-input-mono` | Monospace input modifier | `base.css` |
| `.form-input-error` | Error state input modifier | `base.css` |
| `.field-error` | Error message below input | `base.css` |
| `.btn-primary` | Teal action button | `base.css` |
| `.btn-secondary` | Neutral button | `base.css` |
| `.btn-danger` | Red destructive button | `base.css` |
| `.btn-ghost` | Dashed add/create button | `base.css` |
| `.filter-pill` | Filter toggle pill | `base.css` |
| `.toggle-track` / `.toggle-thumb` | Toggle switch | `base.css` |
| `.tag` / `.tag-remove` | Chip/tag input elements | `base.css` |
| `.section-label` | Uppercase form section divider | `base.css` |
| `.check-row` | Dashboard row hover | `base.css` |
| `.result-row` | History row hover | `base.css` |
| `.uptime-strip` | Dashboard seamless bar strip | `base.css` |
| `.avail-bar` / `.bar-wrap` / `.bar-tooltip` | Detail page chart bars | `base.css` |
| `.pulse-down` | Pulsing animation for down status | `base.css` |
| `.day-nav-btn` | Day pagination button | `base.css` |

---

## 12. Icon Usage

No icon library. All icons are inline SVGs, 14–22px, using `stroke="currentColor"` so they inherit text color. Standard set used:

| Icon | Where | Stroke width |
|---|---|---|
| Circle + checkmark | Logo / nav | 1.5 |
| Chevron left/right | Day pagination | 2 |
| X (cross) | Remove header row, tag remove | 2 |
| Circle + exclamation | Error icon (field + banner) | 2 (1.5 for banner variant) |

Keep SVGs self-contained (no external sprite sheet). Copy-paste from mockups.
