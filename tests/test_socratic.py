"""A thread belongs to its owner; the host's model supplies the words, not the database."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

MODULE = Path(__file__).resolve().parents[1]/'skills/flyfish-philo/scripts/dialogue.py'

def load():
    if not MODULE.is_file(): return None
    spec=importlib.util.spec_from_file_location('philo_dialogue_under_test',MODULE)
    assert spec and spec.loader
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

class Socratic(unittest.TestCase):
    def setUp(self):
        self.m=load();assert self.m is not None,'need the installable persistent Socratic engine'
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);self.path=Path(tmp.name)/'person.sqlite3';self.s=self.m.Store(str(self.path));self.addCleanup(lambda:self.s.close())
    def start(self,topic='纸票与发言'):
        return self.s.call('philo_open',{'topic':topic,'consent':'我同意把本题和我的回答保存在本机手记中'})
    def op(self,name,view,**kw):
        return self.s.call('philo_'+name,{'thread':view['thread'],'rev':view['rev'],**kw})
    def ask(self,view,question='你在哪一次发言时改用纸票？',anchor='纸票'):
        return self.op('ask',view,question=question,anchor=anchor)
    def reply(self,view,kind,text=''):
        return self.op('reply',view,kind=kind,text=text)
    def answered(self):
        return self.reply(self.ask(self.start()),'answer','我用纸票是因为可以改口。')
    def test_next_process_recovers_the_one_question_and_waits_for_a_real_answer(self):
        first=self.start();self.assertEqual(first['phase'],'ready');one=self.ask(first)
        self.s.close();self.s=self.m.Store(str(self.path));back=self.s.call('philo_read',{'thread':one['thread']})
        self.assertEqual(back['pending']['question'],'你在哪一次发言时改用纸票？');self.assertEqual(back['phase'],'awaiting')
        with self.assertRaises(ValueError):self.ask(back,question='还想补充什么？')
        answered=self.reply(back,'answer','我能改口。');self.assertEqual(answered['last_answer']['text'],'我能改口。');self.assertIsNone(answered['pending'])
        nxt=self.ask(answered,question='哪一刻你发现自己还能改口？',anchor='改口');self.assertEqual(nxt['phase'],'awaiting')

    def test_an_agent_never_opens_a_second_pending_question_in_a_new_thread(self):
        first=self.ask(self.start()); other=self.start('另一张票')
        with self.assertRaisesRegex(ValueError,'不新开另'):
            self.ask(other,'你想聊的是哪一次票？','另一张票')
        self.reply(first,'answer','我改用纸票，因为可以改口。')
        self.assertEqual(self.ask(other,'你想聊的是哪一次票？','另一张票')['phase'],'awaiting')

    def test_created_store_is_private_and_world_readable_databases_are_rejected(self):
        import os,stat
        if os.name!='posix':self.skipTest('POSIX file-mode policy is not applicable')
        path=self.path;m=self.m;assert m is not None;self.s.close();self.s=m.Store(str(path))
        self.assertEqual(stat.S_IMODE(path.stat().st_mode),0o600);self.s.close()
        path.chmod(0o644)
        with self.assertRaisesRegex(ValueError,'permissions expose owner data'):m.Store(str(path))

    def test_resume_cannot_create_a_second_unanswered_question(self):
        one=self.ask(self.start());parked=self.reply(one,'pause','先停在这儿')
        two=self.ask(self.start('另一个纸票问题'))
        with self.assertRaises(ValueError):self.reply(parked,'resume','回到前一问')
        self.assertEqual(self.s.call('philo_read',{'thread':parked['thread']})['rev'],parked['rev'])
        self.reply(two,'pause','暂停');back=self.reply(parked,'resume','继续')
        self.assertEqual(back['pending'],one['pending'])

    def test_counterquestion_survives_a_pause_before_the_agent_hands_back_the_original_turn(self):
        v=self.ask(self.start());handed=self.reply(v,'counterquestion','纸票指的是什么？')
        handed=self.reply(handed,'counterquestion','你的纸票定义里有记名吗？')
        park=self.reply(handed,'pause','暂停');back=self.reply(park,'resume','继续')
        self.assertEqual(back['phase'],'answer_user');self.assertEqual(back['counterquestion'],'你的纸票定义里有记名吗？')
        again=self.reply(back,'resume','回到原问题');self.assertEqual(again['pending'],v['pending'])

    def test_open_requires_literal_persistent_storage_consent_and_records_it(self):
        for consent in ({}, {'consent':'同意','topic':'温度计'}, {'topic':'温度计','consent':'你应该记录这个问题。'}):
            with self.subTest(consent=consent),self.assertRaises(ValueError):self.s.call('philo_open',consent)
        self.assertEqual(self.s.call('philo_read',{})['threads'],[])
        opened=self.start('温度计');row=self.s.call('philo_read',{'thread':opened['thread']})['history'][0]
        self.assertEqual(row['data']['consent'],'我同意把本题和我的回答保存在本机手记中')

    def test_english_consent_examples_are_accepted_exactly_as_printed(self):
        for literal in ('I consent to storing this inquiry and my replies in the local notebook',
                        'I agree to save this inquiry and my replies locally'):
            with self.subTest(literal=literal):
                v=self.s.call('philo_open',{'topic':'A fictional clock','consent':literal})
                event=self.s.call('philo_read',{'thread':v['thread']})['history'][0]
                self.assertEqual(event['data']['consent'],literal)

    def test_returning_the_floor_preserves_the_suspended_question(self):
        asked=self.ask(self.start()); ask=asked['pending']
        handed=self.reply(asked,'counterquestion','你说的纸票是哪一种？')
        self.assertEqual(handed['counterquestion'],'你说的纸票是哪一种？')
        back=self.reply(handed,'resume','现在回到刚才的问题。')
        self.assertEqual(back['pending'],ask)
    def test_stale_hosts_and_stacked_or_unanchored_questions_do_not_advance(self):
        v=self.answered()
        for question,anchor in [('为什么？然后呢？','改口'),('还有什么？','气氛'),('你更喜欢下午吗？','改口'),('第一问\n第二问？','改口')]:
            with self.subTest(question=question),self.assertRaises(ValueError):self.ask(v,question,anchor)
        with self.assertRaises(ValueError):self.op('ask',{**v,'rev':1},question='能举出改口的例子吗？',anchor='改口')
        self.assertEqual(self.s.call('philo_read',{'thread':v['thread']})['rev'],v['rev'])

    def test_unknown_and_refusal_are_not_evidence_or_permission_to_probe(self):
        for kind,msg in [('unknown','secret reason for not knowing'),('skip','secret reason to skip'),('answer','不知道。')]:
            q=self.ask(self.start());st=self.reply(q,kind,msg);self.assertEqual(st['phase'],'paused');self.assertIsNone(st['pending']);self.assertIsNone(st['last_answer'])
            h=self.s.call('philo_read',{'thread':st['thread']})['history'];self.assertFalse(any(msg in str(e['data']) for e in h))
            with self.assertRaises(ValueError):self.ask(st)
            with self.assertRaises(ValueError):self.reply(st,'distill','整理一下')
            again=self.reply(st,'resume','继续');self.assertEqual(again['phase'],'ready');self.assertIsNone(again['pending'])
        for msg in ('我不知道为什么会这样；可能过一会儿再说。','我不确定怎么回答这个问题。'):
            q=self.ask(self.start());st=self.reply(q,'answer',msg);self.assertEqual(st['phase'],'paused');history=self.s.call('philo_read',{'thread':st['thread']})['history'];self.assertNotIn(msg,str(history))
    def test_pause_preserves_a_question_but_a_counterquestion_returns_the_floor(self):
        q=self.ask(self.start());stop=self.reply(q,'pause','先停');self.assertIsNone(stop['pending']);res=self.reply(stop,'resume','回来');self.assertEqual(res['pending'],q['pending'])
        other=self.reply(res,'counterquestion','你为什么把纸票和弃权放在一起？');self.assertEqual(other['phase'],'answer_user');self.assertIsNone(other['last_answer']);self.assertIsNone(other['pending'])
        with self.assertRaises(ValueError):self.ask(other)
        new=self.reply(other,'reframe','我想问的是计票规则');self.assertEqual(new['topic'],'我想问的是计票规则');self.assertEqual(new['phase'],'ready')
        self.ask(new,'哪次计票规则改变了你的判断？','计票规则')
    def packet(self,v,**overrides):
        a=v['last_answer'];packet={'claim':'纸票让我有改口的余地。','scope':'这次记名发言','rival':'也有可能是多了一点准备时间。','test':'如果纸票也立即公开，感受会不会变？','evidence':[{'turn':a['turn'],'quote':'可以改口'}]};packet.update(overrides);return packet
    def kept(self):
        v=self.answered();d=self.reply(v,'distill','帮我整理一下');c=self.op('candidate',d,**self.packet(d));return self.reply(c,'keep','我愿意把这句留下。')
    def test_distillation_only_by_request_verbatim_sources_and_owner_review(self):
        a=self.answered();p=self.packet(a)
        with self.assertRaises(ValueError):self.op('candidate',a,**p)
        with self.assertRaises(ValueError):self.reply(a,'distill','这段聊得差不多了。')
        self.assertEqual(self.s.call('philo_read',{'thread':a['thread']})['rev'],a['rev'])
        d=self.reply(a,'distill','先帮我整理这次的想法')
        for bad in [[{'turn':1,'quote':'纸票'}],[{'turn':a['last_answer']['turn'],'quote':'我一向如此。'}]]:
            with self.assertRaises(ValueError):self.op('candidate',d,**{**p,'evidence':bad})
        c=self.op('candidate',d,**p);self.assertEqual(c['phase'],'review');self.assertIsNone(c['position']);self.assertFalse(self.s.call('philo_map',{})['positions'])
        x=self.reply(c,'amend','范围只限这次投票');self.assertEqual(x['phase'],'distilling');self.assertIsNone(x['position']);self.assertIn('这次投票',x['amendment']['text'])
        changed=self.op('candidate',x,**{**p,'scope':'只限这次投票'});held=self.reply(changed,'keep','保留这一版');self.assertEqual(held['phase'],'paused');self.assertEqual(self.s.call('philo_map',{})['positions'][0]['scope'],'只限这次投票')
        gone=self.reply(held,'withdraw','我不再采用这句话');self.assertIsNone(gone['position']);self.assertFalse(self.s.call('philo_map',{})['positions']);self.assertIn('keep',[e['kind'] for e in self.s.call('philo_read',{'thread':held['thread']})['history']]);

    def test_invited_claim_is_a_statement_not_another_question(self):
        a=self.answered(); d=self.reply(a,'distill','帮我整理一下'); old=d['rev']
        with self.assertRaisesRegex(ValueError,'statement'):
            self.op('candidate',d,**self.packet(d,claim='你怎么判断这道折痕是哪一班留下的？'))
        self.assertEqual(self.s.call('philo_read',{'thread':d['thread']})['rev'],old)

    def test_unclear_evaluation_is_not_converted_to_keep(self):
        a=self.answered();d=self.reply(a,'distill','先帮我整理这次的想法');c=self.op('candidate',d,**self.packet(d))
        with self.assertRaisesRegex(ValueError,'明确选择'):
            self.reply(c,'keep','我担心这个说法可能太绝对了。')
        self.assertEqual(self.s.call('philo_read',{'thread':c['thread']})['phase'],'review')
        self.assertEqual(self.s.call('philo_map',{})['positions'],[])
        with self.assertRaises(ValueError):
            self.reply(c,'keep','我不想保留这一版。')
    def test_reframe_prevents_a_former_answer_from_being_cited_as_new_evidence(self):
        a=self.answered();r=self.reply(a,'reframe','我要谈舞台灯光');self.assertIsNone(r['last_answer']);
        with self.assertRaises(ValueError):self.reply(r,'distill','现在收束')
    def test_links_are_version_bound_and_discard_never_accepts(self):
        left=self.kept();a=self.answered();d=self.reply(a,'distill','先帮我整理这次的想法');p=self.packet(d,connection={'thread':left['thread'],'relation':'refines','why':'把这句话限制到有撤回时间的情况。'});c=self.op('candidate',d,**p)
        self.assertFalse(self.s.call('philo_map',{})['links']);right=self.reply(c,'keep','保留这一版');self.assertTrue(self.s.call('philo_map',{})['links'][0]['target_current'])
        self.reply(left,'withdraw','退回这个观点');self.assertFalse(self.s.call('philo_map',{})['links'][0]['target_current'])
        new=self.reply(right,'distill','先帮我整理这次的想法');draft=self.op('candidate',new,**self.packet(new,claim='不同草案'));discard=self.reply(draft,'discard','不要这份草案');self.assertEqual(discard['position']['claim'],right['position']['claim']);

if __name__=='__main__':unittest.main()
