# SERP schema documentation and log progress design

## Scope

Add a maintained PostgreSQL data dictionary and make Railway collection logs
show deterministic progress through the YAML query list. This change does not
alter requests, checkpoints, batching, retry behavior, or stored values.

## Documentation

Create `docs/postgresql-serp-schema.md` as the operational reference for the
`serp` schema. It will describe the purpose, source, PostgreSQL type, and
meaning of every column in `serp.batches`, `serp.products`,
`serp.query_totals`, and `serp.attempts`. It will also document primary and
foreign keys, indexes, cascade deletion, idempotent upserts, six-hour batches,
five-minute retries, page checkpoints, the 90-day retention rule, and compact
read-only SQL examples.

Update `README.md` to link to the data dictionary and remove stale wording
that calls attempts hourly. The Python DDL remains the source of truth; the
documentation must match it exactly at the time of the commit.

## Progress logs

At invocation start, print total queries and checkpoint progress:

```text
PROGRESS queries_total=739 pages_completed=193/1478
```

Every page decision will contain the stable one-based YAML query ordinal,
total query count, remaining query count, one-based page number, configured
page count, and query text:

```text
FETCH query=100/739 remaining=639 page=1/2 text='тюль лен 300x250'
SKIP query=100/739 remaining=639 page=2/2 text='тюль лен 300x250': checkpoint exists
```

`remaining` means queries after the current ordinal (`total - ordinal`), not a
claim that all earlier queries succeeded. On retries, ordinals remain stable;
checkpointed pages log `SKIP`, while only missing pages log `FETCH`.

## Verification and release

Tests will assert startup progress, stable ordinals, page totals, remaining
counts, and resume output. Existing collection and PostgreSQL tests must remain
green. Work stays on `codex/serp-schema-docs-progress`; it is merged and pushed
to `main` only after the active Railway invocation is no longer running, so a
documentation/progress deployment cannot interrupt collection.
