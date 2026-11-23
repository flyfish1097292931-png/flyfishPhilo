"""Live synthetic acceptance on GitHub-hosted runners. Never pass it a real notebook.

Receiver: two independent runners. Transport only: an explicitly started operator
relay, which keeps provider credentials outside GitHub. No fixtures for model outputs.
"""
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import importlib.util
import time

SCRIPTS=Path(__file__).resolve().parents[1]/'skills/flyfish-philo/scripts'
def module(name):
    s=importlib.util.spec_from_file_location('philo_test_'+name,SCRIPTS/(name+'.py'))
    if not s or not s.loader: raise ImportError('Missing skill module.')
    m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
owner=module('owner_turn');cloud=module('cloud_turn')
MODEL='gpt-6.2-astra'
PROTOCOL='flyfishPhilo/frontier-v1'

def gh(path, payload=None):
    cmd=['gh','api',path]
    if payload is not None: cmd+=['--method','POST','--input','-']
    p=subprocess.run(cmd,input=json.dumps(payload) if payload is not None else None,text=True,capture_output=True,timeout=25)
    if p.returncode: raise RuntimeError('GitHub API failed: '+str(p.returncode))
    return json.loads(p.stdout)

def binding():
    repo=os.environ['GITHUB_REPOSITORY']; ref=os.environ['GITHUB_REF_NAME']; issue=os.environ.get('FRONTIER_ISSUE') or ref.rsplit('-',1)[-1]
    assert re.fullmatch(r'[1-9][0-9]{0,9}',issue)
    return repo, 'repos/'+repo+'/issues/'+issue+'/comments'

def unwrap(body):
    if not isinstance(body,str) or not body.startswith('```json\n') or not body.endswith('\n```') or len(body)>40000:return {}
    try: data=json.loads(body[8:-4])
    except (ValueError,RecursionError): return {}
    return data if isinstance(data,dict) else {}

def wrap(data): return '```json\n'+cloud.compact(data)+'\n```'

def request_model(db,state,step,receipts):
    repo,ep=binding(); prep=owner.run(db,'prepare',{'thread':state['thread']})
    body=cloud.make_request(prep,MODEL); ident={'protocol':PROTOCOL,'run':os.environ['GITHUB_RUN_ID'],
        'attempt':os.environ['GITHUB_RUN_ATTEMPT'],'sha':os.environ['GITHUB_SHA'],'step':step,'nonce':secrets.token_hex(12),'request_sha256':cloud.digest(cloud.compact(body))}
    request=gh(ep,{'body':wrap({**ident,'direction':'request','body':body})}); rid=int(request['id'])
    assert request['user']['login']=='github-actions[bot]' and gh('repos/'+repo+'/issues/comments/'+str(rid))['body']==request['body']
    print('LIVE request',step,'posted:',request['html_url'],flush=True)
    end=time.monotonic()+330
    while time.monotonic()<end:
        comments=gh(ep+'?per_page=100'); matches=[]
        for row in comments:
            if row['user']['login'].casefold()!=repo.split('/')[0].casefold() or row['id']<=rid: continue
            v=unwrap(row['body']);
            if v.get('direction')=='response' and all(v.get(k)==val for k,val in ident.items()):matches.append((row,v))
        if matches:
            assert len(matches)==1,'ambiguous response'; row,v=matches[0];r=v['receipt']
            assert r['model']==MODEL and r['name']==prep['tool']['name']
            assert all(re.fullmatch('[0-9a-f]{64}',r[k]) for k in ('response_sha256','call_sha256'))
            assert all(r['response_sha256']!=old['response_sha256'] and r['call_sha256']!=old['call_sha256'] for old in receipts)
            assert v['service_origin'] in ('https://api.openai.com','https://chatgpt.com')
            result=owner.run(db,'commit',{'thread':state['thread'],'rev':state['rev'],'name':r['name'],'arguments':r['arguments']})
            receipts.append({**r,**ident,'service_origin':v['service_origin'],'request':request['html_url'],'response':row['html_url']})
            print('ACCEPTED',step,r['model'],r['name'],flush=True);return result
        time.sleep(3)
    raise RuntimeError('No live model response within the window. No substitute or prerecorded response is accepted.')

def expect_refusal(action):
    try:action()
    except owner.core.DialogueError:return
    raise AssertionError('operation should have failed')

def human(db,s,text):return owner.run(db,'human',{'thread':s['thread'],'rev':s['rev'],'text':text})

