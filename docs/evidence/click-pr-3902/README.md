# Local QA acceptance on Click PR 3902

The ENGCIM Supervisor intake took the PR URL and GitHub connector metadata,
pinned the product checkout and identified its test configuration. A local
Codex session read the PR, issue 3362, changelog and existing formatter tests.
Three existing functions cover nine parameterized formatter assertions. The
supplemental pytest case exercises the user-facing path called out in issue
3362: a custom argument metavar in narrow command help. The split-word
failure on base and intact word on head use the same test file.

The imported ENGCIM project-test skill launched the native tox runner on this
same Linux machine using Python 3.12. See [the plan](plan.json), [test source](test_local_help.py),
[base control](base-control.xml), [head report](report.json) and [default suite log](4.log).
The two AC passed. The default regression suite recorded 2626 passes, 24 skips
and one expected failure; its default selection excludes 31000 stress cases.
This run used local Codex for design. There is no Mac daemon or independent
reviewer run receipt.

## Replay on one machine

With Git, Python 3.11+, uv and a Python 3.12 interpreter available on the
runner, execute from a checkout of this module:

    sh docs/evidence/click-pr-3902/replay-local.sh

The script fetches the PR head and prints a fresh report path. The module
checks the checkout against the recorded revision. The replay uses the saved
plan and supplemental test. The original discovery and design happened before
that plan existed. Existing result files are preserved.
