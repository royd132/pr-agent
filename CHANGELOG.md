# Changelog

## 0.1.0 — 2026-09-07

- Introduced the DiffPrism public package and CLI while retaining legacy import compatibility.
- Added `DIFFPRISM_*` settings with `EVOAGENT_*` fallback.
- Replaced domain workers with the Prism Lead, Scope Mapper, Failure Hunter and Evidence Examiner protocol.
- Added change maps, merge verdicts and evidence decisions to reports.
- Presented Skills as Review Packs without changing package identity or hot reload.
- Added Synthetic Fault Benchmark v1 metadata, p95 latency and cost per verified finding.
- Rebuilt the dependency-free Web console around PR Inbox, Review Workspace and Benchmark Lab.
- Added architecture, protocol, evaluation, security and deterministic example documentation.

This release does not claim production accuracy from the bundled synthetic fixture.