def main(stage):
    assert os.environ.get('GITHUB_ACTIONS')=='true' and os.environ.get('RUNNER_ENVIRONMENT')=='github-hosted','requires a GitHub-hosted runner'
    root=Path(os.environ['RUNNER_TEMP'])/'philo-synthetic';root.mkdir(mode=0o700,exist_ok=True)
    db=root/'fixture.sqlite3';checkpoint=root/'checkpoint.json';machine=os.environ['RUNNER_NAME'];run=os.environ['GITHUB_RUN_ID']
    # RUNNER_NAME can be identical across hosted jobs; boot_id distinguishes fresh kernels.
    boot=cloud.digest(Path('/proc/sys/kernel/random/boot_id').read_text().strip()); host={'name':machine,'boot_hash':boot,'job':os.environ['GITHUB_JOB']}
    if stage=='first':
        assert not db.exists() and not checkpoint.exists(); topic='在虚构码头的'+secrets.token_hex(4)+'号渡船上，两班怎样才算交接完成？'
        expect_refusal(lambda:owner.run(db,'open',{'topic':topic,'consent':'not granted'}));assert not db.exists()
        consent='我同意把本题和我的回答保存在本机手记中'; s=owner.run(db,'open',{'topic':topic,'consent':consent}); receipts=[]
        first=request_model(db,s,'first-question',receipts);assert first['display']==receipts[-1]['arguments']['question']
        answer='我只认蓝纸角上那道双折痕。'
        saved=human(db,first,answer);assert saved['phase']=='ready' and saved['display'] is None
        fresh=owner.run(db,'resume',{'thread':s['thread']});assert fresh==saved
        p=owner.run(db,'prepare',{'thread':s['thread']});assert p['context']['basis']['text']==answer
        second=request_model(db,saved,'follow-up',receipts); a=receipts[-1]['arguments']['anchor']
        assert a in answer and a in second['display'] and a not in topic and second['display']!=first['display']
        reject=lambda:human(db,first,answer);expect_refusal(reject)
        checkpoint.write_text(cloud.compact({'run':run,'sha':os.environ['GITHUB_SHA'],'state':second,'topic':topic,'answer':answer,'host':host,'receipts':receipts,'db_sha256':hashlib.sha256(db.read_bytes()).hexdigest()}));return
    assert stage=='fresh'; cp=json.loads(checkpoint.read_text());assert cp['run']==run and cp['sha']==os.environ['GITHUB_SHA'] and cp['host']['boot_hash']!=boot
    assert hashlib.sha256(db.read_bytes()).hexdigest()==cp['db_sha256']; db.chmod(0o600); thread=cp['state']['thread']; receipts=cp['receipts']
    fresh=owner.run(db,'resume',{'thread':thread});assert fresh==cp['state'] and fresh['phase']=='awaiting'
    counter=human(db,fresh,'你说的交接具体是什么意思？'); reply=request_model(db,counter,'counterquestion',receipts)
    assert reply['transient'] and reply['display'] and reply['rev']==counter['rev'];restored=human(db,counter,'回到原问题');assert restored['display']==fresh['display']
    canary='PRIVATE-DECLINE-'+secrets.token_hex(6);paused=human(db,restored,'我不知道，因为'+canary);assert paused['phase']=='paused' and paused['display'] is None
    expect_refusal(lambda:owner.run(db,'prepare',{'thread':thread})); assert canary.encode() not in db.read_bytes()
    invited=human(db,paused,'帮我整理一下');candidate=request_model(db,invited,'invited-candidate',receipts);assert candidate['display']['status']=='candidate'
    assert not any(ch in candidate['display']['claim'] for ch in '?？') and candidate['display']['claim']!=fresh['display']
    assert all(e['quote'] in cp['answer'] for e in candidate['display']['evidence'])
    with closing(owner.core.Store(db)) as st: assert not st.call('philo_map',{})['positions']
    kept=human(db,candidate,'保留这一版')
    with closing(owner.core.Store(db)) as st: assert len(st.call('philo_map',{})['positions'])==1
    human(db,kept,'撤回这一版')
    with closing(owner.core.Store(db)) as st: assert not st.call('philo_map',{})['positions']
    summary={'verified':True,'synthetic_only':True,'commit':os.environ['GITHUB_SHA'],'run':run,'first_host':cp['host'],'fresh_host':host,'receipts':receipts,'pending_recovered_verbatim':fresh['display'],'actual_reply':cp['answer'],'owner_authority':'candidate -> kept only on human input -> withdrawn','same_store_bytes_before_reopen':cp['db_sha256']}
    (root/'public-evidence.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n');print('PASS: fresh GitHub-hosted VM; exact question/revision; genuine native model calls; decline/private boundary; candidate/keep/withdraw.')

if __name__=='__main__':main(sys.argv[1])
