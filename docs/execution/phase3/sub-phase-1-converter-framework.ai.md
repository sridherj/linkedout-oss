# Sub-Phase 1: Converter Framework + All Converters

**Goal:** linkedin-ai-production
**Phase:** 3 — Import Pipeline + User-Triggered Enrichment
**Depends on:** Nothing (first sub-phase). Assumes Phase 2 complete (connection.sources already ARRAY).
**Estimated effort:** 3-4h
**Source plan sections:** 3.1.1, 3.1.2, 3.1.3, 3.1.4

---

## Objective

Build the converter abstraction layer, implement all 4 CSV converters (LinkedIn, Google Job, Google Phone, Google Email-only), and wire them into a registry with auto-detection. This is the parsing foundation for the import pipeline.

## Context

- Contact format mappings are documented in `docs/reference/contact_format_mapping.md`
- Phase 2 already migrated `connection.sources` from Text to ARRAY(Text) (reconciliation C2)
- Converters write `sources` as a list — no migration needed here

## Pre-Flight Checks

```bash
# Verify connection.sources is already ARRAY
python -c "from src.linkedout.connection.entities.connection_entity import ConnectionEntity; print(type(ConnectionEntity.sources.type))"
# Verify reference docs exist
cat docs/reference/contact_format_mapping.md | head -5
```

## New Dependencies

Add to `pyproject.toml` (if not already present):
```toml
phonenumbers = ">=8.13"   # Phone normalization for Google Phone converter
```

---

## Step 1: Converter Interface + ParsedContact Schema (3.1.1)

### Files to Create

- `src/linkedout/import_pipeline/__init__.py`
- `src/linkedout/import_pipeline/converters/__init__.py`
- `src/linkedout/import_pipeline/converters/base.py`
- `src/linkedout/import_pipeline/schemas.py`

### ParsedContact Schema

```python
@dataclass
class ParsedContact:
    first_name: str | None
    last_name: str | None
    full_name: str | None
    email: str | None
    phone: str | None          # E.164 normalized
    company: str | None
    title: str | None
    linkedin_url: str | None   # Normalized: lowercase, strip trailing slash
    connected_at: date | None
    raw_record: dict           # Original row as dict
    source_type: str           # e.g. 'linkedin_csv', 'google_contacts_job'
```

### BaseContactConverter Interface

```python
class BaseContactConverter(ABC):
    source_type: str  # Class-level constant

    @abstractmethod
    def parse(self, file: BinaryIO) -> tuple[list[ParsedContact], list[tuple[int, dict, str]]]:
        """Parse uploaded file into normalized contacts.
        Returns (parsed_contacts, failed_rows) where failed_rows = [(row_number, raw_data, error_reason)]
        """

    @abstractmethod
    def detect(self, file: BinaryIO) -> bool:
        """Return True if this converter can handle the file."""
```

### Verification

- Unit test: `ParsedContact` validates correctly
- Interface is importable: `from src.linkedout.import_pipeline.converters.base import BaseContactConverter`

---

## Step 2: LinkedIn CSV Converter (3.1.2)

### File

`src/linkedout/import_pipeline/converters/linkedin_csv.py`

### Behavior (from S5 mapping)

- Skip 3-line preamble (detect header row containing "First Name")
- Map columns per `contact_format_mapping.md` section 2.1
- `connected_at` parsed via `datetime.strptime(val, "%d %b %Y").date()` (flexible: handle both `7 Feb` and `07 Feb`)
- `linkedin_url` normalized: lowercase, strip trailing `/`, strip query params
- `email` → None if empty string
- `full_name` = `f"{first_name} {last_name}".strip()`
- Store entire row in `raw_record`
- `source_type = 'linkedin_csv'`

### Edge Cases (from S5)

- Nicknames in parens in last_name: `(UT)` — keep as-is, don't strip
- Comma in Position: handled by csv.reader quoting
- Missing company/position (~4%): leave as None

### Per-Row Error Handling (Decision #8)

Wrap each row's parsing in try/except. On failure, collect into `failed_rows` list with `(row_number, raw_data, error_reason)`. Return `(parsed_contacts, failed_rows)`. Continue processing remaining rows.

### Test File

`tests/unit/import_pipeline/test_linkedin_csv_converter.py`

### Tests

