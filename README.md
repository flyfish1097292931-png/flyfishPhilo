# flyfishPhilo

**在 Agent 里一次只谈一个问题。答案来自你，候选也由你决定。**

`flyfishPhilo` 把一段苏格拉底式思想澄清嵌入你选择的 AI Agent：在你**明确同意本地保存**之后，它逐轮问和上一句有关的问题；你隔几天回来，Agent 可以从本地手记接着这一问。只有你实际回答的话能作证；只有你邀请整理时才起草候选；明确选择「保留这一版」才记录为暂时立场。

这不是一个供你另开网页、再手动把内容交给 AI 的工作台。浏览器工具仍作为可选的独立本地界面保留；**核心用法发生在 Agent 对话里。**

## 你会感受到什么

1. 你：「我同意把本题和我的回答保存在本机手记中。我想一问一答地看看：为什么有些会议我有话却没说？」
2. Agent：「你能想起最近一次想说又没说的时刻吗？」（一个问题；沿用你说过的话。）
3. 你：「上周讨论方案时，主持人突然叫到我，我把已写好的一句删掉了。」
4. Agent：「你说的『已写好的一句』，当时写的是什么？」句子里的「已写好的一句」就来自上一条回答。问完即停，你可以回问、跳过、换题，或者说到此为止。
5. 只有你邀请整理时，Agent 才依据具体原话提出一条有适用范围、竞争解释和可区分情形的**候选**。你可以修改、暂时保留、撤回，或什么也不做。保留某一版不等于它就是真理或定义了你。

这五步是交谈契约，不是预填的剧情。你说「不知道」时，不追问为什么；你说「先停」时，开放问题会留在下次可选位置；你反问时，Agent 先回答你。

## 直接和云端模型对话

在已配置 `OPENAI_API_KEY` 的终端，从本版源码目录运行：

```sh
python3 skills/flyfish-philo/scripts/chat.py --store "$HOME/.local/share/flyfishPhilo/inquiry.sqlite3" --model gpt-6.2-astra --share-with-openai
```

程序先询问是否允许在这个文件里保存；`--share-with-openai` 另外允许把本题所需的少量文字交给 OpenAI。两种许可互不代替。回答一经输入，宿主先保存，再让模型拟下一问；只显示成功写入手记的问题。网络中断不会抹掉刚才的回答。下次在同一命令后加 `--thread` 和屏幕显示的话题 ID，继续同一题。正在用其他 Agent？见[接入说明](docs/agent-hosts.md)；有可信用户回调的宿主可直接使用相同接口。

## 安装到已有 Agent

要求：Python 3.9+；只依赖标准库。SQLite、Skill 和 MCP 不需要模型密钥；上面的远程对话示例另需本人有权使用的 OpenAI 模型与 API 凭据。不要把凭据写进命令、手记或 issue。

**先选择谁能访问手记。** 每个 host 在自己的权限范围内运行 MCP 进程。把不同的人或 Agent 放在不同手记文件里。不要给公开网站、共享 Agent 或未知插件指向个人手记。数据库是明文，不是保险箱。

从仓库根目录把 Agent Skill 复制到你**选择**的 Agent Skill 目录。安装脚本要求写明绝对目标路径；不会改 MCP 配置，也不会覆盖已有同名技能：

从含 `skills/flyfish-philo/` 的本版源码目录执行。旧浏览器版不含这套 Agent 接口。

```sh
python3 tools/install_skill.py --target-dir "$HOME/.claude/skills"
# 或只选你实际在用的：
python3 tools/install_skill.py --target-dir "$HOME/.agents/skills"
python3 tools/install_skill.py --target-dir "$HOME/.hermes/skills"
```

再将这一个本地 stdio MCP 服务**按所选 Agent 的配置方式显式注册**：命令是 `python3`，参数顺序是绝对的 `.../skills/flyfish-philo/scripts/philo.py --store /由本人选择的绝对路径/dialogue.sqlite3 mcp`。`docs/agent-hosts.md` 有对应的 Hermes、Claude Code 与 Codex 配置示例；每个平台配置不同，没有一个文件能自动修改或注册到所有 host。只读清单无需手记或存储文件：

```sh
python3 skills/flyfish-philo/scripts/philo.py tools
```

配置与退出重进后的复测见 [接入任意 Agent](docs/agent-hosts.md)。不希望把文件权限交给 agent 时，不要装本地 MCP；任何只收普通文字的 AI 可使用[不保存的纯文本提问短笺](docs/any-chat.md)，但它本身没有跨会话记忆。

## 当前来源边界

- 每个进行中的谈话**全局最多只有一个待答问题**。下一问须含有用户最近一次回答的原词；不能跳成与回答无关的预设问卷。
- 回答原文保存在用户明确指定的本地文件中，不自动传给 Claude、OpenAI 或任意云端模型。MCP 会把所选本机话题提供给你正在使用的 Agent——若模型部署在云端，仍按该 Agent 服务商的数据政策处理。
- 候选中每一句证据都必须能在该题实际记录的回答里逐字找到。Agent 的问题、它的解释和用户的回答不混为一类。
- 「保留这一版」是一个可以撤回的个人选择；不让保留机制启动执行计划、记忆指令、风险评级或对外副作用。未保留的想法不自动改变其他问题。
- 用户的回答、标签和同意都从不数字签名。一个不可信 Agent 若冒充用户，软件不能识破；因此默认推荐的 host 是本人控制的交谈式 Agent。

**谁负责保存？** 在 `chat.py` 和接入用户回调的宿主中，保存由宿主负责；模型只提问或给候选。单独使用 MCP 的宿主则仍依赖模型实际调用工具。这两种保证不能互换。详见[云端验收与其他宿主的区别](docs/interop.md)。

## 项目构成

- `skills/flyfish-philo/SKILL.md`：可安装的 Agent Skill，告诉模型何时开始、每步如何回应、何时停止。
- `skills/flyfish-philo/scripts/dialogue.py`：平台无关的对话状态机和本地持久层。
- `skills/flyfish-philo/scripts/philo.py`：标准输入/输出 JSON 命令与可直接连接的 stdio MCP 服务。
- `tools/install_skill.py`：复制一个 Skill；需要用户指定 agent 的技能目录，永不写入 host 配置。
- `tests/`：逐轮、换进程恢复、权限、引用和安装边界回归。
- `src/` 与 `ui/`：可选的独立研究工作台。它不接管 agent 中的对话协议或手记存储。

运行测试：

```sh
python3 -m unittest discover -s tests -p 'test_*.py'
python3 -m compileall -q skills/flyfish-philo/scripts tools
node --test
node tools/build.cjs --check
```

[方法说明](docs/method.md) · [隐私与文件权限](docs/privacy.md) · [Agent 接入示例](docs/agent-hosts.md) · [协议实测](docs/interop.md) · [MIT](LICENSE) · [贡献规则](CONTRIBUTING.md)
