;(() => {
  'use strict';

  const core = globalThis.FlyfishPhilo;
  const $ = id => document.getElementById(id);
  const values = Object.values;
  const ORIGIN = { firsthand: '亲历', excerpt: '摘录', retelling: '转述', synthetic: '合成材料', ai: 'AI 的解释' };
  const KIND = { reading: '解释', claim: '主张', practice: '实践' };
  const VERDICT = { counter: '构成反例', limit: '需要收窄边界', open: '暂不能判断', survives: '本次检验仍成立' };
  const STATUS = { candidate: '候选 · 未采纳', adopted: '已采纳', challenged: '遇到反例', withdrawn: '已撤回' };
  const RELATION = { supports: '支持', tensions: '与之有张力', requires: '以其为前提', distinguishes: '有别于' };
  const desk = $('desk'), sheet = $('sheet'), sheetBody = $('sheet-body'), guard = $('guard');
  let book, view, selected = null, pane = 'material', expandedIdea = null, handoff = null;
  let demo = false, edited = false, requestedBackup = false, sheetDirty = false;
  let sheetSession = 0, fieldSerial = 0, noticeTimer = 0, guardingUnload = false;

  function el(tag, cls = '', text) {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined && text !== null) n.textContent = text;
    return n;
  }
  function box(cls, ...children) { const n = el('div', cls); n.append(...children); return n; }
  function btn(label, action, cls = '') {
    const n = el('button', `btn ${cls}`.trim(), label);
    n.type = 'button'; n.addEventListener('click', action); return n;
  }
  function submitBtn(label, cls = 'primary') { const n = el('button', `btn ${cls}`, label); n.type = 'submit'; return n; }
  const p = (text, cls = '') => el('p', cls, text);
  const tag = (text, tone = '') => el('span', `tag ${tone}`.trim(), text);
  const idLabel = id => el('span', 'id', id);
  const compact = (s, n = 48) => s.length > n ? s.slice(0, n) + '…' : s;
  const originTag = n => tag(ORIGIN[n.origin], ['ai', 'synthetic'].includes(n.origin) ? 'rust' : 'neutral');
  const firstNew = (next, prev) => Object.keys(next).find(k => !Object.hasOwn(prev, k));
  const scopeName = qid => qid === null ? '未归题' : view.questions[qid].text;
  function uid() { return 'field-' + (++fieldSerial); }
  function focusOn(id) { const node = $(id); if (node) node.focus(); }
  function kindRev(i) { return `${KIND[i.kind]} · 第 ${revision(i)} 版 · ${i.id}`; }
  function revision(i) {
    let depth = 1;
    for (let prev = i.previous; prev && view.ideas[prev]; prev = view.ideas[prev].previous) depth++;
    return depth;
  }
  function field(name, label, opts = {}) {
    const wrap = el('div', 'field'), lab = el('label', '', label);
    // Clone a native declarative control; keep author styles in the hashed sheet.
    const control = opts.choices ? $('choice-control').content.firstElementChild.cloneNode(true) : el(opts.type === 'text' ? 'input' : 'textarea');
    control.id = uid(); control.name = name; lab.htmlFor = control.id;
    if (control.tagName === 'TEXTAREA') control.rows = opts.rows || 2;
    if (control.tagName === 'INPUT') control.type = 'text';
    if (opts.choices) for (const [value, text] of opts.choices) {
      const option = el('option', '', text); option.value = value; control.append(option);
    }
    if (opts.value !== undefined && opts.value !== null) control.value = opts.value;
    if (opts.placeholder) control.placeholder = opts.placeholder;
    control.required = opts.required !== false; control.readOnly = !!opts.readOnly;
    wrap.append(lab, control);
    if (opts.hint) {
      const h = p(opts.hint, 'field-note'); h.id = uid(); control.setAttribute('aria-describedby', h.id); wrap.append(h);
    }
    return wrap;
  }
  function check(name, value, text, checked = false, required = false) {
    const row = el('label', 'check'), c = el('input'); c.type = 'checkbox'; c.name = name;
    c.id = uid(); row.htmlFor = c.id; c.value = value; c.checked = checked; c.required = required;
    row.append(c, el('span', '', text)); return row;
  }
  function group(label, elements) {
    const f = el('fieldset'), list = box('checkbox-list', ...elements);
    f.append(el('legend', '', label), list); return f;
  }
  function fold(label, ...content) {
    const d = el('details', 'fold'); d.append(el('summary', '', label), ...content); return d;
  }
  function notice(text) {
    clearTimeout(noticeTimer); $('notice').textContent = text;
    noticeTimer = setTimeout(() => { $('notice').textContent = ''; }, 5400);
  }
  function clearError() { $('sheet-error').hidden = true; $('sheet-error').textContent = ''; }
  function fail(err) {
    const msg = err instanceof Error ? err.message : String(err);
    if (!sheet.open) { notice(msg); return; }
    const n = $('sheet-error'); n.hidden = false; n.textContent = msg; n.focus();
  }
  function welcomeTyped() { const t = $('first-question'); return !!(t && t.value.length); }
  function beforeUnload(e) { e.preventDefault(); e.returnValue = ''; }
  function syncUnload() {
    const risk = edited || sheetDirty || welcomeTyped();
    if (risk === guardingUnload) return;
    if (risk) window.addEventListener('beforeunload', beforeUnload);
    else window.removeEventListener('beforeunload', beforeUnload);
    guardingUnload = risk;
  }
  function updateMast() {
    $('file-menu').hidden = !book.events.length;
    $('book-state').textContent = requestedBackup ? '已请求下载 JSON' : edited ? '本页有未备份改动' : '仅在本页';
    syncUnload();
  }
  function openSheet(title, ...body) {
    ++sheetSession; sheetDirty = false; clearError(); $('sheet-title').textContent = title;
    sheetBody.replaceChildren(...body); if (!sheet.open) sheet.showModal(); sheet.scrollTop = 0;
    syncUnload(); return sheetSession;
  }
  function endSheet() {
    ++sheetSession; sheetDirty = false; if (sheet.open) sheet.close(); sheetBody.replaceChildren(); clearError(); syncUnload();
  }
  function currentSession(n) { return sheet.open && sheetSession === n; }
  function dirtyForm(f) {
    const dirty = e => { if (!e.target.readOnly) { sheetDirty = true; syncUnload(); } };
    f.addEventListener('input', dirty); f.addEventListener('change', dirty);
  }
  function ask(title, text, yes, action, backup = false) {
    if (guard.open) return;
    $('guard-title').textContent = title; $('guard-text').textContent = text;
    const no = btn('取消，保留原稿', () => guard.close());
    const buttons = [no]; if (backup) buttons.push(btn('先下载当前 JSON', () => {
      try { downloadBook(); } catch (err) { $('guard-text').textContent = '下载未能开始：' + err.message; }
    }));
    buttons.push(btn(yes, () => { guard.close(); action(); }, 'warn'));
    $('guard-actions').replaceChildren(...buttons); guard.showModal(); no.focus();
  }
  function closeSheet() {
    if (sheetDirty) ask('放弃尚未记入的文字？', '这里的输入还没有写入手记。取消可回去继续写。', '放弃此次输入', endSheet);
    else endSheet();
  }
  function render(focusId) {
    desk.replaceChildren(book.events.length ? workspace() : welcome()); updateMast();
    if (focusId) focusOn(focusId);
  }
  function choose(qid, section = 'material', which = null) {
    selected = qid; pane = section; expandedIdea = which;
    render(which ? 'summary-' + which : 'current-question');
  }
  function place(next, v, type, data) {
    const old = view;
    handoff = type === 'suggest' && handoff && handoff.book === book ? {...handoff,book:next} : null;
    book = next; view = v; edited = true; requestedBackup = false;
    let focusId = 'panel-title';
    if (type === 'question') { selected = firstNew(v.questions, old.questions); pane = 'material'; focusId = 'current-question'; }
    if (type === 'note' || type === 'seed') {
      selected = data.question; pane = 'material'; const group = type === 'note' ? 'notes' : 'seeds';
      focusId = 'entry-' + firstNew(v[group], old[group]);
    }
    if (type === 'idea' || type === 'suggest') {
      expandedIdea = firstNew(v.ideas, old.ideas); selected = v.ideas[expandedIdea].question;
      pane = 'ideas'; focusId = 'summary-' + expandedIdea;
    }
    if (['challenge', 'adopt', 'withdraw', 'trial'].includes(type)) {
      expandedIdea = data.idea; selected = v.ideas[data.idea].question; pane = 'ideas'; focusId = 'summary-' + data.idea;
    }
    if (['reword', 'rest', 'resume'].includes(type)) focusId = 'current-question';
    if (type === 'link') { selected = v.ideas[data.from].question; pane = 'links'; }
    endSheet(); render(focusId);
  }
  function commit(type, data, message) {
    try {
      const next = core.append(book, type, data), projected = core.replay(next);
      place(next, projected, type, data); notice(message); return true;
    } catch (err) { fail(err); return false; }
  }
  function form(handler, track = true) {
    const f = el('form', 'editor'); f.autocomplete = 'off';
    f.addEventListener('submit', e => {
      e.preventDefault(); clearError();
      try { handler(new FormData(f), f); } catch (err) { fail(err); }
    });
    if (track) dirtyForm(f); return f;
  }
  function editor(title, desc, fields, label, handler) {
    const f = form(handler); if (desc) f.append(p(desc, 'helper'));
    f.append(...fields, box('actions', submitBtn(label), btn('取消', closeSheet)));
    openSheet(title, f); const first = f.querySelector('textarea, input, select'); if (first) first.focus();
  }
  function sectionTitle(text, actions = []) {
    const heading = el('h2', '', text); heading.id = 'panel-title'; heading.tabIndex = -1;
    return box('section-head', heading, box('actions', ...actions));
  }
  function welcome() {
    const area = el('div', 'welcome'), left = el('section', 'welcome-main');
    const label = el('label', '', '你的第一个问题'); label.htmlFor = 'first-question';
    const q = el('textarea'); q.id = 'first-question'; q.name = 'text'; q.required = true; q.rows = 2;
    q.placeholder = '写下此刻还没有想通的一件事……'; q.addEventListener('input', syncUnload);
    const f = form(fd => commit('question', {text: fd.get('text')}, '问题已记入本页。'), false); f.className = 'start-form';
    f.append(label, q, box('actions', submitBtn('开始手记'), btn('体验虚构读书会', loadDemo, 'text small'), btn('导入 JSON', () => fileSheet(true), 'text small')));
    left.append(p('自我蒸馏与哲学建构', 'eyebrow'), el('h1', '', '从一个问题开始。'),
      p('先记下发生了什么，再问它意味着什么。判断可以修订，也可以一直悬而未决。', 'lead'), f,
      p('文字只在本页内存中。关闭或刷新前，请下载完整 JSON；只有它能恢复手记。', 'helper privacy'));
    const sample = el('aside', 'specimen'); sample.setAttribute('aria-label', '虚构读书会示例');
    sample.append(p('示例手记 ／ 虚构读书会', 'eyebrow'), el('blockquote', '', '我不喜欢讨论，还是不喜欢被点名？'),
      el('span', 'revision-mark', '由此继续追问'), el('blockquote', '', '名义上可以拒绝，就有拒绝的自由吗？'));
    area.append(left, sample); return area;
  }
  function workspace() {
    const qs = values(view.questions), q = selected ? view.questions[selected] : null;
    const nav = el('nav', 'index'); nav.setAttribute('aria-label','问题目录');
    const index = el('details'); index.open = !window.matchMedia('(max-width: 48rem)').matches;
    const list = el('div', 'index-list');
    function addNav(id, title, state) {
      const n = btn('', () => choose(id)); n.className = 'nav-item';
      if (id === selected) n.setAttribute('aria-current','page');
      n.append(el('span','',compact(title, 60)), el('span','micro',state)); list.append(n);
    }
    qs.forEach((x, n) => addNav(x.id, x.text, `${String(n + 1).padStart(2, '0')} · ${x.paused ? '已悬置' : '追问中'}`));
    const loose = values(view.notes).filter(n => n.question === null);
    addNav(null, '未归题片段', `${loose.length} 条片段`);
    index.append(el('summary','',`问题目录（${qs.length}）`), list);
    nav.append(index, box('index-foot', btn('新建问题', newQuestion, 'small'), btn('下载完整 JSON', downloadBookSafe, 'text small')));
    const page = el('section', 'question-page');
    if (demo) page.append(p('虚构读书会示例：情境与示例中的决定均为演示，不代表你的立场。', 'hint sample-note'));
    const head = el('header','question-head'), meta = box('question-meta');
    meta.append(el('span','eyebrow', q ? `问题 ${String(qs.findIndex(x => x.id === selected) + 1).padStart(2,'0')} ／ ${q.paused ? '已悬置' : '追问中'}` : '片段收件处'));
    if (q) meta.append(btn('与任意 AI 协作', () => aiSheet(q), 'small'));
    const title = el('h1','',q ? q.text : '未归题片段'); title.id = 'current-question'; title.tabIndex = -1;
    head.append(meta, title);
    if (q) {
      const actions = box('actions');
      if (!q.paused) actions.append(btn('改写问题', () => reword(q), 'small text'));
      actions.append(btn(q.paused ? '重开问题' : '悬置问题', () => commit(q.paused ? 'resume' : 'rest', {question:q.id}, q.paused ? '已重新打开。' : '问题已悬置，旧记录仍在。'), 'small text'));
      head.append(actions);
      const versions = q.wording.slice(); if (versions[versions.length - 1] !== q.text) versions.push(q.text);
      if (versions.length > 1) {
        const history = el('details','history'), ol = el('ol'); versions.forEach(s => ol.append(el('li','body-text',s)));
        history.append(el('summary','',`问法沿革（${versions.length} 稿）`), ol); head.append(history);
      }
      if (q.paused) head.append(p('这个问题已悬置。仍可记片段、用反例阻断已采纳稿或撤回采纳。要继续起草，请先重开。','hint'));
    } else head.append(p('暂时不知属于哪个问题的片段，可以先放在这里，起草时仍可引用。','helper'));
    page.append(head);
    if (q) {
      const tabs = el('nav','tabbar'); tabs.setAttribute('aria-label','问题工作区');
      for (const [key, name] of [['material','手边材料'],['ideas','候选观点'],['links','观点连线']]) {
        const tab = btn(name, () => { pane = key; render('panel-title'); }); tab.className = 'tab';
        tab.setAttribute('aria-pressed',String(pane === key)); tabs.append(tab);
      }
      page.append(tabs);
    }
    page.append(pane === 'ideas' && q ? ideasPanel(q) : pane === 'links' && q ? linksPanel(q) : materialPanel(q));
    return box('workspace', nav, page);
  }
  function materialPanel(q) {
    const qid = q ? q.id : null, panel = el('section'), writable = !q || !q.paused;
    const actions = [btn('记片段', () => newNote(qid), 'primary small')];
    if (q && writable) actions.push(btn('保留念头', () => newSeed(q), 'small'));
    panel.append(sectionTitle(q ? '手边材料' : '片段', actions));
    const notes = values(view.notes).filter(n => n.question === qid).reverse();
    if (q) panel.append(el('h3','group-title',`片段 · ${notes.length}`));
    if (!notes.length) panel.append(p('还没有片段。先记一句原话或一件具体的事，再写明它从哪里来。','empty'));
    for (const n of notes) {
      const r = el('article','record'); r.id = 'entry-' + n.id; r.tabIndex = -1;
      const meta = box('meta-row', idLabel(n.id), originTag(n));
      if (n.origin === 'ai') meta.append(el('span','micro','待审解释，非亲历'));
      r.append(meta, p(n.text,'entry-text'), p(`出处：${n.source}`,'source body-text')); panel.append(r);
    }
    if (q) {
      const canCite = noteChoices(qid).length > 0, seeds = values(view.seeds).filter(s => s.question === qid).reverse();
      panel.append(el('h3','group-title',`念头 · ${seeds.length}`));
      if (!seeds.length) panel.append(p('猜想不必马上变成观点，可以先留在这里。','empty'));
      for (const s of seeds) {
        const r = el('article','record'); r.id = 'entry-' + s.id; r.tabIndex = -1;
        r.append(box('meta-row', idLabel(s.id), tag('尚未成论','neutral')), p(s.text,'entry-text'));
        if (writable && canCite) r.append(box('actions', btn('从这个念头起草', () => ideaEditor(q, null, s.id), 'small text')));
        panel.append(r);
      }
      if (writable && canCite) panel.append(box('actions',btn('形成候选观点', () => ideaEditor(q), 'text')));
    }
    return panel;
  }
  function citation(note) {
    const c = el('blockquote','citation'); c.append(box('meta-row',idLabel(note.id),originTag(note)),p(note.text,'body-text'),p(`出处：${note.source}`,'source body-text')); return c;
  }
  function facts(entries) {
    const dl = el('dl','fact-list'); for (const [label, text] of entries) dl.append(el('dt','',label),el('dd','',text)); return dl;
  }
  function goIdea(id) { const i = view.ideas[id]; choose(i.question, 'ideas', id); }
  function ideaJump(id) { const i = view.ideas[id]; return btn(`${kindRev(i)}：${compact(i.text, 36)}`, () => goIdea(id), 'small text'); }
  function relationCard(l) {
    const r = el('article','record'); r.append(box('meta-row',idLabel(l.id),tag('有向连线','neutral')),
      box('relation-line',ideaJump(l.from),el('strong','',`→ ${RELATION[l.relation]} →`),ideaJump(l.to)),p('理由：' + l.why,'entry-text')); return r;
  }
  function familyOf(i) { if (i.family) return i.family; while (i.previous) i = view.ideas[i.previous]; return i.id; }
  function otherAdopted(i) { const family = familyOf(i); return values(view.ideas).find(n=>n.id !== i.id && n.adopted && !n.withdrawn && familyOf(n) === family); }
  function allowAdopt(i) { return !i.adopted && !i.withdrawn && i.kind !== 'reading' && i.checks.some(c=>c.verdict === 'limit' || c.verdict === 'survives') && !i.checks.some(c=>c.verdict === 'counter') && !otherAdopted(i); }
  function allowTrial(i) { return i.kind === 'practice' && i.adopted && !i.withdrawn && core.status(i) === 'adopted' && !i.checks.some(c=>c.verdict === 'counter'); }
  function ideaDetail(i, q) {
    const d = el('details','idea'), summary = el('summary'); summary.id = 'summary-' + i.id; d.open = expandedIdea === i.id;
    const st = core.status(i);
    summary.append(box('meta-row',idLabel(i.id),tag(`${KIND[i.kind]} · 第 ${revision(i)} 版`,'neutral'),
      tag(STATUS[st], st === 'withdrawn' || st === 'challenged' ? 'rust' : ''),tag(i.origin === 'ai' ? 'AI 提案' : '人工起草', i.origin === 'ai' ? 'rust' : 'neutral')),
      el('span','idea-title',i.text));
    d.append(summary);
    function unfold() {
      if (d.childElementCount === 1) d.append(ideaBody(i,q));
    }
    if (d.open) unfold();
    d.addEventListener('toggle',()=>{ if (d.open && d.isConnected) { expandedIdea = i.id; unfold(); } });
    return d;
  }
  function ideaBody(i,q) {
    const detail = el('div','idea-content');
    detail.append(facts([['适用边界',i.scope], ['理由',i.why], ['另一种解释',i.rival], ['怎样检验',i.test]]));
    if (i.seed) detail.append(p(`起草自念头 ${i.seed}：${view.seeds[i.seed].text}`, 'helper body-text'));
    if (i.previous) detail.append(box('relation-line',el('span','micro','上一版'),ideaJump(i.previous)));
    const later = values(view.ideas).filter(x=>x.previous === i.id);
    if (later.length) detail.append(box('relation-line',el('span','micro','后续修订'),...later.map(x=>ideaJump(x.id))));
    detail.append(el('h3','',`引用片段 · ${i.notes.length}`)); i.notes.forEach(id => detail.append(citation(view.notes[id])));
    detail.append(el('h3','',`检验与反例 · ${i.checks.length}`));
    for (const c of i.checks) {
      const r = el('div','record'); r.append(box('meta-row',idLabel(c.id),tag(VERDICT[c.verdict],c.verdict === 'counter' ? 'rust' : 'neutral')), p(c.detail,'entry-text'),citation(view.notes[c.note])); detail.append(r);
    }
    const decisions = book.events.filter(e => (e.type === 'adopt' || e.type === 'withdraw') && (e.data || e).idea === i.id);
    if (decisions.length) detail.append(el('h3','','本人决定的记录'));
    for (const e of decisions) {
      const data = e.data || e;
      detail.append(facts(e.type === 'adopt' ? [['冲突审查',data.review],['采纳理由',data.reason]] : [['撤回理由',data.reason]]));
    }
    const trials = view.trials.filter(t=>t.idea === i.id);
    if (trials.length) { detail.append(el('h3','','试行记录')); trials.forEach(t=>detail.append(p(`${t.id} · ${t.step}`,'body-text'))); }
    const links = view.links.filter(l=>l.from === i.id || l.to === i.id);
    if (links.length) detail.append(fold(`相关连线（${links.length}）`,...links.map(relationCard)));
    const other = otherAdopted(i);
    const explanation = i.withdrawn ? '本版已撤回，旧决定仍可追溯。' : i.kind === 'reading' ? '解释可保留、对照或修订，不能直接采纳为立场。' :
      i.checks.some(c=>c.verdict === 'counter') ? '本版遇到反例，不能据此采纳或试行。可以另写修订版。' :
      other ? `同一修订链已有采纳记录（${other.id}）。只有本人明确撤回旧版后，才可采纳本版。` :
      !i.checks.some(c=>c.verdict !== 'open') ? '采纳前须留下至少一条有结论的检验。待定不算检验通过。' : i.adopted ? '本版有明确的采纳记录；可以随时撤回。' : '可以考虑采纳，也可以继续保留为候选。';
    detail.append(p(explanation,'hint'));
    if (other && !i.withdrawn) detail.append(box('relation-line',el('span','micro','同链已采纳版'),ideaJump(other.id)));
    if (!q.paused || (i.adopted && !i.withdrawn)) {
      const a = box('actions');
      if (!q.paused && !i.withdrawn) a.append(btn('添加检验', () => challengeEditor(i),'small'));
      if (q.paused && core.status(i) === 'adopted') a.append(btn('登记反例', () => challengeEditor(i,true),'small'));
      if (!q.paused) a.append(btn('修订为新版本', () => ideaEditor(q, i),'small'));
      if (!q.paused && allowAdopt(i)) a.append(btn('本人采纳', () => adoptEditor(i),'primary small'));
      if (i.adopted && !i.withdrawn) a.append(btn('本人撤回', () => withdrawEditor(i),'warn small'));
      if (!q.paused && allowTrial(i)) a.append(btn('记录试行', () => trialEditor(i),'small')); detail.append(a);
    }
    return detail;
  }
  function ideasPanel(q) {
    const list = values(view.ideas).filter(i=>i.question === q.id).reverse(), panel = el('section');
    const canStart = noteChoices(q.id).length > 0;
    panel.append(sectionTitle('候选观点', q.paused ? [] : [canStart ? btn('形成候选观点', () => ideaEditor(q),'primary small') : btn('先记片段', () => newNote(q.id),'primary small')]),
      p('解释、主张与实践都从候选开始。展开一版，查看出处、检验、修订和决定。','section-intro'));
    if (list.length) panel.append(box('idea-list',...list.map(i=>ideaDetail(i,q))));
    else panel.append(p(canStart ? '还没有候选。挑一条片段，写出自己的说法和它的边界。' : '还没有可引用的片段。先记材料，不必着急下结论。','empty'));
    return panel;
  }
  function linksPanel(q) {
    const list = view.links.filter(l=>view.ideas[l.from].question === q.id || view.ideas[l.to].question === q.id);
    const eligible = values(view.ideas).filter(i=>!view.questions[i.question].paused).length > 1 && values(view.ideas).some(i=>i.question === q.id);
    const panel = el('section'); panel.append(sectionTitle('观点连线', eligible && !q.paused ? [btn('连接两个观点', () => linkEditor(q), 'primary small')] : []),
      p('把一个观点与另一个并排，写清楚谁支持谁、谁依赖谁，以及为什么。可以跨问题连线。','section-intro'));
    if (!list.length) panel.append(p(eligible ? '还没有与这个问题相关的连线。' : '需要两个不同的观点，且它们所属的问题均未悬置；其中一个须属于当前问题。','empty'));
    list.forEach(l=>panel.append(relationCard(l))); return panel;
  }

  function newQuestion() {
    editor('新建问题', '另开一页，不改变已有的问题和材料。', [field('text','新的问题')], '记入问题',
      fd => commit('question',{text:fd.get('text')},'新问题已记入本页。'));
  }
  function reword(q) {
    editor('改写问题', '旧问法仍留在沿革中，已有材料不移动。', [field('text','新的问法',{value:q.text})], '保留两种问法',
      fd => commit('reword',{question:q.id,text:fd.get('text')},'新问法已记入沿革。'));
  }
  function noteChoices(qid) {
    const notes = values(view.notes).reverse();
    return [...notes.filter(n=>n.question === qid), ...notes.filter(n=>n.question === null && qid !== null), ...notes.filter(n=>n.question !== null && n.question !== qid)];
  }
  function noteName(n) { const origin = n.question === selected ? '' : `${compact(scopeName(n.question),18)} ／ `; return `${n.id} · ${origin}${ORIGIN[n.origin]} · ${compact(n.source,24)}：${compact(n.text,72)}`; }
  function newNote(qid) {
    const qs = values(view.questions), destinations = [['','未归题片段'],...qs.map(q=>[q.id,compact(q.text,60) + (q.paused ? '（已悬置）' : '')])];
    editor('记片段', '把亲历、摘录和别人说的话分开。虚构或模拟场景请标为合成材料。', [
      box('field-pair', field('question','归在哪个问题下',{choices:destinations,value:qid || '',required:false}),
        field('origin','材料性质',{choices:[['','请选择性质'],...Object.entries(ORIGIN)]})),
      field('source','出处',{type:'text',placeholder:'例如：我在周三读书会的记录，或书名与页码'}), field('text','片段原文或记录',{rows:4})
    ], '记入片段', fd=>commit('note',{question:fd.get('question') || null,origin:fd.get('origin'),source:fd.get('source'),text:fd.get('text')},'片段和出处已记入。'));
  }
  function newSeed(q) {
    editor('保留念头', '它可以暂时没有足够的理由，不必装成肯定句。', [field('text','这个念头',{rows:3})], '记下念头',
      fd=>commit('seed',{question:q.id,text:fd.get('text')},'念头已保留，还不是立场。'));
  }
  function ideaEditor(q, prev = null, seedId = null) {
    const notes = noteChoices(q.id);
    if (!notes.length) { notice('先记一条有出处的片段，再起草候选。'); return; }
    const seeds = values(view.seeds).filter(s=>s.question === q.id);
    const fromSeed = seedId || (prev && prev.seed) || '';
    const fields = [prev ? p(`沿用 ${kindRev(prev)} 的种类；旧版及其检验、采纳记录不变。`,'hint') :
      field('kind','候选种类',{choices:[['','请选择种类'],['reading','解释：这段材料可以怎样理解'],['claim','主张：我在什么条件下这样判断'],['practice','实践：我想试着怎样做']]}),
      field('text','候选说法',{rows:3,value:prev ? prev.text : ''}),
      field('scope','适用边界',{value:prev ? prev.scope : '',placeholder:'限于哪些人、场合或条件？'}),
      field('why','理由',{value:prev ? prev.why : '',placeholder:'哪些细节使这个说法值得考虑？'}),
      box('field-pair',field('rival','另一种解释',{value:prev ? prev.rival : ''}),field('test','怎样检验或推翻',{value:prev ? prev.test : ''})),
      group('引用片段（1 至 32 条，可跨问题）',notes.map(n=>check('notes',n.id,noteName(n),!!prev && prev.notes.includes(n.id))))];
    if (seeds.length) fields.push(field('seed','源自哪个念头（可不选）',{required:false,choices:[['','没有对应念头'],...seeds.map(s=>[s.id,`${s.id} · ${compact(s.text)}`])],value:fromSeed}));
    editor(prev ? '修订为新版本' : '形成候选观点', '写成候选并不表示采纳。先交代边界、理由和可能的反面。', fields,
      prev ? '另存为新版本' : '记入候选', fd=>{
        const refs = fd.getAll('notes'); if (!refs.length) throw Error('请至少勾选一条作为依据的片段。');
        commit('idea',{question:q.id,kind:prev ? prev.kind : fd.get('kind'),text:fd.get('text'),scope:fd.get('scope'),why:fd.get('why'),
          rival:fd.get('rival'),test:fd.get('test'),notes:refs,previous:prev ? prev.id : null,seed:fd.get('seed') || null},'新版本已记为候选，未自动采纳。');
      });
  }
  function challengeEditor(i, protective = false) {
    const candidates = noteChoices(i.question);
    editor('添加检验', `${kindRev(i)}：${i.text}`, [
      field('note','用哪条片段检验',{choices:[['','请选择片段'],...candidates.map(n=>[n.id,noteName(n)])],hint:'如果还缺材料，可先关闭，回到「手边材料」记一个片段。'}),
      field('verdict','检验结果',{choices:protective ? [['counter',VERDICT.counter]] : [['','请选择结果'],...Object.entries(VERDICT)]}),field('detail','发生了什么，这对说法有什么影响？',{rows:3})
    ], '记入检验', fd=>commit('challenge',{idea:i.id,note:fd.get('note'),verdict:fd.get('verdict'),detail:fd.get('detail')},'检验已记入这一版。'));
  }
  function adoptEditor(i) {
    if (!allowAdopt(i)) return;
    editor('本人采纳', '只采纳下面这一版；以后修订不会沿用这次授权。', [p(`${kindRev(i)}：${i.text}`,'hint'),
      fold('回看已有结论的检验',...i.checks.filter(c=>c.verdict === 'limit' || c.verdict === 'survives').map(c=>p(`${c.id} · ${VERDICT[c.verdict]}：${c.detail}`,'body-text'))),
      field('review','冲突审查',{placeholder:'是否与已有判断或实践冲突？还有哪些限制、代价或未知？'}),
      field('reason','我采纳这一版的理由'),check('consent','yes','我本人决定在所写边界内采纳这一版。',false,true)
    ], '确认采纳', fd=>{
      if (fd.get('consent') !== 'yes') throw Error('必须由本人明确勾选，才可采纳。');
      commit('adopt',{idea:i.id,review:fd.get('review'),reason:fd.get('reason'),consent:true},'已记入本人的采纳决定。');
    });
  }
  function withdrawEditor(i) {
    editor('本人撤回', '撤回不会抹去旧版、原决定或已记下的试行。', [p(`${kindRev(i)}：${i.text}`,'hint'),
      field('reason','撤回的理由'),check('consent','yes','我本人决定撤回对这一版的采纳。',false,true)
    ], '确认撤回', fd=>{
      if (fd.get('consent') !== 'yes') throw Error('必须由本人明确勾选，才可撤回。');
      commit('withdraw',{idea:i.id,reason:fd.get('reason'),consent:true},'撤回已记入；旧记录仍在。');
    });
  }
  function trialEditor(i) {
    if (!allowTrial(i)) return;
    editor('记录试行', `针对已采纳的实践 ${i.id}：${i.text}`,[field('step','这一次具体做什么？',{rows:3})],'记入试行',
      fd=>commit('trial',{idea:i.id,step:fd.get('step')},'试行已关联到这版实践。'));
  }
  function linkEditor(q) {
    const ideas = values(view.ideas).filter(i=>!view.questions[i.question].paused), start = ideas.filter(i=>i.question === q.id);
    const choice = i=>[i.id,`${kindRev(i)}：${compact(i.text,40)}（${compact(scopeName(i.question),20)}）`];
    editor('连接两个观点','从起点读到终点。举例：「甲以其为前提 → 乙」表示没有乙，就不能主张甲。',[
      field('from','起点观点',{choices:start.map(choice)}),field('relation','关系',{choices:[['','请选择关系'],...Object.entries(RELATION)]}),
      field('to','终点观点',{choices:[['','请选择另一个观点'],...ideas.map(choice)]}),field('why','连线理由')
    ],'记入连线',fd=>{
      if (fd.get('from') === fd.get('to')) throw Error('请选择两个不同的观点。');
      commit('link',{from:fd.get('from'),to:fd.get('to'),relation:fd.get('relation'),why:fd.get('why')},'观点连线已记入。');
    });
  }

  function download(text, type, filename) {
    const url = URL.createObjectURL(new Blob([text],{type})), a = el('a'); a.href = url; a.download = filename;
    try { document.body.append(a); a.click(); }
    finally { a.remove(); setTimeout(()=>URL.revokeObjectURL(url),30000); }
  }
  function fileStatus(msg) { const n = $('file-status'); if (sheet.open && n) n.textContent = msg; else notice(msg); }
  function downloadBook() {
    download(JSON.stringify(book,null,2)+'\n','application/json;charset=utf-8','flyfishPhilo-notebook.json');
    requestedBackup = true; updateMast(); fileStatus('已请求下载完整 JSON。请核对文件已保存，再关闭本页。');
  }
  function downloadBookSafe() { try { downloadBook(); } catch (err) { fail(err); } }
  function offerBook(next, projected, mode, summary) {
    const prompt = {demo:'打开虚构读书会',imported:'打开导入手记',blank:'另起空白手记'}[mode];
    function install() {
      endSheet(); book = next; view = projected; handoff = null; demo = mode === 'demo'; edited = false; requestedBackup = false;
      const qs = values(view.questions); selected = (qs.find(q=>!q.paused) || qs[0] || {}).id || null;
      const ideas = values(view.ideas).filter(i=>i.question === selected);
      pane = demo && ideas.length ? 'ideas' : 'material'; expandedIdea = pane === 'ideas' ? ideas[ideas.length-1].id : null;
      render(book.events.length ? 'current-question' : 'first-question'); notice(demo ? '' : summary);
    }
    if (book.events.length || welcomeTyped() || sheetDirty) {
      const warning = welcomeTyped() ? '首页问题尚未记入，替换后这段输入会消失。' :
        '当前手记将从本页内存移走，不会与新手记合并。若要保留，请先下载完整 JSON 并核对文件。';
      ask(prompt + '并替换当前内容？',summary + ' ' + warning,prompt + '并替换',install,!!book.events.length);
    } else install();
  }
  function loadDemo() {
    try {
      if (typeof globalThis.FlyfishPhiloDemo !== 'function') throw Error('此文件没有附带示例，请打开完整的离线 HTML。');
      const next = globalThis.FlyfishPhiloDemo(core), projected = core.replay(next);
      offerBook(next,projected,'demo','虚构示例用于练习，不代表你的经历或决定。');
    } catch (err) { fail(err); }
  }
  function fileSheet(importFirst = false) {
    const save = el('section','file-group'), load = el('section','file-group'), fresh = el('section','file-group');
    const info = p('','helper'); info.id = 'file-status'; info.setAttribute('role','status');
    const preview = el('pre','preview'); preview.tabIndex = 0;
    const read = fold('预览 Markdown 阅读稿',preview);
    read.addEventListener('toggle',()=>{ if (read.open) { try { preview.textContent = core.markdown(book); } catch (err) { fail(err); } } });
    save.append(el('h3','','带走本册'),p('完整 JSON 保存全部已记入的事件，可以恢复；Markdown 是供阅读的手记，不是备份。','helper'),
      box('actions',btn('下载完整 JSON',downloadBookSafe,'primary'),btn('导出 Markdown 阅读稿',()=>{
        try { download(core.markdown(book),'text/markdown;charset=utf-8','flyfishPhilo-notes.md'); fileStatus('已请求下载阅读稿；若要恢复手记，请另存完整 JSON。'); } catch (err) { fail(err); }
      })),read);
    const picker = el('input'); picker.type = 'file'; picker.id = uid(); picker.accept = '.json,application/json';
    const lbl = el('label','','选择完整 JSON 文件'); lbl.htmlFor = picker.id;
    load.append(el('h3','','从备份恢复'),p('先在本页校验全部事件，校验通过才会替换。请勿在这里导入 AI 提案。','helper'),box('field',lbl,picker));
    fresh.append(el('h3','','换一本'),box('actions',btn('体验虚构读书会',loadDemo),btn('另起空白手记',()=>{
      try { const next = core.blank(); offerBook(next,core.replay(next),'blank','新册没有任何记录。'); } catch (err) { fail(err); }
    })));
    const epoch = openSheet(importFirst ? '导入完整 JSON' : '手记文件',...(importFirst ? [load,save,fresh,info] : [save,load,fresh,info]));
    let reads = 0;
    picker.addEventListener('change',async()=>{
      const file = picker.files[0]; if (!file) return; const k = ++reads, original = book; picker.value = ''; clearError();
      info.textContent = '正在本页校验文件……';
      try {
        if (core.LIMITS && file.size > core.LIMITS.bytes + 2) throw Error('文件超过手记大小上限。');
        const raw = await file.text(); if (!currentSession(epoch) || k !== reads || original !== book) return;
        let next; try { next = JSON.parse(raw); } catch (_) { throw Error('文件不是有效的 JSON。'); }
        if (!next || next.format !== 'flyfishPhilo/1' || !Array.isArray(next.events)) throw Error('这里只接受完整手记 JSON；AI 提案请粘贴到「与任意 AI 协作」。');
        const projected = core.replay(next);
        const summary = `已校验「${file.name}」：${values(projected.questions).length} 个问题，${next.events.length} 条事件。`;
        info.textContent = summary; offerBook(next,projected,'imported',summary);
      } catch (err) { if (currentSession(epoch) && k === reads) { info.textContent = ''; fail('导入未生效，当前内容未改变。' + err.message); } }
    });
    if (importFirst) picker.focus();
  }

  function aiSheet(q) {
    if (q.paused) { openSheet('与任意 AI 协作',p('这个问题已悬置，不能生成外发资料或接收候选。若想继续，请先重开问题。','hint'),btn('返回问题',closeSheet)); return; }
    const bridge = globalThis.FlyfishPhiloBridge, notes = values(view.notes).filter(n=>n.question === q.id).reverse();
    const intro = p('本页不连接模型。你可以把选定内容复制给任何聊天 AI 或 agent，也可以只阅读预览，什么都不发送。','helper');
    const share = el('section','ai-block'), response = el('section','file-group');
    share.append(el('h3','','挑选这次愿意给出的材料'),intro);
    const pickQ = check('share-question',q.id,`当前问题：${q.text}`);
    const pickNotes = group('勾选本题 1 至 32 条片段，默认全不选',notes.map(n=>check('share-note',n.id,noteName(n))));
    const pick = box('ai-block',pickQ,pickNotes);
    const previewField = field('preview','完整外发预览',{readOnly:true,required:false,rows:8,hint:'可在框内滚动查看全文。只复制所示文字；不附出处栏。请检查正文里是否仍有不愿分享的姓名或细节。'});
    const preview = previewField.querySelector('textarea'); previewField.hidden = true;
    const report = p('','helper'); report.setAttribute('role','status');
    let epoch, generation = 0, busy = false, selectedPacket = null;
    const receipt = p('','helper');
    const matched = () => !!handoff && handoff.book === book && handoff.question === q.id;
    const incoming = btn('粘贴 AI 提案 JSON',()=>{ if (matched()) proposalSheet(q,bridge); });
    const selectedNotes = () => Array.from(pick.querySelectorAll('input[name="share-note"]:checked'), n=>n.value);
    const generate = btn('生成外发预览', async()=>{
      const ids = selectedNotes(); if (busy || !pickQ.querySelector('input').checked || !ids.length) return;
      const turn = ++generation, original = book; busy = true; handoff = null; selectedPacket = null; clearError(); resetButtons();
      try {
        const packet = await bridge.context(original,q.id,ids);
        if (!currentSession(epoch) || turn !== generation || original !== book) return;
        preview.value = bridge.prompt(packet); selectedPacket = packet; handoff = {book:original,question:q.id,ids:packet.notes.map(n=>n.id)};
        previewField.hidden = false; report.textContent = '预览已在本页生成，尚未复制或发送。';
        preview.focus({preventScroll:true}); previewField.scrollIntoView({block:'nearest'});
      } catch (err) { if (currentSession(epoch) && turn === generation) fail('无法生成预览：' + err.message); }
      finally { if (turn === generation) { busy = false; resetButtons(); } }
    },'primary');
    const copy = btn('复制完整预览', async()=>{
      if (!preview.value || previewField.hidden) return;
      preview.focus(); preview.select();
      try {
        if (!navigator.clipboard || !navigator.clipboard.writeText) throw Error();
        await navigator.clipboard.writeText(preview.value);
        if (currentSession(epoch)) report.textContent = '已复制所示全文。只有你粘贴到别处后，对方才会收到。';
      } catch (_) { if (currentSession(epoch)) report.textContent = '浏览器未允许自动复制。全文已选中，请使用系统的「复制」。'; }
    });
    const savePacket = btn('下载所选资料 JSON',()=>{
      if (!selectedPacket || !matched() || previewField.hidden || busy) return;
      try { download(JSON.stringify(selectedPacket,null,2)+'\n','application/json;charset=utf-8','flyfishPhilo-context.json'); report.textContent='已请求下载当前选中的资料包，不是整本手记。'; } catch(err) { fail(err); }
    });
    function resetButtons() {
      const count = selectedNotes().length;
      generate.disabled = !bridge || busy || !pickQ.querySelector('input').checked || !count || count > 32;
      copy.disabled = previewField.hidden || !preview.value;
      savePacket.disabled = !selectedPacket || !matched() || busy || previewField.hidden;
      incoming.disabled = !bridge || busy || !matched();
      receipt.textContent = matched() ? `可接收最近这次预览（${handoff.ids.join('、')}）的回复。另选材料会解除此次关联。` : '要接收 JSON，请先明确选择当前问题和片段，并生成预览。普通文字不需要这一步。';
    }
    pick.addEventListener('change',()=>{
      ++generation; handoff = null; selectedPacket = null; busy = false; preview.value = ''; previewField.hidden = true;
      report.textContent = selectedNotes().length > 32 ? '一次最多可选 32 条，请取消多选的片段。' : '选择已改变，须重新生成预览。'; clearError(); resetButtons();
    });
    share.append(pick); if (!notes.length) share.append(p('这个问题还没有可以勾选的片段。先记一条片段，再回来协作。','hint'));
    if (!bridge) share.append(p('此 HTML 未附带协作桥。仍可手工记下 AI 的文字和来源。','hint'));
    share.append(box('actions',generate),previewField,box('actions',copy,savePacket),report); resetButtons();
    response.append(el('h3','','拿到 AI 的回复之后'),p('普通文字记为待审解释。结构化提案只进入候选，不会替你采纳、撤回或试行。','helper'));
    const row = box('actions'); if (bridge) row.append(incoming);
    row.append(btn('手工保存 AI 文字',()=>manualAI(q))); response.append(receipt,row);
    epoch = openSheet('与任意 AI 协作',share,response);
  }
  function manualAI(q) {
    editor('手工保存 AI 文字','不会生成 JSON 也没有关系。原文作为「AI 的解释」待审，不记成亲历，也不表示你认同。',[
      field('source','AI 回复来源',{type:'text',placeholder:'写明 AI、agent 或这段对话的来处'}),field('text','AI 回复原文',{rows:5})
    ],'保存为待审解释',fd=>commit('note',{question:q.id,origin:'ai',source:fd.get('source'),text:fd.get('text')},'已注明 AI 来源，作为待审解释保留。'));
  }
  function proposalSheet(q, bridge) {
    let epoch, busy = false;
    const f = form(async fd=>{
      if (busy) return; const raw = fd.get('proposal'), original = book;
      busy = true; apply.disabled = true;
      try {
        let proposal; try { proposal = JSON.parse(raw); } catch (_) { throw Error('不是有效的 JSON。若对方只给了普通文字，请改用「手工保存 AI 文字」。'); }
        if (proposal && (proposal.format === 'flyfishPhilo/1' || Object.hasOwn(proposal,'events'))) throw Error('这是手记或事件集合，不是候选提案。这个入口不能恢复整本。');
        const next = await bridge.apply(original,proposal);
        if (!currentSession(epoch) || guard.open || book !== original || f.elements.proposal.value !== raw) return;
        const projected = core.replay(next), id = firstNew(projected.ideas,view.ideas), idea = projected.ideas[id];
        if (!idea || idea.origin !== 'ai' || core.status(idea) !== 'candidate') throw Error('没有得到可审阅的 AI 候选。');
        if (idea.question !== q.id) throw Error('提案属于另一个问题，请打开对应问题后再粘贴。');
        place(next,projected,'suggest',{}); notice('AI 提案已作为候选记入，未经本人采纳。');
      } catch (err) { if (currentSession(epoch) && book === original) fail('提案未写入，原手记保留。' + err.message); }
      finally { busy = false; apply.disabled = false; }
    });
    const apply = submitBtn('校验并记入候选');
    f.append(p('只粘贴对方返回的提案 JSON。请不要粘贴整本手记；校验失败不会改变当前内容。','helper'),
      field('proposal','AI 提案 JSON',{rows:8}),box('actions',apply,btn('取消',closeSheet)));
    epoch = openSheet('粘贴 AI 提案 JSON',f); f.elements.proposal.focus();
  }

  $('sheet-close').addEventListener('click', closeSheet);
  sheet.addEventListener('cancel', e => { e.preventDefault(); closeSheet(); });
  $('file-menu').addEventListener('click', () => fileSheet());
  try {
    book = core.blank(); view = core.replay(book); render();
  } catch (_) {
    desk.replaceChildren(el('h1','boot','无法打开工作台'),p('缺少可用的离线核心。请重新打开完整的 flyfishPhilo HTML 文件。'));
  }
})();
