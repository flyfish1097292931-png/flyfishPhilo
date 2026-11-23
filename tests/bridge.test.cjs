'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const { createHash } = require('node:crypto');
const model = require('../src/model.js');
const bridge = require('../src/bridge.js');
const Q = '我们能从一个停顿推测什么？';
function bookFixture() {
  let b = model.append(model.blank(), 'question', { text: Q });
  const note = (question, text) => { b = model.append(b, 'note', { question, origin: 'synthetic', source: '虚构背景：未授权来源', text }); };
  note('e1', '甲停了半拍。'); // e2
  note('e1', '未选：桌上有一封信。'); // e3
  b = model.append(b, 'question', { text: '未选的另一个问题' }); // e4
  note('e4', '另一组的材料。'); // e5
  note(null, '未分组材料。'); // e6
  for (let i = 0; i < 3; i++) note('e1', `未选的补充 ${i}`);
  note('e1', '乙没有马上接话。'); // e10
  return b;
}
function answer(c, edits = {}) {
  return { format: 'flyfishPhilo/proposal-1', base: c.base, question: c.question.id,
    notes: c.notes.map(n => n.id), kind: 'claim', text: '停顿本身不足以说明同意。',
    scope: '只看这段虚构对话。', why: '没有事先约定。', rival: '也许两人有默契。', test: '询问两人是否作了相同理解。', ...edits };
}

test('context projects explicit selections and hashes only that canonical public view', async () => {
  const b = bookFixture();
  const c = await bridge.context(b, 'e1', ['e10', 'e2']);
  const format = 'flyfishPhilo/context-1';
  const notes = [{ id: 'e2', origin: 'synthetic', text: '甲停了半拍。' }, { id: 'e10', origin: 'synthetic', text: '乙没有马上接话。' }];
  const bytes = JSON.stringify([format, ['e1', Q], notes.map(n => [n.id, n.origin, n.text])]);
  const base = createHash('sha256').update(bytes, 'utf8').digest('hex');
  assert.deepEqual(c, { format, base, question: { id: 'e1', text: Q }, notes });
  assert.deepEqual(await bridge.context(b, 'e1', ['e2','e10']), c);
  const unrelated = model.append(b, 'reword', { question: 'e4', text: '无关的新措辞' });
  assert.deepEqual(await bridge.context(unrelated, 'e1', ['e10','e2']), c);
  const reworded = model.append(b, 'reword', { question: 'e1', text: '这个停顿有其他解释吗？' });
  assert.notEqual((await bridge.context(reworded, 'e1', ['e2','e10'])).base, base);
  assert.notEqual((await bridge.context(b, 'e1', ['e2'])).base, base);
  assert.doesNotMatch(bridge.prompt(c), /未选|未授权来源|另一组的材料|未分组材料/);
});

test('selection never defaults to all and rejects mixed groups or a suspended question', async () => {
  const b = bookFixture();
  for (const ids of [undefined, [], ['e3','e3'], ['e5'], ['e6'], ['e2','e999'], ['e1'], ['constructor']]) {
    await assert.rejects(() => bridge.context(b, 'e1', ids));
  }
  await assert.rejects(() => bridge.context(b, 'e4', ['e2']));
  await assert.rejects(() => bridge.context(model.append(b, 'rest', { question: 'e1' }), 'e1', ['e2']));
});

test('apply appends exactly one inert AI suggestion and replay prevents duplicate imports', async () => {
  const b = bookFixture(), before = JSON.stringify(b);
  const c = await bridge.context(b, 'e1', ['e2','e10']), p = answer(c);
  const next = await bridge.apply(b, p);
  assert.equal(JSON.stringify(b), before);
  assert.deepEqual(next.events.slice(0, -1), b.events);
  const {format: _, ...data} = p;
  assert.deepEqual(next.events.at(-1), {...data, id: 'e11', type: 'suggest', previous: null, seed: null});
  const idea = model.replay(next).ideas.e11;
  assert.equal(idea.origin, 'ai'); assert.equal(idea.adopted, false); assert.equal(model.status(idea), 'candidate');
  await assert.rejects(() => bridge.apply(next, p), /重复|已导入|已存在/);
  // A new process or reload cannot undo duplicate detection by replay.
  const reload = JSON.parse(JSON.stringify(next));
  await bridge.context(reload, 'e1', ['e2','e10']);
  await assert.rejects(() => bridge.apply(reload, p), /重复|已导入|已存在/);
  const other = await bridge.apply(reload, {...p, rival:'也可能只是换气。'});
  assert.equal(other.events.at(-1).type, 'suggest'); assert.equal(other.events.length, next.events.length+1);
});

