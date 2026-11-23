#!/usr/bin/env python3
"""flyfishPhilo: local JSON CLI and newline-delimited MCP stdio server."""
import sys
if __name__ == "__main__":
    sys.dont_write_bytecode = True  # Discovery must work in a read-only skill install.

import argparse
from contextlib import closing
from functools import lru_cache
from importlib.util import module_from_spec, spec_from_file_location
import json
import math
import os
from pathlib import Path

VERSIONS = ("2025-06-18", "2024-11-05")  # preferred first; same text-tools subset
MAX_BYTES = 1024 * 1024  # payload bytes, excluding the stdio LF
RESULT_LIMIT = "Result exceeds the 1 MiB limit. Read a single thread and check its current revision before retrying."


class InvalidParams(ValueError):
    """Only fixed, transport-authored messages may be put on the wire."""


class ToolRejected(Exception):
    pass


class ResultTooLarge(Exception):
    pass


class Parser(argparse.ArgumentParser):
    def error(self, message):
        # argparse's default message can contain private text mistakenly passed on argv.
        self.exit(2, "Invalid command or options; use --help. Pass tool arguments on stdin.\n")


def parse_json(raw):
    def unique(pairs):
        obj = dict(pairs)
        if len(obj) != len(pairs):
            raise ValueError
        return obj

    def integer(token):
        if len(token) > 128:  # also bound conversion on Python 3.9
            raise ValueError
        return int(token)

    def finite(token):
        number = float(token)
        if not math.isfinite(number):
            raise ValueError
        return number

    if len(raw) > MAX_BYTES:
        raise InvalidParams("Input exceeds the 1 MiB limit.")
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=unique, parse_int=integer,
                          parse_float=finite, parse_constant=finite)
    except (ValueError, RecursionError):
        raise InvalidParams("Invalid or ambiguous UTF-8 JSON.") from None


def frames(stream):
    """Yield one bounded payload, or None once per oversized line; resume after LF."""
    while True:
        part = stream.readline(MAX_BYTES + 1)
        if not part:
            return
        if part.endswith(b"\n"):
            yield part[:-1]
        elif len(part) <= MAX_BYTES:  # EOF after an unterminated final frame
            yield part
        else:
            yield None
            while part and not part.endswith(b"\n"):
                part = stream.readline(65536)


@lru_cache(maxsize=1)
def core():
    """Load only the installed sibling, including under Python -I; never search cwd."""
    spec = spec_from_file_location("_flyfish_philo_dialogue", Path(__file__).resolve().with_name("dialogue.py"))
    if spec is None or spec.loader is None:
        raise ImportError("Missing dialogue core.")
    module = module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        del sys.modules[spec.name]
        raise
    return module


def catalogue():
    return {"tools": core().TOOLS}


def invoke(path, name, arguments):
    api = core()
    definition = next((tool for tool in api.TOOLS if tool["name"] == name), None)
    if definition is None:
        raise InvalidParams("Unknown tool. Use tools to inspect the catalogue.")
    if not isinstance(arguments, dict):
        raise InvalidParams("Tool arguments must be one JSON object.")
    schema = definition["inputSchema"]
    if not (set(schema.get("required", ())) <= arguments.keys() <= schema["properties"].keys()):
        raise InvalidParams("Missing or unknown tool arguments.")
    try:
        with closing(api.Store(path)) as store:
            return store.call(name, arguments)
    except (api.DialogueError, ValueError):
        raise ToolRejected("Tool rejected the arguments or dialogue state. Check the schema and read the current revision before retrying.") from None


def compact(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))


def emit(value):
    raw = compact(value).encode("utf-8")
    if len(raw) > MAX_BYTES:
        raise ResultTooLarge(RESULT_LIMIT)
    sys.stdout.buffer.write(raw + b"\n")
    sys.stdout.buffer.flush()


def fault(request_id, code, message):
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def valid_id(value):
    if not isinstance(value, str):
        return type(value) is int
    try:
        # Reserve space for a correlated error before accepting any mutating request.
        return len(compact(value).encode("utf-8")) <= MAX_BYTES - 256
    except UnicodeEncodeError:
        return False


