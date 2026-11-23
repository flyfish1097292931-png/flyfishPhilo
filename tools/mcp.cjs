#!/usr/bin/env node
'use strict';
const { once } = require('node:events');
const bridge = require('../src/bridge.js');
const version = '2025-06-18';
const context = require('../schemas/context-v1.json');
const proposal = require('../schemas/proposal-v1.json');
const tools = [
  { name: 'format_prompt', description: 'Format a user-selected context as a plain-text prompt. Does not call a model.', properties: { context } },
  { name: 'check_proposal', description: 'Validate a candidate against a user-selected context. Does not read or change a notebook.', properties: { context, proposal } },
].map(({name, description, properties}) => ({ name, description,
  inputSchema: {type: 'object', properties, required: Object.keys(properties), additionalProperties: false} }));
const object = x => !!x && typeof x === 'object' && !Array.isArray(x);
const allowed = (x, keys) => object(x) && Object.keys(x).every(k => keys.includes(k));
const fail = (id, code, message) => ({ jsonrpc: '2.0', id, error: {code, message} });
const ok = (id, result) => ({ jsonrpc: '2.0', id, result });
let phase = 'new'; // Protocol lifecycle only; never retain packets or proposals.

async function handle(msg) {
  if (!object(msg) || msg.jsonrpc !== '2.0' || typeof msg.method !== 'string' ||
      ('id' in msg && !(typeof msg.id === 'string' || Number.isSafeInteger(msg.id)))) return fail(null,-32600,'Invalid request');
  const {id, method, params} = msg;
  if (id === undefined) {
    if (method === 'notifications/initialized' && phase === 'negotiated') phase = 'ready';
    return; // No reply to notifications, including unknown ones.
  }
  if (method === 'ping') return ok(id, {});
  if (method === 'initialize') {
    if (phase !== 'new') return fail(id,-32600,'Already initialized');
    if (!object(params) || typeof params.protocolVersion !== 'string' || !params.protocolVersion || !object(params.capabilities) ||
        !object(params.clientInfo) || typeof params.clientInfo.name !== 'string' || typeof params.clientInfo.version !== 'string') return fail(id,-32602,'Invalid initialize parameters');
    phase = 'negotiated';
    // Both revisions share the unpaginated text-tools subset used here.
    const negotiated = params.protocolVersion === '2024-11-05' ? '2024-11-05' : version;
    return ok(id, {protocolVersion: negotiated, capabilities: {tools:{}}, serverInfo: {name:'flyfishPhilo',version:'0.1.0'}});
  }
  if (method !== 'tools/list' && method !== 'tools/call') return fail(id,-32601,'Method not found');
  if (phase !== 'ready') return fail(id,-32002,'Server not initialized');
  if (method === 'tools/list') {
    if (params !== undefined && !allowed(params, ['_meta'])) return fail(id,-32602,'Invalid list parameters (no pagination)');
    return ok(id,{tools});
  }
  if (!allowed(params, ['name','arguments','_meta'])) return fail(id,-32602,'Invalid call parameters');
  const tool = tools.find(t => t.name === params.name);
  if (!tool) return fail(id,-32602,'Unknown tool');
  const args = params.arguments, keys = tool.inputSchema.required;
  if (!allowed(args, keys) || !keys.every(k => Object.hasOwn(args,k))) return fail(id,-32602,'Invalid tool arguments');
  try {
    const text = tool.name === 'format_prompt' ? bridge.prompt(await bridge.verifyContext(args.context))
      : JSON.stringify(await bridge.check(args.context,args.proposal));
    return ok(id,{content:[{type:'text',text}]});
  } catch (err) {
    return ok(id,{isError:true,content:[{type:'text',text:err instanceof bridge.BridgeError ? err.message : 'Invalid input'}]});
  }
}

// Drop oversized frames while reading, then resume at the next LF. Do not retain an unbounded line.
async function* frames(stream) {
  const limit = 4 * 1024 * 1024;
  let parts = [], bytes = 0;
  for await (const chunk of stream) {
    for (let start = 0; start < chunk.length;) {
      const lf = chunk.indexOf(10,start), end = lf < 0 ? chunk.length : lf;
      if (parts !== null) {
        bytes += end - start;
        if (bytes > limit) parts = null;
        else if (end > start) parts.push(chunk.subarray(start,end));
      }
      if (lf < 0) break;
      yield parts === null ? null : Buffer.concat(parts,bytes);
      parts = []; bytes = 0; start = lf + 1;
    }
  }
  if (bytes) yield parts === null ? null : Buffer.concat(parts,bytes);
}
async function main() {
  const utf8 = new TextDecoder('utf-8',{fatal:true});
  for await (const frame of frames(process.stdin)) {
    let msg, reply;
    if (frame === null) reply = fail(null,-32600,'Frame exceeds 4 MiB');
    else try { msg = JSON.parse(utf8.decode(frame)); } catch { reply = fail(null,-32700,'Parse error'); }
    reply ??= await handle(msg);
    if (reply && !process.stdout.write(JSON.stringify(reply) + '\n')) await once(process.stdout,'drain');
  }
}
main().catch(() => { process.exitCode = 1; });
