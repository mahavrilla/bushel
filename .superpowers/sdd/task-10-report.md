# Task 10 Report: Cart tab — price-insight badges + inline comparison

## What Was Implemented

### Files Changed
- `frontend/src/recipes/CartTab.test.tsx`: Updated `baseMatch` fixtures with `alternatives: []` / `insight: null` fields; added `multiMatch` fixture with a 2-UPC item plus insight; added two new tests (badge display, expand+switch).
- `frontend/src/recipes/ProductPickerModal.tsx`: Added optional `title` and `chooseLabel` props (defaults preserve existing behavior — "Choose a product" / "Choose").
- `frontend/src/recipes/CartTab.tsx`: Full implementation per brief — new api imports (`addAlternative`, `removeAlternative`, `switchPick`); `Alternative` type import; `expanded` Set state + `pickerMode` state; `toggleExpand`, `choosePick`, `dropAlternative` helpers; updated `pick` to branch on `pickerMode`; `money` formatter; `badges()` renderer (cheaper-alt Pill, on-sale Pill, out-of-stock Pill, Compare/Hide toggle); `altRow()` renderer (description, current marker, sale price with strikethrough, unit price, Use this button, remove button); inline expanded comparison section in `row()`; updated `ProductPickerModal` invocation with `key`, `title`, `chooseLabel`, and reset-on-close.

## TDD Evidence

### RED (before implementation)
Command: `cd frontend && npm test -- CartTab`

Result:
```
src/recipes/CartTab.test.tsx (6 tests | 2 failed)
× CartTab > shows a cheaper-alt badge for a multi-UPC item
× CartTab > expands the comparison and switches the pick
```
Both new tests failed as expected — no badges or Compare button rendered.

### GREEN (after implementation)
Command: `cd frontend && npm test -- CartTab`

Result:
```
✓ src/recipes/CartTab.test.tsx (6 tests) 108ms
Test Files  1 passed (1)
Tests  6 passed (6)
```

## Full Typecheck + Suite

Command: `cd frontend && npx tsc -b && npm test`

TypeScript: clean (no output = no errors)

Full suite:
```
Test Files  29 passed (29)
Tests  112 passed (112)
```

## Commit

SHA: ec7c818
Message: feat(web): multi-UPC price-insight badges and inline comparison in Cart

## Self-Review

- **Single-UPC rows unchanged**: `badges()` returns `null` when `it.insight` is null, so no extra UI on rows without insight. The `expanded.has(item_id)` gate ensures the comparison section only renders when explicitly expanded.
- **Picker mode resets after use**: `pick()` calls `setPickerMode("confirm")` in `finally`; `onClose` also calls `setPickerMode("confirm")`. The `key` prop on `ProductPickerModal` is `${openItem.item_id}-${pickerMode}` ensuring the modal remounts when mode changes.
- **switchPick wired correctly**: `choosePick(itemId, upc)` → `switchPick(itemId, upc)` → `setMatch(result)`.
- **removeAlternative wired correctly**: `dropAlternative(itemId, upc)` → `removeAlternative(itemId, upc)` → `setMatch(result)`.
- **addAlternative wired correctly**: `pick()` in "alternative" mode → `addAlternative(openItem.item_id, body)`.
- **Badge text matches test expectations**: `↓ $1.20 cheaper alt` for 120 cents (regex `/\$1\.20 cheaper/i` matches); `on sale` Pill (regex `/on sale/i` matches).

## Concerns

None. All 112 tests pass, typecheck clean, implementation matches the brief exactly.

## Final-review fixes

### What Was Changed

**Fix 1 (CRITICAL) — token fetch crash in `get_prices`**
- File: `backend/app/matching/price_cache.py`
- Added `import httpx` at the top of the module.
- Wrapped `client.fetch_client_token()` in `try/except (KrogerError, httpx.HTTPError)` that returns `out` (cached results so far) on failure, preventing the error from propagating through `get_match_state` into `GET /list/match`.
- Widened the per-UPC `except KrogerError` to `except (KrogerError, httpx.HTTPError)` to also catch raw transport errors.

**Fix 2 (IMPORTANT) — `confirm_product` route missing Kroger client**
- File: `backend/app/matching/router.py`
- Added `kroger: KrogerClient = Depends(get_kroger_client)` to `confirm_product` handler signature.
- Changed `service.get_match_state(db)` to `service.get_match_state(db, kroger)`.

**Fix 3 (MINOR) — dead import in `service.py`**
- File: `backend/app/matching/service.py`
- Removed `SwitchPickRequest` from the `from app.matching.schemas import (...)` block. It remains defined in `schemas.py` and imported in `router.py` where it is used.

### Fix 1 RED/GREEN Evidence

Command: `DATABASE_URL="postgresql+psycopg://bushel:bushel@localhost:5432/bushel" uv run pytest tests/test_price_cache.py::test_token_failure_degrades_to_cached -v`

RED (before fix):
```
FAILED tests/test_price_cache.py::test_token_failure_degrades_to_cached - app.kroger.client.KrogerUnavailableError: down
1 failed in 0.22s
```

GREEN (after fix):
```
PASSED tests/test_price_cache.py::test_token_failure_degrades_to_cached
1 passed in 0.17s
```

### Covering Tests

Command: `DATABASE_URL="postgresql+psycopg://bushel:bushel@localhost:5432/bushel" uv run pytest tests/test_price_cache.py tests/test_matching_router.py -v`

Result: 18 passed in 0.90s

### Full Suite

Command: `DATABASE_URL="postgresql+psycopg://bushel:bushel@localhost:5432/bushel" uv run pytest -q`

Result: 273 passed, 12 warnings in 1.57s

### Files Changed

- `backend/app/matching/price_cache.py` — `import httpx`; wrap token fetch; widen per-UPC except
- `backend/app/matching/router.py` — add `kroger` dependency to `confirm_product`; pass to `get_match_state`
- `backend/app/matching/service.py` — remove dead `SwitchPickRequest` import
- `backend/tests/test_price_cache.py` — add `test_token_failure_degrades_to_cached` regression test
