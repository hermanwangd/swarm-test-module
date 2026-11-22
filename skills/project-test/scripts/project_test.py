#!/usr/bin/env python3
"""Agent workflow support. The agent designs tests; the existing Framework executes them.

No model, assertion engine, provider, or authorization service is implemented here.
Review pins must come from the host's independent reviewer, never from the QA output.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys

LIMIT = 2 * 1024 * 1024


def require(condition, message):
    if not condition:
        raise ValueError(message)


def regular(path):
    path = Path(path).absolute()
    require(not any(p.is_symlink() for p in [path, *path.parents]), "symlink is not an evidence source")
    require(stat.S_ISREG(path.stat().st_mode), "expected a regular file")
    return path


def content(path):
    path = regular(path)
    require(path.stat().st_size <= LIMIT, "source exceeds 2 MiB")
    with path.open("rb") as stream:
        data = stream.read(LIMIT + 1)
    require(len(data) <= LIMIT, "source exceeds 2 MiB")
    return data


def sha(path):
    with regular(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read(path):
    def unique(pairs):
        value = {}
        for key, item in pairs:
            require(key not in value, "duplicate JSON key")
            value[key] = item
        return value
    return json.loads(content(path).decode("utf-8"), object_pairs_hook=unique)


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def relative(value):
    require(isinstance(value, str) and value and "\\" not in value and "\x00" not in value,
            "invalid relative path")
    path = PurePosixPath(value)
    require(not path.is_absolute() and all(p not in (".", "..") for p in value.split("/")), "unsafe relative path")
    return value


def contained(root, value):
    path = Path(root) / relative(value)
    require(path.resolve().is_relative_to(Path(root).resolve()), "path escapes workflow root")
    require(not any(p.is_symlink() for p in [path, *path.parents]), "symlink is not a workflow input")
    return path


def git(repo, *args):
    result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, timeout=30)
    require(result.returncode == 0, "cannot read pinned Git source")
    require(len(result.stdout) <= LIMIT, "Git source exceeds 2 MiB")
    return result.stdout


def collect(repo, revision, base, sources, output, pr_snapshot=None):
    require(re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", revision) is not None, "revision must be an exact commit")
    require(re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", base) is not None, "base must be an exact commit")
    for commit in [revision, base]:
        require(git(repo, "rev-parse", commit + "^{commit}").decode().strip() == commit, "commit mismatch")
    for kind in ["bdd", "ac", "pr", "code"]:
        require(sources.get(kind) or (kind == "pr" and pr_snapshot), "missing " + kind + " source")
    require(sum(len(v) for v in sources.values()) <= 128, "too many sources; split the scope")
    require(not output.exists(), "context output must be fresh")
    records, payloads = [], []
    def add(identity, kind, data, origin):
        require(data and len(data) <= LIMIT, "empty or oversized source")
        lines = data.decode("utf-8").splitlines()
        require(identity not in {x["id"] for x in records}, "duplicate source")
        snapshot = "sources/" + str(len(records)) + ".txt"
        records.append({"id": identity, "kind": kind, "origin": origin, "snapshot": snapshot,
                        "sha256": hashlib.sha256(data).hexdigest(), "lines": len(lines)})
        payloads.append((snapshot, data))
    for kind, paths in sources.items():
        require(kind in {"bdd", "ac", "pr", "code"}, "unknown source kind")
        for name in paths:
            relative(name)
            entry = git(repo, "ls-tree", "-z", revision, "--", name).decode().split("\t", 1)
            require(len(entry) == 2 and entry[0].split()[0] in {"100644", "100755"}
                    and entry[1] == name + "\x00", "source must be one committed regular file")
            add(kind + ":" + name, kind, git(repo, "show", revision + ":" + name), revision + ":" + name)
    if pr_snapshot:
        pr = read(pr_snapshot)
        require(pr["head"] == revision and pr["base"] == base, "PR snapshot does not match source commits")
        require(pr.get("url") and pr.get("title") and isinstance(pr.get("body"), str), "incomplete PR snapshot")
        add("pr:snapshot", "pr", content(pr_snapshot), pr["url"])
    diff_base = git(repo, "merge-base", base, revision).decode().strip()
    diff = git(repo, "diff", "--no-ext-diff", "--no-textconv", "--unified=3", diff_base, revision, "--")
    if diff:
        add("pr:diff", "pr", diff, diff_base + ".." + revision)
    require(sum(len(p) for _, p in payloads) <= 16 * LIMIT, "context exceeds 32 MiB; split the scope")
    output.mkdir(parents=True, mode=0o700)
    for name, data in payloads:
        path = output / name
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(data)
    context = {"schema": "project-test-context.v1", "revision": revision, "base": base, "diff_base": diff_base, "sources": records}
    write(output / "context.json", context)
    return context


def check(context_dir, design_path):
    context, design = read(context_dir / "context.json"), read(design_path)
    require(context["schema"] == "project-test-context.v1" and design["schema"] == "project-test-design.v1",
            "unsupported workflow schema")
    require(design["context_sha256"] == sha(context_dir / "context.json"), "design uses another context")
    sources = {s["id"]: s for s in context["sources"]}
    require(len(sources) == len(context["sources"]), "duplicate context source")
    for source in sources.values():
        path = contained(context_dir, source["snapshot"])
        require(sha(path) == source["sha256"], "source snapshot changed")
        require(len(content(path).decode("utf-8").splitlines()) == source["lines"], "source line count changed")
    def citations(items):
        require(isinstance(items, list) and 0 < len(items) <= 128, "missing citations")
        kinds = set()
        for item in items:
            require(item["source"] in sources, "unknown citation source")
            source = sources[item["source"]]
            require(type(item["start"]) is int and type(item["end"]) is int
                    and 1 <= item["start"] <= item["end"] <= source["lines"], "citation line range invalid")
            kinds.add(source["kind"])
        return kinds
    require(isinstance(design.get("author"), str) and design["author"].strip(), "missing design author")
    requirements = design["requirements"]
    require(0 < len(requirements) <= 512, "requirements inventory is required")
    ids = [r["id"] for r in requirements]
    require(all(isinstance(x, str) and x.strip() for x in ids) and len(ids) == len(set(ids)), "invalid requirement IDs")
    for requirement in requirements:
        require("ac" in citations(requirement["citations"]), "requirement must cite AC")
    cases, covered, case_ids, suites = design["cases"], set(), set(), set()
    require(len(cases) <= 512, "too many cases")
    for case in cases:
        require(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", case["id"]) is not None, "invalid case ID")
        require(case["id"] not in case_ids and case["suite"] not in suites, "duplicate case or suite")
        case_ids.add(case["id"])
        suites.add(relative(case["suite"]))
        require(case["requirements"] and set(case["requirements"]) <= set(ids), "case has unknown requirement")
        covered.update(case["requirements"])
        require({"bdd", "pr", "code"} <= citations(case["citations"]), "case must cite bdd, pr and code")
        require(case["technique"] in {"equivalence", "boundary", "state", "scenario", "regression"}, "unknown technique")
        for key in ["rationale", "expected", "test_case_id"]:
            require(isinstance(case.get(key), str) and case[key].strip(), "case missing " + key)
        for key in ["preconditions", "steps"]:
            require(isinstance(case.get(key), list) and case[key] and all(isinstance(x, str) and x.strip()
                    for x in case[key]), "case missing " + key)
    for requirement in requirements:
        if requirement["id"] not in covered:
            require(isinstance(requirement.get("gap"), str) and requirement["gap"].strip(),
                    requirement["id"] + " uncovered without an explanation")
    return context, design


def coverage(design, results):
    statuses = {r["id"]: r["status"] for r in results}
    rows = []
    for requirement in design["requirements"]:
        cases = [c["id"] for c in design["cases"] if requirement["id"] in c["requirements"]]
        observed = [statuses.get(c, "BLOCKED") for c in cases]
        status = "UNTESTED" if not cases else "FAIL" if "FAIL" in observed else "BLOCKED" if (
            requirement.get("gap") or any(s != "PASS" for s in observed)) else "PASS"
        rows.append({"requirement": requirement["id"], "status": status, "cases": cases,
                     "gap": requirement.get("gap"), "citations": requirement["citations"]})
    return rows


def run(context_dir, design_path, review_path, review_pin, output):
    require(sha(review_path) == review_pin, "review does not match independent pin")
    context, design = check(context_dir, design_path)
    review = read(review_path)
    require(review.get("status") == "approved" and review.get("reviewer") and review.get("review_ref")
            and review["reviewer"] != design["author"], "independent design review required")
    require(review["context_sha256"] == sha(context_dir / "context.json")
            and review["design_sha256"] == sha(design_path), "review does not match context/design")
    runtime = review["runtime"]
    require(isinstance(review.get("subjects"), list) and review["subjects"], "review must pin the SUT subjects")
    def stable_inputs():
        for kind in ["java", "module", "framework"]:
            require(Path(runtime[kind]["path"]).is_absolute(), "runtime requires absolute paths")
            require(sha(runtime[kind]["path"]) == runtime[kind]["sha256"], kind + " binary changed")
        for subject in review["subjects"]:
            require(Path(subject["path"]).is_absolute(), "SUT requires absolute paths")
            require(sha(subject["path"]) == subject["sha256"], "SUT subject changed")
        require(sha(review_path) == review_pin and sha(design_path) == review["design_sha256"], "review/design changed")
        check(context_dir, design_path)
    stable_inputs()
    require(set(review["handoffs"]) == {c["id"] for c in design["cases"]}, "incomplete reviewed handoff set")
    require(design["cases"], "no runnable cases; inspect requirement gaps")
    prepared = []
    for case in design["cases"]:
        suite = contained(design_path.parent, case["suite"]).resolve(strict=True)
        handoff_path = contained(suite, "handoff/reviewed-tests.json")
        pin = review["handoffs"][case["id"]]
        require(sha(handoff_path) == pin, "reviewed handoff changed")
        handoff = read(handoff_path)
        require(handoff["reviewed_by"] == review["reviewer"] and handoff["review_ref"] == review["review_ref"],
                "handoff uses another reviewer")
        require(handoff["knowledge_mode"] == "not_used", "this local workflow requires directly supplied project sources")
        require(list(handoff["repository_revisions"].values()) == [context["revision"]], "suite targets another revision")
        mappings = handoff["requirement_mapping"]
        require(len(mappings) == len(case["requirements"]) and
                {m["requirement_ref"] for m in mappings} == set(case["requirements"]) and
                all(m["test_case_ids"] == [case["test_case_id"]] for m in mappings), "suite AC/case mapping differs from design")
        # JSON is valid YAML. The agent writes the existing Framework v0.3 DSL, not a new DSL.
        manifest = read(contained(suite, "suite_manifest.yaml"))
        require(manifest["suite_id"] == handoff["suite_id"] and len(manifest["tests"]) == 1, "suite identity or test count differs")
        test = read(contained(suite, manifest["tests"][0]["ref"]))
        require(test["test_case_id"] == case["test_case_id"], "test case identity differs")
        profile_ref = manifest["env_profiles"][handoff["profile"]]["ref"]
        profile = read(contained(suite, profile_ref))["product_test"]
        require(profile["environment_stage"] == "local", "SIT/preprod/live are unsupported")
        prepared.append((case, suite, handoff, pin, profile))
    require(not output.exists(), "run output must be fresh; preserve earlier results")
    output.mkdir(parents=True, mode=0o700)
    results = []
    for case, suite, handoff, pin, profile in prepared:
        work = output / case["id"]
        work.mkdir(mode=0o700)
        (work / "outputs").mkdir(mode=0o700)
        request = {"contract_version": "product-test-request.v1", "module_id": "product-test", "module_version": "1",
                   "mission_ref": "project-test:" + review_pin, "request_ref": case["id"], "execution_revision": context["revision"],
                   "workspace_ref": handoff["workspace_ref"], "project_ref": handoff["project_ref"],
                   "repository_revisions": handoff["repository_revisions"],
                   "requirement_test_mapping": {m["requirement_ref"]: m["test_case_ids"] for m in handoff["requirement_mapping"]},
                   "test_level": profile["test_level"], "test_type": profile["test_type"], "environment_stage": "local",
                   "knowledge_mode": "not_used", "artifact_root": str(suite), "suite_manifest": str(suite / "suite_manifest.yaml"),
                   "suite_id": handoff["suite_id"], "profile": handoff["profile"],
                   "reviewed_handoff": str(suite / "handoff/reviewed-tests.json"), "expected_handoff_sha256": pin}
        write(work / "request.json", request)
        environment = {"SWARM_PRODUCT_TEST_FRAMEWORK_JAR": runtime["framework"]["path"],
                       "SWARM_PRODUCT_TEST_FRAMEWORK_SHA256": runtime["framework"]["sha256"],
                       "SWARM_PRODUCT_TEST_HANDOFF_SHA256": pin, "SWARM_PRODUCT_TEST_ARTIFACT_ROOT": str(suite),
                       "SWARM_PRODUCT_TEST_OUTPUT_ROOT": str(work / "outputs"), "SWARM_PRODUCT_TEST_TIMEOUT_MS": "60000"}
        command = [runtime["java"]["path"], "-Xmx512m", "-XX:MaxMetaspaceSize=256m", "-jar", runtime["module"]["path"],
                   "product-test", "run", "--request", str(work / "request.json")]
        record = {"id": case["id"], "status": "BLOCKED", "command": command, "expected": case["expected"]}
        try:
            stable_inputs()
            with (work / "receipt.json").open("wb") as out, (work / "stderr.log").open("wb") as err:
                completed = subprocess.run(command, env=environment, cwd=work, stdout=out, stderr=err, timeout=75)
            stable_inputs()
            receipt = read(work / "receipt.json")
            record.update(exit_code=completed.returncode, outcome=receipt["outcome"], verdict=receipt["framework_verdict"],
                          receipt=str(work / "receipt.json"), receipt_sha256=sha(work / "receipt.json"))
            require(receipt["request"] == request, "receipt belongs to another request")
            require(receipt["outcome"] == "COMPLETED" and receipt["evidence_validation"] == "validated", "no validated execution")
            require(receipt["release_evidence_eligible"] is False and
                    receipt["evidence_classification"] == "framework_verification_only", "invalid local evidence boundary")
            require(receipt["artifacts"].get("result"), "missing canonical result")
            for artifact in receipt["artifacts"].values():
                path = regular(artifact["path"])
                require(path.resolve().is_relative_to((work / "outputs").resolve()), "evidence outside this invocation")
                require(sha(path) == artifact["sha256"], "evidence digest mismatch")
            if receipt["framework_verdict"] == "passed" and completed.returncode == 0:
                record["status"] = "PASS"
            elif receipt["framework_verdict"] == "failed" and completed.returncode == 1:
                record["status"] = "FAIL"
            record["result"] = receipt["artifacts"]["result"]
        except (ValueError, OSError, KeyError, subprocess.TimeoutExpired) as error:
            record["reason"] = str(error)
        results.append(record)
        # Keep completed case evidence even if a later invocation is interrupted.
        write(output / "progress.json", results)
    rows = coverage(design, results)
    report = {"schema": "project-test-report.v1", "revision": context["revision"], "review_sha256": review_pin,
              "claim": "AGENT_AUTHORED_LOCAL_FRAMEWORK_EXECUTION", "release_eligible": False,
              "cases": results, "requirements": rows, "status": "PASS" if all(r["status"] == "PASS" for r in rows) else "INCOMPLETE",
              "coverage_note": "Coverage of the reviewed AC inventory; not code coverage or proof that the inventory is exhaustive."}
    write(output / "report.json", report)
    return report


def pytest_regression(args):
    """Run the project's pytest configuration with coverage.py in a trusted test environment."""
    import os
    import xml.etree.ElementTree as ET

    repo, out = args.repo.resolve(strict=True), args.out.absolute()
    source = contained(repo, args.source)
    require(source.is_dir(), "production source directory is missing")
    ac = read(args.ac_report)
    require(ac.get("schema") == "project-test-report.v1", "expected project-test AC report")
    def check_revision():
        require(git(repo, "rev-parse", "HEAD").decode().strip() == ac["revision"], "AC and regression revisions differ")
        require(not git(repo, "status", "--porcelain", "--untracked-files=normal"), "test checkout has uncommitted changes")
    check_revision()
    require(not out.resolve().is_relative_to(repo), "write evidence outside the checkout")
    out.mkdir(parents=True, exist_ok=False, mode=0o700)
    python = str(args.python.absolute())
    env = {k: v for k, v in os.environ.items() if not k.startswith(("COVERAGE_", "PYTEST_", "PYTHON"))}
    env.update(COVERAGE_FILE=str(out / ".coverage"), PATH=str(Path(python).parent) + os.pathsep + env.get("PATH", ""))
    pytest_args = ["-o", "addopts="] if args.include_stress else []
    command = [python, "-m", "coverage", "run", "--branch", "--source=" + args.source, "-m", "pytest",
               *pytest_args, "-q", "-ra", "--junitxml=" + str(out / "junit.xml")]
    with (out / "pytest.log").open("wb") as log:
        rc = subprocess.run(command, cwd=repo, env=env, stdout=log, stderr=subprocess.STDOUT).returncode
    result = {"schema": "project-regression-report.v1", "revision": ac["revision"],
              "ac_report_sha256": sha(args.ac_report), "ac_status": ac["status"], "command": command,
              "pytest_exit_code": rc, "source": args.source, "status": "INCOMPLETE"}
    write(out / "report.json", result)
    check_revision()
    subprocess.run([python, "-m", "coverage", "json", "-o", str(out / "coverage.json")],
                   cwd=repo, env=env, check=True)
    data = json.loads((out / "coverage.json").read_text())
    require(data["meta"]["branch_coverage"], "missing branch coverage")
    stats = data["totals"]
    result["lines"] = {"covered": stats["covered_lines"], "total": stats["num_statements"]}
    result["branches"] = {"covered": stats["covered_branches"], "total": stats["num_branches"]}
    suites = ET.parse(out / "junit.xml").getroot()
    result["tests"] = {key: sum(int(node.attrib[key]) for node in suites.iter("testsuite"))
                       for key in ("tests", "errors", "failures", "skipped")}
    result["requirements"] = ac["requirements"]
    result["evidence_sha256"] = {name: sha(out / name) for name in ("coverage.json", "junit.xml", "pytest.log")}
    if rc == 0 and result["tests"]["tests"] > result["tests"]["skipped"] and ac["status"] == "PASS":
        result["status"] = "PASS"
    write(out / "report.json", result)
    print(json.dumps(result))
    return 0 if result["status"] == "PASS" else 1


