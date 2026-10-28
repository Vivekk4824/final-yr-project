# COCOMO II Software Cost Estimation

**Project:** Nashik Street Vendor Management & Zoning Platform

**Estimate date:** 16 October 2026

**Currency:** Indian rupees (INR, ₹)

**Estimate type:** Repository-based post-architecture estimate; illustrative market-cost scenario
**Repository snapshot:** Current working tree on the estimate date, including tracked and untracked project source. The LOC census was frozen immediately before this report was added, so this report is not included in its own documentation LOC. No secrets, local databases, private raw vendor records, or dependency directories were opened or counted.

> **Use and limitations.** This is a reproducible, model-based planning estimate—not a record of the project's actual paid expenditure, actual hours, or a vendor quotation. Salary, team, reuse, service-usage, and hosting assumptions are stated explicitly. The source repository has no validated project-history record of effort or staffing with which to calibrate COCOMO II. The visible project history runs from 9 September to 15 October 2026 (36 days); that is a Git history span, not proof of the complete development period.

## Executive estimate

| Measure | Base estimate |
|---|---:|
| Product source, physical lines | 42,062 |
| Product source, logical-line proxy | 33,558 |
| Known retained historical baseline excluded from new-equivalent size | 177 logical lines (0.177 KSLOC) |
| Effective COCOMO II size | 33.381 KSLOC |
| Scale-factor exponent, E | 1.1153 |
| Effort adjustment factor, EAF | 1.2870 |
| COCOMO II effort | 189.27 person-months |
| COCOMO II schedule | 19.76 calendar months |
| Average staffing implied by effort/schedule | 9.58 full-time equivalents |
| Unburdened illustrative labor | ₹1,37,14,394 |
| Fully loaded illustrative labor (20% benefits/allowances) | ₹1,64,57,273 |
| Initial development plus one-month launch and direct project allocations | ₹1,65,36,014 |
| Contingency (15% of initial direct cost) | ₹24,80,402 |
| Initial budget including contingency | **₹1,90,16,416** |
| First 12-month maintenance after launch, separate from initial development | ₹25,13,288 |

The labor and lifecycle values are hypothetical, replacement-cost estimates in a professional Indian-market scenario. They are not the amount a student team necessarily spent out of pocket.

## 1. Repository and architecture analysis

### Purpose and problem addressed

The project is a Nashik Municipal Corporation street-vendor management and zoning platform. It supports administrative management of vending zones and live capacity, vendor registration/profile workflows, recommendations for suitable zones, allocation requests, mapped pilot slots, and vendor/admin operational screens. Its decision-support features combine location/GIS evidence, operational availability, and numerical ranking rather than relying on a static list alone.

### Architecture summary

The application is a browser-based React client backed by a Python FastAPI service. The frontend uses a same-host/port development arrangement by default and calls the backend through a shared API client. The API routes delegate to services, Pydantic schemas, security helpers, and a repository. SQLite is the default operational database; SQLAlchemy and psycopg support an optional PostgreSQL connection. GIS assets and saved analytical/model artifacts are held alongside the source rather than embedded as code.

| Concern | Repository evidence and implementation |
|---|---|
| Frontend | React 18, JavaScript/JSX, Vite 6, Leaflet/React-Leaflet, Lucide icons, and English/Marathi/Hindi UI support. Feature areas include admin, vendor, authentication, recommendation, zone registry, research, navigation, and pilot-slot mapping. |
| Backend | Python 3 application using FastAPI/Uvicorn, Pydantic, service/repository layering, and nine router modules (auth, health, vendors, zones, recommendations, allocations, pilot slots, navigation, and research). The scan found 61 route decorators; decorators can include aliases and are not asserted to be 61 unique business operations. |
| Data | SQLite is the defaul








































