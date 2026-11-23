# Contributing / 贡献

欢迎改进通用方法、界面可访问性、协议移植或反例测试。最有用的 issue 是一个虚构的具体情形：操作了什么，得到了什么，为什么这个结果可能误导人。不要提交私人手记、人物画像、密钥、截图中的个人信息或版权不明的材料。

改代码前请跑 `node --test`。修改 `src/`、`examples/` 或 `ui/` 后运行 `node tools/build.cjs`；提交时源文件与生成的 `index.html` 应一致。新增状态变更，请给出至少一个必须被拒绝的例子。协议破坏性变更应切换格式版本，不能默默把旧候选变成已采纳。支持更复杂的 AI 宿主时，请保留纯文本入口与离线独立使用路径。

Code, project documentation and original fictional fixtures in this distribution are covered by [MIT](LICENSE). By submitting work, only offer material you may distribute under that license. The software license grants no permission to expose or reuse anyone's private data, likeness, voice or identity. Contributions change the framework, never a real person's beliefs.
