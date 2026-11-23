'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const { spawnSync } = require('node:child_process');
const { join } = require('node:path');
const { createHash } = require('node:crypto');
const exe = join(__dirname, '..', 'tools', 'mcp.cjs');
const version = '2025-06-18';
const rpc = (id, method, params) => ({ jsonrpc: '2.0', ...(id === undefined ? {} : {id}), method, params });
const init = v => rpc(1, 'initialize', { protocolVersion: v, capabilities: {}, clientInfo: { name: 'test-client', version: '1' } });
const initialized = rpc(undefined, 'notifications/initialized');
test('legacy stdio hosts can negotiate the 2024-11-05 tools subset directly',()=>{
  const [hello,list]=exchange(init('2024-11-05'), initialized, rpc(2,'tools/list'));
  assert.equal(hello.result.protocolVersion,'2024-11-05');assert.equal(list.result.tools.length,2);
});
function exchange(...messages) {
  const lines = messages.map(x => typeof x === 'string' ? x : JSON.stringify(x));
  const r = spawnSync(process.execPath, [exe], { input: lines.join('\n') + '\n', encoding: 'utf8', timeout: 5000, maxBuffer: 2**20 });
  assert.equal(r.status, 0, r.stderr || r.error?.message);
  assert.equal(r.stderr, '');
  return r.stdout.trim().split('\n').filter(Boolean).map(line => JSON.parse(line));
}

test('stdio negotiates the preferred version for an unknown request and waits for ready', () => {
  for (const requested of [version, '2099-01-01']) {
    const [before, hello, early, list, ping] = exchange(rpc(0,'tools/list'), init(requested), rpc(2,'tools/list'), initialized, rpc(3,'tools/list'), rpc(4,'ping'));
    assert.ok(before.error); assert.ok(early.error);
    assert.equal(hello.result.protocolVersion, version);
    assert.deepEqual(hello.result.capabilities, { tools: {} });
    assert.equal(list.id, 3);
    assert.deepEqual(list.result.tools.map(t => t.name).sort(), ['check_proposal','format_prompt']);
    assert.deepEqual(ping, { jsonrpc: '2.0', id: 4, result: {} });
  }
});

test('published standalone schemas close both packets; advertised tool inputs embed them', () => {
  const ctx = require('../schemas/context-v1.json');
  const prop = require('../schemas/proposal-v1.json');
  for (const s of [ctx, prop]) {
    assert.equal(s.$schema, 'https://json-schema.org/draft/2020-12/schema');
    assert.equal(s.additionalProperties, false);
    assert.deepEqual([...s.required].sort(), Object.keys(s.properties).sort());
    assert.equal(s.properties.base.maxLength, 64);
    assert.equal(s.properties.notes.minItems, 1);
  }
  assert.equal(ctx.properties.question.additionalProperties, false);
  assert.equal(ctx.properties.notes.items.additionalProperties, false);
  assert.equal(prop.properties.notes.uniqueItems, true);
  const [, response] = exchange(init(version), initialized, rpc(7, 'tools/list'));
  for (const {name, inputSchema: s} of response.result.tools) {
    assert.equal(s.additionalProperties, false);
    assert.deepEqual(s.properties.context.properties, ctx.properties);
    assert.deepEqual(s.required.sort(), name === 'format_prompt' ? ['context'] : ['context','proposal']);
    if (name === 'check_proposal') assert.deepEqual(s.properties.proposal.properties, prop.properties);
  }
});

const format = 'flyfishPhilo/context-1';
const q = {id:'e1', text:'沉默是不是回答？'}, n = {id:'e2', origin:'synthetic', text:'虚构的短暂停顿。'};
const base = createHash('sha256').update(JSON.stringify([format,[q.id,q.text],[[n.id,n.origin,n.text]]])).digest('hex');
const context = {format,base,question:q,notes:[n]};
const proposal = {format:'flyfishPhilo/proposal-1',base,question:q.id,notes:[n.id],kind:'reading',text:'可能在想。',scope:'仅限此段。',why:'有停顿。',rival:'可能没听清。',test:'请对方复述。'};
const call = (id,name,args) => rpc(id,'tools/call',{name,arguments:args});