++t; PostgreSQL is supported through `DATABASE_URL`, SQLAlchemy, and psycopg. Spatial data uses GeoJSON and GIS processing libraries. Local operational database files are ignored and were not inspected. |
| Authentication and authorization | Session-cookie authentication, HMAC-based identity mapping, OTP challenge flows, role-aware vendor/admin access, server-side authorization, and privacy controls. The documented OTP provider is development-only; live SMS delivery is not implemented. |
| Recommendation/decision support | Weighted MCDA and AHP calibration, K-Means/geospatial features, suitability/training/evaluation scripts, capacity-aware allocation/planning, and advisory optimization. The codebase retains a separate historical MCDA implementation for comparison. |
| Maps and routing | Leaflet and OpenStreetMap tiles for maps; OpenRouteService (ORS) routing is optional and configured by a server-side key. GIS features use GeoPandas, Shapely, PyProj, NumPy, pandas, SciPy, and scikit-learn. |
| Other integrations | Optional Google Gemini explanations, disabled by default through configuration; direct Meta WhatsApp Cloud API/webhook and a local simulator. Service usage and account pricing are not represented in the source tree. |
| External APIs | FastAPI JSON endpoints; optional ORS routing, Google GenAI, Meta WhatsApp Graph API, and OpenStreetMap tile service. No payment provider is identified. |
| Deployment | `docs/deployment.md` describes serving the Vite build over HTTPS with SPA fallback and running Uvicorn with persistent storage. SQLite is recommended for an initial single-worker deployment; PostgreSQL is supported. No Docker/Kubernetes/IaC or live cloud deployment configuration was found. |
| Tests and build | Python pytest/unittest-style backend coverage; Node's built-in `node:test` frontend suites; browser smoke test support; Vite production build; `npm ci` lockfile; Python requirements split into app/research/dev manifests. |
| DevOps/configuration | Git repository and documented Windows setup; environment templates, requirements constraints, frontend package manifest/lockfile, and deployment guide. No CI pipeline or infrastructure-as-code definition was identified. |
| Documentation/evidence | README, architecture/deployment/pilot-slot documents, API contract and algorithm baselines, migration/refactor manifests, model artifacts, and evaluation reports. Machine-readable baseline records are documentation/evidence, not executable source. |
| Major functional components | Approximately 12 logical areas for estimation: authentication/onboarding; vendor profile/portal; zone registry/GIS; recommendations/MCDA; allocation requests; capacity/relocation; pilot slots; navigation; WhatsApp; research/admin analytics; data/model preparation; and shared persistence/configuration/security. This is a functional grouping, not a count enforced by the application. |

Relevant repository references: [README](../README.md), [architecture](./architecture.md), [deployment](./deployment.md), [backend application](../backend/application.py), [database repository](../backend/repositories/database.py), [frontend package manifest](../frontend/package.json), and [Python requirements](../requirements/app.txt).

## 2. Software size and LOC method

### Census method

The census covers project-owned source in `backend/`, `frontend/src/`, `scripts/`, `research/`, and `app/`; test files are reported separately. It includes current project source that is untracked in Git as well as tracked files. It excludes `.git`, `node_modules`, `.venv`/`venv`, caches, build output, browser/runtime-validation artifacts, local databases, data/report/model assets, and all private raw inputs. The root `.env` and private vendor records were not read. Third-party dependency source is outside the counted project tree and is excluded.

Physical LOC is the number of lines in source files. The logical-line proxy removes blank lines and full-line comments using extension-specific comment prefixes; it does not parse syntax, split semicolon-separated statements, or strip inline comments. It is therefore a transparent line-count approximation, not a claim of an AST-based statement count. The method and snapshot date should be retained when the count is reused.

| Category | Files | Physical LOC | Logical/nonblank proxy | Treatment |
|---|---:|---:|---:|---|
| Production/maintained project source | 157 | 42,062 | 33,558 | Includes backend, frontend, data/model/research scripts, and retained Streamlit review utility. |
| Tests | 38 | 5,673 | 5,101 | Excluded from KSLOC to avoid counting tests as delivered source; test effort remains in the COCOMO lifecycle allocation. |
| Configuration/infrastructure text | 10 | 1,468 | 1,451 | Includes requirements, `.env.example`, `.gitignore`, frontend manifest, and generated package lock. No IaC source was identified. |
| Documentation and structured baselines | 12 | 4,321 | 4,162 | 793 physical lines of Markdown, plus 3,528 lines of machine-readable contract/baseline JSON. |
| **Total counted text** | **217** | **53,524** | Not meaningful across mixed text types | Does not include datasets, binary models, third-party dependencies, or generated build output. |

The combined source-and-test logical-line proxy is `33,558 + 5,101 = 38,659` lines. Documentation and structured configuration are reported separately because blank-line/comment treatment is not a software-size measure for those artifacts.

Product source by area:

| Area | Physical LOC | Logical-line proxy |
|---|---:|---:|
| Backend | 31,437 | 24,483 |
| Frontend source | 3,578 | 3,319 |
| Scripts | 6,739 | 5,475 |
| Streamlit review utility (`app/`) | 109 | 103 |
| Research baseline package | 199 | 178 |
| **Total** | **42,062** | **33,558** |

The configuration total includes the 1,221-line `frontend/package-lock.json`; it is generated dependency-resolution metadata, not generated application code. No generated application source code was identifiable. AI-assisted authorship cannot be reliably established from the repository; any AI-assisted but retained/maintained source is counted as project source because the repository contains no auditable line-level generation map. Compiled Vite output and binary `.joblib` model artifacts are excluded.

### New, reused, modified, and generated size used by COCOMO

The codebase explicitly retains `research/mcda_baseline.py` as a separate historical model implementation. It contains 177 logical lines (198 physical) and is retained for research comparison, so it is counted in repository source but not charged as newly developed source in the base size. Regression/integration work for the comparison remains in project effort.

