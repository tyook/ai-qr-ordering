# Frontend Guidelines

## Tech Stack

- **Framework:** Next.js 14 (App Router, React Server Components)
- **Language:** TypeScript (strict mode)
- **Styling:** Tailwind CSS + shadcn/ui (New York variant) + Radix UI primitives
- **Icons:** Lucide React
- **State Management:** Zustand (stores in `src/stores/`)
- **Data Fetching:** `@tanstack/react-query` with custom hooks
- **API Client:** `src/lib/api.ts` (`apiFetch` wrapper with JWT handling)
- **Path Alias:** `@/*` maps to `src/*`

## Architecture Rules

### 1. Data Fetching: Always Use Custom Hooks

Never call `apiFetch` or `fetch` directly inside components. Always create a custom hook.

**Pattern — Query hook (read):**

```tsx
// src/hooks/use-menu.ts
import { useQuery } from "@tanstack/react-query";
import { fetchMenu } from "@/lib/api";

export function useMenu(slug: string) {
  return useQuery({
    queryKey: ["menu", slug],
    queryFn: () => fetchMenu(slug),
    enabled: !!slug,
  });
}
```

**Pattern — Mutation hook (write):**

```tsx
// src/hooks/use-confirm-order.ts
import { useMutation } from "@tanstack/react-query";
import { confirmOrder } from "@/lib/api";

export function useConfirmOrder() {
  return useMutation({
    mutationFn: confirmOrder,
    onSuccess: (data) => {
      // handle success
    },
  });
}
```

**Usage in component:**

```tsx
function MenuPage({ slug }: { slug: string }) {
  const { data: menu, isLoading, error } = useMenu(slug);

  if (isLoading) return <LoadingSkeleton />;
  if (error) return <ErrorMessage error={error} />;

  return <MenuList categories={menu.categories} />;
}
```

**Rules:**
- One hook per API endpoint or logical data need
- Hooks live in `src/hooks/` with the naming convention `use-<resource>.ts`
- Queries use `queryKey` arrays for proper cache invalidation
- Mutations use `useMutation` with `onSuccess`/`onError` callbacks
- Never manage `loading`/`error` state with `useState` for API calls — react-query handles this

### 2. Components: Reusable First

**Shared components** go in `src/components/`. These are generic, reusable across pages.

**Page-specific components** go in `src/app/<route>/components/`. These are tied to a single page's logic.

**When to extract a component:**
- Used in 2+ places → extract to `src/components/`
- Has its own loading/error/empty states → extract
- Exceeds ~80 lines → consider splitting

**Component file conventions:**
- One component per file
- File name matches component name in kebab-case: `OrderCard.tsx` → `order-card.tsx` (for new files; existing files may use PascalCase)
- Export the component as a named export
- Props defined as a `type` or `interface` at the top of the file

**Pattern — Reusable component:**

```tsx
// src/components/price-display.tsx
interface PriceDisplayProps {
  amount: number;
  currency?: string;
  className?: string;
}

export function PriceDisplay({ amount, currency = "USD", className }: PriceDisplayProps) {
  const formatted = new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
  }).format(amount);

  return <span className={cn("font-medium", className)}>{formatted}</span>;
}
```

### 3. Styling: Use shadcn/ui Components and Tailwind

- Use existing `src/components/ui/*` components before writing custom markup
- Use `cn()` from `@/lib/utils` to merge class names conditionally
- Use component `variant` props (via CVA) for style variations — don't duplicate classes
- When a style pattern repeats 3+ times, extract it into a reusable component, not a CSS class
- Never use inline `style={{}}` unless absolutely necessary (dynamic values only)

**Adding new shadcn/ui components:**

```bash
npx shadcn@latest add <component-name>
```

### 4. State Management

**Use Zustand stores** (`src/stores/`) for:
- Global state shared across pages (auth, preferences)
- Complex state machines (order flow)

**Use React Query** for:
- All server state (API data, caching, refetching)

**Use local `useState`** for:
- UI-only state (modal open/close, form inputs, toggles)

**Never:**
- Store server data in Zustand — use React Query's cache instead
- Duplicate state between Zustand and components

### 5. Types

- All types live in `src/types/index.ts` or domain-specific files in `src/types/`
- API response types must match the backend serializers
- Use `interface` for object shapes, `type` for unions/intersections
- No `any` — use `unknown` and narrow with type guards if needed

### 6. File Organization

```
src/
  app/                    # Next.js routes (pages + layouts)
    <route>/
      page.tsx            # Page component
      components/         # Page-specific components
  components/             # Shared reusable components
    ui/                   # shadcn/ui primitives (do not edit unless customizing)
  hooks/                  # Custom React hooks (use-*.ts)
  lib/                    # Utilities, API client, constants
  stores/                 # Zustand stores (*-store.ts)
  types/                  # TypeScript type definitions
```

### 7. Error and Loading States

- Every data-fetching component must handle loading, error, and empty states
- Use React Query's `isLoading`, `error`, `data` — not manual `useState`
- Create reusable `<LoadingSkeleton />` and `<ErrorMessage />` components for consistency

### 8. Naming Conventions

| Item | Convention | Example |
|------|-----------|---------|
| Hook files | `use-<name>.ts` | `use-menu.ts` |
| Hook functions | `use<Name>` | `useMenu` |
| Store files | `<name>-store.ts` | `order-store.ts` |
| Component files | `PascalCase.tsx` or `kebab-case.tsx` | `OrderCard.tsx` |
| Utility files | `kebab-case.ts` | `format-price.ts` |
| Type files | `kebab-case.ts` | `index.ts` |

### 9. Do NOT

- Use `useEffect` + `useState` for data fetching — use React Query hooks
- Create god components that do everything — split into smaller pieces
- Hardcode API URLs — use `apiFetch` from `@/lib/api`
- Use `react-hot-toast` for new code — use the `useToast` hook from `@/hooks/use-toast`
- Mix server and client data in Zustand stores
- Skip TypeScript types with `any` or `as any` casts
