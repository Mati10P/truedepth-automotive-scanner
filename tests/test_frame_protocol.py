import importlib.util
import json
from pathlib import Path
import socket
import struct
import tempfile
import threading
import unittest

spec = importlib.util.spec_from_file_location("receiver", Path(__file__).resolve().parents[1] / "apps/windows/receive_frame.py")
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)


class FragmentedSocket:
    def __init__(self, data): self.data = data
    def recv(self, count):
        chunk, self.data = self.data[:min(count, 7)], self.data[min(count, 7):]
        return chunk


class ProtocolTests(unittest.TestCase):
    def test_fragmented_transport_and_lossless_storage(self):
        header, raw = r.read_packet(FragmentedSocket(r.demo_packet()))
        with tempfile.TemporaryDirectory() as folder:
            viewer = r.save_frame(header, raw, Path(folder))
            self.assertEqual((viewer.parent / 'depth.f32le').read_bytes(), raw)
            self.assertEqual(json.loads((viewer.parent / 'metadata.json').read_text()), header)
            self.assertIn('DEMO SINTÉTICA', viewer.read_text(encoding='utf-8'))
            self.assertNotIn('{{', viewer.read_text(encoding='utf-8'))

    def test_corruption_rejected(self):
        packet = bytearray(r.demo_packet()); packet[-1] ^= 1
        with self.assertRaisesRegex(ValueError, 'SHA-256'):
            r.read_packet(FragmentedSocket(packet))

    def test_truncation_rejected(self):
        with self.assertRaisesRegex(ValueError, 'cerrada'):
            r.read_packet(FragmentedSocket(r.demo_packet()[:-10]))

    def test_oversized_header_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Cabecera'):
            r.read_packet(FragmentedSocket(struct.pack('>I', r.MAX_HEADER + 1)))

    def test_invalid_dimensions_and_length(self):
        header, _ = r.read_packet(FragmentedSocket(r.demo_packet()))
        for patch in ({'width': -1}, {'height': True}, {'width': 999999}, {'payload_bytes': 0}, {'units': 'mm'}, {'timestamp': None}):
            with self.subTest(patch=patch), self.assertRaises(ValueError):
                r.validate_header(header | patch)

    def test_real_tcp_request_and_packet(self):
        with socket.socket() as server:
            server.bind(('127.0.0.1', 0)); server.listen(1); server.settimeout(5)
            observed = []
            def serve():
                with server.accept()[0] as client:
                    client.settimeout(5)
                    observed.append(r.exact(client, len(b'TD1 abcdef123456\n')))
                    client.sendall(r.demo_packet())
            worker = threading.Thread(target=serve); worker.start()
            with socket.create_connection(server.getsockname(), timeout=5) as client:
                client.sendall(b'TD1 abcdef123456\n')
                header, raw = r.read_packet(client)
            worker.join(5)
            self.assertFalse(worker.is_alive())
            self.assertEqual(observed, [b'TD1 abcdef123456\n'])
            self.assertEqual(len(raw), header['width'] * header['height'] * 4)


if __name__ == '__main__': unittest.main()
