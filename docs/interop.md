# 把一个问题交给 AI，而不是把整本手记交给它

**只会聊天也能用。** 在本机选一个尚未悬置的问题、1–32 条该问题下的材料，生成并预览提示词，再决定是否复制。对方可以给出自然语言、说「不知道」或拒答；这些都不必转成 JSON，不会改手记。比如：

> 沉默算作回答吗？这里只有一条虚构材料：「乘客没有点头。」你怎么看？还有别的解释吗？不足以判断也请直说。请不要替我下结论或执行任何动作。

需要机器交换时，在工作台勾选材料并生成完整预览后，点「下载所选资料 JSON」。`flyfishPhilo-context.json` 是给 Agent 的资料包；`flyfishPhilo-notebook.json` 是整本私人备份，两者不要混用。能启动本地子进程的 agent 还可选 CLI 或 MCP。本项目不需要账户、密钥、npm 运行依赖、厂商 API 或网络，也不安装、不配置任何宿主。**开放接口不是对每一个模型、浏览器或 agent 的认证。**

## 给双方的数据

- **用户 → 模型：** [context-v1.json](../schemas/context-v1.json)。只有 `format`、`base`、`question:{id,text}`、`notes:[{id,origin,text}]`。不会默认全选，不取其他问题、未分组材料、`source`、kernel、文件路径或历史。`origin` 区分亲历、摘录、转述、虚构、AI，不证明内容真实。选中正文仍是原文；若其中有姓名、路径等敏感信息，先在本机检查，必要时另选脱敏材料。
- **模型 → 用户：** 自然语言始终可用。愿意给候选的，可按 [proposal-v1.json](../schemas/proposal-v1.json) 返回**一个 JSON 对象**，不包 Markdown。原样复制 `base`、问题 ID 和**全部按原顺序**的材料 ID。`kind` 是 `reading`（解读）、`claim`（主张）或 `practice`（实践）；`text / scope / why / rival / test` 分别写候选、范围、理由、竞争解释和区分它们的方法。其余字段一律拒绝。
- **核对 ≠ 采纳。** `check` 只验证资料包及引用，不判断论证真假，也看不到本机问题是否已悬置。可信用户侧的 `apply` 再核对**当前手记、当前选择**，只追加一条 `suggest`（`origin:'ai'`、未采纳、`previous:null`、`seed:null`）。精确重复即使重新载入也不追加；另一个不同候选可以并存。模型无权通过此接口改写旧稿、采纳、撤回或执行。

两份 Schema 都是独立的 JSON Schema Draft 2020-12，可离线校验结构。运行时另外检查摘要、问题/材料关系、唯一 ID、顺序和非空文字（每项最多 6000 个 UTF-16 单元；Schema 的 `maxLength` 按 Unicode 码点计）。不同机器可复算 `base`：材料按事件序号升序（`e2` 在 `e10` 前）；对以下数组做 ECMAScript `JSON.stringify`，不美化、不做 Unicode 或空白归一化，取 UTF-8 字节的 SHA-256 小写十六进制。

```js
["flyfishPhilo/context-1", [question.id, question.text], notes.map(n => [n.id, n.origin, n.text])]
```

只有当前问题措辞和所选材料投影参与绑定，不相关的编辑不改变摘要；完全相同的投影会得到相同的摘要。它**不是签名、用户身份或授权令牌**。请保留自己导出的资料包，不要把模型返回的引用当成你的选择。桥本身不外发；把提示词复制到云端宿主，意味着你选择把其中的文字交给该宿主。无需外发时请使用本地模型或不用 AI。

## Node 22 CLI

在项目根目录执行 `node tools/agent.cjs check < examples/agent-roundtrip.json` 即可试跑。这份[可拷贝的输入/输出对](../examples/agent-roundtrip.json)只使用读书会的两条虚构材料；结果应为 `{"ok":true}`。

从项目根目录运行。一个命令消费 stdin 上的一个 UTF-8 JSON 值（最多 4 MiB），只向 stdout 输出结果；不接受文件路径参数，不扫描目录或自动读写手记。Shell 重定向是用户自己的操作。

| 命令 | stdin | stdout |
|---|---|---|
| `node tools/agent.cjs prompt` | 已选 context | 纯文本提示词，含可选 JSON 模板 |
| `node tools/agent.cjs check` | `{context,proposal}` | `{"ok":true}`，不写入 |
| `node tools/agent.cjs context` **仅本机可信用户** | `{book,question,notes}`，后两项是问题 ID 和显式材料 ID 数组 | 最小 context |
| `node tools/agent.cjs apply` **仅本机可信用户** | `{book,context,proposal}`，`context` 须来自用户自己保留的原包 | 新的**完整私有手记**，原对象不变 |

退出码：`0` 成功；`1` 数据、校验、重复或处理失败（stdout 为空，stderr 给原因，不回显材料）；`2` 命令/参数用法错误。`--help` 查看简表。不要把 `context`、`apply` 的私有输入或 `apply` 输出交给外部模型。保存 `apply` 的结果时用**新文件名**，不要用 shell 重定向覆盖原文件（重定向可能先截断它）。

已有文件时，最短的两个调用：

```sh
node tools/agent.cjs prompt < context.json
node tools/agent.cjs check < pair.json
```

可直接从头复制的 POSIX shell 示例，使用虚构材料，不读写笔记文件：

