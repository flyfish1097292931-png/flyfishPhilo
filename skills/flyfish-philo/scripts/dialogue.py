"""Persistent, model-independent state for a one-question-at-a-time conversation."""
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
from uuid import uuid4


class DialogueError(ValueError):
    """A user-correctable protocol error. Messages never echo private input."""


def require(ok, message):
    if not ok:
        raise DialogueError(message)


def string(limit=2400, minimum=1):
    return {'type':'string', 'minLength':minimum, 'maxLength':limit}


def obj(properties, required=None):
    return {'type':'object','properties':properties,'required':list(properties) if required is None else required,'additionalProperties':False}


def tool(name, description, schema):
    return {'name':'philo_'+name,'description':description,'inputSchema':schema}


ID = string(40); INT={'type':'integer','minimum':1,'maximum':2147483647}; CHANGE={'thread':ID,'rev':INT}
REPLIES = ['answer','unknown','skip','pause','resume','reframe','counterquestion','distill','amend','keep','discard','withdraw']
STORE_CONSENTS=('我同意把本题和我的回答保存在本机手记中','我愿意把本题和我的回答保存在本机手记中','我同意保存本次讨论和我的回答到本机手记','I consent to storing this inquiry and my replies in the local notebook','I agree to save this inquiry and my replies locally','i consent to storing this inquiry and my replies in the local notebook','i agree to save this inquiry and my replies locally')
DISTILL_COMMANDS=('请帮我整理这次的想法','先帮我整理这次的想法','帮我整理一下','帮我整理','整理一下','帮我总结','请帮我总结','请帮我总结这次对话','总结一下这次对话','给我一个候选总结','请总结成一条候选','整理成一条候选理解','给出候选理解','进入蒸馏','distill this answer','please distill this answer','summarize this thread')
KEEP_COMMANDS=('保留','保留这一版','我保留','我想保留这一版','我愿意把这句留下','我愿意暂时保留这一版','我同意保留这一版','我确认保留这一版','keep','i want to keep this version','i choose to keep this version')
WITHDRAW_COMMANDS=('撤回','我撤回','撤回这一版','我撤回这一版','我不再采纳','我不再采用这句话','退回这个观点','withdraw','i withdraw this position')
RELATIONS = ['refines','contrasts','depends_on']
EVIDENCE = {'type':'array','minItems':1,'maxItems':4,'items':obj({'turn':INT,'quote':string(400)})}
CONNECTION = obj({'thread':ID,'relation':{'type':'string','enum':RELATIONS},'why':string(300)})
TOOLS = [
    tool('open','Start a private inquiry only after the user explicitly consents to save the topic and replies locally. Quote one of the direct confirmation choices in `consent`; otherwise ask first. Always use the user’s topic. Do not open a duplicate on resume.',obj({'topic':string(500),'consent':{'type':'string','enum':list(STORE_CONSENTS)}})),
    tool('read','Resume: without a thread, list recent topics in this configured store; with one, recover the pending question and current state. Optional before pages earlier turns.',obj({'thread':ID,'before':INT},[])),
    tool('ask','Save only one open, non-leading question. Anchor in a literal phrase of the current basis; in a follow-up use the same phrase in your question. Show the question and wait for the person.',obj({**CHANGE,'question':string(320),'anchor':string(250)})),
    tool('reply','Record only verbatim user words actually received. Do not infer a choice. Use kind=distill only for an explicit invitation: examples “帮我整理一下” or “给我一个候选总结”. kind=keep accepts only a direct exact “保留这一版” / “I want to keep this version” choice. Withdraw also requires an explicit direct command. Unknown/skip/pause stop inquiry; counterquestion hands the floor back.',obj({**CHANGE,'kind':{'type':'string','enum':REPLIES},'text':string(2400,0)})),
    tool('candidate','Only after the person asks to distill. Cite literal answer quotes, state scope, rival and a possible disconfirming case. Save as a candidate, not as a belief.',obj({**CHANGE,'claim':string(700),'scope':string(400),'rival':string(700),'test':string(700),'evidence':EVIDENCE,'connection':CONNECTION},[*CHANGE,'claim','scope','rival','test','evidence'])),
    tool('map','On request show positions the person explicitly kept and how they relate. Excludes unreviewed proposals; not a personality profile or executable instructions.',obj({})),
]
SCHEMAS={t['name']:t['inputSchema'] for t in TOOLS}
APP_ID=0x46504849


