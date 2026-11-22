"""Offline boundary checks; no network, compiler or SQLite execution."""
import importlib.util
import io
import json
import os
from argparse import Namespace
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch
import zipfile

SCRIPT = Path(__file__).resolve().parents[1] / "public-cli-project.py"
SPEC = importlib.util.spec_from_file_location("public_cli_project", SCRIPT)
HARNESS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HARNESS)


class PublicCliProjectTest(unittest.TestCase):
    def archive(self, names):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            for name, mode in names:
                info = zipfile.ZipInfo(name)
                info.external_attr = mode << 16
                archive.writestr(info, b"public fixture")
        buffer.seek(0)
        return zipfile.ZipFile(buffer)

    def test_only_complete_exact_archive_member_set_is_accepted(self):
        lock = {"root": "source", "members": ["shell.c", "sqlite3.c", "sqlite3.h", "sqlite3ext.h"]}
        with self.archive([("source/" + name, stat.S_IFREG | 0o644) for name in lock["members"]]) as archive:
            self.assertEqual(4, len(HARNESS.archive_members(archive, lock)))
        with self.archive([("source/shell.c", stat.S_IFREG | 0o644)]) as archive:
            with self.assertRaisesRegex(ValueError, "Missing"):
                HARNESS.archive_members(archive, lock)

    def test_traversal_absolute_symlink_and_unreviewed_files_are_rejected(self):
        lock = {"root": "source", "members": ["shell.c"]}
        for name, mode in [("../shell.c", stat.S_IFREG), ("/shell.c", stat.S_IFREG),
                           ("source/shell.c", stat.S_IFLNK), ("source/unreviewed.c", stat.S_IFREG)]:
            with self.subTest(name=name, mode=mode), self.archive([(name, mode | 0o644)]) as archive:
                with self.assertRaises(ValueError):
                    HARNESS.archive_members(archive, lock)

    def test_expanded_source_bound_is_enforced_before_extracting(self):
        class Archive:
            def infolist(self):
                info = zipfile.ZipInfo("source/shell.c")
                info.file_size = 21 * 1024**2
                return [info]
        with self.assertRaisesRegex(ValueError, "20 MiB"):
            HARNESS.archive_members(Archive(), {"root": "source", "members": ["shell.c"]})

    def test_fixed_oracle_detects_real_observation_and_wrong_oracle_separately(self):
        cases = {item["name"]: item for item in HARNESS.read(HARNESS.FIXTURES / "cases.json")["cases"]}
        self.assertEqual(9, len(cases))
        wrong = cases["wrong-oracle"]
        self.assertEqual(cases["argv-query"]["argv"], wrong["argv"])
        self.assertEqual(cases["argv-query"]["stdout"], wrong["observed_stdout"])
        self.assertNotEqual(wrong["stdout"], wrong["observed_stdout"])
        self.assertEqual("ASSERTION_FAILED", wrong["failure"])

    def test_generated_suite_has_one_literal_native_local_operation(self):
        for case in HARNESS.read(HARNESS.FIXTURES / "cases.json")["cases"]:
            with self.subTest(case=case["name"]):
                generated = HARNESS.suite_objects(case, "/owned/sqlite3", "a" * 64)
                profile = generated["env_profiles/local_cli.yaml"]
                self.assertFalse(profile["downstream_release_evidence"])
                self.assertEqual({"cli": "real"}, profile["product_test"]["provider_modes"])
                test = generated["test_cases/cli.yaml"]
                self.assertEqual(1, len(test["execute"]))
                self.assertEqual("-noinit", case["argv"][0], "Never read unreviewed user startup SQL")
                self.assertEqual(case["argv"], test["execute"][0]["with"]["process.argv"])
                self.assertEqual(case.get("stdin", ""), test["execute"][0]["with"]["process.stdin"])
                self.assertEqual(3, len(test["verify"]))

    def test_lock_has_immutable_release_source_license_and_no_latest(self):
        lock = HARNESS.read(HARNESS.FIXTURES / "asset-lock.json")
        self.assertRegex(lock["revision"], "^[a-f0-9]{40}$")
        self.assertIn(lock["revision"], lock["license"]["url"])
        self.assertNotIn("latest", json.dumps(lock))
        self.assertEqual("sha3_256", next(key for key in lock["archive"] if key == "sha3_256"))

    def test_added_operation_and_changed_oracle_fail_before_dispatch(self):
        case = HARNESS.read(HARNESS.FIXTURES / "cases.json")["cases"][0]
        for mutation in ("operation", "oracle", "provider"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as name:
                suite = Path(name)
                objects = HARNESS.suite_objects(case, "/owned/sqlite3", "a" * 64)
                for relative, value in objects.items():
                    HARNESS.write(suite / relative, value)
                HARNESS.check_suite(suite, case, "/owned/sqlite3", "a" * 64)
                if mutation == "operation":
                    objects["test_cases/cli.yaml"]["execute"].append({"op": "extra"})
                elif mutation == "oracle":
                    objects["test_cases/cli.yaml"]["verify"][0]["assert"]["expected"] = 999
                else:
                    objects["env_profiles/local_cli.yaml"]["targets"]["unreviewed"] = {"runtime_mode": "native"}
                for relative, value in objects.items():
                    HARNESS.write(suite / relative, value)
                with self.assertRaisesRegex(ValueError, "differs from the committed oracle"):
                    HARNESS.check_suite(suite, case, "/owned/sqlite3", "a" * 64)

    def test_handoff_expected_fields_are_derived_from_pinned_review_and_file_bytes(self):
        with tempfile.TemporaryDirectory() as name:
            suite = Path(name)
            HARNESS.write(suite / "suite_manifest.yaml", {"suite_id": "PUBLIC-SQLITE-case"})
            (suite / "reviewed.txt").write_text("fixed reviewed input")
            review = {"reviewed_by": "local-ci-policy", "reviewed_files": [{"path": "reviewed.txt", "role": "test"}],
                      "reviewed_contracts": []}
            handoff = HARNESS.expected_handoff(suite, review)
            self.assertEqual("PUBLIC-SQLITE-case", handoff["suite_id"])
            self.assertEqual("local_cli", handoff["profile"])
            self.assertEqual(HARNESS.sha(suite / "reviewed.txt"), handoff["reviewed_files"][0]["sha256"])
            self.assertNotIn("sha256", review["reviewed_files"][0])
            changed = dict(handoff, reviewed_by="unreviewed-human-claim")
            self.assertNotEqual(changed, HARNESS.expected_handoff(suite, review))

    def framework_fixture(self, root):
        for relative, text in ((HARNESS.CONTRACT, "synthetic reviewed contract"),
                               (HARNESS.REVIEW_TEMPLATE, '{"reviewed_by": "template"}')):
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text)
        return root

    def test_framework_source_resolution_explicit_env_and_missing(self):
        with tempfile.TemporaryDirectory() as name, patch.dict(os.environ, {}, clear=True):
            root = self.framework_fixture(Path(name) / "framework")
            self.assertEqual(root, HARNESS.framework_source(Namespace(framework_source=root)))
            with patch.dict(os.environ, {"SWARM_PRODUCT_TEST_FRAMEWORK_SOURCE": str(root)}):
                self.assertEqual(root, HARNESS.framework_source(Namespace(framework_source=None)))
            empty = Path(name) / "empty"
            empty.mkdir()
            with self.assertRaisesRegex(ValueError, "lacks the reviewed contract"):
                HARNESS.framework_source(Namespace(framework_source=empty))
            with self.assertRaisesRegex(ValueError, "Framework source root required"):
                HARNESS.framework_source(Namespace(framework_source=None))

    def test_policy_pins_module_and_framework_files_at_separate_roots(self):
        with tempfile.TemporaryDirectory() as name:
            source = self.framework_fixture(Path(name) / "framework")
            reviewed = {relative: HARNESS.sha(HARNESS.MODULE / relative) for relative in
                        ("scripts/public-cli-project.py", "public-projects/sqlite/asset-lock.json",
                         "public-projects/sqlite/cases.json")}
            reviewed.update({relative: HARNESS.sha(source / relative)
                             for relative in (HARNESS.CONTRACT, HARNESS.REVIEW_TEMPLATE)})
            policy_path = Path(name) / "policy.json"
            args = Namespace(local_ci_policy=policy_path, policy_sha256=None, framework_source=source)
            HARNESS.write(policy_path, {"actor": "local-ci-policy", "claim": HARNESS.CLAIM, "reviewed_files": reviewed})
            args.policy_sha256 = HARNESS.sha(policy_path)
            self.assertEqual("local-ci-policy", HARNESS.policy(args)["actor"])
            reviewed["public-projects/sqlite/cases.json"] = "0" * 64
            HARNESS.write(policy_path, {"actor": "local-ci-policy", "claim": HARNESS.CLAIM, "reviewed_files": reviewed})
            args.policy_sha256 = HARNESS.sha(policy_path)
            with self.assertRaisesRegex(ValueError, "Committed reviewed input changed"):
                HARNESS.policy(args)

    def test_manual_approval_requires_exact_plan_and_handoff_pins_before_runtime(self):
        with tempfile.TemporaryDirectory() as name:
            evidence = Path(name)
            source = self.framework_fixture(evidence / "framework-source")
            plan = {"claim": HARNESS.CLAIM, "cache_dir": str(evidence / "cache"),
                    "harness_sha256": HARNESS.sha(SCRIPT), "framework_sha256": "f" * 64,
                    "module_cli_sha256": "e" * 64, "build": {"binary_sha256": "d" * 64},
                    "asset_lock_sha256": HARNESS.sha(HARNESS.FIXTURES / "asset-lock.json"),
                    "fixtures_sha256": HARNESS.sha(HARNESS.FIXTURES / "cases.json"),
                    "contract_sha256": HARNESS.sha(source / HARNESS.CONTRACT),
                    "cases": [{"name": "synthetic-case", "handoff_sha256": "1" * 64}]}
            HARNESS.write(evidence / "prepared-plan.json", plan)
            approval = {"status": "approved", "reviewer": "synthetic-test-reviewer", "review_ref": "synthetic://approval-test",
                        "prepared_plan_sha256": HARNESS.sha(evidence / "prepared-plan.json"),
                        "harness_sha256": HARNESS.sha(SCRIPT), "framework_sha256": "f" * 64,
                        "module_cli_sha256": "e" * 64, "binary_sha256": "d" * 64,
                        "cases": {"synthetic-case": "0" * 64}}
            approval_path = evidence / "approval.json"
            HARNESS.write(approval_path, approval)
            args = Namespace(evidence_dir=evidence, local_ci_policy=None, policy_sha256=None,
                             approval_file=approval_path, java_home=evidence, framework_source=source)
            with patch.object(HARNESS, "checked_build", side_effect=ValueError("after approval boundary")) as runtime:
                with self.assertRaisesRegex(ValueError, "Runtime approval pin differs: cases"):
                    HARNESS.verify(args)
                runtime.assert_not_called()
                approval["cases"]["synthetic-case"] = "1" * 64
                HARNESS.write(approval_path, approval)
                with self.assertRaisesRegex(ValueError, "after approval boundary"):
                    HARNESS.verify(args)
                runtime.assert_called_once()


if __name__ == "__main__":
    unittest.main()