| Size component | KSLOC | Explanation |
|---|---:|---|
| Maintained logical project source | 33.558 | Counted from the current source snapshot above. |
| Identifiable unchanged historical baseline reuse | −0.177 | `research/mcda_baseline.py`, retained as a historical comparison implementation. Excluded from new-equivalent source; integration/testing is not assumed free. |
| New-equivalent source used in the base model | **33.381** | `(33,558 − 177) / 1,000`. |
| Other modified/reused source | Not separately measurable | The first repository commit already contains a substantial codebase, and there is no line-level source-provenance/adaptation record. No speculative reuse discount is applied to the remaining code; it is treated as new-equivalent for the base case. |
| Automatically generated application code | 0 identified | The package lock is generated metadata, not application code. Build output is excluded. |
| Third-party/dependency LOC | 0 counted | Libraries are installed dependencies, not project-authored repository source. |

**Size arithmetic:** 33,558 logical project source lines − 177 verified retained historical lines = 33,381 new-equivalent logical lines; 33,381 ÷ 1,000 = **33.381 KSLOC**.

This is a whole-repository software estimate, not solely the deployed HTTP/UI runtime. It includes retained model, GIS, and evaluation utilities because they are part of the documented project deliverable. A deployment-only estimate would require an agreed scope boundary and a dependency-level exclusion list. Counting all maintained code as new-equivalent outside the one identifiable historical baseline is conservative and may overstate actual effort if other code was reused or generated.

## 3. Model selection and constants

**COCOMO II Post-Architecture is used because the project's architecture and implementation are sufficiently defined.**

The project has a known web/API/database structure, documented functional boundaries, implemented integrations, tests, and deployment guidance. The Post-Architecture model is therefore more appropriate than an early Conceptual Estimation model. However, COCOMO II is calibrated for conventional software development and has not been locally calibrated to this academic project, its actual team, or AI-assisted work; results should be treated as a planning-equivalent estimate.

The standard Post-Architecture constants used are:

- `A = 2.94` — effort coefficient.
- `B = 0.91` — scale exponent base.
- `C = 3.67` — schedule coefficient.
- `D = 0.28` — schedule exponent base.

## 4. Scale factors

Each scale factor has six standard ratings: Very Low, Low, Nominal, High, Very High, Extra High. The rating values below are standard Post-Architecture scale-factor values. Lower numeric values indicate less scale-factor penalty.

| Factor | Rating | Value | Project-specific rationale/evidence |
|---|---|---:|---|
| PREC — Precedentedness | Nominal | 3.72 | Web administration, vendor portals, and mapping are established patterns, but Nashik-specific vending rules, GIS reconciliation, and decision support are domain-specific. |
| FLEX — Development Flexibility | Nominal | 3.04 | Feature and UI changes are visible through the implementation history; formal contractual flexibility and stakeholder change-control constraints are not recorded. |
| RESL — Architecture/Risk Resolution | Nominal | 4.24 | Architecture, deployment, API contracts, and tests exist. No repository evidence establishes a formal risk-resolution program, quantitative prototyping, or independent architecture review. |
| TEAM — Team Cohesion | Nominal | 3.29 | **Assumption required — information not available in repository.** The repository does not document team size, communication quality, team familiarity, or stakeholder alignment. |
| PMAT — Process Maturity | Low | 6.24 | Git, repeatable tests, package locks, deployment instructions, and architecture guardrails are present; no institutional process maturity level, CI pipeline, or measured quality process is evidenced. |
| **ΣSF** |  | **20.53** | `3.72 + 3.04 + 4.24 + 3.29 + 6.24`. |

`E = B + 0.01 × ΣSF = 0.91 + 0.01 × 20.53 = 1.1153`.

## 5. Post-Architecture effort multipliers

The table applies the standard COCOMO II.2000 Post-Architecture effort-multiplier values. A repository cannot establish individual skills, staffing continuity, organizational experience, or a deadline; those ratings use the nominal planning assumption and are identified as such.

### Product factors

| Driver | Full name | Rating | Numerical EM | Reason | Evidence/assumption |
|---|---|---:|---:|---|---|
| RELY | Required Software Reliability | High | 1.10 | Incorrect zone capacity, allocation, or identity handling can affect real vendor operations; the product is not safety-critical and has no stated availability SLA. | Authentication, allocations, capacity rules, audit-related workflows are present in backend services/tests. Reliability rating is an estimate, not a measured failure rate. |
| DATA | Database Size | Nominal | 1.00 | The product uses structured operational records plus GIS/model evidence, but no validated database-size-to-program-size ratio is available. | SQLite default and optional PostgreSQL are evidenced; local database statistics were not inspected. **Assumption required — information not available in repository.** |
| CPLX | Product Complexity | High | 1.17 | Combines GIS, personalized MCDA/AHP/K-Means, auth/privacy, transactional allocation/capacity rules, role-separated UI, and integrations. | Architecture, APIs, model and service code, plus regression tests provide direct evidence. |
| RUSE | Required Reusability | Nominal | 1.00 | Shared services and utilities are reused within this application, but there is no stated product-line or external reuse target. | Internal shared modules exist; no external reusability requirement found. |
| DOCU | Documentation Match to Lifecycle Needs | Nominal | 1.00 | Architecture, deployment, API-contract, algorithm, and slot-mapping documents exist; a complete formal SRS/user/operations manual set is not evidenced. | `README.md`, `docs/architecture.md`, `docs/deployment.md`, API baselines and test suites. |

