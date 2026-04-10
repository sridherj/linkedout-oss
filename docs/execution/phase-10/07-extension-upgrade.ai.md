# Sub-Phase 07: Extension Upgrade

**Source task:** 10F
**Complexity:** M
**Dependencies:** Sub-phase 05 (core upgrade implementation)

## Objective

Add extension upgrade support to `/linkedout-upgrade`. If the user has the Chrome extension installed, the upgrade flow downloads the latest extension zip from GitHub Releases and provides re-sideload instructions.

## Context

Read `_shared_context.md` for project-level context. Key points:
- Extension zip published as GitHub Release asset (defined in Phase 12B)
- Downloads to `~/linkedout-data/extension/`
- Extension version matches backend version for v1 (released together)
- Extension update is non-blocking — failure doesn't stop the upgrade

## Deliverables

### Files to Create

1. **`backend/src/linkedout/upgrade/extension_updater.py`**

   - `check_extension_installed() -> bool`:
     - Check for `~/linkedout-data/extension/` directory or extension config marker
     - Return whether the user has previously installed the extension
   
   - `download_extension_zip(version: str) -> Path`:
     - Download from GitHub Releases: `linkedout-extension-v{version}.zip`
     - Save to `~/linkedout-data/extension/linkedout-extension-v{version}.zip`
     - Show download progress
     - Return path to downloaded file
   
   - `verify_checksum(path: Path, expected_sha256: str) -> bool`:
     - Compute SHA256 of downloaded file
     - Compare against expected checksum from release metadata
     - Return True if match, False otherwise
   
   - `get_sideload_instructions() -> str`:
     - Return formatted instructions:
       1. Open `chrome://extensions`
       2. Remove old LinkedOut extension
       3. Drag-and-drop new zip (or "Load unpacked" after extracting)
     - Use exact text from UX design doc (sub-phase 01)

### Files to Modify

2. **`backend/src/linkedout/upgrade/upgrader.py`** (extend from sub-phase 05)
   - Add extension update step between post-upgrade check and "What's New"
   - Step is conditional: only runs if `check_extension_installed()` returns True
   - On download failure: log error, show warning, continue upgrade (non-blocking)
   - On success: show sideload instructions as part of upgrade output
   - Include in upgrade report's `next_steps` array

### Tests to Create

3. **`backend/tests/unit/upgrade/test_extension_updater.py`**
   - `check_extension_installed()`: directory exists → True, missing → False
   - `download_extension_zip()`: mocked HTTP download, correct save path
   - `verify_checksum()`: matching checksum → True, mismatch → False
   - `get_sideload_instructions()`: returns non-empty string with key phrases
   - Download failure handled gracefully (returns error, doesn't raise)
   - Integration with upgrader: extension step appears in report when installed
   - Integration with upgrader: extension step skipped when not installed

## Acceptance Criteria

- [ ] Detects if extension was previously installed
- [ ] Downloads latest extension zip from GitHub Releases
- [ ] Saves to `~/linkedout-data/extension/linkedout-extension-v{version}.zip`
- [ ] Verifies SHA256 checksum
- [ ] Shows re-sideload instructions on success
- [ ] Does NOT attempt to auto-install the extension
- [ ] Download failure is non-blocking (upgrade continues)
- [ ] Extension update step appears in upgrade report
- [ ] All unit tests pass with mocked HTTP

## Verification

```bash
# Run extension updater tests
cd backend && python -m pytest tests/unit/upgrade/test_extension_updater.py -v

# Verify integration with upgrader
cd backend && python -m pytest tests/unit/upgrade/test_upgrader.py -v -k "extension"
```

## Notes

- The GitHub Release asset URL format needs to match what Phase 12B defines for extension releases
- For v1, the checksum may be embedded in the release description or as a separate `.sha256` file
- The download progress display should use the same progress pattern as other CLI operations
- Consider: if the user never installed the extension, don't mention it during upgrade