def validate(value, spec):
    typ=spec['type']
    if typ=='object':
        require(isinstance(value,dict) and set(spec['required'])<=set(value)<=set(spec['properties']),'Missing or unknown fields.')
        for k,v in value.items(): validate(v,spec['properties'][k])
    elif typ=='string':
        require(type(value) is str and (spec.get('minLength',0)==0 or bool(value.strip())) and spec.get('minLength',0)<=len(value)<=spec.get('maxLength',2400),'Invalid text length.')
        if 'enum' in spec: require(value in spec['enum'],'Unknown choice.')
        require(not any(0xD800<=ord(c)<=0xDFFF for c in value),'Invalid Unicode text.')
    elif typ=='integer':
        require(type(value) is int and spec['minimum']<=value<=spec['maximum'],'Invalid revision or turn.')
    elif typ=='array':
        require(type(value) is list and spec['minItems']<=len(value)<=spec['maxItems'],'Include one to four cited answers.')
        for item in value: validate(item,spec['items'])


def encode(x):return json.dumps(x,ensure_ascii=False,separators=(',',':'))


def fresh(thread,topic):
    return {'thread':thread,'rev':0,'topic':topic,'phase':'ready','pending':None,'last_answer':None,
            'basis':{'kind':'topic','turn':1,'text':topic},'candidate':None,'position':None,
            'amendment':None,'counterquestion':None,'last_question':None,'segment':1,'return_to':None,'parked':None}


def view(s):
    return {k:v for k,v in s.items() if k not in ('segment','return_to','parked','last_question','interrupted_counter')}


