"""Create an ignored local archive; never publish weights or board data to Git."""
from pathlib import Path
import argparse
import hashlib
import json
import zipfile

ROOT=Path(__file__).resolve().parents[1]
REPO=ROOT.parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,default=ROOT/'artifacts/acx720_v3_closeout_20261125.zip')
    args=parser.parse_args()
    if args.output.exists():raise FileExistsError('Archive exists; choose another --output to keep the original')
    for stage in ['integer_uart','integer_tail']:
        acceptance=json.loads((ROOT/f'reports/{stage}_acceptance.json').read_text(encoding='utf-8'))
        for name,record in acceptance['files'].items():
            if sha(ROOT/name)!=record['sha256']:raise ValueError(f'Accepted artifact changed: {name}')
    paths=[]
    for folder in ['integer_head','integer_tail']:
        base=ROOT/'build'/folder
        paths.extend(base.glob('*.mem'));paths.append(base/'reference.npz')
    for folder in ['ddr_test','ddr_full','integer_head_hw','integer_uart_hw','integer_tail_hw']:
        base=ROOT/'build'/folder
        paths.extend(base.glob('*.bit'));paths.extend(base.glob('*.rpt'))
    paths.extend((ROOT/'build').glob('*_build.log'))
    for name in ['dataset/manifest.json','reference/development_fp32.npz']:
        p=ROOT/'build'/name
        if p.exists():paths.append(p)
    paths=sorted(set(paths))
    manifest={'scope':'Local derived artifacts only; source code and reports are in Git; original model/data/vendor packages not included',
        'files':{p.relative_to(REPO).as_posix():{'bytes':p.stat().st_size,'sha256':sha(p)} for p in paths}}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(args.output,'x',compression=zipfile.ZIP_DEFLATED) as z:
        for p in paths:z.write(p,p.relative_to(REPO).as_posix())
        z.writestr('experiments/02_nofft_vit/build/closeout_bundle_manifest.json',json.dumps(manifest,indent=2)+'\n')
    with zipfile.ZipFile(args.output) as z:
        assert z.testzip() is None
        for name,entry in manifest['files'].items():
            assert hashlib.sha256(z.read(name)).hexdigest()==entry['sha256'],name
    print(json.dumps({'path':str(args.output.resolve()),'files':len(paths),'bytes':args.output.stat().st_size,'sha256':sha(args.output)},indent=2))

if __name__=='__main__':main()
