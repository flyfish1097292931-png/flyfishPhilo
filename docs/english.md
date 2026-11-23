# flyfishPhilo

**Socratically inquire inside your chosen agent. One question at a time; a candidate only when you ask for one.**

`flyfishPhilo` packages a portable Agent Skill and a local stdio MCP server. The Skill guides the agent's listening turn. The server keeps exactly one unanswered question and your verbatim replies in a local SQLite file; a later agent process can resume the same question. Only after you explicitly request distillation will the agent propose a bounded, evidence-anchored idea. Only the exact explicit choice “keep this version” makes it an owner-kept position. That choice is not proof, personality, policy or execution permission.

This is **not** primarily a browser workbench that asks you to repackage your notes for AI. A separate offline browser interface remains an optional tool.

## Talk to a cloud-backed agent

With your own `OPENAI_API_KEY`, run `python3 skills/flyfish-philo/scripts/chat.py --store /absolute/private/inquiry.sqlite3 --model gpt-6.2-astra --share-with-openai` from the source tree. Give local-storage consent separately at the prompt. A trusted human-input callback persists the reply **before** asking the cloud model; only an eligible, validated function call can become the next question or draft. Restart with the same options and `--thread ID`. Omit `--share-with-openai` to prevent network use. You may also integrate the callback in your own UI. The legacy MCP-only route below cannot guarantee that the model remembers to write.

## Install into an agent you choose

Requirements: Python 3.9+, standard library only. No model/provider key, external database, service account or web server. There is no silent install and no universal edit to host configuration. Install the skill in the chosen agent-specific directory:

```sh
# Run from a source directory containing skills/flyfish-philo/.
python3 tools/install_skill.py --target-dir "$HOME/.claude/skills"
# Or just one other chosen host directory:
python3 tools/install_skill.py --target-dir "$HOME/.agents/skills"
python3 tools/install_skill.py --target-dir "$HOME/.hermes/skills"
```

Then connect the local MCP server explicitly in that agent, using a user-chosen SQLite path. See [per-host instructions](agent-hosts.md); different agents have different native configuration, and the installer never touches them. `skills/flyfish-philo/SKILL.md` is written in the open Agent Skills format; `python3 tools/install_skill.py` only copies it to a directory you explicitly specify.

## A human-led conversational contract

- Ask one question and wait. Anchor the next question in a phrase from the user's previous answer. No preloaded questionnaire.
- A follow-up is a question, not a conclusion. The user can decline, pause, ask their own question or rewrite the topic.
- Do not distill before the user asks. Each candidate cites real user answers and includes a scope, rival interpretation and test.
- Do not put a candidate on the active map until the user explicitly selects that exact version. No hidden or agent-authored consent.
- A thread is local plaintext. A local MCP process does **not** make a remote-model host private: the host can send tool results to its provider. Choose the agent and database boundary deliberately.

**Tested boundary:** Two independent Hermes processes recovered the same pending question and stored the reply. The harness selected those calls through the real host registry. In a separate Hermes conversation, local `qwen3:4b` produced text but did not call the persistence tools. A text-only AI can use [a non-persistent prompt](any-chat.md); it is not a cross-session notebook. See [the host evidence](interop.md).

## Test

```sh
python3 -m unittest discover -s tests -p 'test_*.py'
node --test
node tools/build.cjs --check
```

[Chinese README](../README.md) · [Socratic method](method.md) · [Agent installation](agent-hosts.md) · [Privacy and authority](privacy.md) · [MIT](../LICENSE)