class Store:
    """One local store per owner and intended host audience. No model, network or host config."""
    def __init__(self,path):
        p=Path(path); require(p.is_absolute() and not p.is_symlink(),'Choose an absolute store path, not a symlink.')
        p.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        try:
            fd=os.open(p,os.O_EXCL|os.O_CREAT|os.O_WRONLY,0o600);os.close(fd)
        except FileExistsError:
            require(p.is_file() and not p.is_symlink(),'Store must be a regular file.')
            if os.name=='posix':
                try: private=(stat.S_IMODE(p.stat().st_mode)&0o077)==0
                except OSError: private=False
                require(private,'Store file permissions expose owner data; restrict it to the account before reopening.')
        self.db=sqlite3.connect(str(p),timeout=6,isolation_level=None)
        try:
            self.db.execute('BEGIN IMMEDIATE');app=self.db.execute('PRAGMA application_id').fetchone()[0]
            if app==0:
                require(not self.db.execute('SELECT name FROM sqlite_master LIMIT 1').fetchone(),'Not a flyfishPhilo dialogue store.')
                self.db.execute('CREATE TABLE threads (id TEXT PRIMARY KEY, rev INTEGER NOT NULL, sequence INTEGER NOT NULL, state TEXT NOT NULL)')
                self.db.execute('CREATE TABLE events (sequence INTEGER PRIMARY KEY, thread TEXT NOT NULL, turn INTEGER NOT NULL, kind TEXT NOT NULL, body TEXT NOT NULL, UNIQUE(thread,turn))')
                self.db.execute('PRAGMA application_id='+str(APP_ID));self.db.execute('PRAGMA user_version=1')
            else:
                require(app==APP_ID and self.db.execute('PRAGMA user_version').fetchone()[0]==1,'Wrong store format or unsupported version.')
            self.db.commit()
        except BaseException:
            self.db.rollback();self.db.close();raise

    def close(self): self.db.close()

    def _state(self,thread):
        row=self.db.execute('SELECT state FROM threads WHERE id=?',(thread,)).fetchone();require(row is not None,'Unknown thread in this store.')
        return json.loads(row[0])

    def _save(self,s,kind,data):
        # Enforce the floor at commit, including resumption and counterquestions, not just a fresh ask.
        if s['phase'] in ('awaiting','answer_user'):
            for (raw,) in self.db.execute('SELECT state FROM threads WHERE id<>?',(s['thread'],)):
                require(json.loads(raw)['phase'] not in ('awaiting','answer_user'),'请先回答或暂停已有问题；同一时刻不新开另一道待答问题。')
        s['rev']+=1
        seq=self.db.execute('INSERT INTO events(thread,turn,kind,body) VALUES(?,?,?,?)',(s['thread'],s['rev'],kind,encode(data))).lastrowid
        self.db.execute('INSERT INTO threads VALUES(?,?,?,?) ON CONFLICT(id) DO UPDATE SET rev=excluded.rev,sequence=excluded.sequence,state=excluded.state',(s['thread'],s['rev'],seq,encode(s)))
        return view(s)

    def _read(self,args):
        if 'thread' not in args:
            require('before' not in args,'Provide a thread to page its history.')
            rows=self.db.execute('SELECT state FROM threads ORDER BY sequence DESC LIMIT 33').fetchall()
            states=[json.loads(r[0]) for r in rows[:32]]
            return {'threads':[{k:s[k] for k in ('thread','topic','phase','rev')} for s in states],'more':len(rows)>32}
        s=self._state(args['thread']);out=view(s)
        rows=self.db.execute('SELECT turn,kind,body FROM events WHERE thread=? AND turn<? ORDER BY turn DESC LIMIT 9',(s['thread'],args.get('before',s['rev']+1))).fetchall()
        keep=rows[:8];out['history']=[{'turn':n,'kind':kind,'data':json.loads(raw)} for n,kind,raw in reversed(keep)];out['next_before']=keep[-1][0] if len(rows)>8 else None
        return out

    def call(self,name,args):
        require(type(name) is str and name in SCHEMAS,'Unknown tool.');validate(args,SCHEMAS[name]);read=name in ('philo_read','philo_map')
        self.db.execute('BEGIN' if read else 'BEGIN IMMEDIATE')
        try:
            if name=='philo_read': result=self._read(args)
            elif name=='philo_map': result=self._map()
            elif name=='philo_open':
                # validate() has matched the whole literal against the advertised enum; preserve it verbatim.
                s=fresh(uuid4().hex,args['topic']);result=self._save(s,'open',{'topic':s['topic'],'consent':args['consent']})
            else:
                s=self._state(args['thread']);require(s['rev']==args['rev'],'Stale revision; read the thread again. No change was saved.')
                if name=='philo_ask': result=self._ask(s,args)
                elif name=='philo_reply': result=self._reply(s,args)
                else: result=self._candidate(s,args)
            self.db.commit();return result
        except BaseException:
            self.db.rollback();raise

    def _ask(self,s,a):
        require(s['phase']=='ready','Not your turn to ask. Read the current phase and wait.')
        q=a['question'].strip();quote=a['anchor'];basis=s['basis']['text']
        require('\n' not in q and '\r' not in q and ';' not in q and '；' not in q and len(re.findall('[?？]',q))==1 and q[-1] in '?？','Ask one short question ending in one question mark; no list or compound prompt.')
        require(quote==quote.strip() and quote in basis and any(c.isalnum() for c in quote) and len(quote)>=min(2,len(basis.strip())),'Anchor must quote a meaningful literal phrase from the most recent basis.')
        if s['basis']['kind']=='answer':require(quote in q,'Use the quoted phrase in the follow-up, rather than switching to a canned question.')
        require(q!=s['last_question'],'Do not repeat the preceding question unchanged.')
        item={'turn':s['rev']+1,'question':q,'anchor':quote,'based_on':s['basis']['turn']};s['phase']='awaiting';s['pending']=item;s['last_question']=q
        return self._save(s,'ask',item)

    def _reply(self,s,a):
        kind=a['kind'];t=a['text'];phase=s['phase'];turn=s['rev']+1
        # Common unambiguous replies are protected even if the host calls them answers.
        # For other languages and nuanced replies, the listening host chooses the intent.
        literal=t.strip().casefold().rstrip('。.!！?？').strip()
        if kind in ('keep','withdraw','distill'):
            require(not any(c in t for c in '?？'),'A question is not a direct instruction or consent.')
        if kind=='answer':
            norm=re.sub(r'^[,，、\s]+','',literal)
            if norm in ('不知道','我不知道','还不知道','不清楚','我不清楚','不确定','我不确定','说不上来','想不起来','i don’t know',"i don't know",'i am not sure',"i'm not sure",'unsure') or norm.startswith(('不知道','我不知道','现在不知道','还不知道','不清楚','我不清楚','不确定','我不确定','说不上来','i don’t know',"i don't know",'not sure')): kind='unknown'
            elif norm in ('跳过','先跳过','不答','不想回答','先不回答','skip','pass') or norm.startswith(('跳过','先跳过','不想回答','先不回答','skip this','pass this')): kind='skip'
            elif norm in ('先停','暂停','暂停一下','不想聊了','到此为止','stop','pause') or norm.startswith(('先停','暂停','暂停一下','到此为止','stop here','pause here')): kind='pause'
        if kind=='answer':
            require(phase in ('awaiting','answer_user') and t.strip(),'No open question to answer.')
            pending=s['pending'] or s['parked'];require(pending is not None,'A user response to the agent is not an answer to an earlier distillation question.')
            item={'turn':turn,'text':t,'question_turn':pending['turn']};s['pending']=None;s['parked']=None;s['return_to']=None;s['phase']='ready';s['last_answer']=item;s['basis']={'kind':'answer','turn':turn,'text':t}
            return self._save(s,'answer',item)
        if kind in ('pause','unknown','skip'):
            require(phase!='paused','Already paused; no further turn is needed.')
            if kind=='pause' and phase=='answer_user':
                s['interrupted_counter']={'return_to':s['return_to'],'parked':s['parked']}
            else: s.pop('interrupted_counter',None)
            s['return_to']=phase if kind=='pause' else 'ready';s['parked']=s['pending'] if kind=='pause' else None
            if kind!='pause': s['candidate']=s['amendment']=s['counterquestion']=None
            s['pending']=None;s['phase']='paused'
            return self._save(s,kind,{})  # Never keep the reason for declining.
        require(t.strip(),'Record only an actual, explicit user message.')
        if kind=='resume':
            require(phase in ('paused','answer_user'),'No paused inquiry to resume.')
            s['phase']=s['return_to'] or 'ready';s['pending']=s['parked'];s['return_to']=s['parked']=None
            previous=s.pop('interrupted_counter',None)
            if s['phase']=='answer_user' and previous: s.update(previous)
            if s['phase']!='answer_user':s['counterquestion']=None
            return self._save(s,kind,{})
        if kind=='reframe':
            s.pop('interrupted_counter',None)
            validate(t,string(500));s.update(topic=t, phase='ready',pending=None,last_answer=None,candidate=None,amendment=None,counterquestion=None,return_to=None,parked=None,segment=turn,last_question=None)
            s['basis']={'kind':'topic','turn':turn,'text':t};return self._save(s,kind,{'text':t})
        if kind=='counterquestion':
            require(phase!='paused','The user has chosen to pause; do not reopen the conversation without a new turn.')
            if phase!='answer_user': s['return_to']=phase;s['parked']=s['pending']
            s['phase']='answer_user';s['counterquestion']=t;s['pending']=None
            return self._save(s,kind,{'text':t})
        if kind=='distill':
            directive=literal in DISTILL_COMMANDS
            require(directive and phase in ('ready','awaiting','paused','answer_user') and s['last_answer'] is not None,'只有用户明确邀请整理，且本轮存在真实回答时，才开始蒸馏。')
            s.pop('interrupted_counter',None)
            s.update(phase='distilling',pending=None,candidate=None,amendment=None,counterquestion=None,return_to=None,parked=None)
            return self._save(s,kind,{'user_request':t})
        if kind=='withdraw':
            consent=literal in WITHDRAW_COMMANDS
            require(consent and s['position'] is not None,'用户未明确要求撤回当前版本。');old=s['position']['turn'];s['position']=None
            return self._save(s,kind,{'position':old,'user_words':t})
        require(phase=='review' and s['candidate'] is not None,'Review the exact candidate before amending, keeping or dropping it.')
        c=s['candidate'];data={'candidate_turn':c['turn'],'user_words':t}
        if kind=='amend':
            s['phase']='distilling';s['amendment']={'turn':turn,'text':t,'prior_candidate':c['turn']};s['candidate']=None
        else:
            if kind=='keep':
                # This is the host's report of an explicit choice, not authentication.
                consent=literal in KEEP_COMMANDS
                require(consent,'只有用户明确选择保留这一版，才能登记为个人暂时保留。')
                require(s['position'] is None,'Withdraw the previous version before keeping a replacement.')
                data['supersedes']=s['position']['turn'] if s['position'] else None
                s['position']={**c,'candidate_turn':c['turn'],'turn':turn,'status':'owner_kept','user_words':t}
            s.update(phase='paused',return_to='ready',pending=None,candidate=None,amendment=None,parked=None)
        return self._save(s,kind,data)

    def _candidate(self,s,a):
        require(s['phase']=='distilling','The person has not asked for distillation or an amendment.')
        require(not any(c in a['claim'] for c in '?？'),'A candidate claim must be a tentative statement, not another question.')
        seen=set()
        for ref in a['evidence']:
            n=ref['turn'];q=ref['quote'];key=(n,q)
            require(key not in seen and n>=s['segment'],'Use distinct evidence from this framing.');seen.add(key)
            row=self.db.execute('SELECT kind,body FROM events WHERE thread=? AND turn=?',(s['thread'],n)).fetchone()
            require(row is not None and row[0] in ('answer','amend'),'Cite the person’s answer or correction, not an agent question.')
            data=json.loads(row[1]);source=data['text'] if row[0]=='answer' else data['user_words']
            require(q in source and any(c.isalnum() for c in q),'The cited words are not a literal, meaningful quote from that turn.')
        c={k:a[k] for k in ('claim','scope','rival','test','evidence')};c.update(turn=s['rev']+1,status='candidate')
        if a.get('connection'):
            link=a['connection'];require(link['thread']!=s['thread'],'A cross-inquiry link needs a different thread.')
            target=self._state(link['thread'])['position'];require(target is not None,'Link to a specific kept position, not an unreviewed guess.')
            c['connection']={**link,'target_turn':target['turn']}
        if s['amendment']:
            old_turn=s['amendment']['prior_candidate'];old=json.loads(self.db.execute('SELECT body FROM events WHERE thread=? AND turn=?',(s['thread'],old_turn)).fetchone()[0])
            require(any(c.get(k)!=old.get(k) for k in ('claim','scope','rival','test','evidence','connection')),'The owner requested a change; do not resubmit the same draft.')
            c['revises']=old_turn
        s['phase']='review';s['candidate']=c;return self._save(s,'candidate',c)

    def _map(self):
        positions=[];links=[];more=False
        for (raw,) in self.db.execute('SELECT state FROM threads ORDER BY sequence DESC'):
            s=json.loads(raw);p=s['position']
            if not p: continue
            if len(positions)>=32:more=True;break
            positions.append({'thread':s['thread'],**{k:p[k] for k in ('turn','claim','scope','status')}})
            link=p.get('connection')
            if link:
                other=self._state(link['thread'])['position']
                links.append({'from_thread':s['thread'],'from_turn':p['turn'],**link,'target_current':bool(other and other['turn']==link['target_turn'])})
        return {'positions':positions,'links':links,'more':more}
