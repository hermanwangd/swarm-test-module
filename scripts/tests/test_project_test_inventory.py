"""Exercise scoped inventory decisions against a small project with committed test history."""
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[2] / "skills/project-test/scripts/project_test.py"
SPEC = importlib.util.spec_from_file_location("project_test", SCRIPT)
FLOW = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FLOW)


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def commit(repo, message):
    git(repo, "add", "-A")
    git(repo, "-c", "user.name=Inventory Fixture", "-c", "user.email=fixture@example.invalid",
        "commit", "-qm", message)
    return git(repo, "rev-parse", "HEAD")


def cite(source, start=1, end=1):
    return {"source": source, "start": start, "end": end}


def entry(case_id, path, acs, action, reason):
    return {"id": case_id, "path": path, "requirements": acs, "action": action, "reason": reason,
            "citations": [cite("test:" + path, 6, 7)]}


def write_test(repo, path, method, assertion):
    (repo / path).write_text(
        "import unittest\nfrom routes import route\n\n\nclass RouteTest(unittest.TestCase):\n"
        f"    def test_{method}(self):\n        {assertion}\n")


def create_project(repo):
    """Return the two commits. The baseline and modified checkout each contain runnable tests."""
    repo.mkdir()
    git(repo, "init", "-q")
    (repo / "tests").mkdir()
    (repo / "tests/__init__.py").write_text("")
    (repo / "route.feature").write_text("Feature: Route lookup\nScenario: Known and unknown destinations\n")
    (repo / "PR.md").write_text("Preserve named routes and retire the default road route.\n")
    (repo / "AC.md").write_text("AC-TOWN: town uses local delivery\nAC-ROAD: unknown zones use road\n")
    (repo / "other-AC.md").write_text("AC-ISLAND: island uses ferry\nAC-ALIAS: town-centre also uses local\n")
    implementation = 'def route(zone):\n    routes = {"town": "local", "town-centre": "local", "island": "ferry"}\n'
    (repo / "routes.py").write_text(implementation + '    return routes.get(zone, "road")\n')
    town = entry("Route.town", "tests/test_town.py", ["AC-TOWN", "AC-ALIAS"], "reuse", "Local delivery and its alias")
    island = entry("Route.island", "tests/test_island.py", ["AC-ISLAND"], "reuse", "Island ferry")
    road = entry("Route.road", "tests/test_road.py", ["AC-ROAD"], "reuse", "Unknown destinations use road")
    write_test(repo, town["path"], "town", 'self.assertEqual([route("town"), route("town-centre")], ["local", "local"])')
    write_test(repo, island["path"], "island", 'self.assertEqual(route("island"), "ferry")')
    write_test(repo, road["path"], "road", 'self.assertEqual(route("unknown"), "road")')
    inventory = {"schema": "project-test-inventory.v1", "entries": [town, island, road]}
    inventory_path = repo / "test-inventory.json"
    FLOW.write(inventory_path, inventory)
    base = commit(repo, "Record the existing route assertions and inventory")

    (repo / "routes.py").write_text(implementation + "    return routes.get(zone)\n")
    (repo / "AC.md").write_text("AC-TOWN: town uses local delivery\nAC-UNKNOWN: unknown zones have no route\n")
    (repo / town["path"]).rename(repo / "tests/test_local.py")
    (repo / road["path"]).unlink()
    town.update(path="tests/test_local.py", action="update", reason="Move the local route test with its case ID")
    town["citations"] = [cite("test:" + town["path"], 6, 7), cite(f"historical-test:{base}:tests/test_town.py", 6, 7)]
    road.update(action="retire", reason="The default road route was removed")
    road["citations"] = [cite(f"historical-test:{base}:" + road["path"], 6, 7)]
    unknown = entry("Route.unknown", "tests/test_unknown.py", ["AC-UNKNOWN"], "add", "Unknown zones have no route")
    write_test(repo, unknown["path"], "unknown", 'self.assertIsNone(route("unknown"))')
    inventory["entries"].append(unknown)
    FLOW.write(inventory_path, inventory)
    return base, commit(repo, "Remove the fallback route and update only affected inventory rows")