### Platform factors

| Driver | Full name | Rating | Numerical EM | Reason | Evidence/assumption |
|---|---|---:|---:|---|---|
| TIME | Execution Time Constraint | Nominal | 1.00 | No hard real-time or response-time requirement is recorded. | No measured performance SLA or benchmark target in the reviewed repository. **Assumption required — information not available in repository.** |
| STOR | Main Storage Constraint | Nominal | 1.00 | No restricted-memory/storage target or embedded deployment constraint is documented. | Documented target is a normal web/API host with persistent files. **Assumption required — information not available in repository.** |
| PVOL | Platform Volatility | Nominal | 1.00 | Python/Node and external APIs can evolve, but no unusually volatile or fixed changing platform requirement is documented. | Python requirements constraints and npm lockfile are present; future provider/platform changes remain uncertain. |

### Personnel factors

| Driver | Full name | Rating | Numerical EM | Reason | Evidence/assumption |
|---|---|---:|---:|---|---|
| ACAP | Analyst Capability | Nominal | 1.00 | No individual analyst capability or productivity record is available. | **Assumption required — information not available in repository.** |
| PCAP | Programmer Capability | Nominal | 1.00 | Repository quality cannot establish the developers' relative programming capability or prior productivity. | **Assumption required — information not available in repository.** |
| PCON | Personnel Continuity | Nominal | 1.00 | No staff turnover or continuity history is included. | **Assumption required — information not available in repository.** |
| APEX | Applications Experience | Nominal | 1.00 | The code demonstrates an implemented domain solution, but it does not establish the team's prior experience in municipal vending/administrative systems. | **Assumption required — information not available in repository.** |
| PLEX | Platform Experience | Nominal | 1.00 | Runtime and environment familiarity is not measurable from dependency files. | **Assumption required — information not available in repository.** |
| LTEX | Language and Tool Experience | Nominal | 1.00 | Python, JavaScript, React, FastAPI, Vite, GIS and test tooling are used; years of prior team experience are unknown. | **Assumption required — information not available in repository.** |

### Project factors

| Driver | Full name | Rating | Numerical EM | Reason | Evidence/assumption |
|---|---|---:|---:|---|---|
| TOOL | Use of Software Tools | Nominal | 1.00 | Git, npm/pip, Vite, automated tests and editor tooling are evidenced, but there is no CI pipeline or integrated CASE/automated project-management toolchain. | Repository manifests, scripts, tests and deployment instructions. |
| SITE | Multisite Development | Nominal | 1.00 | One Git repository is visible, but team location and communication infrastructure are not recorded. | **Assumption required — information not available in repository.** |
| SCED | Required Development Schedule | Nominal | 1.00 | No contract or externally imposed schedule compression is documented. | **Assumption required — information not available in repository.** |

## 6. Effort and schedule calculation

### Effort Adjustment Factor

`EAF = RELY × DATA × CPLX × RUSE × DOCU × TIME × STOR × PVOL × ACAP × PCAP × PCON × APEX × PLEX × LTEX × TOOL × SITE × SCED`

`EAF = 1.10 × 1.00 × 1.17 × 1.00 × 1.00 × 1.00 × 1.00 × 1.00 × 1.00 × 1.00 × 1.00 × 1.00 × 1.00 × 1.00 × 1.00 × 1.00 × 1.00 = 1.2870`.

### Person-months

`PM = A × KSLOC^E × EAF`

`PM = 2.94 × 33.381^1.1153 × 1.2870 = 189.2713 person-months`

**Base effort result: 189.27 person-months.**

### Calendar schedule and average staffing

For a nominal SCED:

`F = D + 0.2 × (E − B) = 0.28 + 0.2 × (1.1153 − 0.91) = 0.32106`

`TDEV = C × PM^F = 3.67 × 189.2713^0.32106 = 19.7582 months`

**Estimated schedule: 19.76 calendar months.**

`Average staff = effort / development time = 189.2713 / 19.7582 = 9.58 full-time equivalents (FTE).`

COCOMO II does not derive a reliable peak staffing curve from these inputs. For the cost model only, the role mix below represents 13 named role resources with part-time average allocations; all 13 active concurrently is a **planning assumption**, not a COCOMO output.

### Person-month, calendar month, day, and hour interpretation

- A **person-month** is one person-month of work. This estimate follows the stated standard conversion of 152 working hours per person-month.
- A **calendar month** is elapsed project time. Person-months do not equal calendar months; parallel staff and dependencies determine the schedule.
- **Person-hours:** `189.2713 × 152 = 28,769.23 person-hours`.
- **Person-days:** assuming 8 hours/day, `28,769.23 / 8 = 3,596.15 person-days` (equivalently 19 working days per 152-hour person-month).
- **People/FTE:** average FTE is 9.58 over the modelled schedule; the actual headcount may vary by phase and cannot be inferred from LOC.

