# External project acceptance run

**Execution stage: LOCAL.** See the [per-AC stage classification](execution-stages.json). Product CI and post-CD SIT remain unverified by this evidence.

Upstream [pallets/click PR 3884](https://github.com/pallets/click/pull/3884)
specifies how environment variable names appear in option help and errors.
The PR table, CHANGES.md and upstream behavior tests supply the expected
behavior. Click expresses these scenarios in pytest. The probe uses the
public Click API with a different option name and input values.

The sequence case observes the exact missing-option message, including quoting
a name containing a space. The empty case compares complete help and error
output against the same command with no environment variable, for both an empty
string and an empty list. The leading numbers in the observations are Click's
exit codes. The probe exits normally so the Framework can judge its output.

baseline.json records observations from the probe invoked directly against the
base source archive. report.json records execution against the PR head through
the published Test Module and its Framework. The same probe and expected values
were used for both versions. Each archive was created with git archive from
the exact revision's src tree, containing only click/. The probe imports from
that archive under isolated Python and checks the actual module location.
Coverage is local to the two selected behaviors. Automatic environment prefixes
and the complete upstream regression suite are outside this run.

The subsequent [combined module run](upstream-regression/report.json) ran both
authored cases and upstream pytest on Linux / CPython 3.12.14. The production
line coverage was 4207/4857 and branch coverage was 1350/1680. All six upstream
empty-environment help cases passed, including three automatic-prefix cases.
The separately reported 2/2 AC count still describes the original authored
cases. The regression stage ran the upstream default selection, with 2111
passes, 24 platform skips and one expected failure. Upstream excludes 31000
stress iterations by default. See the [scope details](upstream-regression/scope.json),
[pytest log](upstream-regression/pytest.log) and [coverage data](upstream-regression/coverage.json).

The [full upstream run including stress](full-regression/summary.json) has
finished. All 31,000 stress cases passed. The complete run recorded 33,111
passes, 24 Windows-only skips and one expected failure on Linux. This
supplemental run used upstream pytest directly; the module's combined run
above used the project's default regression selection.

The [local tox report](native-tox/report.json) records a separate Linux
CPython 3.12 run through the PR workflow's locked uv/tox entry. Two existing
pytest functions supplied twelve parameterized checks of help and missing-option
diagnostics. Two supplemental pytest tests exercise the invalid-value diagnostic
specified in the PR body. Both failed against the base revision and passed at
the PR head. See the [base JUnit output](native-tox/base-control.xml),
[native plan and assertion mappings](native-tox/plan.json), [default regression
log](native-tox/4.log) and [separate coverage measurement](native-tox/coverage-summary.json).
The plan and tests were prepared in this workspace. Formal ENGCIM agent execution
and independent native-plan review are unverified.

A separate [product CI receipt](product-ci.json) records the real GitHub Actions workflow, returned jobs and selected checkout log. The remote runner tested the PR merge ref. Workflow success and local supplemental case results retain separate scopes.