class IncrementalInventory(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.repo = self.root / "product"
        self.base, self.head = create_project(self.repo)
        self.sources = {"bdd": ["route.feature"], "ac": ["AC.md"], "pr": ["PR.md"], "code": ["routes.py"],
                        "test": ["test-inventory.json", "tests/test_local.py", "tests/test_unknown.py"],
                        "historical-test": [self.base + ":" + p for p in ("tests/test_town.py", "tests/test_road.py")]}

    def prepare(self):
        self.context = self.root / "context"
        FLOW.collect(self.repo, self.head, self.base, self.sources, self.context)
        self.design_path = self.root / "design.json"
        self.design = {"schema": "project-test-design.v2", "author": "fixture-qa",
                       "context_sha256": FLOW.sha(self.context / "context.json"),
                       "test_inventory": {"path": "test-inventory.json", "sha256": FLOW.sha(self.repo / "test-inventory.json")},
                       "inventory_scope": ["Route.town", "Route.road", "Route.unknown"],
                       "requirements": [{"id": ac, "citations": [cite("ac:AC.md", i, i)]}
                                        for i, ac in enumerate(["AC-TOWN", "AC-UNKNOWN"], 1)],
                       "cases": []}
        for case_id, ac, path, zone, expected in [
            ("Route.town", "AC-TOWN", "tests/test_local.py", "town", "local"),
            ("Route.unknown", "AC-UNKNOWN", "tests/test_unknown.py", "unknown", "None"),
        ]:
            self.design["cases"].append({
                "id": case_id, "requirements": [ac], "technique": "scenario", "expected": expected,
                "rationale": f"Verify {ac} for {zone}", "preconditions": ["Load routes"],
                "steps": [f"Look up {zone}"], "suite": "suites/" + case_id, "test_case_id": case_id,
                "citations": [cite(src) for src in ("bdd:route.feature", "pr:PR.md", "code:routes.py", "test:" + path)]})
        FLOW.write(self.design_path, self.design)

    def check(self):
        FLOW.write(self.design_path, self.design)
        return FLOW.check(self.context, self.design_path)

    def test_public_commands_select_changed_rows_and_preserve_historical_blobs(self):
        self.prepare()
        cli_context = self.root / "from-cli"
        args = [sys.executable, str(SCRIPT), "collect", "--repo", str(self.repo), "--base", self.base,
                "--revision", self.head, "--out", str(cli_context)]
        for kind, paths in self.sources.items():
            for path in paths:
                args.extend(["--" + kind, path])
        subprocess.run(args, check=True, capture_output=True)
        subprocess.run([sys.executable, str(SCRIPT), "check", "--context", str(cli_context), "--design",
                        str(self.design_path)], check=True, capture_output=True)
        context = FLOW.read(cli_context / "context.json")
        sources = {s["id"]: s for s in context["sources"]}
        self.assertNotIn("test:tests/test_island.py", sources)
        self.assertNotIn("ac:other-AC.md", sources)
        for path in ("tests/test_town.py", "tests/test_road.py"):
            self.assertFalse((self.repo / path).exists())
            old = sources[f"historical-test:{self.base}:{path}"]
            self.assertEqual(f"{self.base}:{path}", old["origin"])
            self.assertEqual(git(self.repo, "show", old["origin"]), (cli_context / old["snapshot"]).read_text().strip())

    def test_case_must_be_active_selected_and_match_its_scoped_acs(self):
        self.prepare()
        case = self.design["cases"][0]
        for case_id, ac, error in [
            ("Route.road", "AC-TOWN", "active in-scope"),
            ("Route.island", "AC-TOWN", "active in-scope"),
            ("Route.town", "AC-UNKNOWN", "ACs differ"),
        ]:
            with self.subTest(case_id=case_id, ac=ac), self.assertRaisesRegex(ValueError, error):
                case.update(id=case_id, requirements=[ac])
                self.check()
        self.design["inventory_scope"].append("missing")
        with self.assertRaisesRegex(ValueError, "unknown test inventory ID"):
            self.check()

    def test_individual_requirement_and_case_citations(self):
        self.prepare()
        ac = self.design["requirements"][1]
        for refs, error in [(None, "missing citations"), ([cite("code:routes.py")], "must cite AC"),
                            ([cite("ac:AC.md", 2, 3)], "line range")]:
            with self.subTest(refs=refs), self.assertRaisesRegex(ValueError, error):
                ac["citations"] = refs
                self.check()
        ac["citations"] = [cite("ac:AC.md", 2, 2)]
        self.design["cases"][0]["citations"][-1] = cite("test:tests/test_unknown.py")
        with self.assertRaisesRegex(ValueError, "case must cite its own"):
            self.check()

    def test_an_added_inventory_entry_must_cite_its_own_head_path(self):
        inventory_path = self.repo / "test-inventory.json"
        inventory = FLOW.read(inventory_path)
        inventory["entries"][-1]["citations"] = [cite("test:tests/test_local.py")]
        FLOW.write(inventory_path, inventory)
        self.head = commit(self.repo, "Misattribute the new test to an unrelated assertion")
        self.prepare()
        with self.assertRaisesRegex(ValueError, "active test must cite its own"):
            self.check()

    def test_retirement_must_cite_its_own_file(self):
        inventory_path = self.repo / "test-inventory.json"
        inventory = FLOW.read(inventory_path)
        retired = next(e for e in inventory["entries"] if e["action"] == "retire")
        retired["citations"] = [cite("historical-test:" + self.base + ":tests/test_town.py")]
        FLOW.write(inventory_path, inventory)
        self.head = commit(self.repo, "Misattribute retired test evidence")
        self.prepare()
        with self.assertRaisesRegex(ValueError, "retired test must cite its own"):
            self.check()

    def test_historical_source_must_exist_in_the_pinned_history(self):
        git(self.repo, "checkout", "-q", "--detach", self.base)
        (self.repo / "side.txt").write_text("Only on another branch\n")
        unrelated = commit(self.repo, "Advance a sibling branch")
        for ref in (unrelated + ":tests/test_town.py", self.head + ":tests/test_town.py", "HEAD:routes.py"):
            with self.subTest(ref=ref), self.assertRaises(ValueError):
                FLOW.collect(self.repo, self.head, self.base, dict(self.sources, **{"historical-test": [ref]}),
                             self.root / "invalid")
