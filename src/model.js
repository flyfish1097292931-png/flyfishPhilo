/* The portable notebook. No filesystem, network, clock or model dependency. */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.FlyfishPhilo = api;
})(globalThis, function () {
  'use strict';
  const FORMAT = 'flyfishPhilo/1';
  const LIMITS = Object.freeze({events:2000, bytes:2097152, text:6000, refs:32});
  // One small closing entry: up to 256 UTF-16 units, even if JSON escapes each
  // one as six bytes, plus room for pretty-printing, IDs and fixed fields.
  const CLOSING_BYTES=256*6+320;
  const ideaKeys='question kind text scope why rival test notes previous seed';
  const fields = {question:'text', reword:'question text', rest:'question', resume:'question',
    note:'question origin source text', seed:'question text', idea:ideaKeys, suggest:ideaKeys+' base',
    challenge:'idea note verdict detail', adopt:'idea review reason consent', withdraw:'idea reason consent',
    trial:'idea step', link:'from to relation why'};
  const oneOf=(x,list)=>need(list.includes(x),'没有这个类型或状态');
  function status(i) { return i.withdrawn?'withdrawn':i.checks.some(c=>c.verdict==='counter')?'challenged':i.adopted?'adopted':'candidate'; }
  function need(ok, message) { if (!ok) throw new Error(message); }
  function record(x) { return x !== null && typeof x === 'object' && !Array.isArray(x) && [Object.prototype,null].includes(Object.getPrototypeOf(x)); }
  function exact(x, names) {
    need(record(x) && Object.keys(x).length === names.length && names.every(k => Object.hasOwn(x,k)), '字段缺失或含有未定义的权限/字段');
  }
  function text(x) { need(typeof x === 'string' && x.trim() && x.length <= LIMITS.text, '请填写有效的文字（每项不超过 6000 个 UTF-16 单元）'); }
  function ref(map, id, what) { need(typeof id === 'string' && Object.hasOwn(map,id), `没有可引用的${what}：${String(id)}`); return map[id]; }
  function openQ(s, id) { const q = ref(s.questions,id,'问题'); need(!q.paused,'问题已悬置，请先重开'); return q; }
  const blank = () => ({format:FORMAT,events:[]});
  function step(s,e) {
    const {type,id} = e;
    switch (type) {
      case 'question': text(e.text); s.questions[id] = {id,text:e.text,wording:[e.text],paused:false}; break;
      case 'reword': { const q=openQ(s,e.question); text(e.text); need(e.text !== q.text,'措辞未改变'); q.text=e.text; q.wording.push(e.text); break; }
      case 'rest': openQ(s,e.question).paused=true; break;
      case 'resume': { const q=ref(s.questions,e.question,'问题'); need(q.paused,'问题尚未悬置'); q.paused=false; break; }
      case 'note': {
        if(e.question!==null) ref(s.questions,e.question,'问题');
        oneOf(e.origin,['firsthand','excerpt','retelling','synthetic','ai']); text(e.source); text(e.text);
        s.notes[id]={...e}; break;
      }
      case 'seed': openQ(s,e.question); text(e.text); s.seeds[id]={...e}; break;
      case 'idea': case 'suggest': {
        openQ(s,e.question); oneOf(e.kind,['reading','claim','practice']);
        [e.text,e.scope,e.why,e.rival,e.test].forEach(text);
        need(Array.isArray(e.notes) && e.notes.length>0 && e.notes.length<=LIMITS.refs && new Set(e.notes).size===e.notes.length,'请引用一至三十二个不同的材料');
        for(const n of e.notes) ref(s.notes,n,'材料'); // iteration sees sparse slots
        if(e.previous!==null) {
          const p=ref(s.ideas,e.previous,'前稿'); need(p.question===e.question && p.kind===e.kind,'修订须属同一问题和类型');
          const norm=t=>t.trim().replace(/\s+/g,' ');
          const changed=['text','scope','why','rival','test'].some(k=>norm(p[k])!==norm(e[k]));
          need(changed || p.notes.length!==e.notes.length || e.notes.some(n=>!p.notes.includes(n)),'修订须改变论证、适用范围或引用的材料');
        }
        if(e.seed!==null) need(ref(s.seeds,e.seed,'念头').question===e.question,'念头须属于同一问题');
        if(type==='suggest') {
          need(typeof e.base==='string' && /^[0-9a-f]{64}$/.test(e.base),'无效的资料包摘要');
          need(e.seed===null && e.previous===null,'AI 提案不可改写旧稿');
        }
        s.ideas[id]={...e,notes:[...e.notes],origin:type==='suggest'?'ai':'human',checks:[],adopted:false,withdrawn:false,
          family:e.previous?s.ideas[e.previous].family:id}; break;
      }
      case 'challenge': {
        const idea=ref(s.ideas,e.idea,'候选'); const q=ref(s.questions,idea.question,'问题');
        need(!q.paused || (idea.adopted && e.verdict==='counter'),'问题已悬置；只允许阻断已有采纳的反例或撤回'); ref(s.notes,e.note,'材料');
        oneOf(e.verdict,['counter','limit','open','survives']); text(e.detail); idea.checks.push({...e}); break;
      }
      case 'adopt': {
        const idea=ref(s.ideas,e.idea,'候选'); openQ(s,idea.question);
        need(e.consent===true,'须经本人明确同意'); text(e.reason); text(e.review);
        need(idea.kind!=='reading','解释本身不授予立场或行动权限');
        need(!idea.adopted && !idea.withdrawn,'本稿已经采纳或撤回；如需重开，请建修订稿');
        need(!idea.checks.some(c=>c.verdict==='counter'),'此稿仍有反例，请先修订');
        need(idea.checks.some(c=>c.verdict==='limit'||c.verdict==='survives'),'采纳前请记录一次有材料的反向检验');
        need(!Object.values(s.ideas).some(i=>i.adopted && i.family===idea.family),'同一修订链已有生效稿，请先明确撤回');
        idea.adopted=true; idea.approval={...e}; break;
      }
      case 'withdraw': {
        const idea=ref(s.ideas,e.idea,'候选'); need(e.consent===true,'须经本人明确同意'); text(e.reason);
        need(idea.adopted,'只能撤回曾采纳且尚未撤回的版本'); idea.adopted=false; idea.withdrawn=true; idea.withdrawal={...e}; break;
      }
      case 'trial': {
        const idea=ref(s.ideas,e.idea,'候选'); openQ(s,idea.question); text(e.step);
        need(idea.kind==='practice' && status(idea)==='adopted','只能试行本人已采纳且未被反例阻断的实践');
        s.trials.push({...e}); break;
      }
      case 'link': {
        const a=ref(s.ideas,e.from,'想法'), b=ref(s.ideas,e.to,'想法'); openQ(s,a.question); openQ(s,b.question);
        need(a!==b,'不能连接自身'); oneOf(e.relation,['supports','tensions','requires','distinguishes']); text(e.why);
        need(!s.links.some(l=>l.from===e.from && l.to===e.to && l.relation===e.relation),'已有相同方向和类型的连线');
        s.links.push({...e}); break;
      }
    }
  }
  function replay(book) {
    exact(book,['format','events']); need(book.format===FORMAT,'不支持的手记格式或版本');
    need(Array.isArray(book.events) && book.events.length<=LIMITS.events,'手记事件数超过上限或格式不正确');
    const bytes=new TextEncoder().encode(JSON.stringify(book,null,2)).length;
    need(bytes<=LIMITS.bytes,'手记过大，请另开一本');
    const s = {questions:{},notes:{},seeds:{},ideas:{},links:[],trials:[]};
    for (const [i,e] of book.events.entries()) {
      try {
        need(record(e) && typeof e.type==='string' && Object.hasOwn(fields,e.type),'不支持的操作');
        exact(e,['id','type',...fields[e.type].split(' ')]);
        need(e.id === `e${i+1}`,'事件标识或顺序无效'); step(s,e);
      } catch (err) { throw new Error(`第 ${i+1} 条：${err.message}`); }
    }
    // An adopted version always has room to withdraw; an unchallenged one also
    // has room for a counterexample tied to a previously recorded note.
    const reserved=Object.values(s.ideas).reduce((n,i)=>n+(!i.adopted?0:status(i)==='challenged'?1:2),0);
    need(book.events.length+reserved<=LIMITS.events && bytes+reserved*CLOSING_BYTES<=LIMITS.bytes,'需要为已采纳稿的反例与撤回预留空间；请缩短本次记录或另开手记');
    return s;
  }
  function append(book,type,data) {
    need(typeof type==='string' && Object.hasOwn(fields,type),'不支持的操作'); exact(data,fields[type].split(' '));
    exact(book,['format','events']); need(Array.isArray(book.events),'需要事件列表');
    const next = {format:book.format,events:[...book.events,{...data,id:`e${book.events.length+1}`,type}]};
    replay(next); return structuredClone(next);
  }
  function markdown(book) {
    const s=replay(book), rows=['# flyfishPhilo · 我的思想手记','','这是整本私有阅读稿，包含未采纳材料。可恢复的原件是 JSON；本人采纳不等于命题为真。',''];
    const show=v=>String(v).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replace(/([\\`*_\[\]()!#|~])/g,'\\$1').replace(/[\r\n]+/g,' ↵ ');
    const out=(...a)=>rows.push(...a);
    const items=Object.values(s.ideas), issues=Object.values(s.questions);
    const names={firsthand:'亲历',excerpt:'摘录',retelling:'转述',synthetic:'虚构',ai:'AI 解释',reading:'解释',claim:'命题',practice:'实践',candidate:'候选',adopted:'当前采纳',challenged:'反例阻断',withdrawn:'已撤回',counter:'反例',limit:'限制适用域',open:'未决',survives:'本次检验未推翻',supports:'支持',tensions:'有张力',requires:'以前者所指向的区分为前提',distinguishes:'区分'};
    out('## 当前内核 · 我现在采用什么','');
    const active=items.filter(i=>status(i)==='adopted');
    for(const i of active) out(`- ${i.id}（${names[i.kind]}）${show(i.text)}；范围：${show(i.scope)}`);
    if(!active.length) out('尚无采纳。留空是合法结果。');
    out('','## 深层记忆 · 材料及出处','');
    for(const n of Object.values(s.notes)) out(`- ${n.id} · ${names[n.origin]} · ${show(n.source)}：${show(n.text)}`);
    out('','## 未坍缩区 · 问题与未成形的念头','');
    for(const q of issues){out(`- ${q.id}［${q.paused?'已悬置':'开放'}］${show(q.text)}`); if(q.wording.length>1) out(`  - 问法的变化：${q.wording.map(show).join(' → ')}`);}
    for(const seed of Object.values(s.seeds)) out(`- ${seed.id} → ${seed.question}：${show(seed.text)}`);
    out('','## 论证与修订 · 为什么改口','');
    for(const i of items){
      out(`### ${i.id} · ${names[i.kind]} · ${names[status(i)]}`,`${show(i.text)}`,'',`- 问题：${i.question}；材料：${i.notes.join('、')}；来源：${i.origin==='ai'?'AI 提案':'作者录入'}${i.previous?'；修订自 '+i.previous:''}${i.seed?'；源于念头 '+i.seed:''}`,`- 适用范围：${show(i.scope)}`,`- 理由：${show(i.why)}`,`- 竞争解释：${show(i.rival)}`,`- 怎样区分：${show(i.test)}`);
      for(const c of i.checks) out(`- 检验 ${c.id}（${names[c.verdict]}，材料 ${c.note}）：${show(c.detail)}`);
      if(i.approval) out(`- 采纳理由：${show(i.approval.reason)}；冲突审查：${show(i.approval.review)}`);
      if(i.withdrawal) out(`- 撤回：${show(i.withdrawal.reason)}`); out('');
    }
    for(const l of s.links) out(`- ${l.from} → ${l.to}（${names[l.relation]}）：${show(l.why)}`);
    out('','## 执行层 · 本人登记的试行','');
    if(!s.trials.length) out('没有试行。工作台不会执行外部操作。');
    for(const t of s.trials) out(`- ${t.id} → ${t.idea}：${show(t.step)}`);
    return rows.join('\n')+'\n';
  }
  return {FORMAT,LIMITS,blank,append,replay,status,markdown};
});
