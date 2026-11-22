import importlib.util
import json
import subprocess
import tempfile
import unittest
from argparse import Namespace
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch
from xml.etree import ElementTree as ET


SCRIPT = Path(__file__).resolve().parents[2] / "skills/project-test/scripts/project_test.py"
SPEC = importlib.util.spec_from_file_location("project_test", SCRIPT)
FLOW = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FLOW)


class PytestRegressionSummary(unittest.TestCase):
    def check_report(self, outcomes, pytest_exit, ac_status="PASS"):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name).resolve()
        repo = root / "repo"
        repo.mkdir()
        (repo / "src").mkdir()
        (repo / "src/example.py").write_text("answer = 42\n")
        def git(*args):
            return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()
        git("init", "-q")
        git("add", ".")
        git("-c", "user.email=fixture@example.invalid", "-c", "user.name=Fixture", "commit", "-qm", "fixture")
        ac = root / "ac.json"
        FLOW.write(ac, {"schema": "project-test-report.v1", "revision": git("rev-parse", "HEAD"),
                        "status": ac_status, "requirements": [{"requirement": "AC-1", "status": ac_status}]})
        out = root / "out"
        args = Namespace(repo=repo, out=out, source="src", ac_report=ac, include_stress=False, python=root/"runner")
        real_run = subprocess.run

        def runner(cmd, **kwargs):
            if cmd[0] != str(args.python):
                return real_run(cmd, **kwargs)
            if cmd[3] == "json":
                FLOW.write(out / "coverage.json", {"meta": {"branch_coverage": True}, "totals": {
                    "covered_lines": 1, "num_statements": 1, "covered_branches": 0, "num_branches": 0}})
                return subprocess.CompletedProcess(cmd, 0)
            suite = ET.Element("testsuite", tests=str(len(outcomes)), failures=str(outcomes.count("failure")),
                               errors=str(outcomes.count("error")), skipped=str(outcomes.count("skipped")))
            for n, outcome in enumerate(outcomes):
                case = ET.SubElement(suite, "testcase", classname="Example", name=f"test_{n}")
                if outcome != "passed":
                    ET.SubElement(case, outcome)
            ET.ElementTree(suite).write(out / "junit.xml")
            return subprocess.CompletedProcess(cmd, pytest_exit)

        with patch.object(FLOW.subprocess, "run", side_effect=runner), redirect_stdout(StringIO()):
            rc = FLOW.pytest_regression(args)
        report = json.loads((out / "report.json").read_text())
        self.assertEqual(report["status"], report["summary"]["status"])
        markdown = (out / "summary.md").read_text(encoding="utf-8")
        self.assertTrue(markdown.startswith("# Test report summary\n"))
        self.assertEqual(FLOW.markdown_summary(report["summary"]), markdown)
        return rc, report, markdown

    def test_two_passes_reach_top_level_and_summary(self):
        rc, report, _ = self.check_report(["passed", "passed"], 0)
        self.assertEqual((0, "PASS"), (rc, report["status"]))
        self.assertEqual({"total": 2, "passed": 2, "failed": 0, "blocked": 0, "untested": 0},
                         report["summary"]["cases"])

    def test_mixed_junit_outcomes_keep_failures_and_link_evidence(self):
        rc, report, markdown = self.check_report(["passed", "failure", "error", "skipped"], 1)
        self.assertEqual((1, "INCOMPLETE"), (rc, report["status"]))
        self.assertEqual({"total": 4, "passed": 1, "failed": 2, "blocked": 1, "untested": 0},
                         report["summary"]["cases"])
        handoff = report["summary"]["coder_handoff"]
        self.assertTrue(handoff["required"])
        self.assertEqual(["Example::test_1", "Example::test_2"], [row["id"] for row in handoff["cases"]])
        for name in ("junit.xml", "pytest.log"):
            self.assertIn(f"`{name}` (SHA-256 `{report['evidence_sha256'][name]}`)", markdown)
        self.assertNotIn("Receipt SHA-256", markdown)
        for row in handoff["cases"]:
            self.assertEqual("junit.xml", row["evidence"]["junit"])
            self.assertEqual(report["evidence_sha256"]["junit.xml"], row["evidence"]["junit_sha256"])

    def test_all_skipped_never_passes(self):
        rc, report, _ = self.check_report(["skipped"], 0)
        self.assertEqual((1, "INCOMPLETE"), (rc, report["status"]))
        self.assertEqual(1, report["summary"]["cases"]["blocked"])
        self.assertFalse(report["summary"]["coder_handoff"]["required"])

    def test_maven_markdown_includes_jacoco_totals_and_surefire_file(self):
        digest = "a" * 64
        case = {"id": "Example::example", "status": "FAIL",
                "junit": [{"file": "evidence/surefire/TEST-example.xml", "sha256": digest}]}
        coverage = {"status": "COLLECTED", "LINE": {"covered": 3, "missed": 2},
                    "BRANCH": {"covered": 0, "missed": 0}}
        markdown = FLOW.markdown_summary(FLOW.report_summary([case], [], [], coverage))
        self.assertIn("Lines: **3 / 5**", markdown)
        self.assertIn("Branches: **0 / 0**", markdown)
        self.assertIn(f"`evidence/surefire/TEST-example.xml` (SHA-256 `{digest}`)", markdown)
