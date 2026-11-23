#!/usr/bin/env python3
"""Copy the Agent Skill files into one explicit host skills directory.

No MCP settings or host configuration are ever edited.
"""
import argparse
import os
from pathlib import Path
import shutil
import tempfile

SOURCE=Path(__file__).resolve().parent.parent/'skills/flyfish-philo'
FILES=('SKILL.md','scripts/dialogue.py','scripts/philo.py','scripts/owner_turn.py','scripts/cloud_turn.py','scripts/chat.py')

def install(target_dir):
    destroot=Path(target_dir)
    if not destroot.is_absolute(): raise ValueError('Choose an explicit absolute skills directory.')
    if destroot.is_symlink(): raise ValueError('Skills directory may not be a symlink.')
    destroot.mkdir(parents=True,exist_ok=True)
    destroot=destroot.resolve(strict=True)
    dest=destroot/'flyfish-philo'
    if dest.exists() or dest.is_symlink(): raise FileExistsError('The skill already exists; refusing to overwrite it.')
    for f in FILES:
        src=SOURCE/f
        if not src.is_file() or src.is_symlink(): raise FileNotFoundError(f'Incomplete or unsafe skill source: {f}')
    stage=Path(tempfile.mkdtemp(prefix='.flyfish-philo-',dir=destroot))
    try:
        for f in FILES:
            target=stage/f;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(SOURCE/f,target)
        os.replace(stage,dest)
    finally:
        if stage.exists():shutil.rmtree(stage)
    return dest

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target-dir',required=True,help='The chosen absolute host skills directory (for example "$HOME/.claude/skills").')
    args=parser.parse_args()
    print(install(args.target_dir))

if __name__=='__main__':
    try:main()
    except (OSError,ValueError) as e:
        print(f'flyfish-philo: {e}',file=__import__('sys').stderr);raise SystemExit(2)
