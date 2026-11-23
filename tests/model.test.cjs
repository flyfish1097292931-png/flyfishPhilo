'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const file = path.join(__dirname, '../src/model.js');
const M = fs.existsSync(file) ? require(file) : {};

const n = (question='e1',origin='synthetic')=>({question,origin,source:'合成情境',text:'留下时有多种选择。'});
const i = (more={})=>({question:'e1',kind:'practice',text:'约定可以跳过。',scope:'初次读书会',why:'开口成本不平等。',rival:'也可能只是题目不熟。',test:'私下征询会不会更紧张？',notes:['e2'],previous:null,seed:null,...more});
const build=(events)=>events.reduce((b,[t,d])=>M.append(b,t,d),M.blank());
const opening = [['question',{text:'开口与选择有关吗？'}],['note',n()]];
function rooted(more={}) { return build([...opening,['idea',i(more)]]); }

test('observations, seeds and ideas have provenance, not rule authority', () => {
  let b=build([...opening,['seed',{question:'e1',text:'允许跳过与敢于跳过，好像有距离。'}],['idea',i({seed:'e3'})]]);
  const s=M.replay(b); assert.equal(s.notes.e2.source,'合成情境'); assert.equal(s.seeds.e3.question,'e1');
  assert.deepEqual(s.ideas.e4.notes,['e2']); assert.equal(s.ideas.e4.origin,'human');
  assert.equal(M.status(s.ideas.e4),'candidate');
  assert.throws(()=>M.append(b,'idea',i({notes:['e75']})),/材料/);
  assert.throws(()=>M.append(b,'idea',i({notes:[]})),/材料/);
  assert.throws(()=>M.append(b,'idea',i({rival:'  '})),/文字/);
  const p=M.append(b,'rest',{question:'e1'});
  assert.throws(()=>M.append(p,'idea',i()),/悬置/);
  const handwritten=M.append(p,'note',n(null)); assert.equal(Object.values(M.replay(handwritten).notes).length,2);
});

test('manual ideas and machine suggestions report their different authorship', () => {
  const b=build(opening); const d={...i(),base:'3'.repeat(64)};
  const withAI=M.append(b,'suggest',d);
  assert.equal(M.replay(withAI).ideas.e3.origin,'ai'); assert.equal(M.status(M.replay(withAI).ideas.e3),'candidate');
  assert.throws(()=>M.append(b,'suggest',{...d,consent:true}),/字段/);
  assert.throws(()=>M.append(b,'suggest',{...d,base:'wrong'}),/摘要/);
  assert.equal(M.replay(M.append(b,'note',n(null,'ai'))).notes.e3.origin,'ai');
});

const check=(verdict='limit',idea='e3',note='e2')=>({idea,note,verdict,detail:'试了另一个情境，结论只适用于此处。'});
const endorse=(idea='e3')=>({idea,reason:'愿意在下次试用。',review:'已考虑不发言不等于自愿这一异议。',consent:true});

test('adoption requires a reviewed objection, scoped reason and human assent',()=>{
  const b=rooted(); assert.throws(()=>M.append(b,'adopt',endorse()),/检验/);
  const open=M.append(b,'challenge',check('open')); assert.throws(()=>M.append(open,'adopt',endorse()),/检验/);
  const checked=M.append(b,'challenge',check());
  assert.throws(()=>M.append(checked,'adopt',{...endorse(),consent:false}),/本人/);
  assert.throws(()=>M.append(checked,'adopt',{...endorse(),review:''}),/文字/);
  const active=M.append(checked,'adopt',endorse()); assert.equal(M.status(M.replay(active).ideas.e3),'adopted');
  assert.throws(()=>M.append(active,'adopt',endorse()),/已经/);
  assert.equal(M.replay(M.append(active,'trial',{idea:'e3',step:'下次开场说明。'})).trials.length,1);
});

