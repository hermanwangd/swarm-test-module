import ast
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
EXECUTABLE_HARNESSES = (
    "scripts/smoke.py",
    "scripts/grpc-native.py",
    "scripts/verify-host-compatibility.py",
)


class ExecutableHarnessFailClosedTest(unittest.TestCase):
    def test_executable_harnesses_do_not_use_optimizable_asserts(self):
        for relative in EXECUTABLE_HARNESSES:
            path = ROOT / relative
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            offenders = [node.lineno for node in ast.walk(tree) if isinstance(node, ast.Assert)]
            self.assertEqual([], offenders, relative)

    def test_smoke_rejects_wrong_verdict_when_python_optimization_is_enabled(self):
        with tempfile.TemporaryDirectory() as name:
            module = Path(name) / "module"
            scripts = module / "scripts"
            target = module / "target"
            suite = module / "suite"
            fake_java = module / "fakejdk/bin/java"
            scripts.mkdir(parents=True)
            target.mkdir()
            (suite / "handoff").mkdir(parents=True)
            fake_java.parent.mkdir(parents=True)
            shutil.copy2(ROOT / "scripts/smoke.py", scripts / "smoke.py")
            framework = module / "framework.jar"
            framework.write_bytes(b"fake framework")
            for suffix in ("host", "provider", "cli"):
                (target / f"swarm-product-test-1.0.0-{suffix}.jar").write_bytes(b"fake jar")
            (suite / "suite_manifest.yaml").write_text("manifest: synthetic\n", encoding="utf-8")
            handoff = suite / "handoff/reviewed-tests.json"
            handoff.write_text(json.dumps({
                "workspace_ref": "synthetic-workspace",
                "project_ref": "synthetic-project",
                "repository_revisions": {"synthetic": "a" * 40},
                "requirement_mapping": [{"requirement_ref": "synthetic-requirement", "test_case_ids": ["SYNTHETIC-1"]}],
                "knowledge_mode": "not_used",
                "suite_id": "SYNTHETIC",
                "profile": "local",
            }), encoding="utf-8")
            fake_java.write_text("""#!/usr/bin/env python3
import json, sys
args = sys.argv[1:]
request = json.load(open(args[args.index('--request') + 1]))
json.dump({
    'contract_version': 'product-test-receipt.v1', 'module_id': 'product-test', 'module_version': '1',
    'invocation_id': 'synthetic-invocation', 'request': request, 'outcome': 'COMPLETED',
    'framework_verdict': 'failed', 'evidence_validation': 'validated', 'framework_exit_code': 1,
    'run_id': 'synthetic-run', 'output_directory': '/tmp/unused', 'artifacts': {},
    'release_evidence_eligible': False, 'evidence_classification': 'framework_verification_only',
    'diagnostic': 'deliberate verdict mismatch'
}, sys.stdout)
sys.exit(1)
""", encoding="utf-8")
            os.chmod(fake_java, 0o755)
            env = os.environ.copy()
            env["PYTHONOPTIMIZE"] = "1"
            output = module / "output"
            result = subprocess.run([
                sys.executable, "-B", str(scripts / "smoke.py"),
                "--framework-jar", str(framework), "--framework-sha256", hashlib.sha256(framework.read_bytes()).hexdigest(),
                "--suite-dir", str(suite), "--handoff-sha256", hashlib.sha256(handoff.read_bytes()).hexdigest(),
                "--expect-verdict", "passed", "--name", "negative", "--output-dir", str(output),
                "--java-home", str(fake_java.parents[1]),
            ], env=env, capture_output=True, text=True, timeout=15)
            self.assertNotEqual(0, result.returncode, result.stderr)
            self.assertFalse((output / "smoke-evidence.json").exists())
            self.assertIn("framework_verdict", result.stderr)


if __name__ == "__main__":
    unittest.main()
