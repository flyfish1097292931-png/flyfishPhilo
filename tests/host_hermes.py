#!/usr/bin/env python3
"""Optional offline integration check against an installed Hermes Agent (not an MCP SDK test).

python3 tests/host_hermes.py --hermes-src "$HERMES_SRC" \
    --hermes-python "$HERMES_PYTHON" --scratch "$SCRATCH"

Uses only public skill files, synthetic turns, and two empty HOME/HERMES_HOME pairs.
The controller needs only stdlib; the host interpreter must already have Hermes' MCP dependencies.
Keeps a receipt and disposable state under --scratch. No model is involved.
"""
import argparse
import hashlib
import inspect
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import uuid

SKILL = 'flyfish-philo'
SERVER = 'philoqa'
FILES = ('SKILL.md', 'scripts/philo.py', 'scripts/dialogue.py')
TOOLS = {'philo_' + s for s in ('open', 'read', 'ask', 'reply', 'candidate', 'map')}
MARKER = 'HOST_QA_RECEIPT '
INITIAL_ANCHOR = '偶然一致'
ANSWER = '若两个钟受同一齿轮驱动，即使读数相同也只有一个来源。'
NEXT_ANCHOR = '同一齿轮驱动'
FOLLOWUP = '若要排除「同一齿轮驱动」，你会做哪一种观察？'


def check(ok, message):
    if not ok:
        raise RuntimeError(message)