- Sample CSV rows (header + 5 data rows including edge cases)
- Preamble skipping
- Date parsing for both `7 Feb 2026` and `22 Feb 2026`
- Malformed row handling (wrong column count, unparseable date) → row in failed_rows, others still parsed

---

## Step 3: Google Contacts Converters x3 (3.1.3)

### Files

- `src/linkedout/import_pipeline/converters/google_job.py` — `GoogleJobContactConverter`
- `src/linkedout/import_pipeline/converters/google_phone.py` — `PhoneContactConverter`
- `src/linkedout/import_pipeline/converters/google_email.py` — `EmailOnlyContactConverter`

### GoogleJobContactConverter (31-column format)

- `first_name` from `Given Name`, `last_name` from `Family Name`, `full_name` from `Name`
- `email` from `E-mail 1 - Value` (100% populated)
- No phone/company/title/linkedin_url
- Website field is Google Profile URL — do NOT map to linkedin_url
- `source_type = 'google_contacts_job'`

### PhoneContactConverter (67-column Outlook format)

- Phone normalization via `phonenumbers` library → E.164
  - Default country: India (+91) for bare numbers
  - Coalesce: Mobile Phone > Primary Phone > Home Phone
- Name cleaning: strip parenthetical annotations from First Name / Middle Name
- 38% missing last names — leave as None
- `source_type = 'contacts_phone'`

### EmailOnlyContactConverter (27-column format)

- First Name validation: reject if contains `@` (email stored as name), reject if purely numeric
- Email is only reliable field (100%)
- Mark with lower quality indicator: `source_type = 'gmail_email_only'`

### Per-Row Error Handling (Decision #8)

Same pattern as LinkedIn CSV — per-row try/except, collect `failed_rows`.

### Test File

`tests/unit/import_pipeline/test_google_converters.py`

### Tests

- Unit tests per converter with sample rows from S5 documentation
- Include malformed row tests
- Phone normalization tests (Indian numbers, US numbers, bare digits)
- Name validation tests for EmailOnly (reject `@`-containing, numeric names)

---

## Step 4: Converter Registry + Source Type Detection (3.1.4)

### File

`src/linkedout/import_pipeline/converters/registry.py`

### Registry

```python
CONVERTER_REGISTRY: dict[str, type[BaseContactConverter]] = {
    'linkedin_csv': LinkedInCsvConverter,
    'google_contacts_job': GoogleJobContactConverter,
    'contacts_phone': PhoneContactConverter,
    'gmail_email_only': EmailOnlyContactConverter,
}

def get_converter(source_type: str) -> BaseContactConverter:
    """Get converter by explicit source_type."""

def detect_converter(file: BinaryIO) -> BaseContactConverter | None:
    """Auto-detect file format. Returns None if unrecognized."""
```

### Auto-Detection Strategy

1. Read first 5 lines
2. LinkedIn CSV: header contains "First Name,Last Name,URL,Email Address"
3. Google Job: header contains "Given Name" AND "E-mail 1 - Value" AND "Group Membership"
4. Phone contacts: header contains "Mobile Phone" AND 60+ columns
5. Email-only: header contains "E-mail 1 - Value" AND "Labels" AND column count < 30

### Tests

- Detection test with sample headers from each format
- `get_converter` with valid and invalid source_type

---

## Completion Criteria

- [ ] `ParsedContact` dataclass and `BaseContactConverter` ABC created
- [ ] LinkedIn CSV converter implemented with preamble skip, date parsing, URL normalization
- [ ] All 3 Google converters implemented (Job, Phone, Email-only)
- [ ] Phone normalization via `phonenumbers` library working
- [ ] Converter registry with auto-detection working
- [ ] Per-row error handling in all converters (Decision #8)
- [ ] All unit tests pass: `pytest tests/unit/import_pipeline/ -v`
- [ ] `phonenumbers` dependency added to pyproject.toml

## Verification

```bash
# Run unit tests for this sub-phase
pytest tests/unit/import_pipeline/test_linkedin_csv_converter.py tests/unit/import_pipeline/test_google_converters.py -v

# Verify imports work
python -c "from src.linkedout.import_pipeline.converters.registry import get_converter, detect_converter; print('OK')"

# Run full test suite to check nothing broken
precommit-tests
```
