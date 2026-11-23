#!/usr/bin/env python3
"""Trusted UI adapter. Human events and model proposals have separate entrypoints.

No network, host settings or model runtime. The owning application calls human()
from its actual user-input callback, not from a model tool. Pass its own thread
and revision back to commit(), never a thread/revision selected by the model.
"""
import argparse
from contextlib import closing
import importlib.util
import json
from pathlib import Path
import sys


def sibling(name):
    spec = importlib.util.spec_from_file_location('_flyfish_'+name, Path(__file__).with_name(name+'.py'))
    if spec is None or spec.loader is None: raise ImportError('Missing installed skill component.')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


core = sibling('dialogue')
wire = sibling('philo')


def ui(s):
    """Only return a question to display after the transaction has committed."""
    display = None
    if s['phase'] == 'awaiting': display = s['pending']['question']
    elif s['phase'] == 'review': display = s['candidate']
    return {'thread':s['thread'], 'rev':s['rev'], 'phase':s['phase'], 'display':display}


def open_topic(path, topic, consent):
    args = {'topic':topic, 'consent':consent}
    core.validate(args, core.SCHEMAS['philo_open'])  # invalid consent must not even create the file
    with closing(core.Store(path)) as db: return ui(db.call('philo_open', args))


def run(path, command, data):
    core.require(isinstance(data,dict),'Expected object.')
    if command == 'open':
        core.validate(data,core.SCHEMAS['philo_open']); return open_topic(path,**data)
    core.require(Path(path).is_file(),'No notebook at the selected path.')
    with closing(core.Store(path)) as db:
        if command in ('resume','prepare'):
            core.validate(data,core.obj({'thread':core.ID}))
            db.db.execute('BEGIN')  # One coherent snapshot, even when another UI changes this thread.
            s = db._state(data['thread'])
            result = ui(s) if command == 'resume' else prepare(db,s)
            db.db.commit(); return result
        if command == 'human':
            fields={**core.CHANGE,'text':core.string(2400,0),'kind':{'type':'string','enum':core.REPLIES}}
            core.validate(data,core.obj(fields,['thread','rev','text']))
            return ui(db.call('philo_reply',{**data,'kind':data.get('kind') or classify(data['text'])}))
        core.require(command=='commit' and set(data)=={'thread','rev','name','arguments'},'Invalid proposal envelope.')
        core.validate({k:data[k] for k in core.CHANGE},core.obj(core.CHANGE))
        s=db.call('philo_read',{'thread':data['thread']})
        core.require(s['rev']==data['rev'],'Stale revision; read again.')
        eligible = {'ready':'philo_ask','distilling':'philo_candidate','answer_user':'answer_counterquestion'}.get(s['phase'])
        core.require(eligible and data['name']==eligible,'Not a permitted proposal for this turn.')
        args=data['arguments']; core.require(isinstance(args,dict),'Expected proposal arguments.')
        if eligible=='answer_counterquestion':
            core.validate(args,core.obj({'answer':core.string(1200)}))
            core.require(not any(c in args['answer'] for c in '?？'),'Answer the person without a follow-up question.')
            return {**ui(s),'display':args['answer'],'transient':True}
        core.require(not (set(args)&{'thread','rev','connection'}),'The model cannot select records or cross-inquiry links.')
        if eligible=='philo_ask':
            core.require(isinstance(args.get('anchor'),str) and isinstance(args.get('question'),str) and args['anchor'] in args['question'],'Include the literal anchor in the question.')
        return ui(db.call(eligible,{**args,'thread':s['thread'],'rev':s['rev']}))


def classify(text):
    norm=text.strip().casefold().rstrip('。.!！?？').strip()
    # Refusal remains a non-evidentiary control even when phrased as a question.
    if norm.startswith(('不知道','我不知道','还不知道','不清楚','我不确定','我不想回答','不想回答','先不回答','跳过','先跳过','i don’t know',"i don't know",'skip this','pass this')):
        return 'unknown' if ('知道' in norm or '清楚' in norm or '确定' in norm or 'know' in norm) else 'skip'
    if text.rstrip().endswith(('?','？')): return 'counterquestion'
    if norm in core.DISTILL_COMMANDS: return 'distill'
    if norm in core.KEEP_COMMANDS: return 'keep'
    if norm in core.WITHDRAW_COMMANDS: return 'withdraw'
    if norm in ('继续','接着聊','回到原问题','resume'): return 'resume'
    if norm in ('放弃这版','不保留这版','discard'): return 'discard'
    return 'answer'  # core protects refusals/unknown/pause before any text is stored


def prepare(db,s):
    """Local projection only. Returning this value does NOT opt anyone in to cloud sharing."""
    phase=s['phase']; action={'ready':'philo_ask','distilling':'philo_candidate','answer_user':'answer_counterquestion'}.get(phase)
    core.require(action is not None,'No model turn now; show the saved item or wait.')
    ctx={'topic':s['topic'],'basis':s['basis']}
    if action=='philo_ask':
        # A follow-up should not just paraphrase the previous question.
        answer=s['last_answer']
        if answer:
            row=db.db.execute('SELECT body FROM events WHERE thread=? AND turn=? AND kind=?',(s['thread'],answer['question_turn'],'ask')).fetchone()
            if row: ctx['previous_question']=json.loads(row[0])['question']
    if action=='philo_candidate':
        seg=db.db.execute("SELECT COALESCE(MAX(turn),1) FROM events WHERE thread=? AND kind='reframe'",(s['thread'],)).fetchone()[0]
        rows=db.db.execute("SELECT turn,kind,body FROM events WHERE thread=? AND turn>=? AND kind IN ('answer','amend') ORDER BY turn DESC LIMIT 4",(s['thread'],seg)).fetchall()
        ctx['evidence']=[{'turn':n,'text':json.loads(body)['text' if kind=='answer' else 'user_words']} for n,kind,body in reversed(rows)]
        if s['amendment']:
            old=db.db.execute("SELECT body FROM events WHERE thread=? AND turn=? AND kind='candidate'",(s['thread'],s['amendment']['prior_candidate'])).fetchone()
            if old: ctx['previous_draft']={k:v for k,v in json.loads(old[0]).items() if k in ('claim','scope','rival','test','evidence')}
    if action=='answer_counterquestion':
        ctx['counterquestion']=s['counterquestion']
        row=db.db.execute("SELECT body FROM events WHERE thread=? AND kind='ask' ORDER BY turn DESC LIMIT 1",(s['thread'],)).fetchone()
        if row: ctx['previous_question']=json.loads(row[0])['question']
        shape=core.obj({'answer':core.string(1200)})
    else:
        shape=core.obj({k:v for k,v in core.SCHEMAS[action]['properties'].items() if k not in ('thread','rev','connection')})
    return {'context':ctx,'tool':{'name':action,'parameters':shape}}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--store',required=True,help='Absolute owner-selected SQLite file')
    parser.add_argument('action',choices=('open','resume','human','prepare','commit'))
    ns=parser.parse_args()
    try:
        output=run(ns.store,ns.action,wire.parse_json(sys.stdin.buffer.read(wire.MAX_BYTES+1)))
        sys.stdout.buffer.write((wire.compact(output)+'\n').encode('utf-8')); return 0
    except (core.DialogueError,wire.InvalidParams) as e:
        print(json.dumps({'error':str(e)},ensure_ascii=True),file=sys.stderr); return 2
    except (OSError,ValueError,RuntimeError):
        print('{"error":"Request failed. No new item may be assumed; reopen the thread."}',file=sys.stderr); return 2

if __name__=='__main__':
    raise SystemExit(main())
