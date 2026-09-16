#!/usr/bin/env python3
"""Read-only capability discovery. A binary/auth file does not prove an authenticated live render; a credential does not prove entitlement."""
import argparse,json,os,shutil,subprocess,sys
from pathlib import Path
from common import ROOT
import keys

def version(command):
    try:
        r=subprocess.run(command,capture_output=True,text=True,timeout=20)
        return {'exitCode':r.returncode,'version':(r.stdout or r.stderr).strip().splitlines()[:2]}
    except (OSError,subprocess.TimeoutExpired) as e:return {'error':str(e)}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--json',action='store_true',help='JSON is also the default');a=p.parse_args()
    commands={k:shutil.which(k) for k in ['node','npm','ffmpeg','ffprobe','python3','uv','grok','claude','cursor','whisper-cli']}
    if not commands['grok']:
        candidate=Path.home()/'.grok/bin/grok'
        if candidate.is_file():commands['grok']=str(candidate)
    if not commands['cursor']:
        candidate=Path('/Applications/Cursor.app/Contents/Resources/app/bin/cursor')
        if candidate.is_file():commands['cursor']=str(candidate)
    required=['node','npm','ffmpeg','ffprobe','python3'];missing=[k for k in required if not commands[k]]
    versions={k:version([v,'--version']) for k,v in commands.items() if v and k in ['node','grok','claude','cursor']}
    if commands['node']:
        v=versions['node'].get('version',[''])[0]
        if v.startswith('v') and int(v[1:].split('.')[0])<20:missing.append('node>=20')
    providers={name:keys.key_status(name) for name in ['fish','seed2','grok','dashscope']}
    providers['host-tts']=keys.key_status('host-tts');providers['host-music']=keys.key_status('host-music');providers['host-image']=keys.key_status('host-image')
    whisper_models=sorted(str(p) for p in (Path.home()/'Library/Caches/whisper.cpp').glob('ggml-*.bin')) if (Path.home()/'Library/Caches/whisper.cpp').is_dir() else []
    print(json.dumps({'ok':not missing,'missing':missing,'tools':commands,'versions':versions,'providers':providers,'whisperModels':whisper_models,
        'seedKeyAvailable':providers['seed2']['available'],'grokAuthFilePresent':providers['grok']['available'],'liveGenerationVerified':False,'packageRoot':str(ROOT),
        'note':'Credential availability is not a live entitlement check. Host-provided tools (TTS/music/image) are verified only by an actual tool call. Rendering, audio and visual quality are separate checks.'},ensure_ascii=False,indent=2))
    if missing:raise SystemExit(1)
if __name__=='__main__':main()