test('apply requires the current human-selected group, not an old or self-consistent alternative', async () => {
  const b = bookFixture();
  const other = answer(await bridge.context(b, 'e1', ['e3']));
  const c = await bridge.context(b, 'e1', ['e2','e10']), p = answer(c);
  await assert.rejects(() => bridge.apply(b, other));  // It has a valid hash for real material not in this selection.
  const restored = structuredClone(b);
  await assert.rejects(() => bridge.apply(restored, p)); // Never infer local consent from an agent-supplied proposal.
  const changed = model.append(b, 'reword', {question:'e1',text: '换个问法。'});
  await bridge.context(changed, 'e1', ['e2','e10']);
  await assert.rejects(() => bridge.apply(changed, p));
  const paused = model.append(b, 'rest', {question:'e1'});
  await assert.rejects(() => bridge.apply(paused, p));
  // A still-open book object may be edited by caller code; the live projection must be recomputed.
  b.events[1].text = '已经换掉的已选材料。';
  await assert.rejects(() => bridge.apply(b, p));
});

test('proposal is a closed, bounded shape; a natural-language refusal is never an import', async () => {
  const b = bookFixture(), c = await bridge.context(b, 'e1', ['e2','e10']), p = answer(c);
  for (const bad of ['不知道', {}, {...p,format:'other'}, {...p,kind:'adopt'}, {...p,notes:['e10','e2']},
    {...p,notes:['e2']}, {...p,notes:['e2','e2']}, {...p,question:'e4'}, {...p,origin:'human'},
    {...p,base:p.base.toUpperCase()}, {...p,base:'0'.repeat(64)}, {...p,notes:['e5','e10']},
    {...p,previous:null}, {...p,seed:null}, {...p,adopted:true}, {...p,scope:'  '}, {...p,test:'星'.repeat(6001)},
    {...p,why:'🌿'.repeat(3001)}, Object.fromEntries(Object.entries(p).filter(([k])=>k !== 'rival'))]) {
    await assert.rejects(() => bridge.apply(b,bad));
    await assert.rejects(() => bridge.check(c,bad));
  }
  const inert = answer(c, {kind:'practice',text:'一句含「执行」二字的普通引文。'});
  assert.equal((await bridge.apply(b,inert)).events.at(-1).type,'suggest');
});

test('only the most recent explicit selection remains authorized, even with overlapping exports', async () => {
  const b = bookFixture();
  const [old, latest] = await Promise.all([bridge.context(b,'e1',['e2']),bridge.context(b,'e1',['e10'])]);
  await assert.rejects(() => bridge.apply(b,answer(old)));
  assert.equal((await bridge.apply(b,answer(latest))).events.at(-1).type,'suggest');
  await assert.rejects(() => bridge.context(b,'e1',[]));
  await assert.rejects(() => bridge.apply(b,answer(latest)));
});

test('offline file:// classic scripts produce the same digest and inert import as Node', {
  skip: process.env.PHILO_BROWSER_PYTHON ? false : 'set PHILO_BROWSER_PYTHON to a Python with Playwright and installed Chrome',
}, async t => {
  const {spawnSync} = require('node:child_process');
  const {pathToFileURL} = require('node:url');
  const {join} = require('node:path');
  const b = bookFixture(), c = await bridge.context(b,'e1',['e2','e10']), p = answer(c);
  const script = `
import json, sys
from playwright.sync_api import sync_playwright
book, proposal = json.load(sys.stdin)
with sync_playwright() as pw:
    browser = pw.chromium.launch(channel='chrome',headless=True,args=['--disable-background-networking'])
    page = browser.new_page(offline=True, service_workers='block')
    page.goto(sys.argv[2])
    page.set_content('<!doctype html><meta charset=utf-8>')
    page.add_script_tag(url=sys.argv[1]); page.add_script_tag(url=sys.argv[2])
    result = page.evaluate('''async ([book, p])=>{
      const b=globalThis.FlyfishPhiloBridge;
      const c=await b.context(book,'e1',['e10','e2']);
      const checked=await b.check(c,p), next=await b.apply(book,p);
      return {scheme:location.protocol, context:c, checked, prompt:b.prompt(c), next};
    }''',[book,proposal]); result['browser']=browser.version; print(json.dumps(result)); browser.close()`;
  const urls = ['model.js','bridge.js'].map(f=>pathToFileURL(join(__dirname,'..','src',f)).href);
  const r = spawnSync(process.env.PHILO_BROWSER_PYTHON,['-B','-c',script,...urls], {
    input:JSON.stringify([b,p]),encoding:'utf8',timeout:30000,
  });
  assert.equal(r.status,0,r.stderr || r.error?.message);
  const actual=JSON.parse(r.stdout);
  assert.equal(actual.scheme,'file:'); assert.deepEqual(actual.context,c); assert.deepEqual(actual.checked,{ok:true});
  assert.equal(actual.prompt,bridge.prompt(c)); assert.deepEqual(actual.next,await bridge.apply(b,p));
  t.diagnostic(`Chrome ${actual.browser}, file://, offline, SHA-256 / prompt / candidate match Node`);
});
