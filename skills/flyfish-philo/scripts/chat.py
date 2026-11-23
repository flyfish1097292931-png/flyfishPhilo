#!/usr/bin/env python3
"""A reference conversation UI: direct human input -> durable write -> optional cloud turn."""
import argparse
import importlib.util
import json
from pathlib import Path
import sys


def load(name):
    spec=importlib.util.spec_from_file_location('_philo_ui_'+name,Path(__file__).resolve().with_name(name+'.py'))
    if spec is None or spec.loader is None: raise ImportError('Incomplete installation.')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

owner=load('owner_turn');cloud=load('cloud_turn')

def show(text):
    if isinstance(text,dict):
        for k,label in [('claim','候选'),('scope','范围'),('rival','另一种解释'),('test','如何区分'),('evidence','引用')]:
            v=text.get(k);print(label+'：'+(v if isinstance(v,str) else json.dumps(v,ensure_ascii=False)))
        print('你可以说「保留这一版」，也可以 :amend 新措辞，或 :discard。')
    elif text: print(text)

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--store',required=True);p.add_argument('--model',required=True)
    p.add_argument('--thread',help='Resume only the specified thread');p.add_argument('--share-with-openai',action='store_true',help='Allow the selected turn context to reach OpenAI in this run')
    args=p.parse_args(argv); db=args.store
    print('本机手记是明文。云端拟问只接收本题和当前回合所需的原话；不会收到整个手记。输入 :quit 退出。')
    if not args.share_with_openai: print('本次未授权向 OpenAI 外发；新回答仍可在同意后本机保存。')
    if args.thread: s=owner.run(db,'resume',{'thread':args.thread})
    else:
        print('若愿意留存，请逐字输入：'+owner.core.STORE_CONSENTS[0]+'（或 I agree to save this inquiry and my replies locally）。')
        consent=input('> ')
        if consent not in owner.core.STORE_CONSENTS: print('未获同意；没有创建手记。');return 0
        topic=input('你想谈哪一个问题？\n> ')
        if topic==':quit': return 0
        s=owner.run(db,'open',{'topic':topic,'consent':consent})
    thread=s['thread'];print('续接此题：--thread '+thread)
    print('可用：:pause 暂停，:resume 回到原问题，:skip 跳过，:unknown 不知道，:reframe 新题目，:ask 你的反问，:amend 修订，:discard 放下候选，:quit 退出。')
    while True:
        if s['phase'] in ('ready','distilling','answer_user'):
            if not args.share_with_openai: print('当前需拟问或回应；已保存的内容不动。');return 0
            v=owner.run(db,'prepare',{'thread':thread}); sent=cloud.make_request(v,args.model)
            receipt=cloud.send_openai(sent,share=True)
            s=owner.run(db,'commit',{'thread':thread,'rev':s['rev'],'name':receipt['name'],'arguments':receipt['arguments']})
        show(s['display'])
        if s['phase']=='paused': print('已暂停。不需要解释；要继续请输入 :resume，或 :quit 退出。')
        text=input('> ')
        if text==':quit':return 0
        data={'thread':thread,'rev':s['rev'],'text':text}
        if text.startswith(':'):
            cmd,_,rest=text.partition(' ')
            commands={':pause':'pause',':resume':'resume',':unknown':'unknown',':skip':'skip',':reframe':'reframe',':ask':'counterquestion',':amend':'amend',':discard':'discard'}
            if cmd not in commands: print('不识别此命令；没有保存。');continue
            data.update(kind=commands[cmd],text=rest if cmd in (':reframe',':ask',':amend') else cmd[1:])
        try:s=owner.run(db,'human',data)
        except owner.core.DialogueError as exc:
            print(str(exc),file=sys.stderr);s=owner.run(db,'resume',{'thread':thread});continue

if __name__=='__main__':
    try: sys.exit(main())
    except (KeyboardInterrupt,EOFError): print('\n已退出。')
    except (OSError,ValueError) as ex:
        msg=str(ex) if isinstance(ex,(owner.core.DialogueError,cloud.CloudError)) else '手记或云连接不可用。'
        print(msg+' 重新打开原题即可查看最后成功保存的回合。',file=sys.stderr);sys.exit(2)
