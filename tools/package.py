"""Package the public source allowlist, never a private notebook directory."""
import argparse
import hashlib
import io
from pathlib import Path, PurePosixPath
import re
from urllib.parse import unquote, urlsplit
import zipfile

LINK = re.compile(r'\[[^\]\n]*\]\(([^()\s]+)\)')
SUSPECT = re.compile(r'(?:/(?:Users|home)/[\w.-]+/|[A-Z]:\\Users\\[^\\\s]+\\|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|(?:gh[pousr]_|github_pat_)[A-Za-z0-9_]{22,}|\bsk-[A-Za-z0-9_-]{30,})')


def snapshot(root):
    root = Path(root).resolve()
    allow = root/'DIST_FILES.txt'
    if allow.is_symlink(): raise ValueError('symlinked allowlist')
    names = allow.read_text(encoding='utf-8').splitlines()
    if not names or len(names) != len(set(names)): raise ValueError('empty or duplicate distribution list')
    data = {}
    for name in names:
        rel = PurePosixPath(name)
        if (not name or name != str(rel) or rel.is_absolute() or '\\' in name or ':' in name or '..' in rel.parts
            or any(s.casefold() in {'.git','node_modules','private','notebooks','__pycache__'} or s.startswith('.env') for s in rel.parts)):
            raise ValueError('invalid member: '+name)
        target = root.joinpath(*rel.parts)
        if any(q.is_symlink() for q in (target,*target.parents) if q!=root and root in q.parents): raise ValueError('symlink: '+name)
        if not target.is_file(): raise ValueError('missing member: '+name)
        raw=target.read_bytes(); content=raw.decode('utf-8')
        if SUSPECT.search(content): raise ValueError('possible private path or secret in '+name+'; review before distribution')
        data[name]=raw
    for name,raw in data.items():
        if not name.endswith('.md'): continue
        for link in LINK.findall(raw.decode('utf-8')):
            url=urlsplit(link)
            if url.scheme in ('http','https','mailto') or not url.path: continue
            path=(root/name).parent/unquote(url.path)
            if url.scheme or root not in path.resolve().parents or path.resolve().relative_to(root).as_posix() not in data:
                raise ValueError('broken or unlisted link: '+name+' -> '+link)
    return data


def archive(data):
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w') as z:
        for name,raw in sorted(data.items()):
            info=zipfile.ZipInfo('flyfishPhilo/'+name,(2020,1,1,0,0,0));info.create_system=3;info.external_attr=0o100644<<16
            z.writestr(info,raw,compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
    return stream.getvalue()


def main():
    p=argparse.ArgumentParser(description=__doc__); mode=p.add_mutually_exclusive_group(required=True)
    mode.add_argument('--check',action='store_true');mode.add_argument('--out',type=Path);args=p.parse_args()
    root=Path(__file__).resolve().parents[1]; data=snapshot(root); blob=archive(data)
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        if z.testzip() or {n.removeprefix('flyfishPhilo/'):z.read(n) for n in z.namelist()}!=data: raise ValueError('ZIP verification failed')
    if args.out:
        dest=args.out.resolve();
        if dest==root or root in dest.parents or args.out.is_symlink(): raise ValueError('choose a new archive outside the source tree')
        if dest.exists():
            if dest.read_bytes()!=blob: raise ValueError('refusing to overwrite different bytes')
        else:
            with dest.open('xb') as f:f.write(blob)
    print(f'{len(data)} reviewed-list members; source ZIP SHA-256 {hashlib.sha256(blob).hexdigest()}')

if __name__=='__main__': main()
