# BDD / AC / PR / code → designed cases → executed tests

The missing authoring workflow is now supplied by the portable
[project-test skill](../skills/project-test/SKILL.md). The host agent reads the
project, designs cases, gets independent review and invokes the existing module
and Framework. Users provide the project context; they do not author test JSON.
The helper collects pinned sources and validates traceability; **the agent does
the semantic test design**. The JAR alone is not an AI test author.

## Actual local acceptance

A Codex QA agent read the project's [BDD](cli-entry.feature), [AC](CLI-AC.md),
GitHub PR #1 and related Java at `8d2e9447d6dd8a736dfdf109efd18f3834fcbe16`,
then authored three new native CLI cases. These BDD/AC documents restate the
existing published entry contract; this is a focused module-project slice, not
an external application's business acceptance. A separate Codex reviewer read
the sources/assertions and supplied the final independent review pin.

The **ENGCIM-imported copy** of the skill helper executed the published 1.0.0 CLI
as the SUT through the existing Framework's native `cli_process` provider:

| Case | AC | Actual result | Verdict |
|---|---|---|---|
| No command arguments | AC-CLI-1 | exit 2, exact usage, empty stdout | PASS |
| Excess command arguments | AC-CLI-1 | exit 2, exact usage before request read | PASS |
| Readable request, no deployment binding | AC-CLI-2 | exit 2, missing Framework JAR diagnostic | PASS |

**3/3 cases, 9/9 assertions, 2/2 inventoried AC PASS.** Canonical receipts say
`COMPLETED`, `validated`, `passed`; native process evidence records actual launch
and complete cleanup. Local evidence remains release-ineligible.

- [Source, review and result identities](evidence/project-test-20261121/summary.json)
- [Agent-authored design and citations](evidence/project-test-20261121/acceptance/design.json)
- [Per-AC report](evidence/project-test-20261121/acceptance/report.json)
- [Example canonical result](evidence/project-test-20261121/acceptance/TC-CLI-NO-BINDING/result.json)
- [Example actual process evidence](evidence/project-test-20261121/acceptance/TC-CLI-NO-BINDING/native-provider.json)

The same three cases were separately reviewed as a reporting control, with only
the first expected exit deliberately changed from 2 to 99. Actual exit stayed 2;
Framework returned `ASSERTION_FAILED`, that case and AC-CLI-1 stayed **FAIL**, and
the workflow exited 1 with `INCOMPLETE`. This deliberate wrong oracle is excluded
from product acceptance and defect counts. See the
[control report](evidence/project-test-20261121/wrong-oracle-control/report.json).
The first failed assertion stops the control case; its later assertions are not
claimed executed. Positive evidence is preserved unchanged.

## Regression and integration evidence

- New source/trace/review/report checks: **12/12 PASS**. Tests include stale
  snapshots, invented citations, missing sources, partial AC gaps, self-review,
  and GitHub PR diffs when the base branch advances.
- Existing SQLite harness boundaries: **9/9 PASS**; this is not SQLite runtime.
- ENGCIM `clean verify -Pproduct-test`: **253 tests, 252 PASS, one existing source
  history skip**, zero failures/errors. Initial source-map pin failures were
  repaired by updating current skill identities while preserving baseline pins.
- ENGCIM source-copy export/extract tests: **17/17 PASS**, including starting the
  imported helper from the extracted package and the actual Python consumer.
  CI/roadmap files are explicitly excluded from runtime packaging; all 276 module
  records remain accounted for (258 retained, 18 pinned provenance exclusions).
- The previously reported Python AST compatibility blocker is fixed: export
  integrity tests **28/28 PASS on Python 3.12 and 3.13**. Only empty AST compatibility
  fields are normalized; meaningful type parameters are rejected. The original
  expected classifier hash, adapter and historical receipts are unchanged.

The Java runtime artifact remains the immutable, already published `1.0.0`.
Skill delivery is pinned Git source, copied into ENGCIM and included in its source
package. It is not silently added to the old Maven artifact. The published CLI
SHA-256 is `3d8e46807562bc44c11be9d6ff061d6a9dbe8ed30d77c8ad46810ffd33e04ae3`;
Framework SHA-256 is `cccbcbe2879fd2bf2f66eaf5ac60468903cf7a509076efdb5f661f09cbf898dd`.
The source/pom at the test context revision have zero diff from release source
`f7369f5ab872f13c6003aa448f2667c147076c7b`.

## Outstanding acceptance

Native ENGCIM agent adoption is **NOT VERIFIED**: this environment has no Multica
command/connector or live actor bindings. The tested route is local Codex design
and independent review, followed by the imported skill helper and real Framework.
Source integration is not evidence of a deployed agent loading the skill.

Real SIT, Cross-RP E2E and Release Gate are **NOT VERIFIED**. No deployed RP bundle,
service bindings or Cross-RP environment was supplied; the existing SIT preflight
stops at missing `deployment.json`. The local module still rejects SIT/preprod/live.
These limitations cannot be resolved by declaring local cases passed.
