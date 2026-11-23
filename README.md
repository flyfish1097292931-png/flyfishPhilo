# flyfishPhilo

**一本允许你改口的思想手记。** 把一次经历、一种解释和一条你愿意暂时采用的规则分开保存。也可以只留下问题，永远不回答它。

[English](docs/english.md) · [用任意 AI 开始](docs/any-chat.md) · [Agent 接口](docs/interop.md) · [方法说明](docs/method.md)

## 三种用法，选一种即可

| 你现在有什么 | 怎样开始 |
|---|---|
| 一个浏览器 | [下载单文件工作台](https://raw.githubusercontent.com/flyfish1097292931-png/flyfishPhilo/main/index.html)（链接另存为 `flyfishPhilo.html`），双击即可；或下载仓库 ZIP 解压，打开 `index.html`。不用注册、安装或连接模型。 |
| 一个只能聊天的 AI | 复制[一段纯文本短笺](docs/any-chat.md)，替换自己的问题和一两条愿意分享的材料。模型可以用散文回答，不需要支持工具、JSON 或 MCP。 |
| 能处理 JSON 或调用本地工具的 Agent | 读[互操作协议](docs/interop.md)：选中片段 → 上下文包 → 候选提案。可用标准输入/输出或本地 MCP。无模型密钥，无厂商 SDK。 |

### 第一次打开，先看一个改口的瞬间

进入虚构的读书会案例。主持人起初采用「以后不点名，只等举手」。一位新读者却写道：**我等了一晚上，怕举手插进熟人的话里。** 找到这张便笺，查看主持人撤回了哪条规则、哪条新规则仍有适用范围。再看另一个问题：「名义上可以拒绝，就有拒绝的自由吗？」这场读书会让问题变清楚了，却不足以替它作答。

不使用 JavaScript 的客户端也可以直接读取[同一份虚构工作簿（JSON）](examples/reading-circle.json)，无需运行样例生成器。注意区分这份可公开的合成资料和你自己导出的私有手记。

换成你自己的内容时，先写你记得的一幕。一个材料可以支撑多种解释；愿意采纳，也不等于它已经被证明。工作台分别保留出处、竞争解释、反例、修订和本人同意。**离开前下载 JSON 才能恢复；Markdown 是整本阅读稿，不是备份，也不是默认发送给 AI 的资料包。**

## 边界

- 浏览器端在内存里工作；不登记账户、不调用云模型、不自动保存或上传。下载的是明文。若主动把选中的文字复制给第三方，适用对方的数据政策。
- 兼容性的共同下限是**能交换文字**，更强的能力按宿主选用。项目不宣称适配了世界上每一个产品、每种 MCP 传输或每一个模型版本。
- AI 入口只能生成候选。采纳、撤回和是否试行由本人决定。公开的是方法和软件，不是飞鱼的日记、未发表思想或人格副本。详见[隐私与信任边界](docs/privacy.md)。

## 开发与复现

浏览器用户不需要 Node。开发／命令行用户需要 Node.js 22+；构建和测试无 npm 依赖。分发打包器另用 Python 3.9+ 标准库。

```sh
git clone https://github.com/flyfish1097292931-png/flyfishPhilo.git
cd flyfishPhilo
node --test
node tools/build.cjs --check
node tools/notebook.cjs demo | node tools/notebook.cjs read
```

`src/` 是状态机和互操作协议；`ui/` 是界面；`examples/` 是全新虚构案例。修改源码后运行 `node tools/build.cjs` 重新生成单文件。欢迎提交让方法更清楚或协议更可移植的改进，见 [贡献说明](CONTRIBUTING.md)。分发的代码、文档和合成示例采用 [MIT](LICENSE)；私人工作簿不在许可范围内。

可选的整页验收（需已有 Python Playwright 和浏览器）：`python tests/browser_workbench.py chromium --channel chrome`，或指定 `firefox` / `webkit`。测试直接打开已构建的 `index.html`，断网执行选材、提案导入、撤回和真实文件下载。
