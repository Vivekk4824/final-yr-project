# VendorMap project viva guide

This study pack is based on the checked-in source code and artifacts, not only on the README or report. Read it in this order:

1. [Project inventory, pipeline, data, MCDA, clustering, slots, and allocation](01-core-technical-guide.md)
2. [Architecture, execution, formulas, design defence, demo, and validation](02-architecture-demo-validation.md)
3. [66 project-specific viva questions and answers](03-viva-questions.md)
4. [Five explanation levels and one-page revision sheet](04-five-levels-and-cheat-sheet.md)

## The most important truth to defend

VendorMap is not one monolithic “AI model.” It is a decision-support system with four deliberately separate layers:

- offline GIS feature engineering and K-Means environmental profiling;
- a transparent six-factor weighted-sum MCDA recommender;
- provisional, site-level pilot slot geometry and an audited approval workflow;
- an advisory two-stage mixed-integer allocation planner.

K-Means does **not** generate slots, MCDA does **not** grant permits, the optimizer does **not** write allocations, and a map reference is **not** proof of legal vending authorization.

## Evidence and scope notes

- Active model version: `manual-142-v2`, selected by `data/catalog.json`.
- Operational app: React/Vite frontend and FastAPI/SQLAlchemy backend.
- Operational storage: SQLite by default, PostgreSQL supported through `DATABASE_URL`.
- Dataset counts and saved metrics are artifact counts as inspected on 21 November 2026; they are not performance claims.
- The existing database was opened read-only for inventory. It contained 308 live-status rows, 85 active pilot slots across four layouts, one approved request, and one active allocation.
- The repository declares 226 Python test functions and 76 JavaScript `test(...)` cases. This inspection did not run them, so their presence must not be described as a fresh all-green test run.

## Implementation status legend

- **Implemented/active:** called by the normal operational path.
- **Implemented/experimental:** working code behind a flag or research endpoint, disabled by default.
- **Pilot/provisional:** operational UI and persistence exist, but geometry or legal status is explicitly unverified.
- **Utility only:** implemented library code not currently governing production decisions.
- **Not implemented:** documented idea or absent capability.

