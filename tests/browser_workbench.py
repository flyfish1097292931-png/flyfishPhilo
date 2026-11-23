"""Optional acceptance test on the actual offline distribution, not a fixture UI.

Requires Python Playwright and the chosen installed browser. No model or network.
Run: python tests/browser_workbench.py chromium --channel chrome
"""
import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
btn = lambda p, name: p.get_by_role('button', name=name, exact=True)
field = lambda p, name: p.locator('#sheet').get_by_label(name, exact=True)

def pull(p, name, filename):
    with p.expect_download() as wait:
        btn(p, name).click()
    obj=wait.value
    assert obj.suggested_filename==filename and obj.failure() is None
    return Path(obj.path()).read_bytes()

def book(p):
    return json.loads(pull(p,'下载完整 JSON','flyfishPhilo-notebook.json'))

def layout(p):
    assert p.evaluate('document.documentElement.scrollWidth <= innerWidth+1')
    assert p.evaluate("[...document.querySelectorAll('select,textarea,input')].every(x=>x.labels.length)")

def share(p, shots):
    pair=json.loads((ROOT/'examples/agent-roundtrip.json').read_bytes())
    fixture=json.loads((ROOT/'examples/reading-circle.json').read_bytes())
    btn(p,'体验虚构读书会').click(); assert book(p)==fixture
    btn(p,'与任意 AI 协作').click()
    assert not p.locator('#sheet input:checked').count()
    selected_packet=btn(p,'下载所选资料 JSON'); expect(selected_packet).to_be_disabled()
    issue=btn(p,'生成外发预览');expect(issue).to_be_disabled()
    p.locator('[name=share-question]').check()
    for item in ['e3','e2']: p.locator('[name=share-note][value='+item+']').check()
    issue.click(); preview=field(p,'完整外发预览');expect(preview).to_be_visible()
    assert pair['context']['base'] in preview.input_value() and '新读者写道' not in preview.input_value()
    packet=json.loads(pull(p,'下载所选资料 JSON','flyfishPhilo-context.json'));assert packet==pair['context']
    if shots: p.screenshot(path=str(shots/'selected-material.png'))
    p.locator('[name=share-note][value=e2]').uncheck();expect(selected_packet).to_be_disabled();expect(preview).to_be_hidden()
    p.locator('[name=share-note][value=e2]').check();issue.click();expect(preview).to_be_visible()
    btn(p,'粘贴 AI 提案 JSON').click(); prop=field(p,'AI 提案 JSON')
    prop.fill(json.dumps(fixture,ensure_ascii=False));btn(p,'校验并记入候选').click();expect(p.locator('#sheet-error')).to_contain_text('不能恢复整本')
    prop.fill(json.dumps(pair['proposal'],ensure_ascii=False));btn(p,'校验并记入候选').click();expect(p.locator('.idea[open] > summary')).to_contain_text('候选 · 未采纳')
    after=book(p); assert after['events'][:-1]==fixture['events'] and after['events'][-1]['type']=='suggest'
    btn(p,'与任意 AI 协作').click();btn(p,'粘贴 AI 提案 JSON').click();field(p,'AI 提案 JSON').fill(json.dumps(pair['proposal'],ensure_ascii=False));btn(p,'校验并记入候选').click();expect(p.locator('#sheet-error')).to_contain_text('重复')
    btn(p,'关闭').click();btn(p,'放弃此次输入').click();assert book(p)==after
    btn(p,'与任意 AI 协作').click();btn(p,'手工保存 AI 文字').click();field(p,'AI 回复来源').fill('虚构聊天');field(p,'AI 回复原文').fill('另一种读法：也许只是更熟悉楼梯口的人。');btn(p,'保存为待审解释').click()
    end=book(p);assert end['events'][-1]['type']=='note' and end['events'][-1]['origin']=='ai'
    btn(p,'手记文件').click(); picker=field(p,'选择完整 JSON 文件')
    picker.set_input_files({'name':'proposal.json','mimeType':'application/json','buffer':json.dumps(pair['proposal']).encode()});expect(p.locator('#sheet-error')).to_contain_text('当前内容未改变')
    picker.set_input_files({'name':'original.json','mimeType':'application/json','buffer':json.dumps(fixture,ensure_ascii=False).encode()});expect(p.locator('#guard')).to_be_visible();btn(p,'取消，保留原稿').click();btn(p,'关闭').click();assert book(p)==end
    btn(p,'手记文件').click();picker.set_input_files({'name':'original.json','mimeType':'application/json','buffer':json.dumps(fixture,ensure_ascii=False).encode()});btn(p,'打开导入手记并替换').click();assert book(p)==fixture
    btn(p,'手记文件').click();md=pull(p,'导出 Markdown 阅读稿','flyfishPhilo-notes.md').decode();assert '已撤回' in md and '竞争解释' in md