### Sensitivity check

Keeping the same size and scale-factor exponent but setting all 17 cost drivers to Nominal (`EAF = 1.0`) gives approximately **147.06 PM** and **18.26 months**. The selected high RELY and CPLX multipliers raise effort to 189.27 PM. This is a sensitivity check, not a confidence interval. The largest uncertainty remains the size/provenance boundary and the personnel assumptions.

## 7. Effort allocation by lifecycle activity

Percentages below form a single work-breakdown allocation of the 189.2713 COCOMO person-months. Project management includes coordination/meetings; design/testing categories are separated to avoid double-counting. The activity cost is shown at the role model's blended loaded labor cost of ₹86,950.72 per PM. It is an allocation of the labor total, not an additional charge.

| Activity | Effort share | Person-months | Blended loaded labor allocation |
|---|---:|---:|---:|
| Project management, meetings and coordination | 7.0% | 13.2490 | ₹11,52,009 |
| Requirements engineering and stakeholder analysis | 5.0% | 9.4636 | ₹8,22,864 |
| System analysis and feasibility | 3.5% | 6.6245 | ₹5,76,005 |
| Architecture, security and deployment design | 4.0% | 7.5709 | ₹6,58,291 |
| UI/UX design and prototyping | 3.5% | 6.6245 | ₹5,76,005 |
| Database design | 2.5% | 4.7318 | ₹4,11,432 |
| Backend development | 14.0% | 26.4980 | ₹23,04,018 |
| Frontend development | 12.5% | 23.6589 | ₹20,57,159 |
| API and integration development | 5.5% | 10.4099 | ₹9,05,150 |
| AI/ML/GIS development | 8.0% | 15.1417 | ₹13,16,582 |
| Testing and QA (unit, integration, system, regression) | 8.0% | 15.1417 | ₹13,16,582 |
| Security implementation and verification | 2.5% | 4.7318 | ₹4,11,432 |
| Performance, compatibility and usability testing | 1.5% | 2.8391 | ₹2,46,859 |
| Debugging, rework and retesting | 5.0% | 9.4636 | ₹8,22,864 |
| Code review | 2.0% | 3.7854 | ₹3,29,145 |
| Documentation (SRS/design/API/user/test/release/report) | 5.0% | 9.4636 | ₹8,22,864 |
| Deployment and production verification | 2.0% | 3.7854 | ₹3,29,145 |
| Configuration management and release control | 2.0% | 3.7854 | ₹3,29,145 |
| DevOps and infrastructure/environment management | 2.0% | 3.7854 | ₹3,29,145 |
| User acceptance testing | 2.0% | 3.7854 | ₹3,29,145 |
| Maintenance preparation | 1.5% | 2.8391 | ₹2,46,859 |
| Training and knowledge transfer | 1.0% | 1.8927 | ₹1,64,573 |
| **Total** | **100.0%** | **189.2713** | **₹1,64,57,273** |

The allocation recognizes data/GIS and decision-support work, both web clients, identity/security, deployment and configuration control, testing/rework, and formal project documentation. It is a planning work breakdown, not a measurement extracted from commits.

## 8. Labor cost model

### Rate assumptions

The repository contains no payroll or contract-rate records. The following rates are an **illustrative 2026 Indian-market replacement-cost scenario**, not observed local quotations. Each rate is a gross monthly salary assumption. A 20% employer load is applied for benefits/allowances and employer overhead; it is not included in the base salary. Cost per person-month is calculated as `role PM × monthly gross rate`; loaded cost is `base salary × 1.20`.

One to three people per role group below is a staffing illustration, not an inferred actual team. Allocation per person is an average over the 19.758-month COCOMO schedule. Roles can be shared or phase-specific in an actual academic team.

