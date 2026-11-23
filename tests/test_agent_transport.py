"""Black-box tests for the relocated skill. No host registration or network."""
import asyncio
import importlib.util
import json
from itertools import count
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


SKILL = Path(__file__).resolve().parents[1] / "skills" / "flyfish-philo"
INSTALLER = SKILL.parents[1] / "tools" / "install_skill.py"
REQUEST_IDS = count(1)
# Explicit words of a fictional test participant; production never supplies a default.
CONSENT = '我同意把本题和我的回答保存在本机手记中'


def rpc(method, **params):
    message = {"jsonrpc": "2.0", "id": next(REQUEST_IDS), "method": method}
    if params:
        message["params"] = params
    return message


def hello(version="2025-06-18"):
    return rpc("initialize", protocolVersion=version, capabilities={},
               clientInfo={"name": "transport-test", "version": "1"})


def notification(method):
    return {"jsonrpc": "2.0", "method": method}


def ready():
    return notification("notifications/initialized")


def tool_call(name, arguments):
    return rpc("tools/call", name=name, arguments=arguments)


class InstalledSkill(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="philo-transport-")
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        self.cwd = self.root / "unrelated working directory"
        self.home = self.root / "empty home"
        self.cwd.mkdir()
        self.home.mkdir()
        self.db = self.root / "selected store.sqlite3"
        self.assertTrue((SKILL / "scripts" / "philo.py").is_file(), "missing skill transport")
        install = self.root / "installed skills" / SKILL.name
        shutil.copytree(SKILL, install, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        self.script = install / "scripts" / "philo.py"
        self.env = {k: os.environ[k] for k in ("PATH", "SystemRoot", "WINDIR", "TMP", "TEMP", "TMPDIR", "LANG")
                    if k in os.environ}
        self.env.update(HOME=str(self.home), USERPROFILE=str(self.home))

    def run_cli(self, *args, data=b"", env=None):
        return subprocess.run([sys.executable, "-B", "-S", str(self.script), *map(str, args)],
                              input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              cwd=self.cwd, env=self.env if env is None else env, timeout=10)

    def cli_call(self, name, args, *options, env=None):
        return self.run_cli(*options, "call", name,
                            data=json.dumps(args, ensure_ascii=False).encode("utf-8"), env=env)

    def success(self, proc):
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stderr, b"")
        self.assertEqual(len(proc.stdout.splitlines()), 1, "expected exactly one JSON result")
        return json.loads(proc.stdout)

    def exchange(self, *messages):
        lines = [m if isinstance(m, bytes) else json.dumps(m, ensure_ascii=False).encode("utf-8")
                 for m in messages]
        proc = self.run_cli("--store", self.db, "mcp", data=b"\n".join(lines) + b"\n")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stderr, b"")
        replies = [json.loads(line) for line in proc.stdout.splitlines()]
        for reply in replies:
            self.assertEqual(reply["jsonrpc"], "2.0")
            self.assertNotEqual("error" in reply, "result" in reply)
        return replies

    def tool_value(self, reply):
        self.assertIn("result", reply)
        result = reply["result"]
        self.assertFalse(result.get("isError"), result)
        block, = result["content"]
        self.assertEqual(block["type"], "text")
        return json.loads(block["text"])


