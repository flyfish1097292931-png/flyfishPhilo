# 接入 Agent：谁接收用户的原话？

**如果宿主能在模型之前接收用户输入，用可信回合接口。** 这是可靠续接的路径。`scripts/chat.py` 是可直接运行的 OpenAI Responses 参考实现；不需要更改现有 Agent 的配置。[README 的启动命令](../README.md)中，`--share-with-openai` 与本机保存同意是两个不同的选择。

要嵌入已有聊天界面，将以下步骤接入它的用户输入回调。`scripts/owner_turn.py --store ABS_PATH ACTION` 从标准输入读取一个 UTF‑8 JSON 对象。它是宿主 API，**不要作为模型工具注册**。

| ACTION | 由谁调用 | 输入与结果 |
|---|---|---|
| `open` / `resume` | 可信宿主 | 用户明确同意后 `open {topic,consent}`；重开时 `resume {thread}`，直接显示原 `display`，不请求云模型重写它。 |
| `human` | 用户回调 | `{thread,rev,text}`，先持久保存用户原话。暂停、跳过、反问、换题等可由明确 UI 控件传 `kind`。失败不前进；旧 rev 或网络失败后读回，不盲重发。 |
| `prepare` | 宿主 | `{thread}`。只在需要模型时投影当前题干、近答、必要的前问或少量证据。用户同意云处理后才把投影和对应的单个函数给模型。 |
| `commit` | 宿主验证模型提案 | `{thread,rev,name,arguments}`。`thread`、`rev` 必须来自宿主自己的当前回合，不能来自模型；`name`、`arguments` 来自模型原生函数调用。校验和事务成功后才显示返回值。模型不能直接开题、写用户回答、接受候选或访问其他题。 |

网络不可用、模型只说文字、模型回报不同型号，或两个进程争抢同一轮时，不会出现假装保存的新问题。重新用原 thread 打开；若上次回答已存但还没拟出下一问，继续拟问即可，不必再答一遍。反问的解释是临时显示，不冒充手记中的用户证据。

## 只能装 Skill/MCP 的宿主

以下是另外一种接法，有两块彼此独立的能力：

1. **Agent Skill** 约束对话方式：一个问题、一条原话锚点；接住用户的拒答；必须等明确邀请才提候选；不把提案伪装成用户的立场。
2. **本地 MCP server** 承担跨不同会话进程的持续记忆，提供六个 `philo_*` 工具并将其保存在用户指定的 SQLite 文件中。

只装 Skill，Agent 可以遵守一问一答的方法，但不能可靠地跨新 session 读取本地进度。只接 MCP 工具、不装 Skill，也可能有记忆但不懂该怎样节制地追问。**两步都要由本人选择并配置。**只想让代码兼容，不想改任何 Agent 设置的话，可以先在本地或隔离 profile 测试。

## 1. 安装 Agent Skill

从源项目根目录执行 `python3 tools/install_skill.py --target-dir "<明确的绝对技能目录>"`。路径必须绝对；安装器只复制 `SKILL.md` 和本地脚本，不改变 MCP 配置，遇到同名 Skill 时拒绝覆盖。不要向公共 Agent、团队公共 Skill 目录或不信任的人共享自己的 SQLite 手记。

| Agent | Skill 目录示例 | MCP 注册示例 |
|---|---|---|
| Hermes | `$HOME/.hermes/skills` | `hermes mcp add flyfish-philo --command "$(command -v python3)" --args "$HOME/.hermes/skills/flyfish-philo/scripts/philo.py" --store "$HOME/.local/share/flyfishPhilo/dialogue.sqlite3" mcp` |
| Claude Code | `$HOME/.claude/skills` | `claude mcp add --scope user flyfish-philo -- python3 "$HOME/.claude/skills/flyfish-philo/scripts/philo.py" --store "$HOME/.local/share/flyfishPhilo/dialogue.sqlite3" mcp` |
| Codex | `$HOME/.agents/skills` | `codex mcp add flyfish-philo -- python3 "$HOME/.agents/skills/flyfish-philo/scripts/philo.py" --store "$HOME/.local/share/flyfishPhilo/dialogue.sqlite3" mcp` |

如果你之前装过同名 Skill，先由你自己决定是否先检查或移出旧版。不要覆盖它来“自动升级”。目标目录只给一个受信 Agent 使用。

## 2. 创建隔离的本地数据路径

注册服务器之前，你可以先准备由本人选择的数据目录：

```sh
mkdir -p "$HOME/.local/share/flyfishPhilo"
chmod 700 "$HOME/.local/share/flyfishPhilo"
```

MCP 参数 `--store` 必须为绝对路径。例如 `$HOME/.local/share/flyfishPhilo/dialogue.sqlite3`。文件仅在实际第一次调用后建立；只查询 `tools` 不会创建个人手记。不配置隐含默认路径。SQLite 是明文，不做跨加密或凭据管理。

可先只查看候选工具清单，不接触任何数据文件：

```sh
python3 "$HOME/.hermes/skills/flyfish-philo/scripts/philo.py" tools
```

将路径中的 `.hermes/skills` 换成你**实际装入的那一处**即可。该命令列出六个 MCP 工具的 JSON 输入 schema。

## 3. 明确选择 Agent 的 MCP 配置

上表的 `hermes mcp add`、`claude mcp add` 和 `codex mcp add` 命令均会更改**当前用户所用** Agent 的真实 MCP 配置；运行之前应读完完整参数并确认命令里的 Python、Skill 和手记路径。不同产品各自管理配置，flyfishPhilo 不会统一注册，不会写 `.mcp.json`，也不会安装好后代替用户开启工具。上表是 shell 示例，不是平台适配承诺。

- **Hermes**：将此 server 加入当前选定 profile，并确保这个 profile 的工具组开放它。用 `hermes mcp list` 回读配置，`hermes mcp test flyfish-philo` 查连接。已确认测试/实际对话使用的是同一个 profile 和 store 路径，再使用 MCP。
- **Claude Code**：`--scope user` 在当前用户的 Code 配置注册这个 server。用 `claude mcp list` 回读；`claude mcp get flyfish-philo`（若当前 CLI 提供）查看连接信息。新开 session 后，要求模型列出 `philo_*` 工具来确认加载。
- **Codex**：`codex mcp add` 添加于当前 Codex 配置。回读 `codex mcp list`；在新 conversation 内确认工具暴露后再测试。

如 CLI 版本的 `add` 参数与本机帮助不符，请以 `hermes mcp add --help`、`claude mcp add --help` 或 `codex mcp add --help` 为准，不复制不理解的语法。如果本来不想改变真实 agent 配置，请不要运行本节的添加命令。

## 4. 如何进行第一次真实对话

先说一条真实的用户问题，并同时给出本机留存许可。例如：「我同意把本题和我的回答保存在本机手记中。我想一问一答地看看：为什么我在某些会上不发言？」

1. 先显出一句简短的开始问句，而不是自说自答或抛问卷；
2. 下一次追问逐字呼应你刚给出的一个明确表达；
3. 若你说「不知道」或「先停」，真正停下；若你反问，先回答；
4. 在你明确说「帮我整理」之前，不生成候选；
5. 给出的候选包含逐字来源、范围、竞争解释和能够区分二者的测试，并等待你明确选择「保留这一版」。

如果其中任何一步偏离，请在宿主中纠正它；不要将失败回复保存为你接受的内核。测试结束后可以退出 MCP Server，在之后的**新 Agent 进程或新 session**中读取同一路径并恢复未答的问题。AI 的想法是流转中的交谈内容，不因被保存就自动变成用户说过的话。