def native_tox(args):
    """Execute a locally reviewed Click-style uv/tox/pytest plan in a trusted checkout."""
    import os
    import xml.etree.ElementTree as ET

    repo = args.repo.resolve(strict=True)
    plan_path = regular(args.plan)
    require(sha(plan_path) == args.plan_sha256, "native plan digest mismatch")
    plan = read(plan_path)
    revision = plan["revision"]
    def check_checkout():
        require(git(repo, "rev-parse", "HEAD").decode().strip() == revision, "checkout revision mismatch")
        require(not git(repo, "status", "--porcelain"), "dirty checkout")
    check_checkout()
    command = ["uv", "run", "--locked", "--no-default-groups", "--group", "dev", "tox", "run"]
    require(" ".join(command) in git(repo, "show", revision + ":" + relative(plan["workflow"])).decode(),
            "runner command absent from pinned workflow")
    require(re.fullmatch(r"py3\.\d+", plan["environment"]), "unsupported tox environment")
    env = {k: v for k, v in os.environ.items() if not k.startswith(("TOX_", "PYTEST_", "PYTHON", "UV_"))}
    env["TOX_ENV"] = plan["environment"]
    output = args.out.absolute()
    require(not output.resolve().is_relative_to(repo), "write evidence outside checkout")
    output.mkdir(parents=True, exist_ok=False)
    inventory = plan["requirements"]
    require(isinstance(inventory, list) and inventory and all(isinstance(ac, str) and ac for ac in inventory)
            and len(set(inventory)) == len(inventory), "invalid AC inventory")
    jobs = []
    for case in plan["cases"]:
        require(isinstance(case["requirements"], list) and case["requirements"] and
                set(case["requirements"]).issubset(inventory) and case["assertion"], "missing AC or assertion")
        location = case["path"]
        if case["origin"] == "existing":
            git(repo, "show", revision + ":" + relative(location))
        else:
            require(case["origin"] == "added", "unknown case origin")
            original = contained(plan_path.parent, location)
            require(sha(original) == case["sha256"], "supplemental test digest mismatch")
            directory = output / ("case-" + str(len(jobs)))
            directory.mkdir()
            snapshot = directory / original.name
            snapshot.write_bytes(content(original))
            require(sha(snapshot) == case["sha256"], "supplemental snapshot mismatch")
            location = str(snapshot)
        require(re.fullmatch(r"test_[a-zA-Z0-9_]+", case["function"]), "invalid pytest function")
        jobs.append((case, [location + "::" + case["function"]]))
    jobs.append(({"origin": "regression"}, []))
    report = {"revision": revision, "runner": command, "environment": plan["environment"],
              "plan_sha256": args.plan_sha256, "runs": [], "status": "INCOMPLETE"}
    for index, (case, selectors) in enumerate(jobs):
        xml = output / f"{index}.xml"
        log = output / f"{index}.log"
        argv = command + ["--", *selectors, "--junitxml=" + str(xml)]
        with log.open("wb") as stream:
            rc = subprocess.run(argv, cwd=repo, env=env, stdout=stream, stderr=subprocess.STDOUT).returncode
        row = dict(case, exit_code=rc, log=log.name, log_sha256=sha(log), status="BLOCKED")
        if xml.is_file():
            nodes = ET.parse(xml).getroot().findall(".//testcase")
            skipped = sum(node.find("skipped") is not None for node in nodes)
            failed = sum(any(node.find(tag) is not None for tag in ("failure", "error")) for node in nodes)
            row.update(tests=len(nodes), skipped=skipped, failed=failed, junit=xml.name, junit_sha256=sha(xml))
            if failed:
                row["status"] = "FAIL"
            elif rc == 0 and len(nodes) > skipped and (not selectors or not skipped):
                row["status"] = "PASS"
        report["runs"].append(row)
        write(output / "report.json", report)
        check_checkout()
    requirements = {}
    for ac in inventory:
        statuses = [row["status"] for row in report["runs"] if ac in row.get("requirements", [])]
        requirements[ac] = next((state for state in ("FAIL", "BLOCKED") if state in statuses),
                                "PASS" if statuses else "UNTESTED")
    report["requirements"] = requirements
    if all(state == "PASS" for state in requirements.values()) and report["runs"][-1]["status"] == "PASS":
        report["status"] = "PASS"
    write(output / "report.json", report)
    return 0 if report["status"] == "PASS" else 1


