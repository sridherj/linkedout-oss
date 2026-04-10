# Decision: Use nomic-embed-text-v1.5 as Default Embedding Model

**Date:** 2026-04-07
**Status:** Accepted
**Context:** LinkedOut OSS -- choosing a local embedding model for relationship intelligence features

## Question
Which embedding model should LinkedOut OSS use by default for local semantic search?

## Key Findings
- nomic-embed-text-v1.5 scores 6 MTEB points higher than all-MiniLM-L6-v2
- Apache 2.0 licensed (compatible with OSS distribution)
- Matryoshka representations allow flexible dimensionality (64-768) for size/quality tradeoffs
- 8K context window (vs 512 for MiniLM)
- ~275MB model size -- reasonable for local use
- Community consensus treats MiniLM as legacy; nomic is the current recommended local model

## Decision
Use nomic-embed-text-v1.5 as the default embedding model. MiniLM is not recommended -- the quality gap is significant and nomic's licensing is equally permissive.

## Implications
- Users need ~275MB disk for the model (document in setup)
- Can leverage Matryoshka dims to offer a "lite" mode with smaller vectors
- 8K context means less chunking needed for longer text passages
- Model download should be part of first-run setup, not bundled in the repo

## References
- Web research report: .taskos/exploration/web_research_report.md
