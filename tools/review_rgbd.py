"""Verify a saved RGB-D pair and create an offline native-coordinate marking view."""
import argparse
import base64
import hashlib
import io
import json
from pathlib import Path
import sys
import webbrowser

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'apps/windows'))
from receive_frame import validate_header
from rgbd_frame import read_rgb


def review(folder):
    header=json.loads((folder/'metadata.json').read_text(encoding='utf-8'))
    validate_header(header)
    depth=(folder/'depth.f32le').read_bytes()
    if len(depth)!=header['payload_bytes'] or hashlib.sha256(depth).hexdigest()!=header['sha256']:
        raise ValueError('Depth original no coincide con checksum/tamaño')
    rgb=(folder/'rgb.png').read_bytes()
    class Source:
        def __init__(self): self.stream=io.BytesIO(rgb)
        def recv(self,n): return self.stream.read(n)
    if len(rgb)!=header['rgb']['payload_bytes']:
        raise ValueError('Tamaño RGB original incorrecto')
    read_rgb(Source(),header)
    pair=dict(header=header,raw=base64.b64encode(depth).decode(),rgb=base64.b64encode(rgb).decode(),attempt=1)
    template=(Path(__file__).resolve().parents[1]/'apps/windows/rgbd_viewer.html').read_text(encoding='utf-8')
    output=folder/'pair-review.html'
    with output.open('x',encoding='utf-8') as f:
        f.write(template.replace('/*PAIR_DATA*/null',json.dumps(pair).replace('<','\\u003c')))
    return output


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('frame',type=Path)
    parser.add_argument('--no-open',action='store_true')
    args=parser.parse_args()
    output=review(args.frame.resolve())
    print(output)
    if not args.no_open:webbrowser.open(output.as_uri())
