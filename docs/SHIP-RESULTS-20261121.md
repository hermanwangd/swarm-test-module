# Test Module delivery evidence — 2026-11-21

The owner changed the repository delivery condition to **public** during this
execution. The independently created repository is
[hermanwangd/swarm-test-module](https://github.com/hermanwangd/swarm-test-module).
No framework ancestor history was pushed. The root is
`39263d79596a14b4a02b946be69cf58122c19c4f`; the released source is
`f7369f5ab872f13c6003aa448f2667c147076c7b`, tag `v1.0.0`.
Production Java source remains byte-identical to the extraction candidate.

## Verified results

| Check | Observed result | Evidence |
| --- | --- | --- |
| Clean clone of the new repository, Java 17 `mvn verify` | 408 tests; 404 passed, 4 skipped, 0 failures/errors | CI [44872347102](https://github.com/hermanwangd/swarm-test-module/actions/runs/44872347102); independent local clean clone also passed |
| Independent consumer import and ServiceLoader | 2/2 passed | Same CI; includes unsupported-SIT rejection before framework dispatch |
| Fresh project/cache against file Maven repository | PASS | Same CI; local transport regression only |
| Real GitHub Maven publication | PASS: POM, library, host, provider, CLI and sources | Publication [44872441893](https://github.com/hermanwangd/swarm-test-module/actions/runs/44872441893) |
| Fresh project/cache resolves published GitHub package | SHA-256/origin checked before execution; 2/2 passed | Same publication run, `internal-maven-publication-44872441893` |
| SQLite harness portability | Failure reproduced; repaired; 9/9 boundary tests passed | Same module CI |
| ENGCIM separately resolves published package | PASS: independent SHA-256 and registry origin, 253 tests with 1 existing skip, actual packaged CLI entry | Host [44872647253](https://github.com/hermanwangd/engcim-swarm/actions/runs/44872647253), [PR #31](https://github.com/hermanwangd/engcim-swarm/pull/31) |

The four module skips are `ReviewedJdbcTransportTest` cases requiring the
externally supplied `reviewed.mariadb.driver.test` artifact. They are not PASS.
The host skip is its historical FDI source-binding acceptance, whose pinned
source checkout is not available. No native Swarm-agent result is claimed.

## Published artifact identities

Coordinate: `com.featuredeliveryintelligence:swarm-product-test:1.0.0`.
Registry: `https://maven.pkg.github.com/hermanwangd/swarm-test-module`.

| Artifact | Published SHA-256 |
| --- | --- |
| Library | `212039a12c463f43f3f2104e3ed0ee9ee5ac9ede08957f6db601bc0a6be11207` |
| CLI | `3d8e46807562bc44c11be9d6ff061d6a9dbe8ed30d77c8ad46810ffd33e04ae3` |
| Host | `d974b29b10b73c35ab183b7f58b939e7f4185cf8b2a89728a6ffa19d8073a880` |
| Provider | `f25b95c82040584f865ed28bfb5b2f46dc39e9c08286585828c6aac704c1a30e` |
| Sources | `0739630409936150e6ef99f9b17b38626e398e7b37d61a4e0729b66a71e5cfad` |

Publication evidence artifact ID: `14694621607`; ZIP SHA-256:
`68bfd59cd30e79bfb0e0a3e3cbe5de3c096cacbdd4618019918500c1d07c3f2a`.
Its source commit, checksums, consumer XML and registry-resolved checksum were
read back and checked. Local builds have their own hashes; they are not
relabeled as the published bytes.

## Runtime and acceptance limits

The separate Framework was built from
`597064a9c75c6323a164a06d050110e16d165aca`, version **0.3.2**, not main's 0.2.7.
The executed Framework JAR SHA-256 is
`cccbcbe2879fd2bf2f66eaf5ac60468903cf7a509076efdb5f661f09cbf898dd`.
Actual packaged calls preserved the reviewed local fixture's `passed` verdict
and the wrong-oracle fixture's `failed` verdict, with canonical validation and
release eligibility false. Those fixtures use the fake provider. The Framework
was packaged with its tests skipped; this is not a full Framework regression
claim. Host runtime receipts are retained with the host integration evidence.

**Real RP SIT, Cross-RP E2E and Release Gate: NOT VERIFIED.** The existing
protected CD hook was actually invoked without a deployment bundle and returned
`BLOCKED`, `framework_launch_attempted: false`, `module_sit_supported: false`,
reason `Required artifact missing, non-regular, or over size limit: deployment.json`.
No deployed RP revisions, real readiness adapters, approved handoff/plan pins,
Cross-RP environment/ownership records or service endpoints were supplied.
The module still rejects SIT. Package publication does not pass these gates.

Native SQLite execution was not completed: the official pinned asset download
was denied with HTTP 403 by this execution environment's network policy. The
repaired harness does not substitute a different binary or oracle.

Host Python export-integrity checks passed 26/27. The remaining
`test_source_classifier_differential_receipt_pins_both_implementations` AST hash
failure was reproduced on untouched host base `9500c6a` under Python 3.12 and on
the candidate under Python 3.13; it remains a pre-existing compatibility gap.

Independent review found two workflow issues (host pre-execution checksum
verification and incomplete publication preflight). Both were repaired and the
re-review reported no actionable findings. PRs remain open; no merge, production
deployment, native role adoption or terminal release acceptance was performed.
