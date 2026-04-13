# Execution Manifest: Batch Embedding Fix

## How to Execute

Each sub-phase runs in a **separate Claude context**. For each sub-phase:
1. Start a new Claude session
2. Tell Claude: "Read `docs/execution/batch_embedding_fix/_shared_context.md` then execute `docs/execution/batch_embedding_fix/sp1_harden_mocks_and_batch_tests/plan.md`"
3. After completion, update the Status column below

## Sub-Phase Overview

| # | Sub-phase | Directory/File | Depends On | Status | Notes |
|---|-----------|---------------|-----------|--------|-------|
| 1 | Harden mocks + add TestProcessBatch | `sp1_harden_mocks_and_batch_tests/` | -- | Not Started | Single file change |

Status: Not Started -> In Progress -> Done -> Verified -> Skipped

## Dependency Graph

```
[SP1: Harden mocks + batch tests] → Done
```

## Execution Order

### Sequential Group 1
1. Sub-phase 1: Harden mocks + add TestProcessBatch

## Progress Log
