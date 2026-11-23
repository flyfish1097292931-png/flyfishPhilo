"""Zero-dependency sanity checks for the portable Agent Skills directory contract."""
from pathlib import Path
import re
import unittest
ROOT=Path(__file__).resolve().parents[1]
SKILL=ROOT/'skills/flyfish-philo/SKILL.md'
class SkillFormat(unittest.TestCase):
    def test_skill_frontmatter_follows_core_open_format(self):
        raw=SKILL.read_text(encoding='utf-8')
        self.assertTrue(raw.startswith('---\n'))
        header=raw.split('---\n',2)[1].splitlines()
        keys=[line.split(':',1)[0] for line in header if line and not line[0].isspace()]
        self.assertEqual(set(keys),{'name','description','license','compatibility','metadata'})
        self.assertEqual(keys.count('name'),1)
        name_match=re.search(r'^name:\s*([a-z0-9-]+)\s*$',raw,re.M);description_match=re.search(r'^description:\s*"([^"]+)"\s*$',raw,re.M)
        self.assertIsNotNone(name_match);self.assertIsNotNone(description_match)
        assert name_match is not None and description_match is not None
        name=name_match.group(1);description=description_match.group(1)
        self.assertEqual(name,SKILL.parent.name)
        self.assertFalse(name.startswith('-') or name.endswith('-') or '--' in name)
        self.assertTrue(description.strip())
        self.assertLessEqual(len(description),1024)
        self.assertIn('Use when',description)
        self.assertLessEqual(len(raw.splitlines()),500)
    def test_every_local_script_link_is_shipped_with_installable_skill(self):
        for rel in ('scripts/dialogue.py','scripts/philo.py'):
            self.assertTrue((SKILL.parent/rel).is_file(),rel)

if __name__=='__main__':unittest.main()
