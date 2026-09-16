#!/usr/bin/env python3
"""Preserve each source separately; text extraction is not a substitute for visual inspection."""
import argparse, shutil, subprocess, sys, zipfile
from datetime import datetime,timezone
from pathlib import Path
import xml.etree.ElementTree as ET
from common import ROOT,read,write,ident,run_main,filehash

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('project',type=Path);p.add_argument('--id',required=True);p.add_argument('--input',required=True);p.add_argument('--title');a=p.parse_args()
    project=a.project.resolve();id=ident(a.id);manifest=read(project/'content/sources.json',[])
    if any(s['id']==id for s in manifest):raise ValueError('Source id already exists; use a new id to preserve provenance')
    dest=project/'assets/sources'/id;dest.mkdir(parents=True,exist_ok=False);source=a.input
    textfile=dest/'source.md';media=[]
    if source.startswith(('https://','http://')):
        subprocess.run(['uv','run','--with','curl_cffi','--with','trafilatura','python3',str(ROOT/'scripts/fetch_page.py'),source,str(dest)],check=True)
        textfile=dest/'article.md'
    else:
        local=Path(source).expanduser().resolve()
        if not local.is_file():raise ValueError('Input file does not exist')
        target=dest/local.name;shutil.copy2(local,target);suffix=local.suffix.lower()
        if suffix in ['.md','.txt','.json','.csv','.tsv']:
            textfile.write_text(local.read_text(encoding='utf-8-sig'),encoding='utf-8')
        elif suffix in ['.html','.htm']:
            subprocess.run(['uv','run','--with','curl_cffi','--with','trafilatura','python3',str(ROOT/'scripts/fetch_page.py'),'--from-html',str(target),str(dest)],check=True);textfile=dest/'article.md'
        elif suffix=='.pdf':
            subprocess.run(['uv','run','--with','pypdf','python3','-c','from pypdf import PdfReader; import sys; from pathlib import Path; Path(sys.argv[2]).write_text("\\n\\n".join(f"Page {i+1}\\n"+(p.extract_text() or "") for i,p in enumerate(PdfReader(sys.argv[1]).pages)),encoding="utf-8")',str(target),str(textfile)],check=True)
        elif suffix=='.docx':
            with zipfile.ZipFile(local) as z:root=ET.fromstring(z.read('word/document.xml'))
            ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
            paragraphs=[''.join(p.itertext()) for p in root.findall('.//w:p',ns)]
            textfile.write_text('\n'.join(paragraphs),encoding='utf-8')
        else:
            media_dir=project/'public/sources';media_dir.mkdir(parents=True,exist_ok=True);out=media_dir/(id+suffix);shutil.copy2(local,out);media=[str(out.relative_to(project/'public'))]
            textfile.write_text(f'# {a.title or local.name}\n\nMedia source: {local.name}\nSHA256: {filehash(local)}\n\nInspect this original media with the host image/video tools and add an attributed observation before citing its contents.\n',encoding='utf-8')
    item={'id':id,'title':a.title or source,'origin':source,'fetchedAt':datetime.now(timezone.utc).isoformat(),'textFile':str(textfile.relative_to(project)),'mediaFiles':media,'textSha256':filehash(textfile)}
    manifest.append(item);write(project/'content/sources.json',manifest);print(textfile)

if __name__=='__main__':run_main(main)
