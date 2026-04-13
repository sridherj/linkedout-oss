# Querying Your Network

## How It Works

LinkedOut queries are handled by the `/linkedout` skill in your AI assistant (Claude Code, Codex, or Copilot). You ask questions in natural language, and the skill constructs SQL queries against your local PostgreSQL database.

There is no CLI `search` command — the AI skill outperforms a fixed search algorithm because it can write custom joins, interpret context, and combine multiple data sources per query.

### Queryable data

| Data | Source | Description |
|------|--------|-------------|
| **Connections** | LinkedIn CSV import | Your professional connections with titles, companies, locations |
| **Companies** | Seed data + imports | Company profiles with industry, size, funding history |
| **Experience** | CSV + Chrome extension | Work history — companies, roles, dates |
| **Education** | CSV + Chrome extension | Schools, degrees, fields of study |
| **Skills** | Chrome extension | Listed skills and endorsements |
| **Affinity scores** | `linkedout compute-affinity` | Relationship strength (0-1) based on career overlap, contact info, recency |
| **Dunbar tiers** | `linkedout compute-affinity` | Inner circle, active, familiar, acquaintance |
| **Embeddings** | `linkedout embed` | Vector representations for semantic similarity search |

---

## Example Queries

### Company-based queries

> "Who do I know at Stripe?"

Returns connections currently working at Stripe, ranked by affinity score.

> "Who do I know at Series B AI startups?"

Combines company funding data (from seed data) with your connections. Filters for AI-related companies with Series B funding rounds.

> "Companies with the most connections in my network"

Aggregates your connections by employer and returns a ranked list.

> "Find connections at companies that raised funding in the last year"

Joins your connections with the funding_round table to find people at recently funded companies.

### People-based queries

> "Find people who went to Stanford and work in ML"

Combines education records with current role and skills data.

> "Who are my strongest connections at Google?"

Returns Google connections sorted by affinity score (highest first).

> "Show me people who changed jobs in the last 6 months"

Looks at experience records to find connections with recent role changes.

> "Find connections in San Francisco working at startups"

Filters by location and company size/type.

### Skill and interest queries

> "Who has skills in machine learning or data science?"

Searches the skills table for connections with matching skill keywords.

> "Find people with Python and distributed systems experience"

Combines skill data with experience descriptions.

### Relationship queries

> "Show my top Dunbar tier 1 connections"

Returns your inner circle — the ~15 strongest professional relationships based on affinity scoring.

> "Recent profile updates from my network"

Shows connections whose profile data was recently updated (via Chrome extension crawling or re-import).

---

## Understanding Results

### Affinity scores

Affinity scores range from 0 to 1 and measure the strength of your professional relationship. The score is a weighted combination of:

| Signal | Default Weight | What it measures |
|--------|---------------|------------------|
| Career overlap | 40% | Time spent at the same company |
| External contact | 25% | Whether you have their phone/email (from contacts import) |
| Embedding similarity | 15% | How similar your career trajectories are |
| Source count | 10% | Number of data sources confirming the connection |
| Recency | 10% | How recently you overlapped or interacted |

### Dunbar tiers

Based on [Dunbar's number](https://en.wikipedia.org/wiki/Dunbar%27s_number), connections are classified into tiers by their affinity rank:

| Tier | Rank | Description |
|------|------|-------------|
| Inner circle | Top 15 | Your closest professional relationships |
| Active | Top 50 | People you actively maintain contact with |
| Familiar | Top 150 | People you know well enough to have a meaningful conversation |
| Acquaintance | 150+ | Everyone else in your network |

### Embedding similarity

When you run `linkedout embed`, LinkedOut generates vector embeddings from each connection's profile text (bio, experience, skills). This enables semantic search — finding people with similar career paths even when they use different job titles or terminology.

---

## Tips for Better Results

### Import more data

The quality of query results depends directly on how much data is in your database:

- **LinkedIn CSV export** — the foundation. Export from LinkedIn Settings > Data Privacy > Get a copy of your data.
- **Google/iCloud contacts** — adds phone numbers and email addresses, which significantly boost affinity scores.
- **Chrome extension** — captures detailed experience, education, and skills data that isn't in the CSV export.
- **Seed data** — provides company intelligence (funding, industry, size) even for companies your connections haven't worked at.

### Enrich and compute affinity

After importing data, run these commands to unlock the full query capabilities:

```bash
linkedout enrich              # Fetch full profiles via Apify + generate embeddings
linkedout compute-affinity    # Calculate relationship strength scores
```

Enrichment fetches full LinkedIn profiles and generates embeddings in the same step. Without enrichment, you only have basic CSV stub data. Without affinity scores, queries like "strongest connections" won't work. Without embeddings, semantic similarity searches won't return results.

If some profiles are missing embeddings after enrichment, run `linkedout embed` to backfill.

### Be specific in queries

The AI skill works best with specific questions:
- **Good:** "Who do I know at Series B AI startups in San Francisco?"
- **Less useful:** "Tell me about my network"

### Check your data coverage

Run `linkedout status` to see how complete your data is:

```
LinkedOut v0.1.0 | 4,012 profiles | 23,456 companies | embeddings: 98.2% | affinity: computed | extension: not connected
```

If embedding coverage is low, run `linkedout embed`. If affinity shows "not computed", run `linkedout compute-affinity`.
