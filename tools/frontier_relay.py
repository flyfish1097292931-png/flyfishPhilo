#!/usr/bin/env python3
"""Relay FOUR public, fixed synthetic requests to OpenAI for one pinned GitHub Actions run.
No agent runs on the relay. It holds no notebook, selects no tools and cannot author a question.
"""
import argparse
import importlib.util
import json
import re
from pathlib import Path
import sys
import time

spec=importlib.util.spec_from_file_location('_frontier_host',Path(__file__).resolve().parents[1]/'tests'/'frontier_hosted.py')
if spec is None or spec.loader is None: raise ImportError('Missing hosted acceptance code.')
host=importlib.util.module_from_spec(spec);spec.loader.exec_module(host)
cloud=host.cloud
SEQUENCE=['first-question','follow-up','counterquestion','invited-candidate']
NAMES=['philo_ask','philo_ask','answer_counterquestion','philo_candidate']
ANSWER='我只认蓝纸角上那道双折痕。'

def allowed(body,idx,prior):
    ctx=json.loads(body['input'][0]['content']);topic=ctx['topic'];assert re.fullmatch(r'在虚构码头的[a-f0-9]{8}号渡船上，两班怎样才算交接完成？',topic)
    name=NAMES[idx]; c=host.owner.core
    shape=c.obj({'answer':c.string(1200)}) if idx==2 else c.obj({k:v for k,v in c.SCHEMAS[name]['properties'].items() if k not in ('thread','rev','connection')})
    want={'topic':topic,'basis':{'kind':'topic','turn':1,'text':topic} if idx==0 else {'kind':'answer','turn':3,'text':ANSWER}}
    if idx==1: want['previous_question']=prior[0]['arguments']['question']
    if idx==2:want.update(counterquestion='你说的交接具体是什么意思？',previous_question=prior[1]['arguments']['question'])
    if idx==3:want['evidence']=[{'turn':3,'text':ANSWER}]
    assert body==cloud.make_request({'context':want,'tool':{'name':name,'parameters':shape}},host.MODEL), 'Refuse anything other than the public synthetic protocol.'
    return body

def relay(repo,issue,run,sha,send,origin):
    assert re.fullmatch(r'[\w.-]+/[\w.-]+',repo) and all(re.fullmatch(r'[1-9]\d{0,19}',x) for x in (issue,run)) and re.fullmatch(r'[0-9a-f]{40}',sha)
    ep='repos/'+repo+'/issues/'+issue+'/comments';run_ep='repos/'+repo+'/actions/runs/'+run
    meta=host.gh(run_ep); assert meta['head_sha']==sha and meta['path'].split('@')[0]=='.github/workflows/frontier.yml'
    assert meta['head_repository']['full_name'].casefold()==repo.casefold() and meta['head_branch']=='verify/frontier-'+issue
    attempt=str(meta['run_attempt']);deadline=time.monotonic()+700;prior=[]
    for idx,step in enumerate(SEQUENCE):
        while time.monotonic()<deadline:
            rows=host.gh(ep+'?per_page=100'); matched=[]
            for row in rows:
                v=host.unwrap(row['body']);
                if row['user']['login']=='github-actions[bot]' and v.get('protocol')==host.PROTOCOL and (v.get('direction'),v.get('sha'),v.get('run'),v.get('attempt'),v.get('step'))==('request',sha,run,attempt,step):matched.append(v)
            if not matched:
                if host.gh(run_ep)['status']=='completed': raise RuntimeError('Hosted run ended before this live turn.')
                time.sleep(3);continue
            assert len(matched)==1;v=matched[0];ident={k:v[k] for k in ('protocol','run','attempt','sha','step','nonce','request_sha256')}
            body=allowed(v['body'],idx,prior);assert re.fullmatch('[0-9a-f]{24}',v['nonce']) and cloud.digest(cloud.compact(body))==v['request_sha256']
            existing=[host.unwrap(x['body']) for x in rows if x['user']['login'].casefold()==repo.split('/')[0].casefold()]
            replies=[x for x in existing if x.get('direction')=='response' and all(x.get(k)==i for k,i in ident.items())]
            if replies:
                assert len(replies)==1;r=replies[0]['receipt'];print('Already relayed',step,flush=True)
            else:
                r=send(body);assert r['model']==host.MODEL and r['name']==NAMES[idx]
                value={**ident,'direction':'response','receipt':r,'service_origin':origin}
                posted=host.gh(ep,{'body':host.wrap(value)});back=host.gh('repos/'+repo+'/issues/comments/'+str(posted['id']));assert host.unwrap(back['body'])==value
                print('RELAYED',step,r['model'],r['name'],r['arguments'],back['html_url'],flush=True)
            prior.append(r);break
        else:raise TimeoutError('Hosted runner did not request its next step.')
    return prior

def main(argv=None,send=None,origin='https://api.openai.com'):
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('repo','issue','run','sha'):p.add_argument('--'+name,required=True)
    a=p.parse_args(argv);return relay(a.repo,a.issue,a.run,a.sha,send or (lambda body:cloud.send_openai(body,share=True)),origin)

if __name__=='__main__':main()
