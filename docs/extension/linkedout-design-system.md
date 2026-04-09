# Design System — LinkedOut

## Product Context
- **What this is:** AI-powered warm network intelligence tool. Search your own LinkedIn connections with natural language.
- **Who it's for:** Recruiters (primary wedge), founders, anyone with a large LinkedIn network who needs to find the right person in their existing connections.
- **Space/industry:** Recruiting tech / professional networking. Competitors search 850M+ public profiles; LinkedOut searches YOUR connections where warm intros convert 3-5x better.
- **Project type:** Web app (FastAPI backend + frontend). Dashboard for search, profile cards, contact import, enrichment tracking.

## Aesthetic Direction
- **Direction:** Warm Editorial-Technical — inspired by fly.io's signature warmth
- **Decoration level:** Intentional — grainy texture on illustration areas, clean everywhere else. Not sterile, not overwhelming.
- **Mood:** Sophisticated yet approachable. "Your network is personal, not a spreadsheet." The product should feel like a beautifully designed personal tool, not cold enterprise SaaS. Warm pastels give it soul; serif typography gives it editorial credibility.
- **Illustration style:** 2D flat illustration, whimsical tech style, hand-drawn digital art, pastel color palette, grainy texture, playful narrative, Annie Ruygt style. Abstract stylized figures (not a recurring character/mascot) + organic network visuals (constellation-like connection lines, floating profile cards, soft glowing dots). Different people shapes each time, representing diverse connections. No mascot — the real people in the data are the humanity.
- **Illustration usage:** Hero sections, onboarding, empty states, error pages, loading states. NOT used in data UI (search results, tables, forms).
- **Reference sites:** fly.io (typography + illustration approach), sprites.dev (layout + component style)
- **Light mode only.** No dark mode.

