'use strict';
const M=require('../src/model.js');
async function main(){
  const [command,...rest]=process.argv.slice(2);
  if(rest.length||!['demo','check','read','--help'].includes(command)) throw new Error('Usage: node tools/notebook.cjs demo | check | read | --help');
  if(command==='--help'){console.log('demo: emit a fictional notebook; check/read: validate or render a private notebook from stdin. No file writes.');return;}
  if(command==='demo'){console.log(JSON.stringify(require('../examples/reading-circle.js')(M),null,2));return;}
  const chunks=[];let size=0;
  for await(const chunk of process.stdin){size+=chunk.length;if(size>M.LIMITS.bytes+2) throw new Error('Notebook exceeds two MiB'); chunks.push(chunk);}
  const b=JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(Buffer.concat(chunks))); M.replay(b);
  if(command==='check') console.log(JSON.stringify({format:b.format,events:b.events.length,structurallyValid:true}));
  else process.stdout.write(M.markdown(b));
}
main().catch(e=>{console.error(e.message);process.exitCode=2;});