class WireTests(InstalledSkill):
    def test_isolated_python_finds_the_installed_sibling_without_searching_cwd(self):
        p = subprocess.run([sys.executable, "-B", "-I", "-S", str(self.script), "tools"],
                           capture_output=True, cwd=self.cwd, env=self.env, timeout=10)
        self.assertEqual(self.success(p), self.success(self.run_cli("tools")))

    def test_output_frames_are_bounded_even_when_a_valid_id_uses_most_of_the_budget(self):
        limit = 1024 * 1024
        listing = dict(rpc("tools/list"), id="x" * (limit - 1024))
        ping = rpc("ping")
        _, bounded, pong = self.exchange(hello(), ready(), listing, ping)
        self.assertIn("error", bounded.keys(), "large result must produce an error, not a truncated JSON frame")
        self.assertTrue(bounded["id"] == listing["id"])
        self.assertLessEqual(len(json.dumps(bounded).encode()), limit)
        self.assertEqual(pong["id"], ping["id"])

    def test_invalid_requests_and_one_way_calls_cannot_create_a_thread(self):
        call = tool_call("philo_open", {"topic": "DO-NOT-ECHO", "consent": CONSENT})
        one_way = {k: v for k, v in call.items() if k != "id"}
        mixed = dict(call, result={})  # response and request fields cannot be combined
        ping = rpc("ping")
        _, denied, *rest = self.exchange(hello(), call, ready(), one_way, mixed, ping)
        self.assertEqual(denied["error"]["code"], -32002)
        self.assertEqual(len(rest), 2, "notification must not receive a reply")
        self.assertEqual(rest[0].get("error", {}).get("code"), -32600)
        self.assertNotIn("DO-NOT-ECHO", json.dumps(rest))
        self.assertFalse(self.db.exists())

    def test_bad_and_oversize_frames_do_not_echo_or_desynchronize_the_next_ping(self):
        ping = rpc("ping")
        oversized = b" " * (1024 * 1024) + json.dumps(ping).encode()
        malformed = [b"PRIVATE-EXAMPLE", b"\xff", b'{"a":1,"a":2}',
                     b'{"jsonrpc":"2.0","method":"ping","id":NaN}', b"[" * 2500 + b"?"]
        invalid = [[], dict(ping, id=None), dict(ping, id=True),
                   b'{"jsonrpc":"2.0","method":"ping","id":"\\ud800"}']
        *errors, pong = self.exchange(*malformed, *invalid, oversized, ping)
        self.assertEqual([r.get("error", {}).get("code") for r in errors],
                         [-32700] * len(malformed) + [-32600] * (len(invalid) + 1))
        self.assertTrue(all(r["id"] is None for r in errors))
        self.assertNotIn("PRIVATE-EXAMPLE", json.dumps(errors))
        self.assertEqual((pong["id"], pong["result"]), (ping["id"], {}))
        self.assertFalse(self.db.exists())

    def test_cli_rejects_ambiguous_oversize_or_multiple_values_before_opening_the_store(self):
        prefix = b'{"topic":"PRIVATE-EXAMPLE"}'
        for body in (b"[42]", prefix + b" {}", b'{"topic":"first","topic":"PRIVATE-EXAMPLE"}',
                     prefix + b" " * (1024 * 1024), b"\xff"):
            with self.subTest(size=len(body)):
                p = self.run_cli("--store", self.db, "call", "philo_open", data=body)
                self.assertNotEqual(p.returncode, 0)
                self.assertEqual(p.stdout, b"", "a failed CLI call has no result on stdout")
                self.assertIn("error", json.loads(p.stderr))
                self.assertNotIn(b"PRIVATE-EXAMPLE", p.stdout + p.stderr)
                self.assertFalse(self.db.exists())

    def test_bad_cli_usage_does_not_print_an_argument_as_an_error(self):
        p = self.run_cli("call", "philo_open", '{"topic":"PRIVATE-EXAMPLE"}')
        self.assertNotEqual(p.returncode, 0)
        self.assertEqual(p.stdout, b"")
        self.assertTrue(p.stderr)
        self.assertNotIn(b"PRIVATE-EXAMPLE", p.stderr)

    def test_handshake_gates_discovery_and_negotiates_the_text_tools_subset(self):
        definitions = self.success(self.run_cli("tools"))
        for requested, expected in (("2024-11-05", "2024-11-05"), ("2025-06-18", "2025-06-18"),
                                    ("2099-01-01", "2025-06-18")):
            with self.subTest(version=requested):
                before, init, early = rpc("tools/list"), hello(requested), rpc("tools/list")
                listing, ping, unknown = rpc("tools/list", _meta={}), rpc("ping"), rpc("resources/list")
                ping['id'] = str(ping['id'])  # both wire ID types survive unchanged
                replies = self.exchange(before, init, early, ready(), notification("notifications/other"),
                                        listing, ping, unknown)
                self.assertEqual([r['id'] for r in replies],
                                 [r['id'] for r in (before, init, early, listing, ping, unknown)])
                pre, negotiated, wait, found, pong, unsupported = replies
                self.assertEqual(pre["error"]["code"], -32002)
                self.assertEqual(wait["error"]["code"], -32002)
                self.assertEqual(negotiated["result"]["protocolVersion"], expected)
                self.assertEqual(negotiated["result"]["capabilities"], {"tools": {}})
                self.assertEqual(found["result"], definitions)
                self.assertEqual(pong["result"], {})
                self.assertEqual(unsupported["error"]["code"], -32601)
        self.assertFalse(self.db.exists(), "handshake/discovery is not a write")

    def test_help_and_module_import_do_not_require_core_or_store(self):
        self.script.with_name("dialogue.py").unlink(missing_ok=True)  # installed copy only
        help_result = self.run_cli("--help")
        self.assertEqual(help_result.returncode, 0, help_result.stderr)
        for spelling in (b"--store", b"tools", b"call", b"mcp"):
            self.assertIn(spelling, help_result.stdout)
        probe = subprocess.run([sys.executable, "-B", "-S", "-c",
                                "import runpy,sys; runpy.run_path(sys.argv[1])", str(self.script)],
                               capture_output=True, cwd=self.cwd, env=self.env, timeout=10)
        self.assertEqual((probe.returncode, probe.stdout, probe.stderr), (0, b"", b""))
        _, missing, pong = self.exchange(hello(), ready(), rpc("tools/list"), rpc("ping"))
        self.assertEqual(missing["error"]["code"], -32603)
        self.assertEqual(pong["result"], {})
        self.assertFalse(self.db.exists())
        self.assertEqual(list(self.cwd.iterdir()) + list(self.home.iterdir()), [])