```sh
selection=$(node -e '
  const m=require("./src/model.js");
  let book=m.append(m.blank(),"question",{text:"沉默算作回答吗？"});
  book=m.append(book,"note",{question:"e1",origin:"synthetic",source:"虚构背景",text:"虚构：乘客没有点头。"});
  console.log(JSON.stringify({book,question:"e1",notes:["e2"]}));')
packet=$(printf '%s\n' "$selection" | node tools/agent.cjs context)
printf '%s\n' "$packet" | node tools/agent.cjs prompt

pair=$(printf '%s\n' "$packet" | node -e '
  const c=JSON.parse(require("node:fs").readFileSync(0,"utf8"));
  const p={format:"flyfishPhilo/proposal-1",base:c.base,question:c.question.id,notes:c.notes.map(n=>n.id),
    kind:"reading",text:"也许是在等待。",scope:"只看这段虚构对话。",why:"没有明确约定。",rival:"也许没有听清。",test:"再问一次。"};
  console.log(JSON.stringify({context:c,proposal:p}));')
printf '%s\n' "$pair" | node tools/agent.cjs check

# 模拟用户在本机导入，仅打印新增事件的类型、来源和状态。
printf '%s\n%s\n' "$selection" "$pair" | node -e '
  const [s,p]=require("node:fs").readFileSync(0,"utf8").trim().split("\n").map(x=>JSON.parse(x));
  console.log(JSON.stringify({book:s.book,context:p.context,proposal:p.proposal}));' |
  node tools/agent.cjs apply | node -e '
    const m=require("./src/model.js"),book=JSON.parse(require("node:fs").readFileSync(0,"utf8"));
    const e=book.events.at(-1),i=m.replay(book).ideas[e.id]; console.log(e.type,i.origin,m.status(i));'
```

此例 `base` 是 `6bf306ce4bcd7377ecd473691b86dddcf56380c09804fb6aa93e35a657f87827`；最后两步应分别得到 `{"ok":true}` 和 `suggest ai candidate`。

**嵌入页面或本地程序。** 浏览器以普通 `<script>` 先加载 `src/model.js`、再加载 `src/bridge.js`；使用 `globalThis.FlyfishPhiloBridge`。Node 用 `require('./src/bridge.js')`。`await context(book,questionId,noteIds)` 记住该**手记对象**最近一次人工选择；重载、换手记或改选后，先根据当前界面重新选择，不从提案抄 ID。`prompt(packet)` 同步生成文本；对外来包先 `await verifyContext(packet)` 核验摘要。`await check(packet,p)` 不写入；用户决定导入时 `book = await apply(book,p)`。浏览器需要 Web Crypto；若本地文件模式不提供它，请用 CLI，不降级成弱摘要。

## 可选 MCP：本地 stdio，不注册宿主

宿主可在项目根下启动 `node tools/mcp.cjs`，或将脚本参数换为本机仓库内 `tools/mcp.cjs` 的绝对路径；不需要开放端口。只实现 [MCP 握手](https://modelcontextprotocol.io/specification/2025-06-18/basic/lifecycle)及文本工具子集：客户端明确请求 `2024-11-05` 时使用这一版本；其余请求返回首选 `2025-06-18`，不照抄未知版本。若客户端不接受返回版本，可改用 CLI/纯文本。发送 `notifications/initialized` 后才允许 `tools/list`、`tools/call`；支持 `ping`。UTF-8 JSON-RPC 2.0，每条消息一行，单行最多 4 MiB；通知不回包，关闭 stdin 即退出。

| `tools/call` 名称 | `arguments` | 成功时的 `result.content[0].text` |
|---|---|---|
| `format_prompt` | `{context}` | 提示词文本 |
| `check_proposal` | `{context,proposal}` | `{"ok":true}` |

每次调用自带完整的**已选资料包**，两工具不保留调用内容、不接收工作簿、路径或 URL，也不提供文件、网络、采纳或执行能力。传输层未知方法/工具或错误参数返回 JSON-RPC `error`；已知工具拒绝资料时返回 `result.isError:true`。宿主本身的其他工具和云端日志不受此服务控制。

**实测边界：** Node 22 和离线 Chrome `file://` 对同一虚构输入产生了相同摘要、提示词和候选。官方 Python MCP 客户端 0.9.1（`2024-11-05`）与 2.0.0（`2025-06-18`）分别完成握手、列举、调用两个工具与拒绝错误提案。官方 JavaScript SDK 1.27.1 也完成了相同往返。本地 `qwen3:4b` 可用纯文本讨论虚构材料，无需 MCP；曾有短预算回答被截断，不能把渠道连通当成回答正确或充分。这不是对每一个宿主的认证。

**从项目根复验。** 默认只用 Node；可选 Schema 测试使用已有的 Python `jsonschema`。可选 MCP 测试通过独立官方 Python `mcp` SDK 启动真实 stdio 子进程，验证握手、列举、两个工具及拒绝路径，不读取宿主配置。浏览器对照需已有 Playwright 和 Chrome。以下以 POSIX 的解释器选择语法为例，不需要在项目内安装依赖：

```sh
node --test tests/agent.test.cjs tests/bridge.test.cjs tests/mcp.test.cjs
PHILO_SCHEMA_PYTHON=python3 node --test --test-name-pattern='independent Draft' tests/agent.test.cjs
PHILO_MCP_PYTHON=python3 node --test --test-name-pattern='official Python' tests/mcp.test.cjs
PHILO_MCP_EXPECT_VERSION=2024-11-05 PHILO_MCP_PYTHON=python3 node --test --test-name-pattern='official Python' tests/mcp.test.cjs  # 旧版客户端
PHILO_BROWSER_PYTHON=python3 node --test --test-name-pattern='offline file' tests/bridge.test.cjs
```
