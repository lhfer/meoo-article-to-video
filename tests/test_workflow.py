"""Offline integration tests: review invalidation, provenance, real file hashes, and CLI dry runs."""
import copy,json,os,shutil,subprocess,sys,tempfile,unittest,wave,math,struct
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from common import read,write,digest,script_hash,ensure_script,filehash,texthash
from review import opening_hash
from validate import validate
from align import check_words

class Workflow(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.project=Path(self.temp.name)/'project';shutil.copytree(ROOT/'assets/director',self.project,ignore=shutil.ignore_patterns('node_modules','out','__pycache__'))
 def tearDown(self):self.temp.cleanup()
 def build(self):subprocess.run(['node','core/build.mjs','--draft'],cwd=self.project,check=True,capture_output=True)
 def test_script_approval_invalidates_when_words_change(self):
  write(self.project/'content/reviews.json',{'script':{'digest':script_hash(self.project),'evidence':'TEST FIXTURE, not user approval'}});ensure_script(self.project)
  s=read(self.project/'content/script.json');s['thesis']='changed';write(self.project/'content/script.json',s)
  with self.assertRaises(ValueError):ensure_script(self.project)
 def test_internal_notes_do_not_change_approved_script(self):
  before=script_hash(self.project);s=read(self.project/'content/script.json');s['implementationNotes']='Added later scene notes';write(self.project/'content/script.json',s);self.assertEqual(script_hash(self.project),before)
 def test_later_shot_and_alternate_layout_do_not_invalidate_opening(self):
  # Profile-agnostic: the seeded film differs per package (viral ContinuousExample 0–12 s, launch ProductShowcase 0–9 s), so derive spans and formats from film.json.
  self.build();before=opening_hash(self.project);f=read(self.project/'content/film.json');t=read(self.project/'content/timeline.json');primary=t['primaryFormat'];other=next(k for k in t['formats'] if k!=primary);last=max(s['end'] for s in f['shots'])
  (self.project/'src/shots/Later.tsx').write_text('export default function Later(){return null;}')
  f['components']['Later']='shots/Later.tsx';shot=copy.deepcopy(f['shots'][0]);shot.update(id='later',component='Later',start=last,end=last+3);f['shots'].append(shot);f['shots'][0]['layouts'][other]['centerX']=.65;write(self.project/'content/film.json',f);self.build()
  self.assertEqual(opening_hash(self.project),before)
  f['shots'][0]['layouts'][primary]['centerX']=.45;write(self.project/'content/film.json',f);self.build();self.assertNotEqual(opening_hash(self.project),before)
 def test_changed_opening_component_invalidates(self):
  self.build();before=opening_hash(self.project);f=read(self.project/'content/film.json');p=self.project/'src'/f['components'][f['shots'][0]['component']];p.write_text(p.read_text()+'\n// modified opening implementation\n');self.assertNotEqual(opening_hash(self.project),before)
 def test_stale_timeline_rejected(self):
  self.build();validate(self.project,True);f=read(self.project/'content/film.json');f['events']['connect']=2.2;write(self.project/'content/film.json',f)
  with self.assertRaisesRegex(ValueError,'stale'):validate(self.project,True)
 def test_quotes_checked_against_the_named_source(self):
  folder=self.project/'assets';folder.mkdir(exist_ok=True);(folder/'a.md').write_text('实测样本中有三项任务。');(folder/'b.md').write_text('其它报道。')
  write(self.project/'content/sources.json',[{'id':'a','textFile':'assets/a.md'},{'id':'b','textFile':'assets/b.md'}]);write(self.project/'content/claims.json',[{'id':'claim','sourceId':'b','quote':'三项任务'}]);self.build()
  with self.assertRaisesRegex(ValueError,'absent'):validate(self.project,True)
 def test_actual_audio_fingerprint_rejects_replaced_file(self):
  out=self.project/'public/narration';out.mkdir(exist_ok=True);audio=out/'open.wav'
  with wave.open(str(audio),'wb') as w:w.setparams((1,2,16000,16000,'NONE','not compressed'));w.writeframes(b'\0\0'*16000)
  s=read(self.project/'content/script.json');s['beats']=[{'id':'open','narration':'测试'}];write(self.project/'content/script.json',s)
  f=read(self.project/'content/film.json');f['voices']=[{'id':'open','at':0}];write(self.project/'content/film.json',f)
  write(self.project/'content/alignment.json',{'segments':{'open':{'src':'narration/open.wav','durationSeconds':1,'audioSha256':filehash(audio),'textSha256':texthash('测试'),'reviewed':False,'method':'manual','words':[{'text':'测试','startMs':100,'endMs':800}]}}})
  self.build();validate(self.project,True)
  with audio.open('ab') as w:w.write(b'changed')
  with self.assertRaisesRegex(ValueError,'changed after alignment'):validate(self.project,True)
 def test_tts_dry_run_never_creates_silent_voice_or_approval(self):
  subprocess.run([sys.executable,str(ROOT/'scripts/tts_seed2.py'),str(self.project),'--dry-run'],check=True,capture_output=True)
  self.assertFalse((self.project/'public/narration/index.json').exists());self.assertEqual(read(self.project/'content/reviews.json'),{})
 def test_invalid_measured_timestamps_rejected(self):
  with self.assertRaises(ValueError):check_words([{'text':'a','startMs':100,'endMs':80}],1)
  with self.assertRaises(ValueError):check_words([{'text':'a','startMs':100,'endMs':1800}],1)
if __name__=='__main__':unittest.main()
