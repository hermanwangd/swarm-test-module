# Apache Commons CLI PR 450

**Execution stage: LOCAL.** See the [per-AC stage classification](execution-stages.json). Product CI and post-CD SIT remain unverified by this evidence.

The PR describes property values leaking between parses when callers reuse an
Options instance. Its description and the public DefaultParser contract supply
the expected behavior. At the PR head, four existing JUnit methods already
assert the five inventoried behaviors. Three methods came with the PR and one
predates it. QA reused all four. See [the PR snapshot](pr.json) and
[the assertion-to-AC mapping](plan.json).

The QA Module ran the PR workflow's Maven default invocation on Linux with
Temurin 17 and Maven 3.9.9, in a fresh checkout at the plan's head SHA.
[The report](report.json) records individual Surefire outcomes, AC results,
default build exit status and separately generated JaCoCo counters. The build
ran 998 tests (937 passed, 61 skipped). Its final Javadoc goal was blocked by
HTTP 403 while fetching Jakarta platform documentation. See [Maven output](maven.log)
and [coverage execution](coverage.log). The product CI matrix and post-deployment SIT have no execution evidence in this run.

For the [base control](base-control.log), the four head test methods ran under
Surefire against unchanged base production code by copying the head
DefaultParserTest.java into a detached base worktree. Three tests failed. The
pre-existing preset-value precedence case passed on both revisions.

Local Codex selected the product, inspected the PR, and authored the mapping.
The QA Module executed the native runner. A production ENGCIM QA agent,
independent blind reviewer and production mission ID were unavailable here.

A separate [product CI receipt](product-ci.json) records the real GitHub Actions workflow, returned jobs and selected checkout log. The remote runner tested the PR merge ref. Workflow success and local supplemental case results retain separate scopes.
