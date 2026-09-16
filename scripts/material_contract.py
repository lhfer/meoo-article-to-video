"""Verifiable material readiness. Receipts attest a review; they do not perform vision."""
from pathlib import Path
import subprocess
from common import read, inside, filehash, probe

def check_asset(project, item):
    project = Path(project)
    film = read(project / 'content/film.json')
    asset_id = item.get('assetId')
    asset = film.get('assets', {}).get(asset_id)
    if not asset:
        raise ValueError('No registered film.assets entry for ' + str(asset_id))
    path = inside(project / 'public', asset['src'])
    if not path.is_file() or path.stat().st_size == 0:
        raise ValueError('Missing or empty local file: ' + str(path))
    sha = filehash(path)
    if asset.get('sha256') and asset['sha256'] != sha:
        raise ValueError('Asset changed since registration: ' + str(asset_id))
    info = probe(path)
    stream = next((s for s in info.get('streams', []) if s.get('codec_type') == 'video'), None)
    if not stream or min(stream.get('width', 0), stream.get('height', 0)) < 16:
        raise ValueError('Material needs a decodable image or video, not HTML/audio/an empty placeholder')
    subprocess.run(['ffmpeg','-v','error','-xerror','-i',str(path),'-frames:v','1','-f','null','-'],
                   check=True, capture_output=True, timeout=45)
    is_video = asset.get('kind') == 'video' and float(info.get('format', {}).get('duration', 0)) > 0
    if item.get('provenance') not in ('user','official','licensed','browser-capture','generated','code'):
        raise ValueError('Record the actual provenance; do not infer evidence status from a filename')
    if item.get('evidenceKind') == 'real-demo':
        if asset.get('sourceMode')=='local-html':raise ValueError('Offline HTML illustration is not verified live-product evidence')
        if not is_video:
            raise ValueError('real-demo requires moving video, not an animated still or screenshot')
        if item.get('provenance') in ('generated','code') or asset.get('provider') in ('grok-cli','generated'):
            raise ValueError('Generated media cannot substantiate a real-demo claim')
    if not item.get('rights', '').strip():
        raise ValueError('Record the source/use basis; public accessibility alone is not a licence')
    src_id = item.get('sourceId')
    source = next((s for s in read(project/'content/sources.json', []) if s.get('id') == src_id), None)
    if not source:
        raise ValueError('Register a source receipt with sources.py (including user-provided/generated media)')
    source_path = inside(project, source['textFile'])
    if not source_path.is_file() or not source_path.read_text(encoding='utf-8').strip():
        raise ValueError('Source receipt is empty or missing')
    return {'sha256': sha, 'width': stream['width'], 'height': stream['height'],
            'kind': 'video' if is_video else 'image',
            'seconds': float(info.get('format', {}).get('duration', 0))}

def material_errors(project, stage='final', require_usage=True):
    project = Path(project)
    film = read(project/'content/film.json')
    timeline = read(project/'content/timeline.json', {})
    items = read(project/'content/materials.json', {'items': []}).get('items', [])
    errors = []
    if not items:errors.append('Material plan is empty/missing. Create a real required-evidence plan; links or a template are not finished evidence.')
    elif not any(i.get('required') for i in items):errors.append('Material plan has no required evidence; explicitly name what substantiates the central claim or illustration.')
    opening_frames = int(read(project/'content/brief.json',{}).get('review',{}).get('openingSeconds',10) * timeline.get('fps',30))
    shots = timeline.get('shots', [])
    if stage == 'opening': shots = [s for s in shots if s.get('from',0) < opening_frames]
    used = {a for s in shots for a in s.get('assets', [])}
    for item in items:
        required = item.get('required', False)
        in_scope = stage != 'opening' or item.get('requiredFor') == 'opening' or item.get('assetId') in used
        if not in_scope: continue
        status = item.get('status','pending')
        if required and status != 'ready':
            errors.append(f"{item['id']}: required material is {status}; acquire it or explicitly revise/remove the unsupported claim and its requirement")
            continue
        if status != 'ready': continue
        try:
            if item.get('strategy') == 'code':
                if item.get('evidenceKind') == 'real-demo': raise ValueError('Code illustration is not real demo evidence')
                shot = next((s for s in film.get('shots',[]) if s['id'] == item.get('shotId')),None)
                if not shot: raise ValueError('Code material must name an existing --shot')
                code = inside(project/'src', film.get('components',{}).get(shot['component'],''))
                review = item.get('inspection',{})
                if not code.is_file() or review.get('sha256') != filehash(code): raise ValueError('Code review is missing/stale')
                if not review.get('note') or not review.get('toolRef'): raise ValueError('Record the actual rendered-frame review')
            else:
                meta = check_asset(project,item)
                review = item.get('inspection',{})
                if review.get('sha256') != meta['sha256'] or not review.get('note') or not review.get('toolRef'):
                    raise ValueError('Actual-file visual review is missing/stale (a download is not a review)')
                if required and require_usage and item.get('assetId') not in used:
                    raise ValueError('Required asset is not declared on a rendered shot')
                if required and item.get('beat'):
                    voices=[v for v in timeline.get('voices',[]) if v['id']==item['beat']]
                    if voices and not any(item.get('assetId') in s.get('assets',[]) and s['from'] < v['from']+v['durationFrames'] and v['from'] < s['end'] for v in voices for s in shots):
                        raise ValueError('Evidence is not scheduled during its associated narration beat')
        except (ValueError,KeyError,FileNotFoundError,subprocess.SubprocessError) as e:
            errors.append(f"{item['id']}: {e}")
    return errors
