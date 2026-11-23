# Agent-generated trace and independent review

These are metadata around the existing Framework DSL. Neither file defines new
test operations. Paths are relative to the directory containing `design.json`.
The agent creates these files; the user is not asked to fill in JSON.

`design.json`:

```json
{
  "schema": "project-test-design.v2",
  "author": "actual-qa-agent",
  "context_sha256": "sha256-of-context.json",
  "test_inventory": {
    "path": "tests/test-inventory.json",
    "sha256": "sha256-of-the-checked-in-inventory"
  },
  "inventory_scope": ["TC-1", "LegacyDeploymentTest"],
  "requirements": [
    {
      "id": "AC-1",
      "citations": [{"source": "ac:docs/AC.md", "start": 3, "end": 5}],
      "gap": null
    },
    {"id": "AC-2", "citations": [{"source": "ac:docs/AC.md", "start": 7, "end": 8}], "gap": "Required service is unavailable"}
  ],
  "cases": [{
    "id": "TC-1", "requirements": ["AC-1"], "technique": "boundary",
    "rationale": "Input at the documented minimum", "preconditions": ["Reviewed local SUT is built"],
    "steps": ["Send the minimum valid value"], "expected": "The documented result",
    "citations": [
      {"source": "bdd:features/action.feature", "start": 1, "end": 8},
      {"source": "pr:snapshot", "start": 1, "end": 1},
      {"source": "code:src/Action.java", "start": 1, "end": 12},
      {"source": "test:tests/ActionTest.java", "start": 20, "end": 44}
    ],
    "suite": "suites/minimum", "test_case_id": "TC-1"
  }]
}
```

Use actual source IDs/line ranges from `context.json`. Accepted techniques:
`equivalence`, `boundary`, `state`, `scenario`, `regression`. Each case maps to
at least one AC and cites BDD, PR, code and its own `test:<path>` source.
Each requirement cites its AC source and must map to a selected active inventory
entry or carry an explicit gap. A requirement with no designed Framework case
is reported as UNTESTED.

The checked-in test inventory is the durable baseline. Do not rebuild it from
scratch for each task. Its entries use four actions:

- `reuse`: an existing checked-in test remains sufficient.
- `update`: an existing checked-in test is changed for the new requirement.
- `add`: a new checked-in test is introduced.
- `retire`: an obsolete checked-in test is removed from active coverage.

Collect the complete head inventory as a `test:` source and pin its SHA-256.
Every active entry records its project-wide AC mapping and cites its own
`test:<path>`. A retirement records the reason and cites its own current or
historical test. To collect an old path, pass `--historical-test <full-commit>:<path>`
where the commit is reachable from the tested revision. Cite the resulting
`historical-test:<full-commit>:<path>` source. A moved active case keeps its ID,
uses its new path and may also cite the exact prior file.

The optional design field `inventory_scope` selects the affected inventory IDs
for this review. Omission selects every entry, preserving existing v2 designs.
Collect the cited sources for the selected entries. Unselected rows retain their
IDs, mappings and citation metadata without requiring a snapshot of each file.
The checker validates inventory structure and ID uniqueness across the entire
file. For selected rows it also verifies snapshot line ranges. Each executable
case uses a selected active ID and maps to exactly the intersection of the
entry's ACs and the design's ACs. Only executed cases can earn AC credit.
Inventory action totals in the report count the entire pinned inventory.

The independent reviewer verifies inventory completeness,
semantic relevance and baseline decisions; the helper cannot infer that a line
citation justifies an assertion.

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



The checked-in inventory file has this shape:

```json
{
  "schema": "project-test-inventory.v1",
  "entries": [
    {"id": "TC-1", "path": "tests/ActionTest.java",
     "requirements": ["AC-1"], "action": "update",
     "reason": "Extend the existing assertion for the boundary input",
     "citations": [{"source": "test:tests/ActionTest.java", "start": 20, "end": 44}]},
    {"id": "LegacyDeploymentTest", "path": "tests/LegacyDeploymentTest.java",
     "requirements": ["AC-2"], "action": "retire",
     "reason": "The deployment path was removed by the reviewed change",
     "citations": [{"source": "historical-test:<full-ancestor-commit>:tests/LegacyDeploymentTest.java", "start": 1, "end": 30}]}
  ]
}
```

A complete report ties the AC inventory to executed results without promoting
missing evidence:

```json
{
  "schema": "project-test-report.v1",
  "revision": "full-head-sha",
  "review_sha256": "independent-review-pin",
  "claim": "AGENT_AUTHORED_LOCAL_FRAMEWORK_EXECUTION",
  "release_eligible": false,
  "cases": [{"id": "TC-1", "status": "PASS"}],
  "test_inventory": {
    "path": "tests/test-inventory.json",
    "sha256": "sha256-of-the-checked-in-inventory"
  },
  "requirements": [
    {"requirement": "AC-1", "status": "PASS", "cases": ["TC-1"]},
    {"requirement": "AC-2", "status": "UNTESTED", "cases": [], "gap": "Required service is unavailable"}
  ],
  "summary": {
    "status": "INCOMPLETE",
    "cases": {"total": 1, "passed": 1, "failed": 0, "blocked": 0, "untested": 0},
    "requirements": {"total": 2, "passed": 1, "failed": 0, "blocked": 0, "untested": 1},
    "test_inventory": {"total": 2, "reuse": 0, "update": 1, "add": 0, "retire": 1},
    "code_coverage": {"status": "NOT_COLLECTED"},
    "coder_handoff": {"required": false, "assignee": null, "root_cause": "not_applicable", "cases": []}
  },
  "status": "INCOMPLETE"
}
```

Alongside `report.json`, each runner also writes `summary.md`, a human-readable
version of the same status, case/AC counts, inventory actions, code coverage and
coder handoff. The Markdown file is derived from the report; it does not replace
machine-readable evidence.

When a reviewed case FAILs, `summary.coder_handoff.required` is true. The handoff
names the coder as the next owner, but marks the root cause as needing triage
between product code and the reviewed oracle. It links the receipt/result evidence
and asks for a fresh reviewed rerun after the fix. Failure entries also include the
canonical failure code/classification/reason, owner action, run ID, repository
revisions, observed steps, verify results and evidence references so the coder can
reproduce and diagnose the failure instead of relying on a generic FAIL label.
BLOCKED or UNTESTED cases do not become coder work unless a FAIL is present.

A reused existing test still needs an execution record from the applicable native
runner. A citation to an old test is not itself execution evidence. New or updated
cases are reviewed before execution, then checked in so later tasks start from the
updated inventory instead of recreating the baseline.

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