class IntegrationTests(InstalledSkill):
    def test_candidate_uses_the_answer_turn_and_is_not_automatically_in_the_map(self):
        def call(name, **args):
            return self.success(self.cli_call(name, args, "--store", self.db))

        opened = call("philo_open", topic="虚构练习：怎样辨认等待？", consent=CONSENT)
        thread = opened["thread"]
        asked = call("philo_ask", thread=thread, rev=opened["rev"], anchor="等待", question="你怎样辨认这次等待？")
        answered = call("philo_reply", thread=thread, rev=asked["rev"], kind="answer", text="我在等对方说完。")
        # No invented turn number: evidence refers to the store's actual answer.
        last = answered["last_answer"]
        cite = {"turn": last["turn"], "quote": last["text"]}
        drafting = call("philo_reply", thread=thread, rev=answered["rev"], kind="distill", text="请帮我整理这次的想法")
        draft = {"thread": thread, "rev": drafting["rev"], "claim": "等待有时是为了不打断对方。",
                 "scope": "只谈这次虚构的对话。", "rival": "也许当时在走神。", "test": "看能否复述对方最后一句。",
                 "evidence": [cite]}
        other = self.root / "DO-NOT-ECHO.sqlite3"
        _, bad, accepted, mapped = self.exchange(hello(), ready(),
            tool_call("philo_candidate", dict(draft, evidence=[dict(cite, path=str(other))])),
            tool_call("philo_candidate", draft), rpc("tools/call", name="philo_map"))
        self.assertTrue("error" in bad or bad.get("result", {}).get("isError"))
        self.assertNotIn("DO-NOT-ECHO", json.dumps(bad))
        self.assertFalse(other.exists())
        self.assertEqual(self.tool_value(accepted)["candidate"]["evidence"], [cite])
        self.assertEqual(self.tool_value(mapped)["positions"], [])

    def test_tool_or_rpc_arguments_cannot_select_another_store(self):
        other = self.root / "PRIVATE-EXAMPLE.sqlite3"
        attempts = [tool_call("PRIVATE-EXAMPLE", {}), tool_call("philo_map", [str(other)]),
                    rpc("tools/call", name="philo_map", arguments={}, store=str(other)),
                    tool_call("philo_open", {"topic": "PRIVATE-EXAMPLE", "consent": CONSENT, "path": str(other)})]
        _, *errors = self.exchange(hello(), ready(), *attempts)
        self.assertEqual(len(errors), len(attempts))
        for sent, reply in zip(attempts, errors):
            self.assertEqual(reply["id"], sent["id"])
            self.assertTrue("error" in reply or reply.get("result", {}).get("isError"))
            self.assertNotIn("PRIVATE-EXAMPLE", json.dumps(reply))
        self.assertFalse(other.exists())
        self.assertFalse(self.db.exists(), "invalid envelopes and unknown fields must not open SQLite")
        listing = self.success(self.cli_call("philo_read", {}, "--store", self.db))
        self.assertEqual(listing["threads"], [])

    @unittest.skipUnless(importlib.util.find_spec("mcp"), "optional: run with the official Python mcp SDK")
    def test_official_sdk_lists_calls_and_reads_a_tool_refusal(self):
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        async def client():
            options = StdioServerParameters(command=sys.executable,
                args=["-B", "-S", str(self.script), "--store", str(self.db), "mcp"],
                env=self.env, cwd=str(self.cwd))
            async with stdio_client(options) as (reader, writer), ClientSession(reader, writer) as session:
                negotiated = (await session.initialize()).model_dump(by_alias=True)
                self.assertIn(negotiated["protocolVersion"], ("2024-11-05", "2025-06-18"))
                found = await session.list_tools()
                self.assertEqual(sorted(t.name for t in found.tools),
                                 sorted(t["name"] for t in self.success(self.run_cli("tools"))["tools"]))
                opened = await session.call_tool("philo_open", {"topic": "A fictional pause", "consent": CONSENT})
                state = self.tool_value({"result": opened.model_dump(by_alias=True)})
                rejected = await session.call_tool("philo_ask", {"thread": state["thread"], "rev": state["rev"],
                    "question": "What changed in that pause?", "anchor": "DO-NOT-ECHO"})
                refusal = rejected.model_dump(by_alias=True)
                self.assertTrue(refusal["isError"])
                self.assertNotIn("DO-NOT-ECHO", json.dumps(refusal))
        asyncio.run(asyncio.wait_for(client(), timeout=15))

    def test_cli_and_two_independent_mcp_processes_share_the_pending_question(self):
        self.check_cross_process_roundtrip()  # portable folder-copy installation

    def test_project_installer_delivers_the_same_cross_process_roundtrip(self):
        target = self.root / "installer selected skills"
        install = subprocess.run([sys.executable, "-B", "-S", str(INSTALLER), "--target-dir", str(target)],
                                 capture_output=True, cwd=self.cwd, env=self.env, timeout=10)
        self.assertEqual(install.returncode, 0, install.stderr)
        self.script = target / SKILL.name / "scripts" / "philo.py"
        self.assertTrue(self.script.is_file())
        self.check_cross_process_roundtrip()

    def check_cross_process_roundtrip(self):
        topic, anchor = "虚构练习：停顿和倾听有什么关系？", "停顿"
        question = "你从什么线索认出这种停顿？"
        answer = "我等对方把话说完。\n有时我只是在找自己的词。"
        opened = self.success(self.cli_call("philo_open", {"topic": topic, "consent": CONSENT}, "--store", self.db))
        thread = opened["thread"]
        _, first = self.exchange(hello("2024-11-05"), ready(), tool_call("philo_ask", {
            "thread": thread, "rev": opened["rev"], "anchor": anchor, "question": question}))
        asked = self.tool_value(first)
        self.assertEqual((asked["thread"], asked["phase"]), (thread, "awaiting"))
        # exchange() has reaped the first process; there is no in-memory handoff.
        reply = {"thread": thread, "rev": asked["rev"], "kind": "answer", "text": answer}
        _, restored, recorded, stale = self.exchange(hello(), ready(),
            tool_call("philo_read", {"thread": thread}), tool_call("philo_reply", reply),
            tool_call("philo_reply", dict(reply, text="DO-NOT-ECHO")))
        current = self.tool_value(restored)
        self.assertEqual((current["rev"], current["phase"], current["pending"]["question"]),
                         (asked["rev"], "awaiting", question))
        saved = self.tool_value(recorded)
        self.assertEqual((saved["thread"], saved["phase"], saved["last_answer"]["text"]),
                         (thread, "ready", answer))
        self.assertTrue(stale["result"]["isError"])
        self.assertNotIn("DO-NOT-ECHO", json.dumps(stale))
        latest = self.success(self.cli_call("philo_read", {"thread": thread}, "--store", self.db))
        self.assertEqual((latest["rev"], latest["last_answer"]), (saved["rev"], saved["last_answer"]))

    def test_cli_uses_only_the_selected_store_outside_its_working_directory(self):
        other = self.root / "unused.sqlite3"
        topic = "虚构练习：什么样的停顿算是倾听？"
        state = self.success(self.cli_call("philo_open", {"topic": topic, "consent": CONSENT}, "--store", self.db,
                                           env=dict(self.env, FLYFISHPHILO_STORE=str(other))))
        recovered = self.success(self.cli_call("philo_read", {"thread": state["thread"]},
                                               env=dict(self.env, FLYFISHPHILO_STORE=str(self.db))))
        self.assertEqual((recovered["topic"], recovered["rev"], recovered["phase"]),
                         (topic, state["rev"], state["phase"]))
        self.assertTrue(self.db.is_file())
        self.assertFalse(other.exists())
        self.assertEqual(list(self.cwd.iterdir()) + list(self.home.iterdir()), [])

    def test_missing_or_relative_store_refuses_writes_without_echo(self):
        before = set(self.root.rglob("*"))
        for options, env in (((), self.env), (("--store", "relative.sqlite3"), self.env),
                             ((), dict(self.env, FLYFISHPHILO_STORE="~/book.sqlite3"))):
            with self.subTest(options=options, env_has_store="FLYFISHPHILO_STORE" in env):
                bad = self.cli_call("philo_open", {"topic": "PRIVATE-EXAMPLE", "consent": CONSENT}, *options, env=env)
                self.assertNotEqual(bad.returncode, 0)
                self.assertNotIn(b"PRIVATE-EXAMPLE", bad.stdout + bad.stderr)
                self.assertEqual(bad.stdout, b"")
                self.assertIn("error", json.loads(bad.stderr))
                server = self.run_cli(*options, "mcp", data=b"PRIVATE-EXAMPLE\n", env=env)
                self.assertNotEqual(server.returncode, 0)
                self.assertEqual(server.stdout, b"")
                self.assertNotIn(b"PRIVATE-EXAMPLE", server.stderr)
        self.assertEqual(set(self.root.rglob("*")), before)

    def test_catalogue_is_store_free_and_has_the_closed_tool_schemas(self):
        before = set(self.root.rglob("*"))
        plain = self.run_cli("tools")
        explicit = self.run_cli("--store", self.db, "tools")
        self.assertEqual((plain.returncode, explicit.returncode), (0, 0))
        self.assertEqual(plain.stderr + explicit.stderr, b"")
        self.assertEqual(plain.stdout, explicit.stdout)
        self.assertEqual(len(plain.stdout.splitlines()), 1, "expected exactly one JSON catalogue")
        tools = json.loads(plain.stdout)["tools"]
        self.assertEqual(sorted(t["name"] for t in tools),
                         sorted("philo_" + n for n in ("open", "read", "ask", "reply", "candidate", "map")))
        for tool in tools:
            self.assertTrue(tool["description"])
            schema = tool["inputSchema"]
            self.assertEqual(schema["type"], "object")
            self.assertIs(schema["additionalProperties"], False)
            self.assertFalse({"store", "path", "db"} & schema["properties"].keys())
        self.assertEqual(set(self.root.rglob("*")), before)
        # No -B: separate Python's own startup cache from writes by the skill itself.
        cache = self.root / "interpreter cache"
        p = subprocess.run([sys.executable, "-S", str(self.script), "tools"],
                           capture_output=True, cwd=self.cwd,
                           env=dict(self.env, PYTHONPYCACHEPREFIX=str(cache)), timeout=10)
        self.assertEqual(self.success(p)["tools"], tools)
        self.assertFalse(any(cache.rglob("*dialogue*.pyc")))
        self.assertFalse(self.db.exists())


if __name__ == "__main__":
    unittest.main()
