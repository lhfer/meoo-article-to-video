"""One-time import of user-supplied official assets; fail closed on hash mismatch."""
from pathlib import Path
import base64, hashlib, json, urllib.request
from PIL import Image

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'source'
OUT.mkdir(exist_ok=True)
EXPECTED_LOGO='f6f565b955b4b2fb294717e4b326c40c1c87123826cf174cdece5d28f79b2fa5'
EXPECTED_GIF='403f30881aa93a809f04c302d93b81f3f8cd85a55b89c2c6277da5da070f8bdc'
EXPECTED_PIXELS='51d250896c5404695da5a77339fabc2897c6f2e4908e6c242981c362f190a262'

def sha(b):return hashlib.sha256(b).hexdigest()
def pixels(p):
    im=Image.open(p).convert('RGBA')
    data=bytearray(im.tobytes())
    for i in range(0,len(data),4):
        if not data[i+3]:data[i:i+3]=b'\0\0\0'
    return sha(data)

report={}
for p in sorted((ROOT.parent/'media').glob('*.png')):
    im=Image.open(p)
    report[p.name]={'size':im.size,'sha256':sha(p.read_bytes()),'rgba_sha256':pixels(p)}
print(json.dumps(report,indent=2))
encoded=base64.b64encode((OUT/'logo-transfer.bin').read_bytes()).decode()
for bad,good in [('ndsYk0Y0','ndsY0Y0'),('TfH7H9SOt','TfH5SOt'),('I8mnvtHXRd9','I8mnvtHztXRd9'),('Ycr7w','Yyr7w')]:
    print('Repair transfer segment:',bad,encoded.count(bad))
    encoded=encoded.replace(bad,good)
logo=base64.b64decode(encoded)
print('Logo checksum:',sha(logo))
if sha(logo)==EXPECTED_LOGO:
    (OUT/'meoo-logo.png').write_bytes(logo)
else:
    (OUT/'logo-transfer-diagnostic.txt').write_text(encoded)

name='O1CN01x4YHxp27p4HHhyg3v_!!6000000007845-1-tps-500-500.gif'
for n in range(1,5):
    url=f'https://img.alicdn.com/imgextra/i{n}/{name}'
    try:
        with urllib.request.urlopen(url,timeout=20) as r: data=r.read(3_000_000)
        print('Mascot candidate',n,len(data),sha(data))
        if sha(data)==EXPECTED_GIF:
            (OUT/'meoo-mascot.gif').write_bytes(data)
            break
    except Exception as e: print('Mascot fetch failed',n,type(e).__name__)
mascot=OUT/'meoo-mascot.gif'
if mascot.exists():
    assert sha(mascot.read_bytes())==EXPECTED_GIF
    assert pixels(mascot)==EXPECTED_PIXELS
    Image.open(mascot).convert('RGBA').save(OUT/'meoo-mascot-poster.png',optimize=True)
else:
    old=ROOT.parent/'media/cat-b.gif.png'
    assert pixels(old)==EXPECTED_PIXELS,'Mascot pixels differ from supplied source'
    Image.open(old).convert('RGBA').save(OUT/'meoo-mascot-poster.png',optimize=True)
assert (OUT/'meoo-logo.png').is_file(),'Logo transfer checksum failed'
assert sha((OUT/'meoo-icon.png').read_bytes())=='209b2c6bafe805c44c9b205778d960c5dcab083b07595b1424f8b53198ffadef'
print('Official assets verified; no runtime files changed.')
