import copy
import hashlib
import io
import json
from pathlib import Path
import socket
import struct
import sys
import tempfile
import threading
import unittest
import zlib
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'apps/windows'))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from receive_frame import demo_packet, read_packet
from rgbd_frame import read_rgb, validate_rgb_header
from frame_transport import FrameTransport
from review_rgbd import review
from capture_sequence import capture, Preview
from test_frame_transport import trailer


class Source:
    def __init__(self,data): self.data=io.BytesIO(data)
    def recv(self,n): return self.data.read(min(n,97))


def fixture():
    def chunk(name,data):
        return struct.pack('>I',len(data))+name+data+struct.pack('>I',zlib.crc32(name+data))
    rgb=(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',2,2,8,2,0,0,0))
         +chunk(b'IDAT',zlib.compress((b'\x00'+b'\xff\x80\x00'*2)*2))+chunk(b'IEND',b''))
    header,raw=read_packet(Source(demo_packet()))
    header['timestamp']['clock']='capture-session'
    header['rgb']=dict(protocol='td-rgb/1',encoding='png',frame_id=header['frame_id'],
        width=2,height=2,payload_bytes=len(rgb),sha256=hashlib.sha256(rgb).hexdigest(),timestamp=copy.deepcopy(header['timestamp']))
    header['synchronization']=dict(method='AVCaptureDataOutputSynchronizer',depth_dropped=False,rgb_dropped=False,timestamp_delta_ms=0)
    return header,raw,rgb


def packet(header,depth,rgb):
    data=json.dumps(header).encode()
    return struct.pack('>I',len(data))+data+depth+rgb


class RGBDTests(unittest.TestCase):
    def test_native_rgb_with_smaller_depth(self):
        from PIL import Image
        for width,height,dw,dh in [(1920,1080,640,360),(1440,1080,640,480)]:
            with self.subTest(rgb=(width,height),depth=(dw,dh)):
                h,_,_=fixture()
                h['width'],h['height']=dw,dh
                image=Image.new('RGB',(width,height),(40,120,200))
                encoded=io.BytesIO();image.save(encoded,format='PNG');data=encoded.getvalue()
                h['rgb'].update(width=width,height=height,payload_bytes=len(data),
                                sha256=hashlib.sha256(data).hexdigest(),resized=False)
                received=read_rgb(Source(data),h)
                self.assertEqual(received,data)
                self.assertEqual(Image.open(io.BytesIO(received)).size,(width,height))
                h['rgb']['width']=dw
                with self.assertRaisesRegex(ValueError,'PNG'):read_rgb(Source(data),h)

    def test_capture_saves_both_channels_and_pair_metadata(self):
        h,d,c=fixture()
        class Transport:
            def __init__(self,*args):self.rgb=c;self.connections=1
            def request(self,*args):return h,d,None
            def close(self):pass
        args=SimpleNamespace(duration=.02,transport='rgbd',demo=False,host='unused',port=1,
                             token='unused',fps=1,timeout=1,save_depth=True)
        with tempfile.TemporaryDirectory() as tmp,patch('capture_sequence.FrameTransport',Transport):
            folder=Path(tmp);preview=Preview()
            capture(args,folder,preview,threading.Event())
            frame=folder/'frame-000001'
            self.assertEqual((frame/'depth.f32le').read_bytes(),d)
            self.assertEqual((frame/'rgb.png').read_bytes(),c)
            self.assertEqual(json.loads((frame/'metadata.json').read_text()),h)
            state=json.loads(preview.encode())
            self.assertTrue(state['frame']['rgb'])

    def test_fragmented_pair_and_offline_review(self):
        h,d,c=fixture();source=Source(packet(h,d,c))
        received,depth=read_packet(source)
        self.assertEqual(depth,d)
        self.assertEqual(read_rgb(source,received),c)
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);(folder/'metadata.json').write_text(json.dumps(h))
            (folder/'depth.f32le').write_bytes(d);(folder/'rgb.png').write_bytes(c)
            output=review(folder)
            self.assertIn('const embedded={',output.read_text(encoding='utf-8'))
            with self.assertRaises(FileExistsError):review(folder)

    def test_wrong_pair_drops_timestamps_and_bounds(self):
        h,_,_=fixture()
        variants=[]
        bad=copy.deepcopy(h);bad['rgb']['frame_id']+=1;variants.append(bad)
        bad=copy.deepcopy(h);bad['synchronization']['rgb_dropped']=True;variants.append(bad)
        bad=copy.deepcopy(h);bad['rgb']['timestamp']['value']=2;bad['rgb']['timestamp']['timescale']=1000;variants.append(bad)
        bad=copy.deepcopy(h);bad['rgb']['payload_bytes']=100_000_000;variants.append(bad)
        bad=copy.deepcopy(h);bad['synchronization']['timestamp_delta_ms']=float('nan');variants.append(bad)
        for bad in variants:
            with self.subTest(bad=bad),self.assertRaises(ValueError):validate_rgb_header(bad)

    def test_corruption_truncation_and_png_dimensions(self):
        h,_,c=fixture()
        with self.assertRaisesRegex(ValueError,'SHA-256'):read_rgb(Source(c[:-1]+b'x'),h)
        with self.assertRaises(ValueError):read_rgb(Source(c[:-8]),h)
        h['rgb']['width']=3
        with self.assertRaisesRegex(ValueError,'PNG'):read_rgb(Source(c),h)

    def test_persistent_td3_and_reject_stale_rgb_on_error(self):
        h,d,c=fixture();observed=[];errors=[]
        listener=socket.socket();listener.bind(('127.0.0.1',0));listener.listen();listener.settimeout(3)
        def serve():
            try:
                with listener.accept()[0] as peer:
                    peer.settimeout(3)
                    with peer.makefile('rb') as lines:
                        for i in range(1,4):
                            observed.append(lines.readline())
                            peer.sendall(packet(h,d,c)+trailer(i if i<3 else 999))
            except Exception as exc:errors.append(exc)
            finally:listener.close()
        worker=threading.Thread(target=serve);worker.start()
        client=FrameTransport('127.0.0.1',listener.getsockname()[1],'abcdef123456','rgbd')
        try:
            for _ in range(2):
                rh,rd,_=client.request(2,{})
                self.assertEqual(rd,d);self.assertEqual(client.rgb,c);self.assertEqual(rh,h)
            with self.assertRaisesRegex(ValueError,'Telemetría'):client.request(2,{})
            self.assertIsNone(client.rgb);self.assertIsNone(client.sock)
            self.assertEqual(client.connections,1)
        finally:client.close();worker.join(4)
        self.assertFalse(errors,errors)
        self.assertEqual(observed,[f'TD3 abcdef123456 {i}\n'.encode() for i in range(1,4)])
