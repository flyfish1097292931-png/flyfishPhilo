'use strict';
// Build one transferable HTML file. The expanded file needs neither Node nor a server.
const fs=require('node:fs'), path=require('node:path'), crypto=require('node:crypto');
function assemble(shell,css,scripts) {
  const hash=t=>"'sha256-"+crypto.createHash('sha256').update(t,'utf8').digest('base64')+"'";
  if(/<\/style/i.test(css) || scripts.some(s=>/<\/script/i.test(s))) throw new Error('Unexpected HTML end tag inside source');
  const policy=`default-src 'none'; script-src ${scripts.map(hash).join(' ')}; style-src ${hash(css)}; connect-src 'none'; img-src data:; form-action 'none'; object-src 'none'; base-uri 'none'`;
  const slots={CSP:`<meta http-equiv="Content-Security-Policy" content="${policy}">`,STYLE:`<style>${css}</style>`,SCRIPTS:scripts.map(s=>`<script>${s}</script>`).join('\n')};
  for(const [key,body] of Object.entries(slots)) {const mark=`<!--${key}-->`;if(shell.split(mark).length!==2)throw new Error(`Missing or repeated ${mark}`);shell=shell.replace(mark,()=>body);}
  return shell;
}
function main(){
  const args=process.argv.slice(2);if(args.length>1 || (args.length&&args[0]!=='--check'))throw new Error('Usage: node tools/build.cjs [--check]');
  const root=path.join(__dirname,'..'), read=f=>fs.readFileSync(path.join(root,f),'utf8').replaceAll('\r\n','\n');
  const s=assemble(read('ui/shell.html'),read('ui/style.css'),['src/model.js','src/bridge.js','examples/reading-circle.js','ui/app.js'].map(read))+'\n<!--\n'+read('LICENSE')+'-->\n';
  const out=path.join(root,'index.html');
  if(args[0]==='--check'){if(!fs.existsSync(out)||fs.readFileSync(out,'utf8')!==s)throw new Error('index.html absent or stale; run node tools/build.cjs');}
  else fs.writeFileSync(out,s);
  console.log((args.length?'verified':'built')+' index.html · SHA-256 '+crypto.createHash('sha256').update(s).digest('hex'));
}
module.exports={assemble};
if(require.main===module)try{main();}catch(err){console.error(err.message);process.exitCode=1;}
