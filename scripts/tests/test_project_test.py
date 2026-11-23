"""Source-to-case traceability and execution gates, using a real temporary Git repo."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[2] / "skills/project-test/scripts/project_test.py"
SPEC = importlib.util.spec_from_file_location("project_test", SCRIPT)
FLOW = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FLOW)


class ProjectTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        def git(*args):
            return subprocess.check_output(["git", "-C", str(self.repo), *args], text=True).strip()
        self.git = git
        git("init", "-q")
        for name, content in {"behavior.feature": "Feature: command\nScenario: invalid command\nThen reject it\n",
                              "AC.md": "AC-1: reject unknown commands\nAC-2: require a deployment binding\n",
                              "PR.md": "Change: package the command as an executable JAR\n",
                              "Main.java": "class Main {}\n",
                              "MainTest.java": "class MainTest { void rejectsUnknownCommand() {} }\n",
                              "test-inventory.json": """{
  \"schema\": \"project-test-inventory.v1\",
  \"entries\": [
    {\"id\": \"MainTest.rejectsUnknownCommand\", \"path\": \"MainTest.java\", \"requirements\": [\"AC-1\"],
     \"action\": \"reuse\", \"reason\": \"Existing assertion covers the rejected-command behavior\",
     \"citations\": [{\"source\": \"test:MainTest.java\", \"start\": 1, \"end\": 1}]},
    {\"id\": \"TC-1\", \"path\": \"MainTest.java\", \"requirements\": [\"AC-1\"],
     \"action\": \"update\", \"reason\": \"Framework case extends the checked-in assertion\",
     \"citations\": [{\"source\": \"test:MainTest.java\", \"start\": 1, \"end\": 1}]}
  ]
}\n"""}.items():
            (self.repo / name).write_text(content)
        git("add", ".")
        git("-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "baseline")
        self.revision = git("rev-parse", "HEAD")
        self.context = self.root / "context"
        FLOW.collect(self.repo, self.revision, self.revision,
                     {"bdd": ["behavior.feature"], "ac": ["AC.md"], "pr": ["PR.md"], "code": ["Main.java"],
                      "test": ["MainTest.java", "test-inventory.json"]}, self.context)
        inventory_path = self.repo / "test-inventory.json"
        self.design = {
            "schema": "project-test-design.v2", "author": "test-qa",
            "context_sha256": FLOW.sha(self.context / "context.json"),
            "requirements": [
                {"id": "AC-1", "citations": [{"source": "ac:AC.md", "start": 1, "end": 1}], "gap": None},
                {"id": "AC-2", "citations": [{"source": "ac:AC.md", "start": 2, "end": 2}], "gap": "No deployment available"}],
            "test_inventory": {"path": "test-inventory.json", "sha256": FLOW.sha(inventory_path)},
            "cases": [{"id": "TC-1", "requirements": ["AC-1"], "technique": "equivalence",
                       "rationale": "Invalid command class", "preconditions": ["Executable JAR built"],
                       "steps": ["Invoke an unknown command"], "expected": "Reject with usage and exit 2",
                       "citations": [{"source": f"{kind}:{name}", "start": 1, "end": 1} for kind, name in
                                     [("bdd", "behavior.feature"), ("pr", "PR.md"), ("code", "Main.java"),
                                      ("test", "MainTest.java")]],
                       "suite": "suites/rejected-command", "test_case_id": "TC-1"}]}

    def save_design(self):
        path = self.root / "design.json"
        FLOW.write(path, self.design)
        return path

    def test_reads_committed_sources_instead_of_dirty_worktree(self):
        (self.repo / "AC.md").write_text("DO NOT USE DIRTY CONTENT")
        context, _ = FLOW.check(self.context, self.save_design())
        ac = next(x for x in context["sources"] if x["id"] == "ac:AC.md")
        self.assertEqual("AC-1: reject unknown commands\nAC-2: require a deployment binding\n",
                         (self.context / ac["snapshot"]).read_text())
        self.assertEqual(self.revision, context["revision"])

    def test_missing_bdd_cannot_be_silently_replaced_with_code(self):
        with self.assertRaisesRegex(ValueError, "bdd"):
            FLOW.collect(self.repo, self.revision, self.revision, {"ac": ["AC.md"], "pr": ["PR.md"],
                         "code": ["Main.java"]}, self.root / "missing")

    def test_symlink_sources_and_traversal_are_not_project_evidence(self):
        (self.repo / "link").symlink_to("AC.md")
        self.git("add", "link")
        self.git("-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "link")
        for path in ["link", "../AC.md"]:
            with self.subTest(path=path), self.assertRaises(ValueError):
                FLOW.collect(self.repo, self.git("rev-parse", "HEAD"), self.revision,
                             {"bdd": [path], "ac": ["AC.md"], "pr": ["PR.md"], "code": ["Main.java"]},
                             self.root / ("unsafe-" + path.replace("/", "_")))

    def test_source_changes_after_design_are_rejected(self):
        context = FLOW.read(self.context / "context.json")
        (self.context / context["sources"][0]["snapshot"]).write_text("changed")
        with self.assertRaisesRegex(ValueError, "source.*changed"):
            FLOW.check(self.context, self.save_design())

    def test_invented_or_out_of_range_citations_are_rejected(self):
        for citation in [{"source": "code:invented", "start": 1, "end": 1},
                         {"source": "code:Main.java", "start": 1, "end": 999}]:
            with self.subTest(citation=citation):
                self.design["cases"][0]["citations"][-1] = citation
                with self.assertRaisesRegex(ValueError, "citation"):
                    FLOW.check(self.context, self.save_design())

    def test_missing_ac_mapping_and_missing_gap_are_rejected(self):
        self.design["requirements"][1]["gap"] = None
        with self.assertRaisesRegex(ValueError, "AC-2.*no active checked-in test"):
            FLOW.check(self.context, self.save_design())
        self.design["requirements"][1]["gap"] = "Not runnable"
        self.design["cases"][0]["requirements"] = ["invented"]
        with self.assertRaisesRegex(ValueError, "unknown requirement"):
            FLOW.check(self.context, self.save_design())

    def test_case_requires_bdd_pr_and_code_evidence(self):
        self.design["cases"][0]["citations"] = self.design["cases"][0]["citations"][:1]
        with self.assertRaisesRegex(ValueError, "bdd, pr and code"):
            FLOW.check(self.context, self.save_design())


    def test_checked_in_inventory_is_required_and_digest_pinned(self):
        original = self.design.pop("test_inventory")
        with self.assertRaisesRegex(ValueError, "test inventory"):
            FLOW.check(self.context, self.save_design())
        self.design["test_inventory"] = dict(original, sha256="0" * 64)
        with self.assertRaisesRegex(ValueError, "digest"):
            FLOW.check(self.context, self.save_design())

    def test_inventory_reuse_requires_test_citation_and_cases_are_registered(self):
        def replace_inventory(entries):
            context = FLOW.read(self.context / "context.json")
            source = next(item for item in context["sources"] if item["id"] == "test:test-inventory.json")
            snapshot = self.context / source["snapshot"]
            FLOW.write(snapshot, {"schema": "project-test-inventory.v1", "entries": entries})
            source["sha256"] = FLOW.sha(snapshot)
            source["lines"] = len(snapshot.read_text().splitlines())
            FLOW.write(self.context / "context.json", context)
            self.design["context_sha256"] = FLOW.sha(self.context / "context.json")
            self.design["test_inventory"]["sha256"] = source["sha256"]
        inventory = FLOW.read(self.repo / "test-inventory.json")
        without_citation = [dict(entry) for entry in inventory["entries"]]
        without_citation[0]["citations"] = []
        replace_inventory(without_citation)
        with self.assertRaisesRegex(ValueError, "citation"):
            FLOW.check(self.context, self.save_design())

        replace_inventory(inventory["entries"][:1])
        with self.assertRaisesRegex(ValueError, "not registered"):
            FLOW.check(self.context, self.save_design())

    def test_report_never_counts_unexecuted_or_failed_requirements_as_pass(self):
        for status in ["PASS", "FAIL", "BLOCKED"]:
            report = FLOW.coverage(self.design, [{"id": "TC-1", "status": status}])
            self.assertEqual([status, "UNTESTED"], [r["status"] for r in report])
        self.assertEqual("BLOCKED", FLOW.coverage(self.design, [])[0]["status"])

    def test_partially_tested_ac_with_remaining_gap_is_not_pass(self):
        self.design["requirements"][0]["gap"] = "Only the local part ran; remote behavior is missing"
        report = FLOW.coverage(self.design, [{"id": "TC-1", "status": "PASS"}])
        self.assertEqual("BLOCKED", report[0]["status"])


    def test_summary_counts_and_failed_case_coder_handoff(self):
        inventory = FLOW.read(self.repo / "test-inventory.json")["entries"]
        cases = [
            {"id": "PASS-1", "status": "PASS"},
            {"id": "FAIL-1", "status": "FAIL", "expected": "expected", "reason": "ASSERTION_FAILED",
             "receipt": "receipt.json", "result": {"path": "result.json", "sha256": "a" * 64}, "receipt_sha256": "b" * 64},
            {"id": "BLOCKED-1", "status": "BLOCKED"},
        ]
        requirements = [{"status": "PASS"}, {"status": "FAIL"}, {"status": "UNTESTED"}]
        summary = FLOW.report_summary(cases, requirements, inventory,
                                      {"status": "COLLECTED", "lines": {"covered": 1, "total": 2}}, "INCOMPLETE")
        self.assertEqual({"total": 3, "passed": 1, "failed": 1, "blocked": 1, "untested": 0}, summary["cases"])
        self.assertEqual({"total": 3, "passed": 1, "failed": 1, "blocked": 0, "untested": 1},
                         summary["requirements"])
        self.assertEqual({"total": 2, "reuse": 1, "update": 1, "add": 0, "retire": 0},
                         summary["test_inventory"])
        handoff = summary["coder_handoff"]
        self.assertTrue(handoff["required"])
        self.assertEqual("coder", handoff["assignee"])
        self.assertEqual("product_or_test_oracle_needs_triage", handoff["root_cause"])
        self.assertEqual(["FAIL-1"], [case["id"] for case in handoff["cases"]])

    def test_failure_details_include_observed_evidence_and_owner_action(self):
        canonical = {
            "run_id": "RUN-1",
            "product_test": {"repository_revisions": {"example/project": "a" * 40}},
            "failure": {"code": "ASSERTION_FAILED", "classification": "VERIFICATION_FAILED",
                        "reason": "Assertion `exit_code_matches` failed.", "owner_action": "Review assertion evidence."},
            "step_results": [{"id": "invoke", "status": "passed", "outputs": {"exit_code": 2}}],
            "verify_results": [{"id": "exit_code_matches", "status": "failed", "evidence_ref": "assertions/x.yaml"}],
            "evidence_refs": ["assertions/x.yaml", "result.json"],
        }
        details = FLOW.failure_details(canonical)
        self.assertEqual("ASSERTION_FAILED", details["failure_code"])
        self.assertEqual("VERIFICATION_FAILED", details["failure_classification"])
        self.assertEqual("Assertion `exit_code_matches` failed.", details["failure_reason"])
        self.assertEqual("Review assertion evidence.", details["owner_action"])
        self.assertEqual("RUN-1", details["run_id"])
        self.assertEqual({"example/project": "a" * 40}, details["repository_revisions"])
        self.assertEqual(2, details["observed_steps"][0]["outputs"]["exit_code"])
        self.assertEqual("assertions/x.yaml", details["verify_results"][0]["evidence_ref"])
        self.assertEqual(["assertions/x.yaml", "result.json"], details["evidence_refs"])

    def test_blocked_without_failure_does_not_create_coder_handoff(self):
        summary = FLOW.report_summary([{"id": "BLOCKED-1", "status": "BLOCKED"}],
                                      [{"status": "BLOCKED"}], [], status="INCOMPLETE")
        self.assertFalse(summary["coder_handoff"]["required"])
        self.assertEqual("not_applicable", summary["coder_handoff"]["root_cause"])


    def test_markdown_summary_is_human_readable_and_contains_coder_handoff(self):
        inventory = FLOW.read(self.repo / "test-inventory.json")["entries"]
        cases = [{"id": "FAIL-1", "status": "FAIL", "expected": "expected", "reason": "ASSERTION_FAILED",
                  "receipt": "receipt.json", "result": {"path": "result.json", "sha256": "a" * 64},
                  "receipt_sha256": "b" * 64}]
        summary = FLOW.report_summary(cases, [{"status": "FAIL"}], inventory,
                                      {"status": "COLLECTED", "lines": {"covered": 1, "total": 2}}, "INCOMPLETE")
        markdown = FLOW.markdown_summary(summary)
        for expected in ("# Test report summary", "Overall status: **INCOMPLETE**",
                         "| Test cases | 1 | 0 | 1 | 0 | 0 |", "| Requirements | 1 | 0 | 1 | 0 | 0 |",
                         "Coder handoff", "Assignee: **coder**", "product_or_test_oracle_needs_triage",
                         "receipt.json", "Rerun from a fresh output directory after the fix and review"):
            self.assertIn(expected, markdown)

    def test_pull_request_diff_excludes_base_branch_only_changes(self):
        original = self.revision
        (self.repo / "base-only.txt").write_text("Unrelated change on the base branch\n")
        self.git("add", ".")
        self.git("-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "base advances")
        advanced_base = self.git("rev-parse", "HEAD")
        self.git("checkout", "-q", "--detach", original)
        (self.repo / "Main.java").write_text("class Main { int change; }\n")
        self.git("add", ".")
        self.git("-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "PR change")
        output = self.root / "diverged"
        context = FLOW.collect(self.repo, self.git("rev-parse", "HEAD"), advanced_base,
                               {"bdd": ["behavior.feature"], "ac": ["AC.md"], "pr": ["PR.md"], "code": ["Main.java"]}, output)
        diff = next(s for s in context["sources"] if s["id"] == "pr:diff")
        self.assertNotIn("base-only.txt", (output / diff["snapshot"]).read_text())
        self.assertEqual(original, context["diff_base"])

    def test_review_is_pinned_before_any_execution(self):
        review = self.root / "review.json"
        FLOW.write(review, {"status": "approved"})
        with patch.object(FLOW.subprocess, "run") as launch:
            with self.assertRaisesRegex(ValueError, "review.*pin"):
                FLOW.run(self.context, self.save_design(), review, "0" * 64, self.root / "run")
            launch.assert_not_called()

    def test_self_review_cannot_authorize_execution(self):
        review = self.root / "review.json"
        FLOW.write(review, {"status": "approved", "reviewer": "test-qa", "review_ref": "local://review",
                           "context_sha256": FLOW.sha(self.context / "context.json"),
                           "design_sha256": FLOW.sha(self.save_design())})
        with patch.object(FLOW.subprocess, "run") as launch:
            with self.assertRaisesRegex(ValueError, "independent"):
                FLOW.run(self.context, self.save_design(), review, FLOW.sha(review), self.root / "run")
            launch.assert_not_called()

    def test_remote_ci_binds_fork_pr_merge_checkout_and_preserves_evidence_scope(self):
        head, merge = "a" * 40, "b" * 40
        run = dict(id=4, run_attempt=2, name="Build", head_sha=head, event="pull_request",
                   repository={"full_name": "a/b"}, pull_requests=[], status="completed", conclusion="success",
                   html_url="https://github.com/a/b/actions/runs/4")
        job = dict(id=8, name="tests", run_id=4, status="completed", conclusion="success",
                   html_url=run["html_url"] + "/job/8")
        prefix = "repos/a/b"
        responses = {prefix + "/pulls/7": {"head": {"sha": head}},
                     prefix + "/actions/runs?event=pull_request&head_sha=" + head + "&per_page=100":
                     {"total_count": 1, "workflow_runs": [run]},
                     prefix + "/actions/runs/4/attempts/2/jobs?per_page=100": {"total_count": 1, "jobs": [job]}}
        log = f"time [command]/bin/git fetch origin +{merge}:refs/remotes/pull/7/merge\n"
        log += "time [command]/bin/git log -1 --format=%H\ntime " + merge
        def fetch(endpoint, raw=False):
            return log if raw and endpoint == prefix + "/actions/jobs/8/logs" else responses[endpoint]
        receipt = FLOW.github_ci("https://github.com/a/b/pull/7", "Build", "tests", fetch)
        self.assertEqual(merge, receipt["inspected_job"]["checkout_sha"])
        self.assertEqual(head, receipt["pr_head"])
        self.assertEqual("NOT_VERIFIED", receipt["per_ac_verdict"])
        log = log.replace("/7/merge", "/3/merge")
        with self.assertRaisesRegex(ValueError, "not bound"):
            FLOW.github_ci("https://github.com/a/b/pull/7", "Build", "tests", fetch)

    def test_local_evidence_cannot_promote_product_ci_or_sit(self):
        report = {"revision": self.revision, "requirements": {"AC1": "PASS", "AC2": "FAIL"}}
        FLOW.record_local_execution(report, "example/project", ["AC1", "AC2"], "local JUnit",
                                    {"AC1": {"CI": True, "POST_CD_SIT": False}})
        rows = report["execution"]["acceptance_criteria"]
        self.assertEqual(rows["AC1"]["CI"], {"applicable": True, "status": "NOT_VERIFIED"})
        self.assertEqual(rows["AC1"]["POST_CD_SIT"]["status"], "NOT_APPLICABLE")
        self.assertEqual(rows["AC2"]["LOCAL"]["status"], "FAIL")
        self.assertEqual(rows["AC2"]["POST_CD_SIT"], {"applicable": None, "status": "NOT_VERIFIED"})
        with self.assertRaisesRegex(ValueError, "inapplicable"):
            FLOW.record_local_execution(report, "example/project", ["AC1"], "local JUnit", {"AC1": {"LOCAL": False}})

    def test_maven_ci_success_cannot_cover_absent_or_skipped_assertions(self):
        from argparse import Namespace
        import os
        (self.repo / 'ci.yml').write_text('  run: mvn test\n')
        self.git('add', 'ci.yml')
        self.git('-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'ci')
        binary = self.root / 'mvn'
        binary.write_text("""#!/bin/sh
mkdir -p target/surefire-reports
echo '<testsuite><testcase classname="C" name="ok"/><testcase classname="C" name="skip"><skipped/></testcase></testsuite>' > target/surefire-reports/TEST-C.xml
""")
        binary.chmod(0o755)
        path = self.root / 'plan.json'
        cases = [dict(origin='existing', path='Main.java', method=name, requirements=[name],
                      assertion='checked by fixture', **{'class': 'C'}) for name in ('ok', 'skip', 'missing')]
        FLOW.write(path, dict(revision=self.git('rev-parse', 'HEAD'), runner=['mvn', 'test'],
                              workflow='ci.yml', requirements=['ok', 'skip', 'missing', 'unmapped'], cases=cases))
        args = Namespace(repo=self.repo, plan=path, plan_sha256=FLOW.sha(path), out=self.root / 'native')
        with patch.dict(os.environ, PATH=str(self.root) + os.pathsep + os.environ['PATH']):
            self.assertEqual(1, FLOW.native_maven(args))
        report = FLOW.read(args.out / 'report.json')
        self.assertEqual('PASS', report['regression']['status'])
        self.assertEqual({'ok': 'PASS', 'skip': 'BLOCKED', 'missing': 'BLOCKED', 'unmapped': 'UNTESTED'},
                         report['requirements'])


if __name__ == "__main__":
    unittest.main()