| Role | People assumed | Average allocation/person | Duration window | Person-months | Gross monthly rate | Basic labor cost | 20% benefits/load | Fully loaded labor |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Project manager | 1 | 76.6% | 19.76 mo | 15.14 | ₹80,000 | ₹12,11,336 | ₹2,42,267 | ₹14,53,603 |
| Business/system analyst | 1 | 86.2% | 19.76 mo | 17.03 | ₹65,000 | ₹11,07,237 | ₹2,21,447 | ₹13,28,684 |
| Software architect | 1 | 67.1% | 19.76 mo | 13.25 | ₹1,00,000 | ₹13,24,899 | ₹2,64,980 | ₹15,89,879 |
| Backend/database/API developers | 3 | 79.8% | 19.76 mo | 47.32 | ₹75,000 | ₹35,48,836 | ₹7,09,767 | ₹42,58,604 |
| Frontend/UI/UX developers | 2 | 81.4% | 19.76 mo | 32.18 | ₹65,000 | ₹20,91,448 | ₹4,18,290 | ₹25,09,737 |
| AI/ML/GIS engineer | 1 | 95.8% | 19.76 mo | 18.93 | ₹90,000 | ₹17,03,441 | ₹3,40,688 | ₹20,44,130 |
| QA/security/performance engineers | 2 | 71.8% | 19.76 mo | 28.39 | ₹60,000 | ₹17,03,441 | ₹3,40,688 | ₹20,44,130 |
| DevOps/configuration/deployment engineer | 1 | 47.9% | 19.76 mo | 9.46 | ₹75,000 | ₹7,09,767 | ₹1,41,953 | ₹8,51,721 |
| Technical writer/support/training | 1 | 38.3% | 19.76 mo | 7.57 | ₹50,000 | ₹3,78,543 | ₹75,709 | ₹4,54,251 |
| **Total** | **13 role resources** | — | — | **189.27** | — | **₹1,37,14,394** | **₹27,42,879** | **₹1,64,57,273** |

The QA/security grouping includes focused security verification, not a separately priced penetration-test vendor. No separate dedicated database engineer is needed in this compact scenario; database design and implementation are allocated to the analyst/architect/backend role groups. No dedicated AI API operator, cloud architect, or support desk is assumed.

## 9. Hardware and development infrastructure

No hardware purchases or inventory are evidenced. The estimate allocates depreciation for existing equipment rather than charging full purchase prices. Assumptions: four existing developer laptops at ₹65,000 each, 48-month useful life, 60% project use; two existing monitors at ₹12,000 each, 36-month useful life, 50% project use; project duration 19.758 months.

| Existing equipment | Assumed purchase value | Depreciation/project allocation | Project-attributable cost |
|---|---:|---|---:|
| 4 developer laptops | 4 × ₹65,000 = ₹2,60,000 | `₹2,60,000 × 19.758 / 48 × 60%` | ₹64,214 |
| 2 monitors | 2 × ₹12,000 = ₹24,000 | `₹24,000 × 19.758 / 36 × 50%` | ₹6,586 |
| Additional server/GPU/IoT/network/UPS | Not assumed | No GPU training or dedicated hardware requirement is evidenced; local development services are assumed. | ₹0 |
| **Total hardware allocation** | — | Existing equipment only; no new purchase assumed. | **₹70,800** |

If equipment must be purchased specifically for the project, replace the depreciation allocation with documented purchase quotes and apply the institution's accounting policy.

## 10. Software and licenses

No paid software license is specified in the manifests. Values below are direct project-cost assumptions; they do not represent a formal transitive license audit.

| Software/service | Purpose | Free/paid | License/cost basis | Cost | Project allocation |
|---|---|---|---|---:|---:|
| Python 3, FastAPI, Uvicorn, Pydantic | Backend/runtime/API | Open source | No license purchase evidenced | ₹0 | ₹0 |
| React, React DOM, Vite, Lucide | Frontend/build/UI | Open source | No license purchase evidenced | ₹0 | ₹0 |
| Leaflet, React-Leaflet | Interactive maps | Open source | No license purchase evidenced | ₹0 | ₹0 |
| SQLite, SQLAlchemy, PostgreSQL/psycopg | Persistence and optional PostgreSQL | Open source | No license purchase evidenced | ₹0 | ₹0 |
| NumPy, pandas, SciPy, scikit-learn, GeoPandas, Shapely, PyProj, joblib | Numerical, ML and GIS processing | Open source | No license purchase evidenced | ₹0 | ₹0 |
| pytest, Node `node:test`, npm | Automated testing/package management | Open source | No license purchase evidenced | ₹0 | ₹0 |
| Git, GitHub repository, Visual Studio Code | Version control and development | Free tier/editor assumed | No paid plan evidenced | ₹0 | ₹0 |
| Windows/Linux operating system | Developer environment | Existing license/free Linux assumed | No incremental project license evidenced | ₹0 | ₹0 |
| OpenStreetMap tiles | Development map rendering | Public service/data with usage policy | No development charge budgeted; production traffic must follow provider policy/attribution | ₹0 | ₹0 |
| OpenRouteService | Optional directions/routing | Usage/account dependent | Key configured server-side; no measured calls or current quote | Not priced | Excluded pending usage plan |
| Google Gemini API | Optional AI-generated explanations | Usage/account dependent | Disabled by default; token volume and rate not available | ₹0 in base case | Excluded; enablement must be metered |
| Meta WhatsApp Cloud API | Optional bot/webhook | Usage/account dependent | No actual production messages or rate card available | ₹0 in base case | Excluded; production fees must be budgeted |
| Commercial IDE/design/security/monitoring tools | None required by manifests | Not evidenced | No purchases identified | ₹0 | ₹0 |

Open-source license obligations and the public map-tile service terms should be reviewed before commercial/high-volume production use. Optional provider costs are not assumed to be free at production scale; the project lacks the usage volume and account pricing needed to calculate them.