## Typography
- **Display/Hero:** Fraunces (700-900) — Warm optical-size serif with personality. Used for headlines, page titles, hero text. Variable weight for flexibility. Google Fonts available.
  - *Production alternative:* If licensing Fricolage Grotesque (fly.io's actual display font), use that instead.
- **Body:** Fraunces (400, italic) — Same family for body text, lighter weight. Serif body in a tech tool is the signature risk — says "personal, human, your network." Line-height 1.65 for readability.
  - *Production alternative:* Mackinac (fly.io's actual body serif) if licensed.
- **UI/Labels:** Fraunces (500-600) — Sans-like usage at smaller sizes with tighter tracking. Buttons, nav items, form labels.
- **Data/Tables:** Fragment Mono (400) — Clean monospace for affinity scores, dates, counts, costs. Tabular figures for aligned numbers. Google Fonts available.
- **Code:** Fragment Mono (400, italic)
- **Loading:** Google Fonts CDN via `<link>` tags. Preconnect to `fonts.googleapis.com` and `fonts.gstatic.com`.
- **Scale:**
  - `display-xl`: clamp(2.5rem, 5vw, 4rem), weight 800, tracking -0.02em
  - `display-lg`: clamp(1.75rem, 3.5vw, 2.5rem), weight 700, tracking -0.015em
  - `display-md`: clamp(1.25rem, 2vw, 1.5rem), weight 600
  - `body`: 1.0625rem, weight 400, line-height 1.65
  - `ui`: 0.875rem, weight 500, tracking 0.01em
  - `mono`: 0.875rem, weight 400
  - `mono-sm`: 0.75rem

## Color
- **Approach:** Expressive pastels — Berry Fields Soft palette
- **Palette name:** Berry Fields Soft
- **Light mode only.**

### Foundations
| Token | Hex | Usage |
|-------|-----|-------|
| `--bg-primary` | `#FDFBFE` | Page background (soft warm white with purple tint) |
| `--bg-surface` | `#FFFFFF` | Cards, panels, elevated surfaces |
| `--bg-subtle` | `#F6F2F8` | Alternating section backgrounds |
| `--bg-accent-soft` | `#F5EFFC` | Berry-tinted highlight panels |

### Berry Fields Pastels
| Token | Hex | Usage |
|-------|-----|-------|
| `--pastel-peach` | `#FAEAEE` | Whisper rose — light backgrounds, import source badges |
| `--pastel-peach-mid` | `#F2D4DC` | Deeper rose — borders, hover states |
| `--pastel-lavender` | `#F0EAF5` | Pale plum — section backgrounds, typography specimen |
| `--pastel-lavender-mid` | `#E2D8EE` | Deeper plum — borders, active states |
| `--pastel-sage` | `#F6EDE4` | Warm blush — section backgrounds, feature cards |
| `--pastel-sage-mid` | `#EEDCC8` | Deeper blush — borders |
| `--pastel-mint` | `#EDE0F2` | Light lilac — accent panels, search hint chips |
| `--pastel-cream` | `#FDF8FA` | Warm tinted white — hero gradient base |

### Accent
| Token | Hex | Usage |
|-------|-----|-------|
| `--accent` | `#A87AD0` | Primary accent — buttons, links, focus rings, active nav |
| `--accent-hover` | `#9568BE` | Hover state for primary accent |
| `--accent-light` | `#F5EFFC` | Accent tint — soft backgrounds, focus glow |
| `--accent-dark` | `#8558AC` | Dark accent — text on light accent backgrounds |

### Text
| Token | Hex | Usage |
|-------|-----|-------|
| `--text-primary` | `#1B1B18` | Warm near-black — headings, body text |
| `--text-secondary` | `#6B6B63` | Muted olive-gray — secondary text, descriptions |
| `--text-tertiary` | `#9C9C93` | Placeholders, hints, metadata labels |

### Borders
| Token | Hex | Usage |
|-------|-----|-------|
| `--border` | `#E5E3DD` | Default border — cards, dividers, table rows |
| `--border-focus` | `#A87AD0` | Focus ring border (matches accent) |

### Semantic
| Token | Hex | Usage |
|-------|-----|-------|
| `--success` | `#16A34A` | Import complete, enrichment done |
| `--warning` | `#D97706` | Enrichment queued, stale profiles |
| `--error` | `#DC2626` | Invalid CSV, enrichment failed |
| `--info` | `#2563EB` | Tips, affinity scoring explanation |

### Section Backgrounds
Sections alternate between pastel gradients to create visual rhythm:
- `section-peach`: gradient from `--pastel-peach` to `--pastel-cream`
- `section-lavender`: gradient from `--pastel-lavender` to a lighter tint
- `section-sage`: gradient from `--pastel-sage` to a lighter tint
- `section-mint`: gradient from `--pastel-mint` to `--accent-light`

### Dunbar Tier Colors
| Tier | Background | Text |
|------|------------|------|
| Inner Circle | `--pastel-lavender` | `#5B4A7A` |
| Active | `--pastel-sage` | `#4A6340` → use `#6B5A42` for blush variant |
| Familiar | `--pastel-peach` | `#8B5E34` → use `#8B4A5E` for rose variant |
| Acquaintance | `--bg-subtle` | `--text-secondary` |

### Affinity Score Colors
| Level | Background | Text |
|-------|------------|------|
| High (>0.7) | `--pastel-mint` | `--accent-dark` |
| Mid (0.4-0.7) | `--pastel-peach` | rose-brown |
| Low (<0.4) | `--bg-subtle` | `--text-secondary` |

## Spacing
- **Base unit:** 4px
- **Density:** Comfortable
- **Scale:**
  - `2xs`: 2px
  - `xs`: 4px
  - `sm`: 8px
  - `md`: 16px
  - `lg`: 24px
  - `xl`: 32px
  - `2xl`: 48px
  - `3xl`: 64px

## Layout
- **Approach:** Grid-disciplined for the app (search, results, tables). Creative-editorial for marketing/landing pages.
- **Grid:** 12 columns. Responsive breakpoints at 768px, 1024px, 1200px.
- **Max content width:** 1200px
- **Border radius:**
  - `sm`: 6px (buttons, inputs, tags)
  - `md`: 10px (cards, panels, search bar)
  - `lg`: 16px (feature cards, illustration spots, modals)
  - `full`: 9999px (badges, pills, avatars)
- Slightly rounded — not bubbly, not sharp. Warm, approachable.

## Motion
- **Approach:** Minimal-functional. Subtle fade/slide transitions only. No bounce, no parallax, no scroll-driven animation.
- **Easing:**
  - Enter: `ease-out`
  - Exit: `ease-in`
  - Move: `ease-in-out`
- **Duration:**
  - `micro`: 75ms (hover state changes)
  - `short`: 150ms (button transitions, focus rings)
  - `medium`: 300ms (card hover, panel open/close)
  - `long`: 500ms (page transitions — use sparingly)

## Component Patterns

### Buttons
- **Primary:** Berry accent bg, white text. Hover darkens.
- **Secondary:** White bg, border, dark text. Hover shows accent border + accent text.
- **Ghost:** Transparent bg, accent text. Hover shows accent-light bg.
- **Pastel variants:** Rose, plum, blush backgrounds for import source selection.

### Profile Cards
- White surface, 1px border, rounded-md. Hover: accent border + subtle shadow.
- Avatar: colored circle with initials. Color varies by connection.
- Metadata in Fragment Mono. Affinity badge + Dunbar tier badge in pastels.

### Search Bar
- 2px border, rounded-md. Focus: accent border + 3px accent-light glow.
- Search hint chips below in pastel backgrounds.

### Data Tables
- Fragment Mono for numeric columns. Hover row highlights in accent-soft.
- Dunbar badges inline. LinkedIn links as accent-colored text with arrow.

### Alerts
- Left border accent (3px). Semantic color backgrounds. Icon + message layout.

## Decisions Log
| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-03-27 | Berry Fields Soft palette chosen | Sophisticated, editorial feel. Muted pastels pair well with warm serif typography and whimsical illustrations. Selected from 8 palette variations. |
| 2026-03-27 | Light mode only | Matches fly.io's approach. Recruiters work in bright environments. Simplifies implementation. |
| 2026-03-27 | Fraunces serif for display + body | Closest Google Fonts equivalent to fly.io's Mackinac. Warm optical-size serif gives LinkedOut personality and warmth vs cold sans-serif competitors. |
| 2026-03-27 | Fragment Mono for data | Clean monospace with tabular figures. Essential for aligned affinity scores, dates, and enrichment costs. |
| 2026-03-27 | Annie Ruygt illustration style | 2D flat, whimsical, pastel, grainy texture. Proven by fly.io to work for technical products. Gives LinkedOut a soul that recruiting tools lack. |
| 2026-03-27 | Teal→Berry accent pivot | Original teal was too generic. Berry purple (#A87AD0) is distinctive, pairs perfectly with rose/plum pastels, and stands out from LinkedIn's blue. |
