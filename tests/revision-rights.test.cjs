'use strict';
const test=require('node:test'), assert=require('node:assert/strict'), M=require('../src/model.js');
const note={question:'e1',origin:'synthetic',source:'虚构投票',text:'票上没有划线。'};
const idea={question:'e1',kind:'practice',text:'记录为空白票。',scope:'测试议程',why:'不代填意向。',rival:'可能是纸笔失效。',test:'核查设备。',previous:null,seed:null};
const mark=(idea,verdict='limit',detail='只适用这里。')=>({idea,note:'e2',verdict,detail});
const agree={idea:'e4',reason:'暂时保留。',review:'检查过设备解释。',consent:true};
function base(){let b=M.append(M.blank(),'question',{text:'空白票是弃权吗？'});b=M.append(b,'note',note);return M.append(b,'note',{...note,text:'另一张票。'});}
function active(){let b=M.append(base(),'idea',{...idea,notes:['e2']}); b=M.append(b,'challenge',mark('e4'));return M.append(b,'adopt',agree);}
const quit=(reason)=>({idea:'e4',reason,consent:true});
test('appending snapshots source selections and earlier events by value',()=>{
  const b=base(), picked=['e2']; const next=M.append(b,'idea',{...idea,notes:picked}); picked[0]='e3'; b.events[1].text='后来修改输入对象';
  assert.deepEqual(next.events[3].notes,['e2']); assert.equal(M.replay(next).notes.e2.text,note.text);
});
test('an accepted source list must also replay after a JSON round trip',()=>{
  const holes=Array(2);holes[0]='e2';assert.throws(()=>M.append(base(),'idea',{...idea,notes:holes}),/材料/);
  const b=active();assert.deepEqual(M.replay(b),M.replay(JSON.parse(JSON.stringify(b))));
});
test('ordinary records cannot consume the last counterexample and withdrawal slots',()=>{
  const b=active();while(b.events.length<M.LIMITS.events-2) b.events.push({id:`e${b.events.length+1}`,type:'note',...note});
  M.replay(b);assert.throws(()=>M.append(b,'note',note),/预留/);
  const c=M.append(b,'challenge',mark('e4','counter'));assert.throws(()=>M.append(c,'note',note),/预留/);
  const w=M.append(c,'withdraw',quit('不再采纳'));assert.equal(w.events.length,M.LIMITS.events);assert.equal(M.status(M.replay(w).ideas.e4),'withdrawn');
});
test('the byte ceiling also reserves room for two short, maximally escaped reasons',()=>{
  let b=active(); const filler={...note,text:'x'.repeat(5800)};
  while(true){try{b=M.append(b,'note',filler);}catch{break;}}
  let reserveHit=false;while(true){try{b=M.append(b,'note',note);}catch(e){reserveHit=/预留/.test(e.message);break;}}
  assert.ok(reserveHit);const escaped='\u0001'.repeat(256);b=M.append(b,'challenge',mark('e4','counter',escaped));b=M.append(b,'withdraw',quit(escaped));assert.equal(M.status(M.replay(b).ideas.e4),'withdrawn');
});
test('suspending inquiry cannot block a protective objection to an existing permission',()=>{
  let b=M.append(active(),'rest',{question:'e1'});b=M.append(b,'challenge',mark('e4','counter'));b=M.append(b,'withdraw',quit('退出'));assert.equal(M.status(M.replay(b).ideas.e4),'withdrawn');
});
test('copying an earlier version verbatim is not a revision; changing scope is',()=>{
  let b=active();b=M.append(b,'challenge',mark('e4','counter'));b=M.append(b,'withdraw',quit('变更范围'));
  assert.throws(()=>M.append(b,'idea',{...idea,notes:['e2'],previous:'e4',text:' '+idea.text+' '}),/修订/);
  const ok=M.append(b,'idea',{...idea,notes:['e2'],previous:'e4',scope:'只限纸笔确认无误时'});assert.equal(M.status(M.replay(ok).ideas[ok.events.at(-1).id]),'candidate');
});
