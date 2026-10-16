import json
from pathlib import Path
import socket
import struct
import sys
import threading
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'apps/windows'))
from frame_transport import FrameTransport
from receive_frame import demo_packet


def trailer(request_id, **changes):
    record = dict(protocol='td-telemetry/1', request_id=request_id,
                  queue_ms=1.0, prepare_ms=2.0, dispatch_ms=.5, send_ms=3.0,
                  session_id='test-session', connection_id='test-connection')
    record.update(changes)
    data = json.dumps(record).encode()
    return struct.pack('>I', len(data)) + data


class TransportTests(unittest.TestCase):
    def serve(self, action):
        listener = socket.socket()
        listener.bind(('127.0.0.1', 0))
        listener.listen()
        listener.settimeout(3)
        errors = []
        def run():
            try:
                action(listener)
            except Exception as error:
                errors.append(error)
            finally:
                listener.close()
        thread = threading.Thread(target=run)
        client = FrameTransport('127.0.0.1', listener.getsockname()[1], 'abcdef123456')
        thread.start()
        self.addCleanup(client.close)
        self.addCleanup(lambda: thread.join(4))
        return client, thread, errors

    def test_persistent_fragmented_packets_and_telemetry(self):
        observed = []
        def action(listener):
            with listener.accept()[0] as peer:
                peer.settimeout(3)
                reader = peer.makefile('rb')
                for i in range(1, 4):
                    observed.append(reader.readline())
                    packet = demo_packet() + trailer(i)
                    for begin, end in [(0, 1), (1, 3), (3, 333), (333, len(packet))]:
                        peer.sendall(packet[begin:end])
                reader.close()
        client, thread, errors = self.serve(action)
        for i in range(1, 4):
            timings = {}
            _, raw, telemetry = client.request(2, timings)
            self.assertEqual(len(raw), 160 * 120 * 4)
            self.assertEqual(telemetry['request_id'], i)
            self.assertEqual(timings['ios_prepare_ms'], 2)
            self.assertGreaterEqual(timings['payload_receive_ms'], 0)
            if i > 1:
                self.assertEqual(timings['connect_ms'], 0)
        thread.join(3)
        self.assertFalse(errors, errors)
        self.assertEqual(client.connections, 1)
        self.assertEqual(observed, [f'TD2 abcdef123456 {i}\n'.encode() for i in range(1, 4)])

    def test_reconnect_after_corrupt_payload(self):
        def action(listener):
            for i in range(1, 3):
                with listener.accept()[0] as peer:
                    peer.recv(128)
                    data = bytearray(demo_packet())
                    if i == 1:
                        data[-1] ^= 1
                    peer.sendall(data + trailer(i))
        client, thread, errors = self.serve(action)
        with self.assertRaisesRegex(ValueError, 'SHA-256'):
            client.request(2, {})
        self.assertIsNone(client.sock)
        client.request(2, {})
        thread.join(3)
        self.assertFalse(errors, errors)
        self.assertEqual(client.connections, 2)

    def test_invalid_or_missing_trailer_closes_connection(self):
        for suffix in (b'', trailer(999), trailer(1, send_ms=float('nan')),
                       struct.pack('>I', 20000)):
            with self.subTest(suffix=suffix[:20]):
                def action(listener):
                    with listener.accept()[0] as peer:
                        peer.recv(128)
                        peer.sendall(demo_packet() + suffix)
                client, thread, errors = self.serve(action)
                with self.assertRaises(ValueError):
                    client.request(2, {})
                self.assertIsNone(client.sock)
                thread.join(3)
                self.assertFalse(errors, errors)

    def test_slow_trickle_obeys_whole_request_deadline(self):
        def action(listener):
            with listener.accept()[0] as peer:
                peer.recv(128)
                try:
                    for byte in demo_packet()[:20]:
                        peer.sendall(bytes([byte]))
                        time.sleep(.04)
                except OSError:
                    pass
        client, thread, errors = self.serve(action)
        start = time.perf_counter()
        with self.assertRaises(TimeoutError):
            client.request(.15, {})
        self.assertLess(time.perf_counter() - start, .5)
        self.assertIsNone(client.sock)


if __name__ == '__main__':
    unittest.main()