def host_worker(stage, thread=None):
    """Called only in an isolated *new* host interpreter; no app modules imported here."""
    root = Path.cwd()
    profile = root / 'home' / '.hermes'
    check((root / '.philo-qa').is_file() and Path.home() == root / 'home'
          and Path(os.environ['HERMES_HOME']) == profile, 'refusing a non-test HOME')
    from hermes_constants import get_hermes_home
    from hermes_cli.config import load_config_readonly
    from hermes_cli.plugins_discovery import suppress_plugin_discovery
    from tools import skills_tool  # registers Hermes' own skills_list and skill_view handlers
    from tools.mcp_tool_discovery import discover_mcp_tools
    from tools.mcp_tool_lifecycle import shutdown_mcp_servers
    from tools.registry import registry

    installed = profile / 'skills' / SKILL
    source = Path(os.environ['PYTHONPATH'])
    origins = [Path(inspect.getfile(obj)).resolve().relative_to(source).as_posix()
               for obj in (discover_mcp_tools, type(registry), skills_tool.skill_view)]
    check(get_hermes_home().resolve() == profile, 'Hermes did not select the isolated profile')
    servers = load_config_readonly()['mcp_servers']
    check(set(servers) == {SERVER} and servers[SERVER]['args'] == [str(installed / FILES[1]),
          '--store', str(root.parent / 'shared.sqlite3'), 'mcp'], 'unexpected server config')
    prefix = 'mcp__' + SERVER + '__'
    expected = {prefix + name for name in TOOLS}
    receipt = {'pid': os.getpid(), 'profile': str(profile), 'host_modules': origins,
               'host_python': sys.version.split()[0], 'stage': stage, 'calls': []}

    def dispatch(name, args):
        result = registry.dispatch(name, args)
        return json.loads(result) if isinstance(result, str) else result

    def call(name, args, *, reject=False):
        envelope = dispatch(prefix + name, args)
        result = envelope if 'error' in envelope else json.loads(envelope['result'])
        error = isinstance(result, dict) and ('error' in result or result.get('ok') is False)
        check(bool(error) == reject, '%s unexpected result: %r' % (name, result))
        if reject:
            detail = json.dumps(result, ensure_ascii=False).lower()
            check('reject' in detail or 'anchor' in detail, 'not a dialogue rejection: ' + detail)
        receipt['calls'].append(name + (':rejected' if reject else ''))
        return result

    with suppress_plugin_discovery():
        try:
            index = dispatch('skills_list', {})
            check(index.get('success') and [s['name'] for s in index['skills']] == [SKILL],
                  'skill missing or non-isolated skills index')
            view = dispatch('skill_view', {'name': SKILL})
            check(view.get('success') and Path(view['skill_dir']) == installed, 'wrong skill loaded')
            # skill_view may expand skill-dir placeholders. Match actual body prose, not frontmatter.
            body = (installed / FILES[0]).read_text(encoding='utf-8').split('---', 2)[-1]
            prose = [line.strip() for line in body.splitlines() if len(line.strip()) > 25]
            check(any(line in view.get('content', '') for line in prose), 'skill body not readable')
            receipt['skill'] = {'index': index['skills'][0]['name'], 'body_read': True}
            (root/'skill-loader.json').write_text(json.dumps(receipt['skill']), encoding='utf-8')

            discovered = set(discover_mcp_tools([SERVER]))
            check(discovered == expected, 'Hermes discovery: ' + repr(sorted(discovered)))
            schemas = registry.get_definitions(expected, quiet=True)
            check({s['function']['name'] for s in schemas} == expected, 'incomplete live tool schemas')
            receipt['tools'] = sorted(discovered)

            if stage == 'A':
                call('philo_map', {})  # harmless first dispatch
                # This fixture is the synthetic speaker's choice. Never invent this value in the host adapter.
                topic = '两个钟偶然一致时，我可能误把巧合当作验证。'
                no_consent = dispatch(prefix + 'philo_open', {'topic': topic})
                check('error' in no_consent and not call('philo_read', {})['threads'],
                      'an inquiry without local-storage consent was accepted')
                opened = call('philo_open', {'topic': topic, 'consent': '我同意把本题和我的回答保存在本机手记中'})
                check(opened['pending'] is None and opened['last_answer'] is None, 'unexpected new thread')
                # This nonce never goes into the second host's environment, args, or messages.
                question = '在钟表实验%s里，你如何区分「偶然一致」与独立验证？' % uuid.uuid4().hex[:10]
                asked = call('philo_ask', {'thread': opened['thread'], 'rev': opened['rev'],
                             'question': question, 'anchor': INITIAL_ANCHOR})
                check(asked['phase'] == 'awaiting' and asked['pending']['question'] == question
                      and asked['thread'] == opened['thread'] and asked['rev'] > opened['rev'],
                      'initial question was not persisted')
                receipt.update(thread=asked['thread'], initial_rev=opened['rev'], rev=asked['rev'],
                               pending=asked['pending'], phase=asked['phase'])
            else:
                before = call('philo_read', {'thread': thread})  # only locator crosses processes
                check(before['thread'] == thread and before['phase'] == 'awaiting'
                      and before['last_answer'] is None, 'no unanswered question on restart')
                replied = call('philo_reply', {'thread': thread, 'rev': before['rev'],
                               'kind': 'answer', 'text': ANSWER})
                check(replied['phase'] == 'ready' and replied['pending'] is None
                      and replied['last_answer']['text'] == ANSWER and replied['last_answer']['turn']
                      and replied['rev'] > before['rev'], 'reply did not advance the thread')
                # The old topic anchor is in this question but not in the latest real answer.
                bad = {'thread': thread, 'rev': replied['rev'], 'anchor': INITIAL_ANCHOR,
                       'question': '你会如何再检查「偶然一致」？'}
                call('philo_ask', bad, reject=True)
                # Conversely: a genuine answer quote that the new question does not use.
                call('philo_ask', dict(bad, anchor=NEXT_ANCHOR, question='你会怎样独立检验两次测量？'),
                     reject=True)
                same = call('philo_read', {'thread': thread})
                check(all(same[k] == replied[k] for k in ('thread','rev','phase','pending','last_answer')),
                      'rejected anchor changed state')
                after = call('philo_ask', {'thread': thread, 'rev': same['rev'],
                             'anchor': NEXT_ANCHOR, 'question': FOLLOWUP})
                reread = call('philo_read', {'thread': thread})
                check(after['phase'] == 'awaiting' and after['pending']['question'] == FOLLOWUP
                      and after['rev'] > replied['rev'] and reread['pending'] == after['pending']
                      and reread['rev'] == after['rev'] and reread['last_answer'] == replied['last_answer'],
                      'anchored follow-up not readable')
                receipt.update(thread=thread, recovered_rev=before['rev'], recovered=before['pending'],
                               answer_rev=replied['rev'], last_answer=replied['last_answer'],
                               rev=after['rev'], pending=after['pending'], phase=after['phase'])
        finally:
            shutdown_mcp_servers()
    print(MARKER + json.dumps(receipt, ensure_ascii=False))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--hermes-src', type=Path, required=True, help='installed Hermes source checkout')
    p.add_argument('--hermes-python', type=Path, required=True, help='Python in that Hermes venv')
    p.add_argument('--server-python', type=Path, default=Path(sys.executable), help='Python 3.9+ for the skill')
    p.add_argument('--skill', type=Path, default=Path(__file__).resolve().parents[1] / 'skills' / SKILL)
    p.add_argument('--scratch', type=Path, required=True, help='existing writable scratch directory')
    a = p.parse_args()
    src, skill, scratch = (x.resolve() for x in (a.hermes_src, a.skill, a.scratch))
    host_py, server_py = (str(x.absolute()) for x in (a.hermes_python, a.server_python))  # preserve venv symlink
    check((src/'tools/mcp_tool_discovery.py').is_file() and os.access(host_py, os.X_OK),
          'missing Hermes checkout or interpreter')
    check(not (src/'.env').exists(), 'refusing checkout with a dev .env; use a clean Hermes source tree')
    check(os.access(server_py, os.X_OK) and scratch.is_dir(), 'missing server Python or scratch directory')
    for rel in FILES:
        file = skill / rel
        check(file.resolve().is_relative_to(skill) and file.is_file(), 'missing/outside public skill input: ' + rel)
    snapshot = {rel: (skill / rel).read_bytes() for rel in FILES}
    run = Path(tempfile.mkdtemp(prefix='philo-hermes-', dir=scratch))
    print('Hermes QA artifacts: ' + str(run), file=sys.stderr, flush=True)
    db = run / 'shared.sqlite3'
    receipts = []
    for stage in ('A', 'B'):
        work = run / stage
        home = work / 'home'
        profile = home / '.hermes'
        installed = profile / 'skills' / SKILL
        (installed / 'scripts').mkdir(parents=True)
        for rel, data in snapshot.items():
            (installed / rel).write_bytes(data)
        for name in ('tmp','empty-plugins','empty-managed'):
            (work / name).mkdir()
        (work / '.philo-qa').touch()
        (profile / '.no-bundled-skills').touch()
        config = {'plugins': {'enabled': []}, 'mcp_servers': {SERVER: {'enabled': True, 'command': server_py,
                  'args': [str(installed / FILES[1]), '--store', str(db), 'mcp']}}}
        (profile / 'config.yaml').write_text(json.dumps(config), encoding='utf-8')  # JSON is valid YAML
        env = {'HOME': str(home), 'HERMES_HOME': str(profile), 'TMPDIR': str(work/'tmp'), 'PATH': os.defpath,
               'HERMES_BUNDLED_PLUGINS': str(work/'empty-plugins'), 'HERMES_MANAGED_DIR': str(work/'empty-managed'),
               'HERMES_ENABLE_PROJECT_PLUGINS': '0', 'HERMES_DISABLE_LAZY_INSTALLS': '1',
               'PYTHONPATH': str(src), 'PYTHONNOUSERSITE': '1', 'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONUTF8': '1'}
        worker = shutil.copyfile(__file__, work/'worker.py')
        argv = [host_py, '-B', str(worker), '_host', stage]
        if stage == 'B':
            argv.append(json.dumps(receipts[0]['thread']))
        proc = subprocess.run(argv, env=env, cwd=work, stdin=subprocess.DEVNULL,
                              capture_output=True, encoding='utf-8', timeout=90)
        (work / 'host.log').write_text(proc.stdout + proc.stderr, encoding='utf-8')
        check(proc.returncode == 0, stage + ' failed (see ' + str(work/'host.log') + '): ' + proc.stderr[-900:])
        rows = [line[len(MARKER):] for line in proc.stdout.splitlines() if line.startswith(MARKER)]
        check(len(rows) == 1, 'missing or ambiguous receipt for ' + stage)
        receipts.append(json.loads(rows[0]))
    first, second = receipts
    check(first['pid'] != second['pid'] and first['profile'] != second['profile'] and first['thread'] == second['thread']
          and first['rev'] == second['recovered_rev'] and first['pending'] == second['recovered'],
          'second host did not recover the exact first-host question and revision')
    with db.open('rb') as f:
        check(f.read(16) == b'SQLite format 3\x00', 'no SQLite state store')  # no direct business-data reads
    report = {'status': 'PASS', 'driver': 'tester-selected real Hermes registry dispatch (no LLM)',
              'source_sha256': {rel: hashlib.sha256(b).hexdigest() for rel, b in snapshot.items()}, 'hosts': receipts}
    text = json.dumps(report, ensure_ascii=False, indent=2)
    (run / 'receipt.json').write_text(text + '\n', encoding='utf-8')
    print(text)


if __name__ == '__main__':
    if sys.argv[1:2] == ['_host'] and sys.argv[2:3] in (['A'], ['B']):
        host_worker(sys.argv[2], json.loads(sys.argv[3]) if len(sys.argv) == 4 else None)
    else:
        main()
