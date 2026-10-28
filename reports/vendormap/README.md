# VendorMap redesign verification

Implemented locally against the existing React/Vite application and FastAPI contracts. No backend source, decision logic, database schema, model artifacts, or official data was changed. Browser writes use a disposable database; geometry is copied read-only without vendor assignments. Existing user changes outside this frontend work remain untouched.

## Experience

- Forest green, ivory and lime identity, large typography, centralized design styles, visible focus and reduced-motion support.
- Desktop top navigation and four-destination vendor mobile navigation replace the permanent sidebar.
- Vendor home emphasizes finding a place; request and allocation information appears when present. Recommendations retain Top 3, full eligible-zone browsing, real GIS, preference persistence and application controls. Detail scoring is expandable; unscored zones do not display a numeric score.
- Profile and account settings remain one workspace with existing language, privacy and export features.
- Officer overview, applications, allocations, zone list/city map, geographic slots and a readable vendor directory. Full registry table remains expandable. Relocation planning is available under Vendors, with individual read-only alternatives in vendor details.
- Removed Research Recommendations, GIS & Model Insights, Expert Review and their unused research page dependencies from frontend source. Backend APIs and research assets remain intact.
- Added DirectoryResults, VendorWorkspace and RelocationPlanning feature components, product translation overrides, CSS cascade layers, and lazy screen bundles.

## Checks

- `npm test`: **46 passed**. Updated obsolete terminology expectations and supplied actual slot records in the selection-persistence fixture. Runtime selection and backend logic were not changed.
- `node tests/pilot-browser-smoke.mjs`: **passed**. Uses fixtures for API, GPS and routing responses. Covers slot selection, assignment update, retained map state, responsive screens, own-slot access and private-vendor field exclusion. Removed references to obsolete layout-generation controls from this test.
- `node tests/vendormap-browser.mjs`: real FastAPI and disposable database; see [browser-results.json](browser-results.json). Checks onboarding entry, three recommendations, preference persistence, all-zone map/list, non-Top-3 application submission, tracking, profile saving, officer approval, vendor search, read-only relocation alternatives, city map and slot workspace. No browser runtime exceptions in the passing run.
- Seven screens checked at **360, 390, 768, 1024 and 1440 pixels**: 35 comparisons, with no horizontal page overflow. Tables retain their own horizontal scrolling. Screenshots are saved alongside this report.
- Production build: `npm run build`.
- `git diff --check`: passed.

## Existing backend test mismatches

The selected backend suite returned **35 passed, 7 failed**:

- One personalization test expects earlier preference multipliers.
- Five admin workflow tests submit business categories that conflict with the authenticated vendor profile and receive HTTP 422.
- One historical registry test expects an earlier vendor name in the official dataset.

These backend tests and protected backend/data files were not modified. This result does not establish full backend test-suite parity. Browser verification exercises representative workflows, not every permission, error or language combination.

## Rollback

Original tracked frontend checkpoint: commit `8773d6cc65566bc5bfee97befe0ea130c2aec111` and [vendormap-frontend-before.zip](../vendormap-frontend-before.zip).
