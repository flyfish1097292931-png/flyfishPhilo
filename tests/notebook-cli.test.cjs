'use strict';
const test=require('node:test'), assert=require('node:assert/strict'), path=require('node:path');
const {spawnSync}=require('node:child_process'); const root=path.join(__dirname,'..');
const cli=(cmd,input='')=>spawnSync(process.execPath,[path.join(root,'tools/notebook.cjs'),cmd],{input,encoding:'utf8'});
test('portable demo pipes to validator and a readable Markdown notebook',()=>{
  const d=cli('demo'); assert.equal(d.status,0,d.stderr);const b=JSON.parse(d.stdout);assert.equal(b.format,'flyfishPhilo/1');
  assert.deepEqual(b,JSON.parse(require('node:fs').readFileSync(path.join(root,'examples/reading-circle.json'),'utf8')),'non-JavaScript clients receive the same synthetic case');
  const check=cli('check',d.stdout);assert.equal(check.status,0,check.stderr);assert.equal(JSON.parse(check.stdout).events,b.events.length);
  const md=cli('read',d.stdout);assert.equal(md.status,0,md.stderr);assert.match(md.stdout,/当前内核/);
  const broken=cli('check','{}');assert.notEqual(broken.status,0);assert.equal(broken.stdout,'');
  assert.notEqual(cli('adopt',d.stdout).status,0);
});
