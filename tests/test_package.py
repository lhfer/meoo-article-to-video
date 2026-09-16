"""Both profiles package into self-contained zips: root = SKILL name, overlay wins, no symlinks, shared scripts identical."""
import io, subprocess, sys, tempfile, unittest, zipfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / 'scripts'))
import package

@unittest.skipUnless((ROOT / 'profiles').is_dir(), 'packaging tests need the source tree with profiles/')
class Packaging(unittest.TestCase):
    def test_manifests(self):
        vname, vfiles = package.manifest('viral'); lname, lfiles = package.manifest('launch')
        self.assertEqual(vname, 'article-to-vertical-video'); self.assertEqual(lname, 'vibecoding-launch-video')
        self.assertEqual(lfiles['SKILL.md'][0], 'overlay'); self.assertEqual(vfiles['SKILL.md'][0], 'base')
        self.assertEqual(lfiles['references/profile.md'][0], 'overlay'); self.assertEqual(lfiles['references/pacing.md'][0], 'base')
        for f in (vfiles, lfiles):
            self.assertIn('scripts/common.py', f); self.assertIn('assets/director/src/kit/core.ts', f)
            self.assertFalse(any(r.startswith('profiles/') or '/node_modules/' in r or r.startswith('dist/') for r in f))
        self.assertNotIn('docs/v3-upgrade.md', lfiles)
        shared = [r for r in vfiles if r.startswith('scripts/')]
        for r in shared: self.assertEqual(vfiles[r][1].read_bytes(), lfiles[r][1].read_bytes(), r)
    def test_zips_build_and_have_no_symlinks(self):
        with tempfile.TemporaryDirectory() as tmp:
            for profile, expected in [('viral', 'article-to-vertical-video'), ('launch', 'vibecoding-launch-video')]:
                out = Path(tmp) / f'{profile}.zip'; name, files, sha = package.build(out, profile)
                self.assertEqual(name, expected); self.assertTrue(sha)
                with zipfile.ZipFile(out) as z:
                    names = z.namelist(); self.assertTrue(all(n.startswith(expected + '/') for n in names))
                    self.assertIn(f'{expected}/SKILL.md', names); self.assertIn(f'{expected}/scripts/common.py', names)
                    self.assertFalse(any((i.external_attr >> 16) & 0o170000 == 0o120000 for i in z.infolist()))
                    text = z.read(f'{expected}/SKILL.md').decode('utf-8'); self.assertIn(f'name: {expected}', text)

if __name__ == '__main__': unittest.main()
