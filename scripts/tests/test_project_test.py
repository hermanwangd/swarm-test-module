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
                              "Main.java": "class Main {}\n"}.items():
            (self.repo / name).write_text(content)
        git("add", ".")
        git("-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "baseline")
        self.revision = git("rev-parse", "HEAD")
        self.context = self.root / "context"
        FLOW.collect(self.repo, self.revision, self.revision,
                     {"bdd": ["behavior.feature"], "ac": ["AC.md"], "pr": ["PR.md"], "code": ["Main.java"]}, self.context)
        self.design = {
            "schema": "project-test-design.v1", "author": "test-qa",
            "context_sha256": FLOW.sha(self.context / "context.json"),
            "requirements": [
                {"id": "AC-1", "citations": [{"source": "ac:AC.md", "start": 1, "end": 1}], "gap": None},
                {"id": "AC-2", "citations": [{"source": "ac:AC.md", "start": 2, "end": 2}], "gap": "No deployment available"}],
            "cases": [{"id": "TC-1", "requirements": ["AC-1"], "technique": "equivalence",
                       "rationale": "Invalid command class", "preconditions": ["Executable JAR built"],
                       "steps": ["Invoke an unknown command"], "expected": "Reject with usage and exit 2",
                       "citations": [{"source": f"{kind}:{name}", "start": 1, "end": 1} for kind, name in
                                     [("bdd", "behavior.feature"), ("pr", "PR.md"), ("code", "Main.java")]],
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
        with self.assertRaisesRegex(ValueError, "AC-2.*uncovered"):
            FLOW.check(self.context, self.save_design())
        self.design["requirements"][1]["gap"] = "Not runnable"
        self.design["cases"][0]["requirements"] = ["invented"]
        with self.assertRaisesRegex(ValueError, "unknown requirement"):
            FLOW.check(self.context, self.save_design())

    def test_case_requires_bdd_pr_and_code_evidence(self):
        self.design["cases"][0]["citations"] = self.design["cases"][0]["citations"][:1]
        with self.assertRaisesRegex(ValueError, "bdd, pr and code"):
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
