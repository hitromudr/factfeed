# Phase 1: Database Foundation - Context

**Gathered:** 2026-02-23
**Status:** Ready for planning

<domain>
## Phase Boundary

Establish the PostgreSQL schema with all indexes, child tables, and columns required before any data is inserted. Includes Docker Compose setup, Alembic migration infrastructure, and the initial Python project scaffolding. No application logic — just the foundation that all subsequent phases build on.

</domain>

<decisions>
## Implementation Decisions

### Project structure
- Single top-level package: `factfeed/` with submodules: `db/`, `nlp/`, `web/`, `ingestion/`
- Dependency management via `uv` with `pyproject.toml` and lockfile
- Configuration via `pydantic-settings` reading from `.env` file and environment variables
- Test framework: `pytest` with fixtures for DB setup/teardown
- Tests live in a top-level `tests/` directory mirroring the package structure

### Claude's Discretion
- Schema design: table structure, column types, index choices (guided by research and roadmap success criteria)
- Docker Compose configuration: PostgreSQL version, service naming, volume setup
- Migration strategy: single initial migration vs incremental, Alembic configuration
- Exact directory layout within each submodule

</decisions>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches. The roadmap success criteria are precise:
- articles, sentences, sources tables
- tsvector STORED column with GIN index from migration zero
- Sentences as child table with label, confidence, position columns
- url_hash unique constraint for deduplication
- Docker Compose with postgres, migrate, app services

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 01-database-foundation*
*Context gathered: 2026-02-23*
