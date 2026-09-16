"""Regression contracts added for V5/V2. Offline fixtures, never user approval or product proof."""
import copy,json,shutil,subprocess,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from common import read,write,filehash
from material_contract import check_asset,material_errors
from delivery import project_fingerprint
from capture import validate_url,validate_actions
from visual_review import critical_frames
from fonts import ensure_font
import qa
class Reliability(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.p=Path(self.tmp.name)/'project'
  shutil.copytree(ROOT/'assets/director',self.p,ignore=shutil.ignore_patterns('node_modules','__pycache__','out','work'))
  write(self.p/'content/materials.json',{'version':2,'items':[]})
 def tearDown(self):self.tmp.cleanup()
 def cli(self,script,*args):return subprocess.run([sys.executable,str(ROOT/'scripts'/script),str(self.p),*args],capture_output=True,text=True)
 def asset(self):
  # Small actual decodable PNG, made with standard-library zlib, not an extra image dependency.
  import zlib,struct
  def chunk(k,v):return struct.pack('>I',len(v))+k+v+struct.pack('>I',zlib.crc32(k+v)&0xffffffff)
  raw=b''.join(b'\0'+b'\x90\xb0\xa0'*64 for _ in range(64))
  path=self.p/'public/test.png';path.write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',64,64,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(raw))+chunk(b'IEND',b''))
  film=read(self.p/'content/film.json');film['assets']={'test':{'src':'test.png','kind':'image','sha256':filehash(path)}};write(self.p/'content/film.json',film)
  (self.p/'source.md').write_text('Local synthetic test fixture. No real product claim.')
  write(self.p/'content/sources.json',[{'id':'source','textFile':'source.md'}])
  return {'id':'test','assetId':'test','sourceId':'source','rights':'Locally authored test fixture','provenance':'user','strategy':'existing','status':'acquired','required':True,'evidenceKind':'screenshot'}
 def ledger(self,item):write(self.p/'content/materials.json',{'items':[item]})
 def test_missing_material_plan_cannot_pass(self):
  self.assertTrue(material_errors(self.p))
 def test_optional_only_plan_cannot_pass(self):
  self.ledger({'id':'a','required':False,'status':'pending'});self.assertTrue(material_errors(self.p))
 def test_existing_is_not_ready(self):
  r=self.cli('materials.py','add','--id','demo','--need','Demo','--why','Evidence','--strategy','existing','--required');self.assertEqual(r.returncode,0,r.stderr)
  self.assertEqual(read(self.p/'content/materials.json')['items'][0]['status'],'pending')
 def test_add_accepts_documented_asset_flag(self):
  r=self.cli('materials.py','add','--id','demo','--need','Demo','--why','Evidence','--asset','file');self.assertEqual(r.returncode,0,r.stderr)
  self.assertEqual(read(self.p/'content/materials.json')['items'][0]['status'],'acquired')
 def test_cannot_set_ready_without_verification(self):
  self.ledger({'id':'a','need':'a'});r=self.cli('materials.py','set','--id','a','--status','ready');self.assertNotEqual(r.returncode,0)
 def test_required_pending_blocks(self):
  self.ledger({'id':'a','required':True,'status':'pending'});self.assertTrue(material_errors(self.p))
 def test_required_skipped_blocks_even_direct_json(self):
  self.ledger({'id':'a','required':True,'status':'skipped'});self.assertTrue(material_errors(self.p))
 def test_required_skip_cli_refused(self):
  self.ledger({'id':'a','required':True,'status':'pending'});r=self.cli('materials.py','set','--id','a','--status','skipped');self.assertNotEqual(r.returncode,0)
 def test_no_partial_project_created_by_materials(self):
  p=Path(self.tmp.name)/'missing';r=subprocess.run([sys.executable,str(ROOT/'scripts/materials.py'),str(p),'init'],capture_output=True)
  self.assertNotEqual(r.returncode,0);self.assertFalse(p.exists())
 def test_asset_missing_refused(self):
  with self.assertRaises(ValueError):check_asset(self.p,{'assetId':'absent'})
 def test_real_file_is_decoded(self):
  item=self.asset();self.assertEqual(check_asset(self.p,item)['width'],64)
 def test_no_review_means_not_ready(self):
  item=self.asset();item['status']='ready';self.ledger(item);self.assertTrue(any('review' in e for e in material_errors(self.p)))
 def test_stale_media_hash_rejected(self):
  item=self.asset();(self.p/'public/test.png').write_bytes(b'not a png')
  with self.assertRaisesRegex(ValueError,'changed'):check_asset(self.p,item)
 def test_html_masquerading_as_image_rejected(self):
  item=self.asset();(self.p/'public/test.png').write_text('<html>Access denied</html>');film=read(self.p/'content/film.json');film['assets']['test'].pop('sha256');write(self.p/'content/film.json',film)
  with self.assertRaises((subprocess.CalledProcessError,ValueError)):check_asset(self.p,item)
 def test_no_source_refused(self):
  item=self.asset();item['sourceId']='missing'
  with self.assertRaisesRegex(ValueError,'source'):check_asset(self.p,item)
 def test_no_rights_refused(self):
  item=self.asset();item['rights']=''
  with self.assertRaisesRegex(ValueError,'basis'):check_asset(self.p,item)
 def test_no_provenance_refused(self):
  item=self.asset();item.pop('provenance')
  with self.assertRaisesRegex(ValueError,'provenance'):check_asset(self.p,item)
 def test_still_cannot_prove_real_demo(self):
  item=self.asset();item['evidenceKind']='real-demo'
  with self.assertRaisesRegex(ValueError,'video'):check_asset(self.p,item)
 def test_required_ready_must_be_used(self):
  item=self.asset();meta=check_asset(self.p,item);item.update(status='ready',inspection={**meta,'note':'Synthetic test review','toolRef':'test-fixture'});self.ledger(item)
  self.assertTrue(any('rendered shot' in e for e in material_errors(self.p)))
 def test_ready_used_actual_file_passes(self):
  item=self.asset();item.update(status='ready',inspection={**check_asset(self.p,item),'note':'Synthetic test review','toolRef':'test-fixture'});self.ledger(item)
  write(self.p/'content/timeline.json',{'shots':[{'id':'s','assets':['test'],'from':0,'end':90}],'fps':30});self.assertEqual(material_errors(self.p),[])
 def test_opening_scope_does_not_require_unused_later_asset(self):
  self.ledger({'id':'later','required':True,'requiredFor':'final','status':'pending'});self.assertEqual(material_errors(self.p,'opening'),[]);self.assertTrue(material_errors(self.p,'final'))
 def test_init_and_resume_never_overwrite(self):
  marker=self.p/'content/film.json';before=marker.read_bytes()
  cmd=[sys.executable,str(ROOT/'scripts/project.py'),'init',self.tmp.name,'--resume'];r=subprocess.run(cmd,capture_output=True)
  self.assertEqual(r.returncode,0,r.stderr);self.assertEqual(marker.read_bytes(),before)
  r=subprocess.run(cmd[:-1],capture_output=True);self.assertNotEqual(r.returncode,0);self.assertEqual(marker.read_bytes(),before)
 def test_fingerprint_changes_for_component_and_engine(self):
  old=project_fingerprint(self.p);f=self.p/'src/Film.tsx';f.write_text(f.read_text()+'\n// regression edit');self.assertNotEqual(old,project_fingerprint(self.p))
  old=project_fingerprint(self.p);f=self.p/'core/render-checked.mjs';f.write_text(f.read_text()+'\n// regression edit');self.assertNotEqual(old,project_fingerprint(self.p))
 def test_referenced_media_bytes_invalidate_delivery_fingerprint(self):
  self.asset();before=project_fingerprint(self.p);f=self.p/'public/test.png';f.write_bytes(f.read_bytes()+b'changed');self.assertNotEqual(before,project_fingerprint(self.p))
 def test_project_symlink_has_same_delivery_fingerprint(self):
  self.asset();alias=self.p.parent/'project-alias';alias.symlink_to(self.p,target_is_directory=True)
  self.assertEqual(project_fingerprint(self.p),project_fingerprint(alias))
 def test_qa_uses_custom_caption_geometry(self):
  film=read(self.p/'content/film.json');film.setdefault('style',{})['layout']={'16x9':{'insets':{'bottom':104}}};write(self.p/'content/film.json',film)
  qa.configure_layout(self.p);self.assertAlmostEqual(qa.CAPTION_TOP['16x9'],819/1080)
 def test_private_capture_needs_explicit_allow(self):
  with self.assertRaises(ValueError):validate_url('http://127.0.0.1:8123')
  validate_url('http://127.0.0.1:8123',True)
 def test_capture_rejects_embedded_credentials_and_file_urls(self):
  for url in ['file:///etc/passwd','http://a:b@example.com']:
   with self.assertRaises(ValueError):validate_url(url,True)
 def test_recording_actions_are_allowlisted_and_bounded(self):
  for actions in [[{'type':'eval','code':'x'}],[{'type':'wait','seconds':11}],[{'type':'click'}]]:
   with self.assertRaises(ValueError):validate_actions(actions)
  self.assertEqual(len(validate_actions([{'type':'click','selector':'#demo'}])),1)
 def test_critical_frames_include_ends_cues_and_extremes(self):
  frames=critical_frames({'shots':[{'from':0,'end':90,'props':{'qaFrames':[7,29]}}],'captions':[{'from':10,'end':20}],'events':{'click':30}},90,30)
  for n in [0,1,7,29,89,10,19,30,31,38,46]:self.assertIn(n,frames)
 def test_font_receipt_is_not_assumed(self):
  film=read(self.p/'content/film.json');film.setdefault('style',{})['fonts']=[];write(self.p/'content/film.json',film)
  with self.assertRaises(ValueError):ensure_font(self.p)
 def test_qa_failure_exit_is_not_success(self):
  out=self.p/'out';out.mkdir(exist_ok=True);video=out/'static-16x9.mp4'
  subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','color=c=gray:s=320x180:r=10:d=3','-c:v','libx264','-pix_fmt','yuv420p',str(video)],check=True)
  write(self.p/'content/timeline.json',{'shots':[],'events':{},'voices':[],'fps':10,'captions':[]})
  result=self.cli('qa.py','--input','out/static-16x9.mp4','--format','16x9');self.assertNotEqual(result.returncode,0,result.stdout)
  report=read(self.p/'out/qa/report-16x9.json');self.assertFalse(report['ok']);self.assertEqual(report['inputSha256'],filehash(video))
  result=self.cli('qa.py','--input','out/static-16x9.mp4','--format','16x9','--advisory');self.assertEqual(result.returncode,0,result.stderr);self.assertFalse(read(self.p/'out/qa/report-16x9.json')['ok'])
if __name__=='__main__':unittest.main()
