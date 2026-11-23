'use strict';
const test=require('node:test'), assert=require('node:assert/strict'), M=require('../src/model.js');
const run=(b,t,d)=>M.append(b,t,d);
test('event tags are literal strings; sparse or coerced events must not disappear',()=>{
  for(const events of [[{id:'e1',type:['question'],text:'失效'}],Array(1)]) assert.throws(()=>M.replay({format:M.FORMAT,events}));
});
test('refusing an oversized update leaves the previous book readable',()=>{
  const events=Array.from({length:137},(_,i)=>({id:`e${i+1}`,type:'note',question:null,origin:'firsthand',source:'合成数据测试',text:'文'.repeat(4950)}));
  let b={format:M.FORMAT,events}; M.replay(b);
  let last;
  for (let k=0;k<5;k++) {const before=JSON.stringify(b);try {b=run(b,'note',{question:null,origin:'firsthand',source:'测试',text:'文'.repeat(5900)});}catch(e){assert.match(e.message,/过大/);assert.equal(JSON.stringify(b),before);M.replay(b);last=e; break;}}
  assert.ok(last,'crossed the serialized size ceiling');
});
test('only one version of a revision family may be adopted at once',()=>{
  let b=run(M.blank(),'question',{text:'问题'}); b=run(b,'note',{question:'e1',origin:'synthetic',source:'样例',text:'片段'});
  const prop={question:'e1',kind:'practice',text:'规则',scope:'这里',why:'理由',rival:'别的解释',test:'反面',notes:['e2'],previous:null,seed:null};
  const check=id=>({idea:id,note:'e2',verdict:'limit',detail:'仅适用于此时。'}), adopt=id=>({idea:id,reason:'尝试',review:'已看过限制',consent:true});
  b=run(b,'idea',prop);b=run(b,'challenge',check('e3'));b=run(b,'adopt',adopt('e3'));b=run(b,'idea',{...prop,text:'新规则',previous:'e3'});b=run(b,'challenge',check('e6'));
  assert.throws(()=>run(b,'adopt',adopt('e6')),/撤回/); b=run(b,'withdraw',{idea:'e3',reason:'试新稿',consent:true});
  b=run(b,'adopt',adopt('e6'));assert.equal(M.status(M.replay(b).ideas.e6),'adopted');assert.equal(M.status(M.replay(b).ideas.e3),'withdrawn');
});
