# SP5: Backend Infrastructure Constants Extraction

**Sub-phase:** 5 of 7
**Plan task:** 4E (Backend Infrastructure Constants Extraction)
**Dependencies:** SP4 (config.py has been modified with LLM/embedding config — build on it)
**Estimated complexity:** S (smallest backend sub-phase)
**Changes code:** Yes

---

## Objective

Move log rotation settings and pagination defaults into config. Fix the log rotation mismatch (code says 500MB/10d, decision doc says 50MB/30d). Document constants that intentionally stay hardcoded.

---

## Steps

### 1. Add infrastructure config fields to config.py

Add to `LinkedOutSettings` in `backend/src/shared/config/config.py`:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `log_rotation` | `str` | `50 MB` | Log file rotation size (loguru format string) |
| `log_retention` | `str` | `30 days` | Log file retention period (loguru format string) |
| `default_page_size` | `int` | `20` | Default pagination page size |

**Note:** Check if Phase 3 already added `log_rotation` / `log_retention` fields. If so, verify the defaults match the decision doc (50 MB, 30 days). If not, add them.

### 2. Update `logger.py` to read from config

In `backend/src/shared/utilities/logger.py`:
- Replace hardcoded `500 MB` rotation with config value (default: `50 MB` per decision doc)
- Replace hardcoded `10 days` retention with config value (default: `30 days` per decision doc)
- This simultaneously fixes the mismatch between code and decision doc

**Important:** The values change from what's currently in code (500MB → 50MB, 10d → 30d). This is intentional — the decision doc values are the approved values. Phase 3 should have already fixed this; Phase 4 makes them configurable.

### 3. Document hardcoded constants that stay

Add brief comments to these files explaining WHY the constants stay hardcoded:

**`backend/src/shared/common/nanoids.py`:**
```python
# Nanoid sizes are data-format constants. Changing them would break existing IDs in the database.
# 21 chars: standard entity IDs. 8 chars: timestamped suffix component.
# These are NOT user-configurable — they are part of the data contract.
```

**Entity ID prefixes** (wherever they're defined — e.g., `co_`, `cp_`, etc.):
```python
# Entity ID prefix is a data-format constant. Changing it would break existing records.
# Not user-configurable.
```

### 4. Update config.yaml template

```yaml
# ── Logging ──────────────────────────────────────────────
# log_rotation: 50 MB              # Rotate log files at this size
# log_retention: 30 days           # Keep rotated logs for this long

# ── Pagination ───────────────────────────────────────────
# default_page_size: 20            # Default page size for list endpoints
```

---

## Verification

- [ ] `log_rotation` field exists in `LinkedOutSettings` with default `"50 MB"`
- [ ] `log_retention` field exists in `LinkedOutSettings` with default `"30 days"`
- [ ] `default_page_size` field exists in `LinkedOutSettings` with default `20`
- [ ] `logger.py` reads rotation and retention from config
- [ ] `logger.py` no longer has hardcoded `500 MB` or `10 days` (these were wrong per decision doc)
- [ ] `nanoids.py` has a comment explaining why sizes stay hardcoded
- [ ] Backend boots without errors with default config
- [ ] Run: `grep -rn "500 MB\|10 days" backend/src/shared/utilities/logger.py` — zero results

---

## Notes

- This is the smallest backend sub-phase. Quick to execute.
- The log rotation fix (500→50, 10→30) aligns code with the approved decision in `docs/decision/logging-observability-strategy.md`. Phase 3 was supposed to set the correct defaults; Phase 4 externalizes them. If Phase 3 already fixed the values, this step just confirms and adds config wiring.
- Verify the current state of `logger.py` before making changes — Phase 3 may have already corrected the rotation/retention values.
