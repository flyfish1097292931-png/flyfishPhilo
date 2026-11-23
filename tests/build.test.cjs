'use strict';
const test=require('node:test'), assert=require('node:assert/strict'), fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const tool=path.join(__dirname,'../tools/build.cjs'); const bundle=fs.existsSync(tool)?require(tool).assemble:undefined;
test('offline build binds CSS/JS to actual inline hashes and leaves no dependencies',()=>{
  assert.equal(typeof bundle,'function','need the offline assembler');
  const html=bundle('<html><head><!--CSP--><!--STYLE--></head><body><!--SCRIPTS--></body></html>','p{color:green}', ['const x="$&";', 'void 0;']);
  for(const tag of ['style','script']) for(const m of html.matchAll(new RegExp(`<${tag}>([\\s\\S]*?)</${tag}>`,'g'))){const h=crypto.createHash('sha256').update(m[1]).digest('base64');assert.ok(html.includes(`'sha256-${h}'`));}
  assert.match(html,/connect-src 'none'/);assert.ok(html.includes('const x="$&";'));assert.doesNotMatch(html,/<!--(?:SCRIPTS|STYLE|CSP)-->/);
  assert.throws(()=>bundle('<!--STYLE-->','x',[]));
});