def suspend(p, shots):
    btn(p,'体验虚构读书会').click();btn(p,'悬置问题').click()
    if p.locator('#summary-e13').locator('..').get_attribute('open') is None: p.locator('#summary-e13').click()
    btn(p,'登记反例').click();field(p,'用哪条片段检验').select_option('e10'); field(p,'发生了什么，这对说法有什么影响？').fill('虚构：更改入场方式仍有代价。');btn(p,'记入检验').click()
    expect(p.locator('#summary-e13')).to_contain_text('遇到反例');assert btn(p,'记录试行').count()==0
    btn(p,'本人撤回').click();field(p,'撤回的理由').fill('暂时不再采用。');assert not p.locator('[name=consent]').is_checked();btn(p,'确认撤回').click();expect(p.locator('#sheet')).to_be_visible();p.locator('[name=consent]').check();btn(p,'确认撤回').click()
    b=book(p);assert [e['type'] for e in b['events'][-3:]]==['rest','challenge','withdraw']
    btn(p,'观点连线').click();expect(p.get_by_text('→ 以其为前提 →',exact=True)).to_be_visible();p.locator('.relation-line button').filter(has_text='e18').click();expect(p.locator('#current-question')).to_contain_text('自由');expect(p.locator('#summary-e18')).to_contain_text('候选 · 未采纳')

def fresh(p, shots):
    p.set_viewport_size({'width':342,'height':684});layout(p)
    if shots: p.screenshot(path=str(shots/'welcome-mobile.png'))
    p.get_by_label('你的第一个问题',exact=True).fill('有多少种方式加入讨论？');btn(p,'开始手记').click();btn(p,'记片段').click();field(p,'材料性质').select_option('synthetic');field(p,'出处').fill('虚构课堂');field(p,'片段原文或记录').fill('甲写了一张纸条。');btn(p,'记入片段').click()
    btn(p,'保留念头').click();field(p,'这个念头').fill('写也许是一种加入。');btn(p,'记下念头').click();btn(p,'从这个念头起草').click()
    field(p,'候选种类').select_option('practice')
    for k,v in [('候选说法','下次加一个纸条入口。'),('适用边界','小组讨论'),('理由','看见纸上的问题。'),('另一种解释','可能是怕打断。'),('怎样检验或推翻','观察纸条是否被阅读。')]: field(p,k).fill(v)
    p.locator('[name=notes]').check();btn(p,'记入候选').click();assert btn(p,'本人采纳').count()==0
    btn(p,'添加检验').click();field(p,'用哪条片段检验').select_option('e2');field(p,'检验结果').select_option('limit');field(p,'发生了什么，这对说法有什么影响？').fill('记录限于这组。');btn(p,'记入检验').click();btn(p,'本人采纳').click();field(p,'冲突审查').fill('不替沉默者断言意图。');field(p,'我采纳这一版的理由').fill('本人愿试一次。');assert not p.locator('[name=consent]').is_checked();p.locator('[name=consent]').check();btn(p,'确认采纳').click()
    btn(p,'记录试行').click();field(p,'这一次具体做什么？').fill('准备纸条。');btn(p,'记入试行').click();btn(p,'修订为新版本').click();btn(p,'另存为新版本').click();expect(p.locator('#sheet-error')).to_contain_text('修订须改变');field(p,'适用边界').fill('仅在线下小组讨论');btn(p,'另存为新版本').click()
    events=book(p)['events'];assert [e['type'] for e in events]==['question','note','seed','idea','challenge','adopt','trial','idea'];assert events[-1]['previous']=='e4';layout(p)

def main():
    cli=argparse.ArgumentParser(description=__doc__);cli.add_argument('engine',choices=['chromium','firefox','webkit']);cli.add_argument('--channel');cli.add_argument('--executable');cli.add_argument('--html',type=Path,default=ROOT/'index.html');cli.add_argument('--shots',type=Path);cli.add_argument('--case',choices=['share','suspend','fresh']);args=cli.parse_args()
    if args.shots: args.shots.mkdir(exist_ok=True,parents=True)
    with sync_playwright() as pw, TemporaryDirectory() as tmp:
        opts={'headless':True,'downloads_path':tmp};opts.update({'channel':args.channel} if args.channel else {});opts.update({'executable_path':args.executable} if args.executable else {})
        browser=getattr(pw,args.engine).launch(**opts);results=[]
        for name,fn in [('share',share),('suspend',suspend),('fresh',fresh)]:
            if args.case and args.case!=name: continue
            ctx=browser.new_context(offline=True,locale='zh-CN',viewport={'width':1280,'height':832});p=ctx.new_page();p.set_default_timeout(4000);errors=[];remote=[]
            p.on('pageerror',lambda e:errors.append(str(e)));p.on('console',lambda m:errors.append(m.text) if m.type=='error' else None);p.on('request',lambda r:remote.append(r.url) if r.url.split(':')[0] in ('https','http','wss','ws') else None)
            try:
                p.goto(args.html.resolve().as_uri());expect(p.get_by_role('heading',name='从一个问题开始。')).to_be_visible();layout(p)
                if args.shots and name=='share': p.screenshot(path=str(args.shots/'welcome-desktop.png'))
                fn(p,args.shots);assert not errors and not remote,(errors,remote);results.append(name)
            finally: ctx.close()
        print(json.dumps({'engine':args.engine,'version':browser.version,'offline':True,'scenarios':results,'runtimeErrors':0,'remoteRequests':0}));browser.close()
if __name__=='__main__': main()