test('a counterexample blocks adoption and stops new trials without erasing history',()=>{
  const b=rooted(); const blocked=M.append(b,'challenge',check('counter')); assert.throws(()=>M.append(blocked,'adopt',endorse()),/反例/);
  let active=M.append(M.append(b,'challenge',check()),'adopt',endorse());
  active=M.append(active,'trial',{idea:'e3',step:'一次邀请。'});
  const challenged=M.append(active,'challenge',check('counter'));
  assert.equal(M.status(M.replay(challenged).ideas.e3),'challenged'); assert.equal(M.replay(challenged).trials.length,1);
  assert.throws(()=>M.append(challenged,'trial',{idea:'e3',step:'继续执行。'}),/试行/);
  const paused=M.append(challenged,'rest',{question:'e1'});
  const withdrawn=M.append(paused,'withdraw',{idea:'e3',reason:'缩小范围再试。',consent:true});
  assert.equal(M.status(M.replay(withdrawn).ideas.e3),'withdrawn');
  assert.equal(M.replay(withdrawn).ideas.e3.checks.length,2);
});

test('accepting a philosophical position is not proof or an execution license',()=>{
  const claim=rooted({kind:'claim'});const a=M.append(M.append(claim,'challenge',check()),'adopt',endorse());
  assert.throws(()=>M.append(a,'trial',{idea:'e3',step:'运行'}),/试行/);
  const reading=rooted({kind:'reading'}); assert.throws(()=>M.append(M.append(reading,'challenge',check()),'adopt',endorse()),/解释/);
});

test('revision never launders a blocked or withdrawn version; ideas can connect across questions',()=>{
  let b=M.append(rooted(),'challenge',check('counter'));
  b=M.append(b,'idea',i({previous:'e3',text:'只在第一次见面时明确两种入口。'}));
  assert.equal(M.status(M.replay(b).ideas.e3),'challenged'); assert.equal(M.status(M.replay(b).ideas.e5),'candidate');
  b=M.append(b,'question',{text:'什么叫自由？'}); b=M.append(b,'idea',i({question:'e6',kind:'claim',text:'区分许可与实际代价。'}));
  const link={from:'e5',to:'e7',relation:'requires',why:'改进邀请要先区分名义选择和实际选择。'};
  b=M.append(b,'link',link); assert.equal(M.replay(b).links[0].why,link.why);
  assert.throws(()=>M.append(b,'link',link),/已有/); assert.throws(()=>M.append(b,'link',{...link,to:'e5'}),/自身/);
});

test('unknown fields, forged permissions, dangling refs and malformed history are rejected on replay',()=>{
  const b=rooted();const x=structuredClone(b);x.events[0].adopted=true;assert.throws(()=>M.replay(x),/字段/);
  const bad=structuredClone(b);bad.events[1].id='e99';assert.throws(()=>M.replay(bad),/顺序/);
  assert.throws(()=>M.replay({...b,format:'later'}),/版本/); assert.throws(()=>M.append(b,'link',{from:'e3',to:'e94',relation:'supports',why:'内容'}),/引用/);
  assert.equal(M.replay(b).ideas.e3.adopted,false);
});

test('a question can stand unanswered; rest and reword preserve the original', () => {
  assert.equal(typeof M.blank, 'function', 'need an empty private notebook');
  const start = M.blank();
  let b = M.append(start, 'question', {text:'为什么我没留下？'});
  b = M.append(b,'rest',{question:'e1'});
  assert.equal(M.replay(b).questions.e1.paused, true);
  assert.deepEqual(Object.keys(M.replay(b).ideas), []);
  assert.deepEqual(start, {format:'flyfishPhilo/1',events:[]});
  b = M.append(b,'resume',{question:'e1'});
  b = M.append(b,'reword',{question:'e1',text:'在哪些情况下我愿意留下？'});
  assert.deepEqual(M.replay(b).questions.e1.wording,['为什么我没留下？','在哪些情况下我愿意留下？']);
});
