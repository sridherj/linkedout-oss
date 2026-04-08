# Learnings

---

## 2026-04-07 | TaskOS Run State Management | taskos-wrap-up

**Learning:** Status-transition endpoints should be idempotent and self-healing -- a "recheck" on a terminal state with incomplete data should re-process, not silently no-op.

**Context:** When an agent run was marked "completed" without its output.json populated, the recheck endpoint refused to process it (it only acts on non-terminal states). This required manual DB state reset before recheck would work. Applies to any system with async job completion and a reconciliation/recheck mechanism.

**Tags:** orchestration, idempotency, state-machine, taskos, error-recovery

---

## 2026-04-07 | Parent-Child Run Consistency | taskos-wrap-up

**Learning:** In parent-child async workflows, parent output can become stale when children complete after the parent writes its summary. Design for eventual consistency -- parent summaries should be lazily computed or re-derived on read.

**Context:** The parent exploration run wrote output.json containing error messages about a child that was still running. When the child later completed successfully, the parent's output remained stale. Required manual update of parent output.json and re-triggering recheck.

**Tags:** orchestration, eventual-consistency, parent-child, taskos

---
