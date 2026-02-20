# ThemeProvider Design — Dual Theme System

## Overview

Apply the landing page's orange/amber identity across all customer-facing pages, and a separate slate/blue theme for admin/kitchen pages. A `ThemeProvider` enables easy theme switching via CSS variables.

## Architecture

- `ThemeProvider` React context determines theme from URL pathname
- Applies `data-theme="customer"` or `data-theme="admin"` attribute
- CSS variables in `globals.css` define both token sets
- shadcn/ui components automatically pick up the correct colors — zero changes needed to component files

### Route Mapping

- `/admin/*`, `/kitchen/*` -> `admin` theme
- Everything else -> `customer` theme

## Color Tokens

### Customer Theme (orange/amber — warm, inviting)

| Token | HSL Value | Equivalent |
|---|---|---|
| --primary | 36 96% 45% | amber-600 |
| --primary-foreground | 0 0% 100% | white |
| --accent | 48 100% 96% | amber-50 |
| --accent-foreground | 22 78% 25% | amber-900 |
| --ring | 38 92% 50% | amber-500 |
| --border | 36 30% 85% | warm gray |
| --muted | 40 20% 96% | warm gray-50 |
| --muted-foreground | 25 10% 40% | warm gray-600 |
| --secondary | 40 20% 94% | warm gray-100 |
| --secondary-foreground | 22 20% 20% | warm gray-900 |

### Admin Theme (slate/blue — calm, professional)

| Token | HSL Value | Equivalent |
|---|---|---|
| --primary | 217 33% 17% | slate-800 |
| --primary-foreground | 0 0% 100% | white |
| --accent | 214 100% 97% | blue-50 |
| --accent-foreground | 222 47% 11% | slate-900 |
| --ring | 217 91% 60% | blue-500 |
| --border | 214 20% 85% | slate-200 |
| --muted | 210 20% 96% | cool gray-50 |
| --muted-foreground | 215 16% 47% | slate-500 |
| --secondary | 210 20% 94% | cool gray-100 |
| --secondary-foreground | 222 47% 11% | slate-900 |

### Shared (both themes)

- `--background`: white / near-black (dark)
- `--foreground`: near-black / white (dark)
- `--destructive`: red (unchanged)
- `--radius`: 0.5rem (unchanged)

## File Changes

### New: `src/components/ThemeProvider.tsx`

- React context + provider
- Route-based theme detection via `usePathname()`
- Exposes `useTheme()` hook
- Applies `data-theme` attribute to wrapper div

### Modified: `src/app/globals.css`

- Replace `:root` with `[data-theme="customer"]` and `[data-theme="admin"]` blocks
- Add `.dark [data-theme="customer"]` and `.dark [data-theme="admin"]` variants

### Modified: `src/app/layout.tsx`

- Wrap children in `<ThemeProvider>`

### Modified: `src/app/page.tsx`

- Replace hardcoded amber/orange Tailwind classes with semantic `bg-primary`, `text-primary` where appropriate
- Keep decorative elements (glow orb, gradient washes) as explicit amber/orange — they're landing-page-specific

### Unchanged

- All 14 shadcn/ui components (already use semantic classes)
- Header.tsx / CustomerHeader.tsx
- Tailwind config structure
- Order flow components (inherit customer theme automatically)
