"""racecar_full_assembly_tenth_scale_ur10e: the fixed hidden set, the grader's checks of it, and what the agent is given.

The grader reads the set straight from tests/hidden/episodes.json (format racecar-asm-set/1: four episodes, one per
stratum of arm/assembly_car/layout.py, each a seed and a layout digest) and compares the digest at every reset; a
malformed set, and a layout the cell builds differently, are task errors whose messages name no value of the set; every
agent process starts through netguard; the hidden kit is pinned by sha256 and file count (the development copy
tests/assets/gt.tar.xz, when present, has that sha256); the oracle token's sha256 is the one under tests/hidden/; once
the set is frozen it holds four distinct seeds in [0, 2**63), one per stratum, the selection record keeps each of them,
and nothing agent-visible (instruction.md, environment/) holds a value of the set or the token.

Stdlib only: the grader's set functions are taken from tests/verify.py by name (it imports numpy and MuJoCo at module
level, which the host venv does not have). Tests that need the frozen set skip until it exists (the hidden-set package
writes tests/hidden/episodes.json and selection.json).
"""
import ast
import hashlib
import json
import os
import re
import tempfile
import unittest
from pathlib import Path

SLUG = "racecar_full_assembly_tenth_scale_ur10e"
_HERE = Path(__file__).resolve()
_CANDIDATES = [_HERE.parents[1] / "tasks" / "driving" / SLUG, _HERE.parents[2] / SLUG]
TASK = next((p for p in _CANDIDATES if (p / "tests" / "verify.py").is_file()), _CANDIDATES[0])
TESTS = TASK / "tests"
VERIFY = TESTS / "verify.py"
HIDDEN = TESTS / "hidden"
SET_PATH = HIDDEN / "episodes.json"
SELECTION_PATH = HIDDEN / "selection.json"
CONFIG = json.loads((TESTS / "grader_config.json").read_text())
TEXT_EXT = (".md", ".txt", ".json", ".py", ".sh", ".toml", ".yaml", ".yml", ".xml", ".csv", ".mtl", ".cfg", ".ini")


class TaskError(Exception):
    pass


def _fail(reason):
    raise TaskError(reason)


def _grader(names, consts=("SET_FORMAT", "STRATA", "SEED_LIMIT")):
    """the named functions and module constants of tests/verify.py, executed in a stdlib namespace (fail -> TaskError)"""
    tree = ast.parse(VERIFY.read_text())
    body = [n for n in tree.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id in consts for t in n.targets)]
    body += [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    have = {n.name for n in body if isinstance(n, ast.FunctionDef)}
    assert have == set(names), "verify.py lacks %s" % (set(names) - have)
    ns = {"json": json, "os": os, "re": re, "fail": _fail}
    exec(compile(ast.Module(body=body, type_ignores=[]), str(VERIFY), "exec"), ns)
    return ns


G = _grader(["load_hidden_set", "check_layout_digest"])


def _layout_strata():
    tree = ast.parse((TESTS / "arm" / "assembly_car" / "layout.py").read_text())
    for n in tree.body:
        if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "STRATA" for t in n.targets):
            return tuple(ast.literal_eval(n.value))
    raise AssertionError("layout.py has no STRATA")


def _agent_visible_texts():
    """(relative path, text) of every agent-visible text file: instruction.md and environment/**"""
    out = []
    p = TASK / "instruction.md"
    if p.is_file():
        out.append(("instruction.md", p.read_text(errors="replace")))
    env = TASK / "environment"
    for dp, dns, fns in os.walk(env):
        dns[:] = [d for d in dns if d != "__pycache__"]
        for fn in fns:
            q = Path(dp) / fn
            if q.suffix.lower() in TEXT_EXT or fn.startswith(("Dockerfile", "requirements")):
                out.append((str(q.relative_to(TASK)), q.read_text(errors="replace")))
    return out


