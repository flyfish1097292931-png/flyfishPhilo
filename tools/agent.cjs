#!/usr/bin/env node
'use strict';
const bridge = require('../src/bridge.js');

async function main(args) {
  const command = args[0];
  if (args.length === 1 && (command === '--help' || command === '-h')) {
    process.stdout.write('Node 22; UTF-8 JSON on stdin, result on stdout. No file arguments.\n' +
      'prompt   context -> plain text\ncheck    {context,proposal} -> {"ok":true}\n' +
      'Trusted local user only (private book; never a model tool):\n' +
      'context  {book,question,notes} -> selected context\napply    {book,context,proposal} -> new book (AI candidate only)\n');
    return;
  }
  if (args.length !== 1 || !['prompt','check','context','apply'].includes(command)) {
    process.stderr.write('Usage: node tools/agent.cjs prompt|check|context|apply < input.json\n');
    process.exitCode = 2;
    return;
  }
  const chunks = []; let bytes = 0;
  for await (const chunk of process.stdin) {
    bytes += chunk.length;
    if (bytes > 4 * 1024 * 1024) throw new bridge.BridgeError('输入超过 4 MiB。');
    chunks.push(chunk);
  }
  const input = JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(Buffer.concat(chunks)));
  let output;
  if (command === 'prompt') {
    output = bridge.prompt(await bridge.verifyContext(input));
  } else if (command === 'check') {
    fields(input, ['context','proposal']);
    output = JSON.stringify(await bridge.check(input.context, input.proposal));
  } else if (command === 'context') {
    fields(input, ['book','question','notes']);
    output = JSON.stringify(await bridge.context(input.book, input.question, input.notes));
  } else {
    fields(input, ['book','context','proposal']);
    // The local user supplies the original packet, separately from the model's proposal.
    await bridge.check(input.context, input.proposal);
    await bridge.context(input.book, input.context.question.id, input.context.notes.map(n => n.id));
    output = JSON.stringify(await bridge.apply(input.book, input.proposal));
  }
  process.stdout.write(output + '\n');
}
function fields(value, keys) {
  if (!value || typeof value !== 'object' || Array.isArray(value) || Object.keys(value).length !== keys.length || !keys.every(k => Object.hasOwn(value,k))) {
    throw new bridge.BridgeError('输入字段缺失或多余。');
  }
}
main(process.argv.slice(2)).catch(err => {
  // JSON parser and core errors can contain fragments of the private input.
  process.stderr.write((err instanceof bridge.BridgeError ? err.message : '输入不是有效的 JSON 或手记。') + '\n');
  process.exitCode = 1;
});
