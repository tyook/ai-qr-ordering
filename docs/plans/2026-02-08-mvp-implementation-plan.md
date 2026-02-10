# AI QR Ordering System - MVP Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Execute phases in order.

**Goal:** Build a working MVP where customers scan a QR code, speak/type an order in any language, an LLM parses it, and the order appears on a real-time kitchen dashboard.

**Architecture:** Monorepo with Django 4.2 backend (DRF + Channels) and Next.js 14 frontend. PostgreSQL + Redis for data and WebSocket support. LLM abstraction layer with OpenAI as default provider.

**Tech Stack:** Django 4.2, DRF, Django Channels, Next.js 14, TypeScript, Tailwind, shadcn/ui, Zustand, PostgreSQL 16, Redis 7, OpenAI API

---

## Phase Overview

| Phase | Name | Tasks | Depends On |
|-------|------|-------|------------|
| 0 | [Infrastructure & Scaffolding](./2026-02-08-mvp-phase-0-scaffolding.md) | 5 | - |
| 1 | [Backend Models & Auth](./2026-02-08-mvp-phase-1-backend-models-auth.md) | 6 | Phase 0 |
| 2 | [Backend Menu & Restaurant API](./2026-02-08-mvp-phase-2-backend-menu-restaurant-api.md) | 6 | Phase 1 |
| 3 | [Backend LLM & Order Parsing](./2026-02-08-mvp-phase-3-backend-llm-orders.md) | 4 | Phase 1, 2 |
| 4 | [Backend WebSocket & Kitchen](./2026-02-08-mvp-phase-4-backend-websocket-kitchen.md) | 3 | Phase 1, 3 |
| 5 | [Frontend Customer Ordering](./2026-02-08-mvp-phase-5-frontend-customer-ordering.md) | 5 | Phase 0, 3 |
| 6 | [Frontend Kitchen & Admin](./2026-02-08-mvp-phase-6-frontend-kitchen-admin.md) | 8 | Phase 0, 4, 5 |
| **Total** | | **37 tasks** | |

---

## Execution Order

```
Phase 0: Infrastructure & Scaffolding
    │
    ├── Phase 1: Backend Models & Auth
    │       │
    │       ├── Phase 2: Backend Menu & Restaurant API
    │       │       │
    │       │       └── Phase 3: Backend LLM & Order Parsing
    │       │               │
    │       │               └── Phase 4: Backend WebSocket & Kitchen
    │       │
    │       └── (Phase 5 can start after Phase 3)
    │
    ├── Phase 5: Frontend Customer Ordering
    │       │
    │       └── Phase 6: Frontend Kitchen & Admin
    │
    └── (Phases 5-6 frontend work can partially parallelize with backend)
```

**Recommended serial order:** 0 → 1 → 2 → 3 → 4 → 5 → 6

---

## Key Design Decisions

1. **LLM output is untrusted.** Every parsed item is validated against the database. Prices are always calculated server-side.

2. **Two-step ordering.** `parse` → customer confirms → `confirm`. The customer always reviews before submitting.

3. **Customer endpoints are unauthenticated.** No friction to order. JWT auth is only for restaurant owners/staff.

4. **Soft deletes for menu items.** `DELETE` deactivates rather than destroying, preserving order history integrity.

5. **Valid status transitions enforced.** Orders can only move: pending → confirmed → preparing → ready → completed.

6. **WebSocket only for kitchen.** REST for everything else. Keeps complexity contained.

---

## Post-MVP Notes

After all 6 phases are complete, the following are natural next steps (not in scope for this plan):

- Stripe payment integration
- Order history API endpoint for admin panel
- Sound notifications on kitchen dashboard
- Image upload for menu items
- Drag-and-drop menu reordering
- E2E tests with Playwright