## 11. Cloud, hosting, network, and training

### Cloud/hosting scenario

The application does not technically require a cloud provider for development: it runs locally with SQLite, Vite, and Uvicorn. The deployment document describes a possible HTTPS production host but no actual cloud resources, account, deployment pipeline, or production usage. Therefore local development and test/staging have a zero incremental cloud charge in the base scenario.

For budgeting only, a small single-instance production pilot is assumed after development. It is a budgetary placeholder, not a provider quote:

| Environment/item | Monthly assumption | COCOMO project-period treatment | Notes |
|---|---:|---:|---|
| Development | ₹0 | ₹0 over 19.76 months | Local existing workstation/services. |
| Test/staging | ₹0 | ₹0 over 19.76 months | Local test databases and automated test tools; no separate staging host evidenced. |
| Production API + static frontend host | ₹2,500 | Included in launch estimate | Small single-instance host; scale and availability are not validated. |
| Persistent storage/backups | ₹500 | Included in launch estimate | Data/model backup allocation; backup sizing not measured. |
| DNS/domain allocation | ₹100 | Included in launch estimate | Assumed allocation; no project domain identified. |
| Bandwidth/basic monitoring allowance | ₹400 | Included in launch estimate | Low-traffic pilot assumption. |
| TLS certificate | ₹0 | ₹0 | Assumes an automated free certificate such as Let's Encrypt. |
| **Production total** | **₹3,500/month** | **₹3,500 for one initial launch month** | One month is included in the initial project cost; 12-month maintenance hosting is budgeted separately after launch. |

The scenario assumes a low-traffic single-worker deployment and persistent storage. Managed PostgreSQL, high availability, backups beyond the small allowance, data egress, paid email/SMS, ORS, Gemini, and WhatsApp usage are not included. Actual provider selection and capacity/security testing are release decisions, not repository facts.

### Network/internet

Assumption: existing broadband costs ₹899/month; 25% of the connection is attributed to the project over 19.7582 months:

`₹899 × 25% × 19.7582 = ₹4,440.65` project-attributable connectivity.

No VPN, dedicated networking, mobile-data plan, or remote-access service is evidenced. No incremental networking equipment cost is included.

### Training

Paid training, books, certifications, and workshops are not listed in the repository: **₹0 assumed external training expense**. Research, learning, onboarding, and knowledge transfer are not treated as free labor; they are included in the 1% training/knowledge-transfer effort allocation and role labor estimate.

## 12. Requirements, design, QA, security, project management, and documentation cost

These are already represented in the 100% work breakdown in Section 7 and are not added a second time. Key roll-ups at the blended loaded rate:

| Work group | Included work | Person-months | Loaded labor allocation |
|---|---|---:|---:|
| Requirements and analysis | Requirements, stakeholder analysis, feasibility, system analysis | 16.0881 | ₹13,98,868 |
| Design | Architecture/security/deployment design, UI/UX/prototyping, database design | 18.9271 | ₹16,45,727 |
| Testing and quality | Testing/QA, security verification, performance/compatibility/usability, UAT, code review, debugging/retest | 39.7470 | ₹34,56,027 |

These roll-ups are allocations from Section 7, rounded to the nearest rupee; the detailed activity table and Section 8 labor total are authoritative. Tests themselves exist, but that does not make test planning, test execution, security review, bug fixing, or retesting cost-free.

Project-management effort includes planning, scheduling, progress tracking, risk/change management, coordination, meetings, and stakeholder communication. Configuration management includes Git/release/version control, and DevOps covers environment/deployment operations. Documentation includes SRS/requirements, architecture, API/database, test, user/install/deployment/maintenance guides, final-year report and presentation preparation. The repository does not contain evidence for paid analyst interviews or a formal penetration test; their effort is included only as the stated labor allocation, with no external vendor cost.

> **Presentation note:** The costs in this roll-up are labor allocations, not extra project budget lines. The initial labor total in Section 8 is the authoritative labor amount.

## 13. Initial development, launch, maintenance, and contingency

### Initial project cost

| Cost item | Amount | Calculation/interpretation |
|---|---:|---|
| Unburdened labor | ₹1,37,14,394 | Sum of role person-months × gross monthly rates. |
| Employer benefits/allowances | ₹27,42,879 | Assumed 20% of basic labor. |
| **Fully loaded labor** | **₹1,64,57,273** | COCOMO effort × role-weighted rates, including management, development, testing, docs, and deployment effort. |
| Hardware depreciation allocation | ₹70,800 | Existing laptops and monitors only. |
| Allocated internet | ₹4,441 | Existing broadband share over COCOMO duration. |
| Software licenses | ₹0 | No paid tool identified; optional API charges excluded. |
| Development/test cloud | ₹0 | Assumed local development and testing. |
| **Initial development cost (before launch)** | **₹1,65,32,514** | Loaded labor + hardware + network + licenses + dev/test cloud. |
| Initial production launch hosting | ₹3,500 | One month of the illustrative production-hosting scenario. Deployment labor is already in loaded labor. |
| **Initial direct cost including launch** | **₹1,65,36,014** | Initial development + one launch month. |
| Contingency reserve | ₹24,80,402 | 15% × initial direct cost. |
| **Initial budget including reserve** | **₹1,90,16,416** | Direct cost + contingency. |

