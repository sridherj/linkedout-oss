# S4: OpenAI Embedding Spike Results

**Date:** 2026-03-27
**Model:** text-embedding-3-small
**Profiles tested:** 50
**Source:** `linkedin_profile_data_2.json` (first 50 profiles via ijson streaming)

## Embedding Text Format

```
{full_name} | {headline} | {about} | Experience: {company1} - {title1}, ...
```

## Results

| Metric | Value |
|--------|-------|
| Profiles embedded | 50 |
| Embedding dimensions | 1536 |
| API call latency | 5.70s |
| Actual tokens used | 6,625 |
| Avg tokens/profile | 132.5 |
| Min tokens (estimated) | 4 |
| Max tokens (estimated) | 504 |
| Cost for this spike | $0.0001 |

## Cost Estimates for 20K Profiles

| Method | Cost | Notes |
|--------|------|-------|
| Real-time `/v1/embeddings` | $0.05 | $0.02/1M tokens |
| Batch API `/v1/batches` | $0.03 | $0.01/1M tokens (50% cheaper) |

## Error Handling

| Scenario | Result |
|----------|--------|
| Empty text | API rejects with 400 error: "input cannot be an empty string" — must filter empty texts before calling |
| Long text (~40K chars, ~11K tokens) | API truncates to 8191 tokens, returns 1536-dim vector (7001 tokens billed) |

## Batch API Strategy for Production

For production embedding of ~20K profiles, use the **Batch API** (`/v1/batches`):

1. **File format:** JSONL with one request per line:
   ```jsonl
   {"custom_id": "profile-1", "method": "POST", "url": "/v1/embeddings", "body": {"model": "text-embedding-3-small", "input": "text..."}}
   ```
2. **Upload:** `POST /v1/files` with purpose `batch`
3. **Create batch:** `POST /v1/batches` with input_file_id
4. **Poll:** `GET /v1/batches/{batch_id}` until `status == "completed"`
5. **Download:** `GET /v1/files/{output_file_id}/content`

**Advantages:**
- 50% cheaper than real-time API
- 24-hour completion window (typically much faster)
- No rate limit concerns for bulk operations
- Idempotent with custom_id for retry safety

**Recommended batch size:** 50K requests per batch file (API limit)

## Recommendations

1. Use `text-embedding-3-small` (1536 dims) — good quality/cost balance
2. Use Batch API for initial bulk embedding and periodic refreshes
3. Use real-time API only for single-profile on-demand embedding (e.g., new connection added)
4. Store embeddings in pgvector `vector(1536)` column
5. Total cost for 20K profiles: ~$0.03 (one-time, Batch API)
