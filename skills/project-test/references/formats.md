# Agent-generated trace and independent review

These are metadata around the existing Framework DSL. Neither file defines new
test operations. Paths are relative to the directory containing `design.json`.
The agent creates these files; the user is not asked to fill in JSON.

`design.json`:

```json
{
  "schema": "project-test-design.v1",
  "author": "actual-qa-agent",
  "context_sha256": "sha256-of-context.json",
  "requirements": [
    {"id": "AC-1", "citations": [{"source": "ac:docs/AC.md", "start": 3, "end": 5}], "gap": null},
    {"id": "AC-2", "citations": [{"source": "ac:docs/AC.md", "start": 7, "end": 8}], "gap": "Required service is unavailable"}
  ],
  "cases": [{
    "id": "TC-1", "requirements": ["AC-1"], "technique": "boundary",
    "rationale": "Input at the documented minimum", "preconditions": ["Reviewed local SUT is built"],
    "steps": ["Send the minimum valid value"], "expected": "The documented result",
    "citations": [
      {"source": "bdd:features/action.feature", "start": 1, "end": 8},
      {"source": "pr:snapshot", "start": 1, "end": 1},
      {"source": "code:src/Action.java", "start": 1, "end": 12}
    ],
    "suite": "suites/minimum", "test_case_id": "TC-1"
  }]
}
```

Use actual source IDs/line ranges from `context.json`. Accepted techniques:
`equivalence`, `boundary`, `state`, `scenario`, `regression`. Each case cites
BDD/PR/code and maps to at least one AC. Each requirement cites its AC source.
The independent reviewer verifies inventory completeness and semantic relevance;
the helper cannot infer that a line citation justifies an assertion.

For each suite, its reviewed handoff must use the same AC IDs in
`requirement_mapping[].requirement_ref`, the same `test_case_id`, the same source
revision and the actual reviewer. There is exactly one test per suite. Suite
manifest, profile and test files use the existing Framework's v0.3 structure in
JSON syntax; reviewed contract files retain the Framework's format.

The host/reviewer supplies `review.json`:

```json
{
  "status": "approved", "reviewer": "actual-independent-reviewer",
  "review_ref": "actual-review-evidence-reference",
  "context_sha256": "sha256-of-context.json", "design_sha256": "sha256-of-design.json",
  "runtime": {
    "java": {"path": "/approved/jdk/bin/java", "sha256": "independent-sha256"},
    "module": {"path": "/approved/swarm-product-test-1.0.0-cli.jar", "sha256": "independent-sha256"},
    "framework": {"path": "/approved/framework.jar", "sha256": "independent-sha256"}
  },
  "subjects": [{"path": "/project/build/product.jar", "sha256": "reviewed-SUT-sha256"}],
  "handoffs": {"TC-1": "sha256-of-prepared-reviewed-tests.json"}
}
```

Pin the complete SUT and indirect executable/input dependencies in `subjects`;
the reviewer validates their source/build provenance. This helper checks their
bytes before and after execution, but does not establish supply-chain provenance.
The review file's externally supplied hash is the trusted host's binding. Text
such as `"reviewer": "someone"` alone proves no identity or approval.

`run` exits 0 only when every inventoried AC has all assigned cases PASS. Exit 1
means an incomplete report (failed/blocked/untested); exit 2 means invalid inputs
or execution prevented before dispatch. `check` only validates a design.

## Execution stages and evidence

Each product report identifies the target and revision in `execution.target`,
the stage actually observed in `execution.stage`, and its evidence source.
For each AC, `execution.acceptance_criteria` records applicability and status
for three stages. Applicability is true, false, or null (undetermined). A reviewed
design or native plan can declare it with the optional per-AC mapping
`"stage_applicability": {"AC1": {"CI": true, "POST_CD_SIT": false}}`.
Historical contexts without a product name or PR retain a null identity.

| Stage | Evidence required |
|---|---|
| LOCAL | Tested commit and local case results, logs or framework receipts. Running a project's CI command locally produces LOCAL evidence. |
| CI | Product pipeline run ID or URL, tested checkout SHA and results of the required jobs. Module publication and downstream package-import jobs describe their own targets. |
| POST_CD_SIT | CD deployment record, target SIT environment, observed artifact version or digest, and integration results from that deployment. |

The local collectors emit NOT_VERIFIED for stages without evidence, or
NOT_APPLICABLE for a stage explicitly excluded by the reviewed scope. Each
top-level verdict describes only that report's execution scope. A local AC
can pass while the local build remains incomplete or a release gate is pending.

Unit describes the scope of a test case. The same unit case can execute in a
developer checkout and again in the product pipeline. Preserve its scope across
runs. A JUnit or pytest result alone cannot establish whether a case exercises
one unit, several components, or a deployed system.