class Session:
    def __init__(self, path):
        self.path = path
        self.phase = "new"

    def receive(self, msg):
        if (not isinstance(msg, dict) or msg.get("jsonrpc") != "2.0" or "result" in msg or "error" in msg or
                not isinstance(msg.get("method"), str) or
                ("id" in msg and not valid_id(msg["id"]))):
            return fault(None, -32600, "Invalid request.")
        method = msg["method"]
        params = msg.get("params", {})
        if "id" not in msg:
            if (method == "notifications/initialized" and self.phase == "negotiated" and
                    isinstance(params, dict)):
                self.phase = "ready"
            return None  # Notifications never execute tools and never receive a reply.
        request_id = msg["id"]
        if not isinstance(params, dict):
            return fault(request_id, -32602, "Expected object parameters.")
        if method == "ping":
            result = {}
        elif method == "initialize":
            if self.phase != "new":
                return fault(request_id, -32600, "Already initialized.")
            version, client = params.get("protocolVersion"), params.get("clientInfo")
            if (not isinstance(version, str) or not version or not isinstance(client, dict) or
                    not all(isinstance(client.get(k), str) for k in ("name", "version")) or
                    not isinstance(params.get("capabilities"), dict)):
                return fault(request_id, -32602, "Invalid initialize parameters.")
            self.phase = "negotiated"
            result = {"protocolVersion": version if version in VERSIONS else VERSIONS[0],
                      "capabilities": {"tools": {}}, "serverInfo": {"name": "flyfishPhilo", "version": "stdio-1"}}
        elif method not in ("tools/list", "tools/call"):
            return fault(request_id, -32601, "Method not found.")
        elif self.phase != "ready":
            return fault(request_id, -32002, "Server not initialized.")
        elif method == "tools/list":
            if params.keys() - {"_meta"}:
                return fault(request_id, -32602, "Invalid list parameters (no pagination).")
            result = catalogue()
        else:
            if params.keys() - {"name", "arguments", "_meta"}:
                return fault(request_id, -32602, "Invalid call parameters.")
            try:
                value = invoke(self.path, params.get("name"), params.get("arguments", {}))
                result = {"content": [{"type": "text", "text": compact(value)}]}
            except InvalidParams as exc:
                return fault(request_id, -32602, str(exc))
            except ToolRejected as exc:
                result = {"isError": True, "content": [{"type": "text", "text": str(exc)}]}
        return {"jsonrpc": "2.0", "id": request_id, "result": result}


def serve(path):
    session = Session(path)
    for line in frames(sys.stdin.buffer):
        if line is None:
            emit(fault(None, -32600, "Frame exceeds the 1 MiB limit."))
            continue
        try:
            msg = parse_json(line)
        except InvalidParams:
            reply = fault(None, -32700, "Parse error.")
        else:
            try:
                reply = session.receive(msg)
            except Exception:
                # Never put SQLite diagnostics, paths, exception text or input in a reply.
                reply = fault(msg.get("id"), -32603, "Internal error. Check the skill installation and store permissions.")
        if reply is not None:
            try:
                emit(reply)
            except ResultTooLarge:
                emit(fault(reply["id"], -32603, RESULT_LIMIT))
    return 0


def main():
    parser = Parser(description=__doc__, allow_abbrev=False, epilog=(
        "tools prints {\"tools\":[...]}. call reads one UTF-8 JSON object; success writes one JSON line, "
        "failure writes only a diagnostic to stderr and exits nonzero. MCP frames are at most 1 MiB."))
    parser.add_argument("--store", default=os.environ.get("FLYFISHPHILO_STORE"),
                        metavar="ABS_PATH", help="absolute SQLite path (or FLYFISHPHILO_STORE)")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("tools", help="print tool definitions without opening a store")
    commands.add_parser("call", help="call one tool with a JSON object on stdin").add_argument("name")
    commands.add_parser("mcp", help="serve JSON-RPC 2.0 over stdin/stdout")
    args = parser.parse_args()
    try:
        if args.command == "tools":
            emit(catalogue())
            return 0
        if not args.store or not Path(args.store).is_absolute():
            raise InvalidParams("Choose an absolute --store path or set FLYFISHPHILO_STORE.")
        if args.command == "call":
            value = parse_json(sys.stdin.buffer.read(MAX_BYTES + 1))
            emit(invoke(args.store, args.name, value))
            return 0
        return serve(args.store)
    except BrokenPipeError:
        return 1
    except (InvalidParams, ToolRejected, ResultTooLarge) as exc:
        message = str(exc)
    except Exception:
        message = "Request failed. Check the JSON input, skill installation and store permissions."
    # Stdout contains only a successful CLI result or well-formed JSON-RPC responses.
    print(compact({"error": {"message": message}}), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
