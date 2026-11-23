# Contributing / 贡献

欢迎改进 Agent 对话方法、协议实现、host 适配或合成回归用例。该项目首先是一个**嵌入 Agent 的一问一答自我蒸馏 Skill 和本地持久层**；可选浏览器工作台不是相同产品的主入口。先在 [Agent 接入](docs/agent-hosts.md)与 [方法契约](docs/method.md)中理解边界。

只用合成话语测试。不得把真实私人手记、人格描述、候选观点、会话日志、真实数据库、未取得分发权的材料或任何口令提交到 issue、PR、工作流或测试资源。重现隐私问题时，只写能检验约束的假名或合成文本。

代码改动要求：

- `skills/flyfish-philo/scripts/` 必须保持只依赖 Python 标准库并兼容 Python 3.9+；MCP 不启动 HTTP 服务、不访问 Internet、不接收绝对/相对文件路径作为 tool 参数。
- 编写前先写会失败的测试。测试跨进程续接，验证一个 Active thread 只问一个问题，测试过期 revision 拒绝，候选引用必须逐字出自同一 framing 的用户回答，模糊回应绝不可变成肯定、采纳、试行或工具许可。
- 接触已答问题、放弃或重开用户选择应写成可逆的显式动作。题目可以没有答案，也可以只留问题。不得依赖 token 输出中的“看起来像同意”的 AI 自述。
- 变更 MCP 合同或事件状态版本时更新工具 schema、全套回归与宿主矩阵；如果拒绝某个合规输入，提供具名边界及复现用例。
- 对宿主兼容性的每一项报告写明 Agent/CLI/Python/MCP 精确版本、是否模型自主选择工具、是否跨独立进程回读和网络/模型边界；SDK 客户端 smoke ≠ 自动 Agent 对话验收。
- 本人不授权配置具体 profile 前，不得在任何真实 `~/.hermes`、`~/.claude`、`~/.agents` 路径注册服务或复制 Skill。只验证隔离的临时 home/profile。
- 不提交、不推送或发布包，除非负责人确认相应交付门。仅外观打包不代表安全验收通过。

Test：

```sh
python3 -B -m unittest discover -s tests -p 'test_*.py'
node --test
node tools/build.cjs --check
python3 -B tools/package.py --check
```

Sources, tests and fictional examples ship under the project MIT License. By submitting work, only offer material you may distribute under that licence. The project license never authorizes processing or publishing anyone's private conversation.
