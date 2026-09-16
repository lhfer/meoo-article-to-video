#!/usr/bin/env python3
"""Reproducible offline render test with synthetic tones, not narration or audience-quality evidence.
Creates a fresh isolated DRAFT project. It does not create user approvals or claim real product evidence.
Requires npm ci in assets/director. Default scale .25; --scale 1 tests target delivery dimensions.
"""
import argparse,copy,json,math,shutil,struct,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from common import read,write,filehash,texthash

def run(script,*args):subprocess.run([sys.executable,str(ROOT/'scripts'/script),*map(str,args)],check=True)
def rms(file,second):
    raw=subprocess.check_output(['ffmpeg','-v','error','-ss',str(second),'-i',str(file),'-t','0.08','-ar','48000','-ac','1','-f','f32le','-'])
    samples=struct.unpack('<'+'f'*(len(raw)//4),raw)
    return math.sqrt(sum(x*x for x in samples)/len(samples))

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--workdir',type=Path,required=True);ap.add_argument('--scale',type=float,default=.25);args=ap.parse_args()
    if not (ROOT/'assets/director/node_modules/remotion/package.json').is_file():raise SystemExit('Run npm ci in assets/director before this test')
    p=args.workdir.resolve()/'project'
    if p.exists():raise SystemExit('Use a fresh workdir; existing artifacts are preserved')
    shutil.copytree(ROOT/'assets/director',p,ignore=shutil.ignore_patterns('node_modules','out','__pycache__'))
    (p/'node_modules').symlink_to(ROOT/'assets/director/node_modules',target_is_directory=True)
    (p/'public/narration').mkdir(exist_ok=True)
    b=read(p/'content/brief.json');b.setdefault('pacing',{})['enforce']=False;write(p/'content/brief.json',b)  # synthetic tones cannot meet a real chars-per-second target; this test checks rendering, not pacing
    for name,freq,seconds in [('open',440,2),('next',880,1.2),('music',110,12)]:
        subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i',f'sine=frequency={freq}:sample_rate=48000:duration={seconds}','-ac','1',str(p/f'public/narration/{name}.wav')],check=True)
    s=read(p/'content/script.json');s.update(title='ENGINEERING AUDIO FIXTURE',beats=[{'id':'open','narration':'先看结果'},{'id':'next','narration':'接着理解'}]);write(p/'content/script.json',s)
    alignment={'version':3,'segments':{}}
    for id,seconds,words in [('open',2,[{'text':'先看','startMs':100,'endMs':700},{'text':'结果','startMs':1100,'endMs':1800}]),('next',1.2,[{'text':'接着理解','startMs':100,'endMs':1100}])]:
        text=next(b['narration'] for b in s['beats'] if b['id']==id)
        alignment['segments'][id]={'src':f'narration/{id}.wav','durationSeconds':seconds,'reviewed':True,'method':'manual','reviewNote':'SYNTHETIC TONE TEST, not a voice quality review','words':words,'audioSha256':filehash(p/f'public/narration/{id}.wav'),'textSha256':texthash(text)}
    write(p/'content/alignment.json',alignment)
    f=read(p/'content/film.json');f['voices']=[{'id':'open','at':.3},{'id':'next','at':{'after':'open','offset':.4}}]
    f['events']['result']={'voice':'open','word':'结果'}
    first=copy.deepcopy(f['shots'][0]);first.update(id='first',end=2)
    second=copy.deepcopy(f['shots'][0]);second.update(id='second',start=1.5,end=12,transitionIn={'type':'fade','seconds':.5})  # fixed 12 s film regardless of the seed shot's own length
    f['shots']=[first,second];f['audio']=[{'src':'narration/music.wav','start':0,'end':12,'gain':.08,'duck':.4,'fadeIn':.3,'fadeOut':.4}];write(p/'content/film.json',f)
    run('fonts.py',p,'auto')
    run('render.py',p,'--stage','draft','--format','all','--scale',args.scale)
    results=[]
    for fmt in ['3x4','9x16','16x9']:
        file=p/f'out/draft-{fmt}.mp4';levels={str(t):rms(file,t) for t in [1,2.1,2.5,3.1,4.5]}
        assert levels['2.1']>.04 and levels['2.5']<.02 and levels['3.1']>.04,levels
        results.append({'format':fmt,'rms':levels,'render':read(file.with_suffix('.render.json'))})
    write(p/'out/render-smoke.json',{'ok':True,'syntheticTonesOnly':True,'stage':'draft','scope':'Rendering, audio placement and per-frame DOM geometry only; not an approved production film','results':results})
    print(p/'out/render-smoke.json')

if __name__=='__main__':main()
