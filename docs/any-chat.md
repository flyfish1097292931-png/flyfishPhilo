# 非持久的纯文本备用 / Non-persistent text fallback

只有不支持 Agent Skills 或本地 MCP 的 AI 才需要这张卡片。它给出**当次对话**的一问一答约定；它无法跨新 session 恢复未答问题、不写入 local SQLite，也不是本项目的 Agent 集成路径。使用任意云端聊天时，该模型服务仍会接收你输入的全部文字。只分享你愿意交给它的内容。不需要使用任何私人手记。

```text
请一次只问我一个问题，帮助我澄清下面这个问题。先不要总结。
如果我回答，下一问必须接住我刚刚使用的原词，不要照抄预制问卷或自己回答。
我可以说不知道、跳过、反问你、改题或停止；请把对话交还给我，不要劝我继续。
在我明确说“帮我整理一下”之前，不要替我提炼原则或总结人格。
如果我邀请整理，只基于我实际说过的话，提出一条仍待确认的候选理解；指出它的适用范围、一个竞争解释和可区分二者的观察。
不要替我采纳观点、推断诊断、记录待办或采取外部行动。

我想探的问题是：[写下一句你的问题]
```

## English fallback

```text
Ask one Socratic question at a time about this question. Wait for my reply.
Anchor each follow-up in a meaningful phrase from what I just said; do not use a canned questionnaire or answer for me.
I may not know, skip, ask you a question, reframe the topic, or stop. Yield the turn without trying to persuade me.
Do not distill an idea before I explicitly say “help me distill this.” If I ask, offer one provisional, contestable reading grounded in my actual words; give its scope, one competing explanation, and an observation that could distinguish them.
Do not adopt beliefs, diagnose me, save to a hidden memory, create tasks, or take external action.

Question: [one sentence]
```

A text-only conversation cannot prove literal citations, keep the exact open question outside that chat, or enforce consent. Treat it as temporary dialogue, not as a backup notebook or durable claim store.
