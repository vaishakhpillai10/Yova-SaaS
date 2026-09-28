# UI Redesign — Presentation Layer Only

**Date:** 2026-08-16
**Scope:** Visual design system + template presentation across all pages.
**Logic changes:** None. No `.py` file was modified.

---

## Verification

| Check | Result |
|---|---|
| `manage.py check` | No issues |
| Template parse (all 27) | 27 OK / 0 failed |
| Page render smoke test (15 pages, real seeded data, logged in) | 15 × HTTP 200 |
| Test suite | 49/50 pass — the 1 error is **pre-existing** and reproduces identically on the untouched original (`test_full_work_order_controlled_flow`, segregation-of-duties assertion) |
| Undefined CSS classes | 0 remaining (was 14) |
| Files changed | 20 — 1 CSS, 19 templates. **0 Python files.** |

---

## What was actually wrong

The audit found real defects, not just taste issues:

1. **The login page had zero CSS.** `login-bg`, `login-wrap`, `login-hero`, `login-card` were referenced in the template but defined nowhere. The first screen every user sees was rendering as unstyled HTML.
2. **Form validation errors were not red.** `.text-danger` was undefined, so field errors on every form in the system rendered as plain body text.
3. **Form help text and checkbox labels were unstyled** — `.form-text`, `.form-check-label` undefined.
4. **`.process-box`** — the workflow explainer strip on the maintenance request, work order, scheduling and reliability pages — was undefined and rendered as a bare paragraph.
5. **`.list-group` / `.list-group-item`** on the engineering dashboard were undefined; the pending-approvals list had no separators or padding.
6. **`.text-bg-danger`** ("Production stopped" badge) was undefined, so a safety-critical badge rendered with no background.
7. **Four dashboards were left behind by the earlier rework.** `engineering`, `mm`, `store` and `utility` still used the old `kpi` / `card-soft` classes, and their `<canvas>` elements had no `.chart-shell` wrapper — so those charts had no height constraint and did not size responsively.
8. **30 empty states across 14 templates** were bare `<td colspan="n">No records.</td>` — unpadded, unstyled, left-aligned.
9. **Non-renderable font weights.** The stylesheet used `font-weight: 950 / 880 / 850 / 760`. With a system font stack these snap to the nearest real weight, so the intended hierarchy was not being expressed.

---

## Design direction

The previous look was consumer-SaaS decorative: 22–30px corner radii, glassmorphism with `backdrop-filter`, a radial-gradient page background, and large diffuse glow shadows.

That works against this product. This is a CMMS used by planners, technicians and store staff — often on tablets, often in bright light — to scan dense operational data quickly. The redesign moves it to a **control-room aesthetic**: flat, dense, high-contrast, precise.

| | Before | After |
|---|---|---|
| Page background | Radial gradient | Flat `#f4f6f9` |
| Panel radius | 22px / 30px | 10px |
| Shadows | `0 24px 70px` glow | `0 1px 2px` hairline |
| Sidebar | Floating pill, blurred | Docked, hairline border |
| Font weights | 950 / 880 / 850 / 760 | 500 / 600 / 650 / 700 |
| KPI accent | Decorative corner blob | Status rail on the top edge |
| Numbers | Proportional | `tabular-nums` — columns align |

**Signature choice:** tabular figures on every metric, table cell and KPI. In a product whose entire job is comparing quantities down a column — stock levels, planned hours, utilisation percentages — digits that don't align are a real legibility cost. It's the one deliberate, domain-specific decision in the system.

---

## Changes by file

**`static/asset_mgmt/css/app.css`** — rewritten as a documented design system. Token block (colour, radius, elevation, 4px spacing scale, type), then components in labelled sections. Every pre-existing class name is preserved, so no template depends on something that vanished. Added: all 14 previously-undefined classes, focus-visible rings throughout, `prefers-reduced-motion`, and a print stylesheet (work orders and PM plans get printed on the shop floor).

**`login.html`** — rebuilt as a two-panel split: dark brand panel with the logo, light form panel. Collapses to a single column under 1100px. Button relabelled "Login" → "Sign in" to match the heading.

**`engineering_dashboard.html`, `mm_dashboard.html`, `store_dashboard.html`, `utility_dashboard.html`** — migrated onto the `dashboard-*` system used by the three already-reworked dashboards. KPI cards now carry a label, value and a line of context; charts are wrapped in `.chart-shell` so they size correctly; tables gained proper headers and empty states. All context variables, `{% url %}` names and chart JS are unchanged.

**14 further templates** — empty-state cells given `.empty-cell`, which supplies padding, centring and muted colour. Where a table was rewritten, the message was also rewritten to say what the state means and what to do next ("Stock levels are healthy — no item is below its minimum level") rather than "No records."

---

## Not done — needs your input

- **`module_list.html`** (15KB) and **`work_order_detail.html`** (14KB) are the two densest pages. They render correctly and picked up the new system, but both would benefit from a structural pass that I'd rather do with your direction on what matters most on each.
- **Dark mode** — the token structure supports it now, but no dark palette is defined.
- **`.table-sticky`** is defined and ready; add the class to long registers (asset list, audit log) if you want sticky headers on scroll.