def _bounded(value):
    return re.compile(r"(?<![0-9A-Za-z])" + re.escape(value) + r"(?![0-9A-Za-z])")


class GraderSetChecks(unittest.TestCase):
    """the grader's own set loader and digest check, on synthetic sets"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)
        self.digests = [hashlib.sha256(b"layout %d" % i).hexdigest() for i in range(4)]
        self.seeds = [6151231234567890123, 4242, 9000000000000000001, 1 << 50]
        self.good = [{"seed": s, "stratum": st, "layout_digest": d} for s, st, d in zip(self.seeds, G["STRATA"], self.digests)]

    def _put(self, doc):
        (self.dir / "episodes.json").write_text(doc if isinstance(doc, str) else json.dumps(doc))

    def _set(self, eps):
        return {"format": G["SET_FORMAT"], "episodes": eps}

    def test_format_and_strata_are_the_cells(self):
        self.assertEqual(G["SET_FORMAT"], "racecar-asm-set/1")
        self.assertEqual(tuple(G["STRATA"]), _layout_strata())
        self.assertEqual(G["SEED_LIMIT"], 1 << 63)

    def test_a_valid_set_is_read_in_order(self):
        self._put(self._set(self.good))
        eps = G["load_hidden_set"]({"episodes": 4}, str(self.dir))
        self.assertEqual([e["seed"] for e in eps], self.seeds)
        self.assertEqual([e["stratum"] for e in eps], list(G["STRATA"]))

    def test_a_malformed_set_is_a_task_error_naming_no_value(self):
        g = self.good

        def with0(**kw):
            return [dict(g[0], **kw)] + g[1:]
        variants = {
            "missing file": None, "not json": "{oops", "wrong format": {"format": "x/1", "episodes": g},
            "no list": {"format": G["SET_FORMAT"], "episodes": {"a": 1}}, "three episodes": self._set(g[:3]),
            "five episodes": self._set(g + [dict(g[0], seed=77)]), "float seed": self._set(with0(seed=1.0)),
            "bool seed": self._set(with0(seed=True)), "negative seed": self._set(with0(seed=-1)),
            "seed of 2**63": self._set(with0(seed=1 << 63)), "string seed": self._set(with0(seed=str(g[0]["seed"]))),
            "repeated seed": self._set([g[0], dict(g[1], seed=g[0]["seed"])] + g[2:]),
            "unknown stratum": self._set(with0(stratum="yaw0lead0")),
            "two in one stratum": self._set([g[0], dict(g[1], stratum=g[0]["stratum"])] + g[2:]),
            "upper-case digest": self._set(with0(layout_digest=g[0]["layout_digest"].upper())),
            "short digest": self._set(with0(layout_digest=g[0]["layout_digest"][:63])),
            "no digest": self._set([{"seed": g[0]["seed"], "stratum": g[0]["stratum"]}] + g[1:]),
            "not an object": self._set([7] + g[1:]),
        }
        values = [str(s) for s in self.seeds] + self.digests + [d.upper() for d in self.digests] + [self.digests[0][:63]]
        for name, doc in variants.items():
            with self.subTest(name):
                if doc is None:
                    p = self.dir / "episodes.json"
                    if p.exists():
                        p.unlink()
                else:
                    self._put(doc)
                with self.assertRaises(TaskError) as cm:
                    G["load_hidden_set"]({"episodes": 4}, str(self.dir))
                msg = str(cm.exception)
                self.assertFalse([v for v in values if v in msg], msg)

    def test_a_different_layout_is_a_task_error_naming_no_digest(self):
        e = self.good[1]
        self.assertIs(G["check_layout_digest"](2, e, e["layout_digest"]), True)
        with self.assertRaises(TaskError) as cm:
            G["check_layout_digest"](2, e, "f" * 64)
        self.assertNotIn(e["layout_digest"], str(cm.exception))
        self.assertNotIn("f" * 64, str(cm.exception))
        self.assertIs(G["check_layout_digest"](2, e, "anything", nominal=True), False)


class GraderWiring(unittest.TestCase):
    """the grader's main path reads the set, checks every reset's digest and starts every agent process through netguard"""

    @classmethod
    def setUpClass(cls):
        tree = ast.parse(VERIFY.read_text())
        cls.fns = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}

    def _calls(self, fn):
        return [ast.unparse(n.func) for n in ast.walk(self.fns[fn]) if isinstance(n, ast.Call)]

    def test_the_set_is_read_from_hidden_and_drives_the_episodes(self):
        src = ast.unparse(self.fns["_main_locked"])
        self.assertIn("load_hidden_set(cfg, HIDDEN)", src)
        self.assertIn("for k, ep in enumerate(episodes, 1)", src)
        self.assertNotIn("seed_rng", src)                 # no OS-entropy draw: the set is fixed

    def test_every_reset_is_compared(self):
        calls = self._calls("run_episode")
        self.assertIn("server.reset", calls)
        self.assertIn("check_layout_digest", calls)
        src = ast.unparse(self.fns["run_episode"])
        self.assertLess(src.index("server.reset("), src.index("check_layout_digest("))
        self.assertLess(src.index("check_layout_digest("), src.index("wire.AgentProcess("))

    def test_agent_processes_start_through_netguard(self):
        self.assertIn("guarded", self._calls("run_episode"))
        self.assertIn("guarded", self._calls("contract_check"))
        self.assertIn("netguard_folder", self._calls("_main_locked"))
        g = ast.unparse(self.fns["guarded"])
        self.assertIn('"-I", "-S", guard, "exec", program_dir', g.replace("'", '"'))
        self.assertTrue((TESTS / "netguard.py").is_file())

    def test_the_kit_is_fetched_with_its_pins(self):
        src = ast.unparse(self.fns["fetch_hidden_gt"])
        for needle in ("assets", "gt.tar.xz", "sha256_file(src)", 'spec["files"]', "gt/", 'filter="data"'):
            self.assertIn(needle, src.replace("'", '"'))


class ConfigAndToken(unittest.TestCase):
    def test_grader_config_pins(self):
        self.assertEqual(CONFIG["episodes"], 4)
        self.assertIs(CONFIG["oracle_nominal_layout"], False)
        hg = CONFIG["hidden_gt"]
        self.assertRegex(hg["sha256"], r"\A[0-9a-f]{64}\Z")
        self.assertIsInstance(hg["files"], int)
        self.assertGreater(hg["files"], 0)
        self.assertTrue(hg["url"].endswith("/tasks/driving/%s/verifier/gt.tar.xz" % SLUG), hg["url"])
        self.assertEqual(CONFIG["scope"]["premounted"], [])
        self.assertIs(CONFIG["scoring"]["count_subassembly"], True)

    def test_the_givens_and_the_kit_are_pinned_at_one_published_dataset_commit(self):
        # published 2026-11-15: the asset list and hidden_gt.url name the same 40-hex commit of the asset dataset,
        # never the placeholder of forty zeros, and the kit sits in the task's own verifier/ folder next to payload/
        head = {}
        for ln in (TASK / "environment" / "assets.sha256").read_text(encoding="utf-8").splitlines():
            if ln.startswith("#"):
                k, _, v = ln[1:].partition(":")
                head[k.strip()] = v.strip()
        rev = head.get("revision", "")
        self.assertRegex(rev, r"\A[0-9a-f]{40}\Z")
        self.assertNotEqual(rev, "0" * 40, "the asset list holds the placeholder revision")
        self.assertEqual(head.get("prefix"), "tasks/driving/%s/payload" % SLUG)
        want = "%s/datasets/%s/resolve/%s/tasks/driving/%s/verifier/gt.tar.xz" % (
            head.get("endpoint", "https://huggingface.co").rstrip("/"), head.get("repo"), rev, SLUG)
        self.assertEqual(CONFIG["hidden_gt"]["url"], want)
        self.assertNotIn("placeholder", CONFIG["hidden_gt"].get("note", ""))

    def test_the_local_kit_copy_has_the_pinned_sha256(self):
        p = TESTS / "assets" / "gt.tar.xz"
        if not p.is_file():
            self.skipTest("no development copy tests/assets/gt.tar.xz here (an asset root, never in git)")
        h = hashlib.sha256()
        with open(p, "rb") as f:
            for b in iter(lambda: f.read(1 << 20), b""):
                h.update(b)
        self.assertEqual(h.hexdigest(), CONFIG["hidden_gt"]["sha256"])

    def test_the_oracle_token(self):
        tok = (TASK / "solution" / "reference" / "oracle_token").read_bytes().strip()
        self.assertRegex(tok.decode(), r"\A[0-9a-f]{64}\Z")
        self.assertEqual((HIDDEN / "oracle_token.sha256").read_text().strip(), hashlib.sha256(tok).hexdigest())

    def test_nothing_agent_visible_holds_the_token_or_names_the_hidden_files(self):
        tok = (TASK / "solution" / "reference" / "oracle_token").read_text().strip()
        sha = (HIDDEN / "oracle_token.sha256").read_text().strip()
        texts = _agent_visible_texts()
        self.assertTrue(texts, "no agent-visible text file found")
        for rel, text in texts:
            for v in (tok, sha, CONFIG["hidden_gt"]["sha256"]):
                self.assertIsNone(_bounded(v).search(text), rel)
            for name in ("oracle_token", "hidden/episodes", "hidden/selection", "hidden/bench_plan"):
                self.assertNotIn(name, text, rel)


class FrozenSet(unittest.TestCase):
    """the frozen set itself (skips until the hidden-set package has written tests/hidden/episodes.json)"""

    def setUp(self):
        if not SET_PATH.is_file():
            self.skipTest("tests/hidden/episodes.json not written yet (the hidden-set package selects it)")
        self.set = json.loads(SET_PATH.read_text())

    def test_the_set_passes_the_graders_own_loader(self):
        eps = G["load_hidden_set"](CONFIG, str(HIDDEN))
        self.assertEqual(len(eps), 4)
        self.assertEqual(sorted(e["stratum"] for e in eps), sorted(G["STRATA"]))
        self.assertEqual(len({e["seed"] for e in eps}), 4)

    def test_the_selection_keeps_every_episode(self):
        if not SELECTION_PATH.is_file():
            self.skipTest("tests/hidden/selection.json not written yet")
        sel = json.loads(SELECTION_PATH.read_text())
        cands = sel.get("candidates") or []
        seeds = {c.get("seed") for c in cands if isinstance(c, dict)}
        for e in self.set["episodes"]:
            self.assertIn(e["seed"], seeds)
        kept = [c for c in cands if isinstance(c, dict) and c.get("seed") in {e["seed"] for e in self.set["episodes"]}]
        for c in kept:
            if "selection" in c:
                self.assertEqual(c["selection"], "kept", c.get("seed"))

    def test_nothing_agent_visible_holds_a_value_of_the_set(self):
        values = []
        for e in self.set["episodes"]:
            values += [str(e["seed"]), e["layout_digest"]]
            if len("%x" % e["seed"]) >= 8:
                values.append("%x" % e["seed"])
        if SELECTION_PATH.is_file():
            for c in json.loads(SELECTION_PATH.read_text()).get("candidates") or []:
                if isinstance(c, dict) and isinstance(c.get("seed"), int):
                    values.append(str(c["seed"]))
        for rel, text in _agent_visible_texts():
            for v in values:
                self.assertIsNone(_bounded(v).search(text), "%s holds a value of the hidden set" % rel)


if __name__ == "__main__":
    unittest.main()