The 15% contingency is a planning reserve for unmeasured reuse, staffing/rate variability, stakeholder changes, integration/provider changes, defects/rework, deployment hardening, and cloud/API usage. It is not a probability-weighted risk model.

### Maintenance after initial launch

Maintenance is a separate lifecycle phase and is not mixed into COCOMO development PM. Assumption: annual maintenance effort is 15% of initial COCOMO effort:

`189.2713 PM × 15% = 28.3907 maintenance PM/year`.

At the same loaded blended rate, maintenance labor is approximately ₹24,68,591 per year. Add the illustrative 12 months of production hosting (₹42,000) and allocated internet (₹2,697):

| Maintenance item | First 12 months after launch |
|---|---:|
| Bug fixes, security/dependency updates, small enhancements, monitoring/support and database care (28.3907 PM) | ₹24,68,591 |
| Production hosting (₹3,500 × 12) | ₹42,000 |
| Internet share (₹899 × 25% × 12) | ₹2,697 |
| **First-year maintenance estimate** | **₹25,13,288** |

Optional annual maintenance thereafter is approximately **₹25,13,288/year at the same 2026 assumed rates**, excluding inflation, changing provider pricing, paid API traffic, and major enhancements. A combined initial budget including contingency plus one full post-launch maintenance year is approximately **₹2,15,29,704**. This is a lifecycle budget, not the initial development amount.

## 14. Cost and interpretation risks

1. **Source provenance and generated code:** only one retained historical source baseline could be positively identified. Other copied, generated, or modified lines cannot be classified without a provenance record. If a meaningful share was reused or produced by code-generation/AI tools and required little manual rework, this human-effort estimate may be high.
2. **Repository scope:** the 33.381 KSLOC includes maintained research/training/evaluation scripts, not only deployed runtime code. A narrower production-only boundary would reduce size and requires stakeholder agreement.
3. **Personnel and PMAT:** capability, experience, continuity, team cohesion, and schedule ratings are assumptions because the repository does not record them. Nominal ratings were used except for documented product reliability/complexity concerns and the low process-maturity rating.
4. **Model calibration and academic context:** COCOMO II estimates traditional human effort; this project has no actual effort diary, team size, or calibration history. The Git-visible 36-day span does not reconcile with the 19.76-month model schedule and must not be represented as a measured schedule. The mismatch is evidence that the model output is indicative and/or the assumed LOC boundary/productivity differs from actual work.
5. **Security/deployment readiness:** repository documentation states development OTP only and no validated production deployment, external security assessment, load test, or disaster-recovery exercise. Budgeted production infrastructure is a hypothetical low-traffic pilot, not certification of readiness.
6. **Provider charges:** actual Gemini, WhatsApp, ORS, map tiles, SMS, email, backup, and egress charges depend on enabled features, provider plans, and traffic not present in the codebase.
7. **Rate assumptions:** salary, benefits, hardware, internet, and hosting rates are hypothetical scenario inputs. Replace them with local quotes, institution rates, and actual equipment records for a formal procurement budget.

## 15. References and reproducibility

### Model references

- Barry W. Boehm et al., *Software Cost Estimation with COCOMO II*, Prentice Hall, 2000.
- USC Center for Software Engineering, *COCOMO II.2000 Model Definition Manual* (Post-Architecture model; scale factors, effort multipliers, and effort/schedule equations).
- The 152 working-hours/person-month conversion is applied as specified in the project-estimation brief.

### Repository evidence

- [README and configuration guidance](../README.md)
- [Architecture and module ownership](./architecture.md)
- [Deployment requirements and limitations](./deployment.md)
- [Backend app/router composition](../backend/application.py)
- [Backend configuration](../backend/core/config.py)
- [Authentication and database services](../backend/services/authentication.py), [database repository](../backend/repositories/database.py)
- [Recommendation and capacity implementations](../backend/mcda_engine.py), [allocation optimizer](../backend/allocation_optimizer.py)
- [WhatsApp integration](../backend/whatsapp/cloud_api.py) and [optional AI explanation service](../backend/services/ai_zone_explanations.py)
- [Python app dependencies](../requirements/app.txt), [research dependencies](../requirements/research.txt), [development dependencies](../requirements/dev.txt), [frontend manifest](../frontend/package.json)

The source-count date and categories are recorded above. Re-run the census after code changes before presenting the numerical estimate as a current measurement. The provided pasted brief ended mid-sentence during its contingency-reserve section; this report completes the visible cost, contingency, and lifecycle requirements but cannot infer any omitted text after that truncation.