test('tools operate independently on supplied packets; no write, book, path or higher permissions', () => {
  const reqs = [call(10,'check_proposal',{context,proposal}), call(11,'format_prompt',{context}),
    call(12,'check_proposal',{context,proposal:{...proposal,base:'a'.repeat(64)}}),
    call(13,'check_proposal',{proposal}), call(14,'format_prompt',{context:{...context,book:{private:'KEEP-LOCAL'}}}),
    call(15,'format_prompt',{context,path:'KEEP-LOCAL'}), call(16,'apply',{context,proposal}),
    call(17,'check_proposal',{context,proposal:{...proposal,adopt:true}}),
    call(18,'format_prompt',{context:{...context,question:{...q,text:'KEEP-LOCAL'}}}), rpc(19,'resources/list'),
    call(20,'format_prompt',{context:{format:'flyfishPhilo/1',events:[]}})];
  const [hello, checked, formatted, ...rejections] = exchange(init(version), initialized, ...reqs);
  assert.equal(hello.result.protocolVersion,version);
  assert.deepEqual(JSON.parse(checked.result.content[0].text),{ok:true});
  assert.equal(formatted.result.content[0].type,'text'); assert.ok(formatted.result.content[0].text.includes(n.text));
  assert.deepEqual(rejections.map(x=>x.id),reqs.slice(2).map(x=>x.id));
  for (const reply of rejections) {
    assert.ok(reply.error || reply.result?.isError, `unexpected success for ${reply.id}`);
    assert.doesNotMatch(JSON.stringify(reply),/KEEP-LOCAL/);
  }
});

test('malformed or oversized frames fail locally without desynchronizing following requests', () => {
  const big = ' '.repeat(4 * 1024 * 1024) + JSON.stringify(rpc(88,'ping'));
  const replies = exchange('not-json', [], rpc(null,'ping'), init(version), initialized,
    rpc(undefined,'notifications/ignored'), big, rpc(8,'ping'));
  assert.deepEqual(replies.slice(0,3).map(r=>r.error.code), [-32700,-32600,-32600]);
  assert.equal(replies.length,6);
  assert.ok(replies[4].error); assert.equal(replies[4].id,null);
  assert.deepEqual(replies[5], {jsonrpc:'2.0',id:8,result:{}});
});

// Opt-in independent client; neither Python nor the official SDK is a runtime dependency.
test('independent official Python MCP client negotiates, lists, calls and rejects', {
  skip: process.env.PHILO_MCP_PYTHON ? false : 'set PHILO_MCP_PYTHON to a Python with the official mcp SDK',
}, t => {
  const client = `
import asyncio, json, sys
from importlib.metadata import version
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
c, p = json.load(sys.stdin)
async def run():
    server = StdioServerParameters(command=sys.argv[1], args=[sys.argv[2]])
    async with stdio_client(server) as (read, write), ClientSession(read, write) as session:
        hello = (await session.initialize()).model_dump(by_alias=True)
        assert hello['protocolVersion'] == sys.argv[3], hello['protocolVersion']
        assert sorted(t.name for t in (await session.list_tools()).tools) == ['check_proposal', 'format_prompt']
        prompt = await session.call_tool('format_prompt', {'context': c})
        assert not prompt.model_dump(by_alias=True).get('isError') and c['base'] in prompt.content[0].text
        check = await session.call_tool('check_proposal', {'context': c, 'proposal': p})
        assert not check.model_dump(by_alias=True).get('isError') and json.loads(check.content[0].text) == {'ok': True}
        bad = await session.call_tool('check_proposal', {'context': c, 'proposal': dict(p, base='0'*64)})
        assert bad.model_dump(by_alias=True).get('isError') is True
        print('official Python mcp', version('mcp'), 'protocol', hello['protocolVersion'], 'list + format + check + rejection OK')
asyncio.run(run())`;
  const r = spawnSync(process.env.PHILO_MCP_PYTHON, ['-B','-c', client, process.execPath, exe,process.env.PHILO_MCP_EXPECT_VERSION || version], {
    input: JSON.stringify([context,proposal]), encoding:'utf8',timeout:20000,
  });
  assert.equal(r.status,0,r.stderr || r.error?.message); t.diagnostic(r.stdout.trim());
});
