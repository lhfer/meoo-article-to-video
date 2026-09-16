#!/usr/bin/env python3
"""Build a self-contained skill ZIP for one profile from this source tree; generated work and credentials stay out.

  package.py <output.zip> [--profile viral|launch] [--list] [--dry-run]
The base set is the source tree minus profiles/ and excluded paths; profiles/<p>/files/** overlays the same relative paths.
The zip root is the effective SKILL.md `name`, so install.py and every host discover the package under that name.
"""
import argparse, hashlib, re, zipfile
from pathlib import Path
from common import ROOT, run_main

EXCLUDE_PARTS = {'.git', 'node_modules', '__pycache__', '.DS_Store', 'out', 'work', 'config.env', '.env', 'profiles', 'dist', '.claude'}
EXCLUDE_SUFFIX = {'.pyc', '.log', '.ttf', '.otf', '.ttc', '.woff', '.woff2'}
NAME_RE = re.compile(r'^[a-z][a-z0-9-]*$')


def skill_name_of(text):
    m = re.search(r'\A---\s*\n(.*?)\n---', text, re.S)
    n = re.search(r'^name:\s*([A-Za-z0-9._-]+)\s*$', m.group(1), re.M) if m else None
    return n.group(1) if n else None


def glob_match(rel, patterns):
    from fnmatch import fnmatch
    return any(fnmatch(rel, p) or rel.startswith(p.rstrip('*')) for p in patterns)


def manifest(profile):
    cfg = {'name': None, 'exclude': []}
    pdir = ROOT / 'profiles' / profile
    if (pdir / 'profile.json').exists():
        import json
        cfg.update(json.loads((pdir / 'profile.json').read_text(encoding='utf-8')))
    files = {}
    for path in sorted(ROOT.rglob('*')):
        if not path.is_file(): continue
        rel = path.relative_to(ROOT).as_posix()
        parts = path.relative_to(ROOT).parts
        if any(p in EXCLUDE_PARTS for p in parts) or path.suffix in EXCLUDE_SUFFIX: continue
        if rel.startswith('docs/verification/') and profile != 'viral': continue
        if glob_match(rel, cfg.get('exclude', [])): continue
        files[rel] = ('base', path)
    overlay = pdir / 'files'
    if overlay.is_dir():
        for path in sorted(overlay.rglob('*')):
            if path.is_file() and not any(p in EXCLUDE_PARTS for p in path.relative_to(overlay).parts):
                files[path.relative_to(overlay).as_posix()] = ('overlay', path)
    skill = files.get('SKILL.md')
    if not skill: raise ValueError('SKILL.md missing from the package')
    name = skill_name_of(skill[1].read_text(encoding='utf-8'))
    if not name or not NAME_RE.match(name): raise ValueError('SKILL.md name must match ^[a-z][a-z0-9-]*$')
    if cfg.get('name') and cfg['name'] != name: raise ValueError(f"profile.json name {cfg['name']} differs from SKILL.md name {name}")
    return name, files


def build(output, profile, dry_run=False):
    name, files = manifest(profile)
    for required in ['scripts/common.py', 'assets/director/core/compile.mjs', 'references/runtime.md']:
        if required not in files: raise ValueError('Required file missing: ' + required)
    if any(rel.startswith('profiles/') for rel in files): raise ValueError('profiles/ must not be packaged')
    for rel in ['assets/director/content/reviews.json']:
        if rel in files and files[rel][1].read_text(encoding='utf-8').strip() not in ('{}', ''): raise ValueError('reviews.json must be empty in a package')
    if dry_run: return name, files, None
    output = Path(output).resolve(); output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists(): raise ValueError('Output exists; choose a new package filename to preserve the prior package')
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as z:
        for rel, (_, src) in sorted(files.items()):
            real = src.resolve()
            if not real.is_relative_to(ROOT.resolve()): raise ValueError('Symlink escapes the source tree: ' + rel)
            z.write(real, f'{name}/{rel}')
    with zipfile.ZipFile(output) as z:
        if z.testzip(): raise ValueError('Archive integrity check failed')
        for info in z.infolist():
            if (info.external_attr >> 16) & 0o170000 == 0o120000: raise ValueError('Symlink member in archive: ' + info.filename)
    return name, files, hashlib.sha256(output.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter); p.add_argument('output', type=Path, nargs='?'); p.add_argument('--profile', choices=['viral', 'launch'], default='viral'); p.add_argument('--list', action='store_true'); p.add_argument('--dry-run', action='store_true'); a = p.parse_args()
    if a.list:
        name, files = manifest(a.profile)
        print(f'name={name}')
        for rel, (kind, _) in sorted(files.items()): print(f'{kind:7s} {rel}')
        return
    if not a.output: raise ValueError('Provide the output zip path')
    name, files, sha = build(a.output, a.profile, a.dry_run)
    print(str(a.output.resolve())); print(f'profile={a.profile}'); print(f'name={name}'); print('files=' + str(len(files)))
    if sha: print('sha256=' + sha)


if __name__ == '__main__': run_main(main)
