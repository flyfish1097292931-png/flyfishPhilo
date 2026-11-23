import unittest
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from tempfile import TemporaryDirectory
spec = spec_from_file_location('philo_dist', Path(__file__).resolve().parents[1]/'tools/package.py')
assert spec and spec.loader
module = module_from_spec(spec)
spec.loader.exec_module(module)
snapshot, archive = module.snapshot, module.archive

class Distribution(unittest.TestCase):
    def test_exact_allowlist_excludes_neighbors_and_is_reproducible(self):
        self.assertIsNotNone(snapshot, 'need a source-pack allowlist')
        with TemporaryDirectory() as d:
            p=Path(d);(p/'README.md').write_text('Synthetic public file.');(p/'private.json').write_text('must not appear');(p/'DIST_FILES.txt').write_text('README.md\nDIST_FILES.txt\n')
            material=snapshot(p); self.assertEqual(set(material), {'README.md','DIST_FILES.txt'});self.assertEqual(archive(material),archive(snapshot(p)))
    def test_missing_and_escaping_members_fail_closed(self):
        self.assertIsNotNone(snapshot,'need a source-pack allowlist')
        with TemporaryDirectory() as d:
            p=Path(d)
            for name in ['../a','/absolute','does-not-exist','a\\b','.git/config','.env','foo/../key']:
                with self.subTest(name=name):
                    (p/'DIST_FILES.txt').write_text(name+'\n');
                    with self.assertRaises((ValueError,OSError)):snapshot(p)
    def test_pack_checks_relative_document_links(self):
        self.assertIsNotNone(snapshot,'need a source-pack allowlist')
        with TemporaryDirectory() as d:
            p=Path(d); (p/'DIST_FILES.txt').write_text('a.md\n');(p/'a.md').write_text('[missing](b.md)');
            with self.assertRaisesRegex(ValueError,'link'):snapshot(p)
if __name__=='__main__': unittest.main()
