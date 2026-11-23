'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { createHash } = require('node:crypto');
const { spawnSync } = require('node:child_process');
const { join } = require('node:path');

const exe = join(__dirname, '..', 'tools', 'agent.cjs');
const run = (args, input) => spawnSync(process.execPath, [exe, ...args], {
  input: typeof input === 'string' ? input : JSON.stringify(input), encoding: 'utf8', timeout: 5000,
});
const format = 'flyfishPhilo/context-1';
const question = { id: 'e1', text: '沉默算作回答吗？' };
const notes = [{ id: 'e2', origin: 'synthetic', text: '虚构：乘客没有点头。' }];
// Independent digest: reference vector, not a private workbook or bridge output.
const base = createHash('sha256').update(JSON.stringify([
  format, [question.id, question.text], notes.map(n => [n.id, n.origin, n.text]),
])).digest('hex');
const context = { format, base, question, notes };
const proposal = { format: 'flyfishPhilo/proposal-1', base, question: 'e1', notes: ['e2'],
  kind: 'reading', text: '也许是在等待。', scope: '限于这一段虚构对话。', why: '没有明确约定。',
  rival: '也许没有听清。', test: '再问一次，看解释是否改变。' };

test('prompt consumes only a selected packet on stdin; stdout is copyable plain text', () => {
  const r = run(['prompt'], context);
  assert.equal(r.status, 0, r.stderr);
  assert.equal(r.stderr, '');
  for (const part of [question.text, notes[0].text, base, proposal.format, '自然语言', '不知道', '拒答']) {
    assert.ok(r.stdout.includes(part), `prompt missing ${part}`);
  }
});

test('check independently binds the exact packet; validation failures never echo input', () => {
  const good = run(['check'], { context, proposal });
  assert.equal(good.status, 0, good.stderr);
  assert.deepEqual(JSON.parse(good.stdout), { ok: true });
  for (const input of [
    { context, proposal: { ...proposal, action: 'adopt' } },
    { context, proposal: { ...proposal, notes: ['e99'] } },
    { context, proposal: { ...proposal, base: 'a'.repeat(64) } },
    { context: { ...context, notes: [{ ...notes[0], text: 'DO-NOT-ECHO' }] }, proposal },
    { context, proposal, book: { private: 'DO-NOT-ECHO' } },
    'DO-NOT-ECHO invalid json',
  ]) {
    const r = run(['check'], input);
    assert.equal(r.status, 1); assert.equal(r.stdout, ''); assert.ok(r.stderr); assert.doesNotMatch(r.stderr, /DO-NOT-ECHO/);
  }
  for (const bad of [ { ...context, kernel: 'DO-NOT-ECHO' }, { ...context, notes: [{ ...notes[0], source: 'DO-NOT-ECHO' }] }, { ...context, question:{ ...question, text: 'DO-NOT-ECHO' } } ]) {
    const r = run(['prompt'], bad);
    assert.equal(r.status, 1); assert.equal(r.stdout, ''); assert.doesNotMatch(r.stderr, /DO-NOT-ECHO/);
  }
  assert.equal(run(['prompt', 'path-not-permitted'], context).status, 2);
});

test('local context/apply use explicitly trusted inputs and write only to stdout', () => {
  const model = require('../src/model.js');
  let book = model.append(model.blank(), 'question', { text: question.text });
  book = model.append(book, 'note', {question: 'e1', origin: 'synthetic', source: 'DO-NOT-ECHO', text: notes[0].text});
  const selected = run(['context'], { book, question: 'e1', notes: ['e2'] });
  assert.equal(selected.status, 0, selected.stderr); assert.deepEqual(JSON.parse(selected.stdout), context);
  assert.equal(run(['context'], { book, question: 'e1' }).status, 1);
  const applied = run(['apply'], { book, context, proposal });
  assert.equal(applied.status, 0, applied.stderr);
  const updated = JSON.parse(applied.stdout);
  assert.equal(updated.events.at(-1).type, 'suggest'); assert.equal(model.replay(updated).ideas.e3.adopted, false);
  assert.equal(run(['apply'], { book:updated, context, proposal }).status, 1);
  assert.equal(run(['apply'], { book, proposal }).status, 1);
  const newer = model.append(book, 'reword', {question: 'e1', text:'问法已经改变。'});
  assert.equal(run(['apply'], {book:newer,context,proposal}).status, 1);
  const large = run(['check'], ' '.repeat(4 * 1024 * 1024) + JSON.stringify({ context, proposal }));
  assert.equal(large.status, 1); assert.equal(large.stdout, '');
});

test('--help distinguishes packet operations from private workbook operations', () => {
  const help = run(['--help'], '');
  assert.equal(help.status, 0); assert.equal(help.stderr, '');
  for (const word of ['context','prompt','check','apply','book','proposal']) assert.ok(help.stdout.includes(word));
  assert.equal(run(['--unknown'],'').status,2);
});

test('independent Draft 2020-12 validator accepts the examples and rejects out-of-contract data', {
  skip: process.env.PHILO_SCHEMA_PYTHON ? false : 'set PHILO_SCHEMA_PYTHON to a Python with jsonschema',
}, t => {
  const suite = [
    [require('../schemas/context-v1.json'),context,[{...context,kernel:'x'}, {...context,notes:[]},
      {...context,notes:[{...notes[0],source:'x'}]}, {...context,question:{...question,id:'e1\n'}}, {...context,base:'A'.repeat(64)}]],
    [require('../schemas/proposal-v1.json'),proposal,[{...proposal,adopt:true}, {...proposal,kind:'execute'}, {...proposal,notes:[]},
      {...proposal,notes:['e2','e2']}, {...proposal,scope:' '}, {...proposal,test:'x'.repeat(6001)}]],
  ];
  const verify = `
import json, sys
from importlib.metadata import version
from jsonschema import Draft202012Validator as Validator
for schema, good, bad in json.load(sys.stdin):
    Validator.check_schema(schema)
    v = Validator(schema); v.validate(good)
    assert all(not v.is_valid(x) for x in bad)
print('jsonschema',version('jsonschema'),'both Draft 2020-12 schemas and positive/negative fixtures OK')`;
  const r = spawnSync(process.env.PHILO_SCHEMA_PYTHON,['-B','-c',verify],{input:JSON.stringify(suite),encoding:'utf8',timeout:10000});
  assert.equal(r.status,0,r.stderr || r.error?.message); t.diagnostic(r.stdout.trim());
});
