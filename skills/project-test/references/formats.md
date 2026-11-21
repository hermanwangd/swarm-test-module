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
