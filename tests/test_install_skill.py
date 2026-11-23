"""The host installer only writes into a user's explicitly chosen skill directory."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('philo_skill_installer',ROOT/'tools/install_skill.py')
assert spec and spec.loader
installer=importlib.util.module_from_spec(spec);spec.loader.exec_module(installer)

class InstallSkill(unittest.TestCase):
    def test_install_is_self_contained_and_repeat_safe_for_hermes_claude_and_codex_roots(self):
        with tempfile.TemporaryDirectory() as t:
            for host in ('hermes','claude','codex'):
                dest=installer.install(Path(t)/host/'skills')
                for name in installer.FILES:self.assertEqual((dest/name).read_bytes(),(installer.SOURCE/name).read_bytes())
                with self.assertRaises(FileExistsError):installer.install(dest.parent)
    def test_requires_one_explicit_absolute_directory_and_refuses_symlinks(self):
        with tempfile.TemporaryDirectory() as t:
            with self.assertRaises(ValueError):installer.install('relative-agent-skills')
            actual=Path(t)/'actual';actual.mkdir();link=Path(t)/'link';link.symlink_to(actual)
            with self.assertRaises(ValueError):installer.install(link)
            self.assertEqual(list(actual.iterdir()),[])

if __name__=='__main__':unittest.main()