def native_maven(args):
    """Run a reviewed Maven CI invocation once, mapping Surefire results to AC."""
    import shutil
    import tempfile
    import xml.etree.ElementTree as ET

    require(sha(args.plan) == args.plan_sha256, "native plan digest mismatch")
    plan = read(args.plan)
    revision = plan["revision"]
    require(re.fullmatch("[0-9a-f]{40}", revision), "expected full commit")
    workflow = git(args.repo, "show", revision + ":" + relative(plan["workflow"])).decode()
    cmd = plan["runner"]
    allowed = {"--errors", "--show-version", "--batch-mode", "--no-transfer-progress",
               "-B", "-ntp", "clean", "test", "verify", "package"}
    require(isinstance(cmd, list) and cmd and cmd[0] == "mvn" and all(v in allowed for v in cmd[1:]),
            "unsupported Maven invocation")
    require("run: " + " ".join(cmd) in [line.strip() for line in workflow.splitlines()],
            "command absent from pinned CI workflow")
    inventory = plan["requirements"]
    require(isinstance(inventory, list) and inventory and len(set(inventory)) == len(inventory), "invalid AC inventory")
    for case in plan["cases"]:
        require(case["requirements"] and set(case["requirements"]).issubset(inventory) and case["assertion"],
                "invalid AC mapping")
        require(case["origin"] == "existing", "expected a test in the PR checkout")
        git(args.repo, "show", revision + ":" + relative(case["path"]))
    output = args.out.absolute()
    require(not output.resolve().is_relative_to(args.repo.resolve()), "write evidence outside checkout")
    output.mkdir(parents=True, exist_ok=False)
    report = {"revision": revision, "runner": cmd, "plan_sha256": args.plan_sha256,
              "status": "INCOMPLETE", "runs": [], "requirements": {}, "coverage": None}
    with tempfile.TemporaryDirectory() as temp:
        checkout = Path(temp) / "repo"
        subprocess.run(["git", "clone", "-q", "--no-checkout", "--", str(args.repo.resolve()), str(checkout)], check=True)
        subprocess.run(["git", "checkout", "-q", "--detach", revision], cwd=checkout, check=True)
        xmls = "target/surefire-reports/TEST-*.xml"
        require(not list(checkout.rglob(xmls)) and not (checkout / "target/site/jacoco/jacoco.xml").exists()
                and not (checkout / "target/jacoco.exec").exists(), "checkout contains pre-existing test evidence")
        log = output / "maven.log"
        with log.open("wb") as stream:
            rc = subprocess.run(cmd, cwd=checkout, stdout=stream, stderr=subprocess.STDOUT).returncode
        observed = {}
        counts = {"PASS": 0, "FAIL": 0, "SKIPPED": 0}
        for xml in sorted(checkout.rglob(xmls)):
            nodes = ET.parse(regular(xml)).getroot().findall(".//testcase")
            for node in nodes:
                failed = any(node.find(tag) is not None for tag in ("failure", "error"))
                status = "FAIL" if failed else "SKIPPED" if node.find("skipped") is not None else "PASS"
                counts[status] += 1
                key = (node.get("classname"), node.get("name"))
                observed.setdefault(key, []).append((status, xml, node))
        for case in plan["cases"]:
            matches = observed.get((case["class"], case["method"]), [])
            states = {status for status, _, _ in matches}
            status = "FAIL" if "FAIL" in states else "PASS" if states == {"PASS"} else "BLOCKED"
            evidence = []
            for state, xml, node in matches:
                destination = output / "evidence" / xml.relative_to(checkout)
                if not destination.exists():
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(xml, destination)
                evidence.append({"file": str(destination.relative_to(output)), "sha256": sha(destination),
                                 "class": node.get("classname"), "method": node.get("name"), "status": state})
            report["runs"].append(dict(case, status=status, junit=evidence))
        for ac in inventory:
            statuses = [r["status"] for r in report["runs"] if ac in r["requirements"]]
            report["requirements"][ac] = next((s for s in ("FAIL", "BLOCKED") if s in statuses),
                                               "PASS" if statuses else "UNTESTED")
        regression = "FAIL" if counts["FAIL"] else "PASS" if rc == 0 and counts["PASS"] else "BLOCKED"
        report["regression"] = dict(counts, status=regression, exit_code=rc, log_sha256=sha(log))
        jacoco = checkout / "target/site/jacoco/jacoco.xml"
        if plan.get("coverage_goal") == "jacoco:report" and not jacoco.exists() and (checkout / "target/jacoco.exec").is_file():
            coverage_log = output / "coverage.log"
            with coverage_log.open("wb") as stream:
                coverage_rc = subprocess.run(["mvn", "-B", "-ntp", "jacoco:report"], cwd=checkout,
                                             stdout=stream, stderr=subprocess.STDOUT).returncode
            report["coverage_execution"] = {"exit_code": coverage_rc, "log_sha256": sha(coverage_log)}
        if jacoco.is_file() and report.get("coverage_execution", {}).get("exit_code", 0) == 0:
            report["coverage"] = {c.get("type"): {"covered": int(c.get("covered")), "missed": int(c.get("missed"))}
                                  for c in ET.parse(regular(jacoco)).getroot().findall("counter")
                                  if c.get("type") in ("LINE", "BRANCH")}
        if regression == "PASS" and all(s == "PASS" for s in report["requirements"].values()):
            report["status"] = "PASS"
    write(output / "report.json", report)
    return 0 if report["status"] == "PASS" else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    acquire = commands.add_parser("collect")
    acquire.add_argument("--repo", type=Path, required=True)
    for name in ["revision", "base"]:
        acquire.add_argument("--" + name, required=True)
    for name in ["bdd", "ac", "pr", "code"]:
        acquire.add_argument("--" + name, action="append", default=[])
    acquire.add_argument("--pr-snapshot", type=Path)
    acquire.add_argument("--out", type=Path, required=True)
    for name in ["check", "run"]:
        command = commands.add_parser(name)
        command.add_argument("--context", type=Path, required=True)
        command.add_argument("--design", type=Path, required=True)
        if name == "run":
            command.add_argument("--pytest-repo", type=Path)
            command.add_argument("--pytest-python", type=Path)
            command.add_argument("--pytest-source")
            command.add_argument("--include-stress", action="store_true")
            command.add_argument("--review", type=Path, required=True)
            command.add_argument("--review-sha256", required=True)
            command.add_argument("--out", type=Path, required=True)
    regression = commands.add_parser("pytest-regression", help="Collect native regression, line and branch results for a reviewed checkout")
    for field in ["repo", "python", "ac-report", "out"]:
        regression.add_argument("--" + field, type=Path, required=True)
    regression.add_argument("--source", required=True)
    regression.add_argument("--include-stress", action="store_true", help="Clear pytest addopts to include normally excluded tests")
    native = commands.add_parser("native-tox", help="Run existing and supplemental pytest cases via the reviewed uv/tox CI entry")
    for field in ("repo", "plan", "out"):
        native.add_argument("--" + field, type=Path, required=True)
    native.add_argument("--plan-sha256", required=True)
    maven = commands.add_parser("native-maven", help="Run the pinned Maven CI entry and map exact Surefire methods to AC")
    for field in ("repo", "plan", "out"):
        maven.add_argument("--" + field, type=Path, required=True)
    maven.add_argument("--plan-sha256", required=True)
    args = parser.parse_args()
    try:
        if args.command == "native-maven":
            return native_maven(args)
        if args.command == "native-tox":
            return native_tox(args)
        if args.command == "pytest-regression":
            return pytest_regression(args)
        if args.command == "collect":
            collect(args.repo, args.revision, args.base, {kind: getattr(args, kind) for kind in ["bdd", "ac", "pr", "code"]},
                    args.out.absolute(), args.pr_snapshot)
            print(json.dumps({"context": str(args.out / "context.json"), "sha256": sha(args.out / "context.json")}))
        elif args.command == "check":
            _, design = check(args.context, args.design)
            print(json.dumps({"status": "DESIGNED_NOT_EXECUTED", "cases": len(design["cases"]),
                              "requirements": coverage(design, [])}))
        else:
            project_options = [args.pytest_repo, args.pytest_python, args.pytest_source]
            require(not any(project_options) or all(project_options), "provide pytest repo, python and source together")
            require(not args.include_stress or all(project_options), "stress selection requires a pytest checkout")
            if all(project_options):
                require(sha(args.review) == args.review_sha256, "regression review pin mismatch")
                binding = {"repo": str(args.pytest_repo.resolve()), "python": str(args.pytest_python.absolute()),
                           "python_sha256": sha(args.pytest_python.resolve(strict=True)), "source": args.pytest_source,
                           "revision": git(args.pytest_repo, "rev-parse", "HEAD").decode().strip(),
                           "include_stress": args.include_stress}
                require(read(args.review).get("pytest_regression") == binding, "regression settings differ from review")
            result = run(args.context.absolute(), args.design.absolute(), args.review.absolute(), args.review_sha256, args.out.absolute())
            if all(project_options):
                return pytest_regression(argparse.Namespace(
                    repo=args.pytest_repo, python=args.pytest_python, source=args.pytest_source,
                    include_stress=args.include_stress, out=args.out / "regression",
                    ac_report=args.out / "report.json"))
            print(json.dumps(result, ensure_ascii=False))
            return 0 if result["status"] == "PASS" else 1
        return 0
    except (ValueError, OSError, KeyError, TypeError, subprocess.SubprocessError) as error:
        print(json.dumps({"status": "BLOCKED", "reason": str(error)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
