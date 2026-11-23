"""The owner UI writes first; only a validated, saved question is displayable."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1]/'skills'/'flyfish-philo'/'scripts'
HOST = SCRIPTS/'owner_turn.py'
CONSENT = '我同意把本题和我的回答保存在本机手记中'

class OwnerTurns(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name)/'test.sqlite3'

    def cmd(self, op, payload, ok=True):
        self.assertTrue(HOST.is_file(), 'Owner-controlled turn adapter is missing')
        p = subprocess.run([sys.executable, '-B', str(HOST), '--store', str(self.db), op],
                           input=json.dumps(payload, ensure_ascii=False).encode(), capture_output=True)
        self.assertEqual(p.returncode == 0, ok, (p.stdout,p.stderr)); return json.loads(p.stdout if ok else p.stderr)

    def test_crash_between_human_and_model_neither_loses_nor_repeats_a_reply(self):
        topic = '为什么看到船票就想到出发？'
        a = self.cmd('open', {'topic':topic, 'consent':CONSENT}); t=a['thread']
        self.assertEqual(a['phase'], 'ready')
        p = self.cmd('prepare', {'thread':t}); self.assertEqual(p['context']['basis']['text'], topic)
        q = self.cmd('commit', {'thread':t,'rev':a['rev'],'name':'philo_ask',
                      'arguments':{'question':'你看到船票时最先想到什么？','anchor':'船票'}})
        self.assertEqual(self.cmd('resume',{'thread':t})['display'], q['display'])
        text = '我只想到票角那块蓝墨水。'
        b = self.cmd('human', {'thread':t, 'rev':q['rev'], 'text':text})
        self.assertEqual(b['phase'],'ready'); self.assertIsNone(b['display'])
        self.cmd('human', {'thread':t,'rev':q['rev'],'text':text},False)
        p = self.cmd('prepare',{'thread':t}); self.assertEqual(p['context']['basis']['text'],text)
        self.assertNotIn('history',p['context'])
        self.cmd('commit', {'thread':t,'rev':b['rev'],'name':'philo_ask','arguments':{'question':'你从什么时候开始？','anchor':'蓝墨水'}},False)
        after = self.cmd('resume',{'thread':t}); self.assertEqual((after['rev'],after['display']),(b['rev'],None))
        next_q = '你记得的蓝墨水是什么样子？'
        c = self.cmd('commit',{'thread':t,'rev':b['rev'],'name':'philo_ask','arguments':{'question':next_q,'anchor':'蓝墨水'}})
        self.assertEqual(self.cmd('resume',{'thread':t})['display'],next_q)
        self.assertEqual(c['rev'],b['rev']+1)

    def test_no_local_consent_or_store_no_side_effect(self):
        for consent in ('', 'yes', CONSENT+'?'):
            self.cmd('open',{'topic':'虚构','consent':consent},False);self.assertFalse(self.db.exists())
        self.cmd('prepare',{'thread':'nothing'},False);self.assertFalse(self.db.exists())

    def test_model_cannot_supply_a_human_event_or_read_another_topic(self):
        st=self.cmd('open',{'topic':'虚构木盒','consent':CONSENT});t=st['thread']
        self.cmd('open',{'topic':'another-secret-topic','consent':CONSENT});p=self.cmd('prepare',{'thread':t})
        self.assertNotIn('another-secret-topic',str(p));self.assertNotIn(t,str(p));self.assertNotIn(CONSENT,str(p))
        for name,arguments in [('philo_reply',{'kind':'keep','text':'保留这一版'}),('philo_ask',{'thread':t,'question':'这个木盒？','anchor':'木盒'}),('philo_candidate',{})]:
            self.cmd('commit',{'thread':t,'rev':st['rev'],'name':name,'arguments':arguments},False)
        self.assertEqual(st,self.cmd('resume',{'thread':t}))

    def test_declining_with_private_reason_or_punctuation_is_not_evidence(self):
        st=self.cmd('open',{'topic':'虚构木盒','consent':CONSENT});t=st['thread']
        q=self.cmd('commit',{'thread':t,'rev':st['rev'],'name':'philo_ask','arguments':{'question':'木盒里面有什么？','anchor':'木盒'}})
        s=self.cmd('human',{'thread':t,'rev':q['rev'],'text':'我不想回答，因为CANARY-IGNORE？'})
        self.assertEqual(s['phase'],'paused');self.assertNotIn(b'CANARY-IGNORE',self.db.read_bytes());self.cmd('prepare',{'thread':t},False)

    def test_reference_ui_waits_for_cloud_consent_and_reopens_without_network(self):
        import os
        args=[sys.executable,'-B',str(SCRIPTS/'chat.py'),'--store',str(self.db),'--model','unused']
        def chat(argv,text):
            p=subprocess.run(argv,input=text.encode(),capture_output=True,env={**os.environ,'PYTHONUTF8':'1','OPENAI_API_KEY':''});return p.returncode,p.stdout.decode(),p.stderr.decode()
        self.assertEqual(chat(args,'no\n')[0],0);self.assertFalse(self.db.exists())
        result=chat(args,CONSENT+'\n虚构木盒\n');self.assertEqual(result[0],0);t=result[1].split('--thread ')[-1].splitlines()[0]
        st=self.cmd('resume',{'thread':t});self.cmd('commit',{'thread':t,'rev':st['rev'],'name':'philo_ask','arguments':{'question':'木盒里装了什么？','anchor':'木盒'}})
        rc,out,err=chat(args+['--thread',t,'--share-with-openai'],'蓝纸角的双折痕。\n');self.assertEqual(rc,2);self.assertIn('OPENAI_API_KEY',err)
        self.assertEqual(self.cmd('prepare',{'thread':t})['context']['basis']['text'],'蓝纸角的双折痕。')

    def test_response_boundary_rejects_text_wrong_model_and_multiple_calls(self):
        import importlib.util
        spec=importlib.util.spec_from_file_location('tc_cloud',SCRIPTS/'cloud_turn.py');assert spec and spec.loader
        c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
        req=c.make_request({'context':{},'tool':{'name':'philo_ask','parameters':{}}},'pinned-model')
        self.assertIs(req['store'],False);self.assertEqual(req['tool_choice'],'auto');self.assertFalse(req['parallel_tool_calls'])
        call={'type':'function_call','name':'philo_ask','call_id':'synthetic-id','arguments':'{"question":"Q?","anchor":"Q"}'}
        good={'status':'completed','model':'pinned-model','id':'synthetic-resp','output':[call]}
        self.assertEqual(c.parse_result(good,req)['arguments'],{'question':'Q?','anchor':'Q'})
        for changes in ({'model':'different'},{'status':'incomplete'},{'output':[]},{'output':[call,call]},{'output':[{**call,'name':'philo_reply'}]},{'output':[{**call,'arguments':'{"a":0,"a":1}'}]}):
            with self.assertRaises(c.CloudError):c.parse_result({**good,**changes},req)
        with self.assertRaises(c.CloudError):c.send_openai(req,share=False)

if __name__=='__main__': unittest.main()
