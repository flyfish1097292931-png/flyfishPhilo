# flyfishPhilo

English · [简体中文](README.zh-CN.md)

flyfishPhilo is an open-source notebook for developing your own philosophy through conversation with an AI agent. Start with a hunch or an experience. The agent asks about the words you used, one question at a time, to help you work out what you believe, why, and what might change your mind. Over time, the views you choose to keep form a record you can revisit and revise.

## What does that look like?

> **You:** I think freedom means having options.
>
> **Agent:** If you could pick either of two jobs but couldn't turn both down, would that count as “having options”?
>
> **You:** I could choose an employer. I couldn't choose whether to take a job.

That distinction gives you something more precise to think about. You can follow it, challenge the question, or stop there. If you ask the agent to help put your view into words, it must quote your replies, say where its interpretation applies, offer another reading, and suggest a case that would distinguish the two. A draft only becomes part of your map of views if you explicitly keep it. You can withdraw it later.

## Try it

**Just want to try the method?** Paste the [English prompt](docs/any-chat.md#english-fallback) into a chat and add a question of your own. This route doesn't create a flyfishPhilo notebook or let you resume from one.

**Want to keep a notebook?** The reference terminal chat saves your replies in a local SQLite file. It requires Python 3.9+ and, for cloud-generated questions, an `OPENAI_API_KEY` with access to the model you select. From the repository root:

```sh
python3 skills/flyfish-philo/scripts/chat.py \
  --store "$HOME/.local/share/flyfishPhilo/inquiry.sqlite3" \
  --model gpt-6.2-astra --share-with-openai
```

The terminal prompts are currently in Chinese. To opt in at the first prompt, enter `I agree to save this inquiry and my replies locally` exactly as written. At the next prompt, type the question you want to explore. The program prints a thread ID: to return to the same inquiry later, rerun the command with `--thread` followed by that ID. Use `summarize this thread` to request a draft and `I want to keep this version` only if you agree with it.

**Saving and sharing are separate choices.** The notebook is not encrypted. The reference chat saves your reply before asking the model for the next question; a failed network request does not erase that reply. `--share-with-openai` lets the chat send context from the current inquiry to OpenAI for this run. Without the flag it makes no OpenAI request or new model-generated question.

## Use it in an existing agent

The [Agent Skill](skills/flyfish-philo/SKILL.md) supplies the conversation rules. A local [Model Context Protocol (MCP) server](skills/flyfish-philo/scripts/philo.py) lets a compatible host save replies and recover the exact unanswered question. Neither component needs a provider key. Choose a host you trust: a cloud-backed host may send tool results to its model provider.

1. Install the skill in **one** host. For example, for Claude Code run `python3 tools/install_skill.py --target-dir "$HOME/.claude/skills"`. Use `$HOME/.agents/skills` for Codex or `$HOME/.hermes/skills` for Hermes. The installer requires an absolute target, refuses to overwrite a skill, and does not edit host configuration.
2. Register a stdio MCP server in that host. Use `python3` as the command and pass, in order, the absolute path to the installed `flyfish-philo/scripts/philo.py`, `--store`, the absolute path to your chosen notebook, and `mcp`. You can inspect the available tools without creating a notebook: `python3 skills/flyfish-philo/scripts/philo.py tools`.
3. For reliable saving in your own chat interface, call [the host adapter](skills/flyfish-philo/scripts/owner_turn.py) directly when the user submits a reply, as the reference chat does. An MCP-only integration depends on the model actually calling the save tool. Give each person a separate notebook; the software cannot authenticate a user's words if a host impersonates them.

For a separate offline browser interface, open [index.html](index.html) from a downloaded copy of the project. It uses its own notebook, separate from the agent's SQLite file.

## Development

```sh
python3 -m unittest discover -s tests -p 'test_*.py'
python3 -m compileall -q skills/flyfish-philo/scripts tools
node --test
node tools/build.cjs --check
```

Further reading (in Chinese): [Method](docs/method.md) · [Host setup examples](docs/agent-hosts.md) · [Privacy](docs/privacy.md) · [Interoperability and test results](docs/interop.md).

[MIT License](LICENSE) · [Contributing](CONTRIBUTING.md)
