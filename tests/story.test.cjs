'use strict';
const test = require('node:test'); const assert=require('node:assert/strict');
const M=require('../src/model.js'); const fs=require('node:fs'), path=require('node:path');
const demoPath=path.join(__dirname,'../examples/reading-circle.js');
const demo=fs.existsSync(demoPath)?require(demoPath):null;
test('a complete fictional notebook joins experience, objection, revision and a philosophical distinction',()=>{
  assert.equal(typeof demo,'function','need the worked reading-circle case');
  const b=demo(M);const s=M.replay(b), ideas=Object.values(s.ideas);
  assert.ok(ideas.some(i=>i.kind==='practice'&&M.status(i)==='adopted'&&i.previous));
  assert.ok(ideas.some(i=>i.kind==='practice'&&M.status(i)==='withdrawn'&&i.checks.some(c=>c.verdict==='counter')));
  assert.ok(ideas.some(i=>i.kind==='claim'&&M.status(i)==='candidate'));assert.ok(s.links.some(l=>s.ideas[l.from].question!==s.ideas[l.to].question));
  assert.ok(s.trials.length>0);assert.ok(Object.values(s.questions).some(q=>q.paused));
  assert.ok(Object.values(s.notes).every(n=>n.origin==='synthetic'));assert.deepEqual(b,demo(M));
  const md=M.markdown(b);for(const expected of ['深层记忆','当前内核','执行层','未坍缩区','反例','读书会','拒绝','撤回','材料','竞争解释']) assert.ok(md.includes(expected),expected);
  for(const i of ideas) assert.ok(md.includes(i.id));
});

test('Markdown is safe-to-read text, not an auto-loading remote image or HTML projection',()=>{
  assert.equal(typeof M.markdown,'function');
  let b=M.append(M.blank(),'question',{text:'<u>问题</u> ![随笔](https://example.invalid/photo)'});
  const md=M.markdown(b); assert.ok(!md.includes('<u>'));assert.ok(!md.includes('![随笔]('));
});
