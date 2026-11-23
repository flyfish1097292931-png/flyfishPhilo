# 用任意 AI 开始 / Start in any chat

不需要安装工具。把下面的短笺复制给能处理文字的聊天模型，把方括号换成**你愿意分享**的内容。也可以把它当作纸上练习，跳过 AI。

```text
我在用 flyfishPhilo 整理一个问题。我只分享以下片段，请不要猜测未分享的经历。
问题：[我为什么在有些讨论里不说话，却在散场后说了很多？]
材料 A：[一件具体发生的事，或注明这是想象]
材料 B：[可选：一次不同的情形]
请先指出一个会改变判断的区分。给一个可能解释、另一个也说得通的解释，
再说什么例子能把二者区分开。指明分别用了哪个片段，不必凑出结论。
你可以说信息不足；我可以改问题、不答或到此为止。不要替我总结人格、采纳立场或安排任务。
```

收到回复后，只挑一句真正改变了问法的话。要留档，把它作为来源为 **AI 的解释** 的材料；不要标成亲历或本人立场。浏览器还可按已选片段生成带引用号的提示，支持 JSON 的模型可以返回可审阅的候选。

**English copyable version**

```text
I am using flyfishPhilo to think about one question: [question].
A: [a scene I chose to share; mark fiction if applicable]. B: [optional contrast].
Identify a distinction that changes the answer. Offer a possible reading, a competing
reading, and a case that could distinguish them. Say which note supports which step.
Insufficient information is a valid outcome. Do not infer a personality, accept a
position for me, or turn an unanswered question into a task. Plain text is fine.
```

This is an interchange convention, not a system prompt that overrides a model’s own rules. Before pasting into any hosted service, consider its retention policy. No service is contacted by the workbench.
