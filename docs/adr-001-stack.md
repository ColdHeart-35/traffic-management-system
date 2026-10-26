# ADR-001: Technology stack

**Status:** accepted (Sprint 1)

**Decision:** Python, FastAPI, SQLAlchemy over SQLite, Jinja2 server-rendered pages, pytest.

**Why:** one language for the whole team; FastAPI gives request validation and OpenAPI docs for free, which matches the
API tables in the SAD; SQLite needs no server for a simulation project; pytest lets test names carry the SRS test-case IDs.

**Consequences:** SQLite limits concurrent writes (acceptable for a simulated intersection); the modular layout keeps each
module replaceable, as the SAD requires. Time comes from `tms.common.clock`, which can be frozen so tests are deterministic.
