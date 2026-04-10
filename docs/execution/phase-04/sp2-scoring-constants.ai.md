# SP2: Backend Scoring Constants Extraction

**Sub-phase:** 2 of 7
**Plan task:** 4B (Backend Scoring Constants Extraction)
**Dependencies:** SP1 (audits completed — reference `docs/audit/backend-constants-audit.md`)
**Estimated complexity:** M
**Changes code:** Yes

---

## Objective

Move all affinity scoring weights, Dunbar tier thresholds, seniority boosts, and recency thresholds from hardcoded values in `affinity_scorer.py` into the config system via a nested `ScoringConfig` pydantic model.

---

## Steps

### 1. Create `ScoringConfig` nested model in config.py

Add a new `ScoringConfig(BaseModel)` class in `backend/src/shared/config/config.py` with all scoring constants as fields. Add a `scoring: ScoringConfig = ScoringConfig()` field to `LinkedOutSettings`.

**Constants to add:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `weight_career_overlap` | `float` | `0.40` | Career overlap scoring weight |
| `weight_external_contact` | `float` | `0.25` | External contact scoring weight |
| `weight_embedding_similarity` | `float` | `0.15` | Embedding similarity scoring weight |
| `weight_source_count` | `float` | `0.10` | Source count scoring weight |
| `weight_recency` | `float` | `0.10` | Recency scoring weight |
| `dunbar_inner_circle` | `int` | `15` | Dunbar inner circle threshold |
| `dunbar_active` | `int` | `50` | Dunbar active tier threshold |
| `dunbar_familiar` | `int` | `150` | Dunbar familiar tier threshold |
| `seniority_boosts` | `dict[str, float]` | `{"founder": 3.0, ...}` | Seniority boost multipliers (copy exact current values) |
| `external_contact_scores` | `dict[str, float]` | `{"phone": 1.0, "email": 0.7}` | External contact type scores (copy exact current values) |
| `career_normalization_months` | `int` | `36` | Career overlap normalization window |
| `recency_thresholds` | `list[tuple[int, float]]` | `[(12, 1.0), (36, 0.7), (60, 0.4)]` | Recency decay thresholds (months, score) |

**Env var override pattern:** `LINKEDOUT_SCORING__WEIGHT_CAREER_OVERLAP=0.35` (double underscore for nesting, per pydantic-settings convention).

### 2. Update `affinity_scorer.py` to read from config

In `backend/src/linkedout/intelligence/scoring/affinity_scorer.py`:
- Remove hardcoded constant definitions for all values listed above
- Import the settings/config (use the existing pattern for accessing `LinkedOutSettings`)
- Read all scoring values from config
- Ensure `AFFINITY_VERSION` stays at its current value (no scoring algorithm change — only config extraction)

### 3. Add scoring section to config.yaml template

Add a `scoring:` section to the config.yaml template (commented out, showing defaults with explanatory comments):

```yaml
# ── Scoring (Affinity Algorithm Tuning) ──────────────────
# scoring:
#   weight_career_overlap: 0.40       # Weight for career path overlap
#   weight_external_contact: 0.25     # Weight for external contact signals (phone, email)
#   weight_embedding_similarity: 0.15 # Weight for embedding vector similarity
#   weight_source_count: 0.10         # Weight for number of data sources
#   weight_recency: 0.10              # Weight for recency of interaction
#   dunbar_inner_circle: 15           # Top N connections for inner circle tier
#   dunbar_active: 50                 # Top N for active tier
#   dunbar_familiar: 150              # Top N for familiar tier
```

---

## Verification

- [ ] `ScoringConfig` model exists in `config.py` with all fields listed above
- [ ] `LinkedOutSettings` has a `scoring: ScoringConfig` field
- [ ] `affinity_scorer.py` has zero hardcoded scoring constants (all read from config)
- [ ] `AFFINITY_VERSION` in `affinity_scorer.py` is unchanged
- [ ] Default values in `ScoringConfig` match the previously hardcoded values exactly
- [ ] Backend boots without errors with default config (no YAML, no env vars)
- [ ] Run: `grep -rn "WEIGHT_CAREER_OVERLAP\|WEIGHT_EXTERNAL_CONTACT\|WEIGHT_EMBEDDING_SIMILARITY\|WEIGHT_SOURCE_COUNT\|WEIGHT_RECENCY" backend/src/ --include="*.py" | grep -v config.py | grep -v __pycache__` — should return zero results for hardcoded float assignments

---

## Notes

- Read the actual file first to capture the EXACT current values. The table above is from the plan — verify against the code.
- The nested pydantic model pattern with `BaseModel` (not `BaseSettings`) is correct for sub-config. Only the top-level `LinkedOutSettings` extends `BaseSettings`.
- For `seniority_boosts` and `external_contact_scores` dicts — read the actual current values from `affinity_scorer.py`. The plan only shows partial examples.
- For `recency_thresholds` — pydantic may need a custom type or validator for list of tuples. Consider `list[list[int | float]]` if tuples cause issues with YAML deserialization.
