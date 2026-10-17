import csv
import json
from pathlib import Path
import socket
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.request import urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'apps/windows'))
import capture_sequence as c


class SequenceTests(unittest.TestCase):
    def test_preview_age_uses_monotonic_clock_and_survives_errors(self):
        preview = c.Preview()
        self.assertIsNone(json.loads(preview.encode())['unique_age_s'])
        preview.note_unique(10)
        preview.update(status='Error de solicitud')
        with patch.object(c.time, 'perf_counter', return_value=12.24):
            self.assertAlmostEqual(json.loads(preview.encode())['unique_age_s'], 2.24)
        preview.note_unique(12.3)
        with patch.object(c.time, 'perf_counter', return_value=12.4):
            self.assertAlmostEqual(json.loads(preview.encode())['unique_age_s'], .1)

    def test_cloud_routes_and_synthetic_calibration(self):
        server = c.make_server(c.Preview(), 'cloud')
        thread = threading.Thread(target=server.serve_forever)
        thread.start()
        try:
            url = f'http://127.0.0.1:{server.server_port}'
            for path, marker in [('/', 'VISOR EXPERIMENTAL'), ('/cloud_math.js', 'intrinsics'),
                                 ('/point_cloud.js', 'webgl')]:
                with urlopen(url + path) as response:
                    self.assertIn(marker, response.read().decode())
            h, _ = c.synthetic_frame(1, .2)
            self.assertTrue(h['calibration']['synthetic'])
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_duplicates_gaps_and_reset(self):
        m = c.Metrics()
        for frame_id, timestamp, arrival in [(10, 1, 0), (10, 1, .1), (13, 1.1, .2), (1, .1, .3)]:
            m.attempts += 1
            m.accept(dict(frame_id=frame_id, timestamp=dict(value=timestamp*1000, timescale=1000)), 10, arrival)
        result = m.snapshot()
        self.assertEqual(result['duplicates'], 1)
        self.assertEqual(result['unique'], 3)
        self.assertEqual(result['skipped_sensor_frames'], 2)
        self.assertEqual(result['discontinuities'], 1)
        self.assertAlmostEqual(result['received_hz'], 10)
        self.assertAlmostEqual(result['max_valid_gap_s'], .1)
        self.assertIsNone(result['sensor_hz_estimate'])

    def test_rate_and_p95(self):
        m = c.Metrics()
        for i in range(20):
            m.accept(dict(frame_id=6*i, timestamp=dict(value=i, timescale=5)), i+1, i/5)
        self.assertAlmostEqual(m.snapshot()['sensor_hz_estimate'], 30)
        self.assertEqual(m.snapshot()['request_ms_p95'], 19)
        self.assertEqual(m.snapshot()['skipped_sensor_frames'], 95)

    def test_real_tcp_sequence_recovers_after_corruption(self):
        with tempfile.TemporaryDirectory() as directory, socket.socket() as server:
            server.bind(('127.0.0.1', 0))
            server.listen()
            server.settimeout(3)
            observed = []
            def serve():
                for i in range(3):
                    with server.accept()[0] as client:
                        client.settimeout(3)
                        observed.append(c.read_packet.__globals__['exact'](client, len(b'TD1 abcdef123456\n')))
                        packet = bytearray(c.demo_packet())
                        if i == 1:
                            packet[-1] ^= 1
                        client.sendall(packet)
            thread = threading.Thread(target=serve)
            thread.start()
            args = SimpleNamespace(duration=.55, fps=5, demo=False, host='127.0.0.1',
                                   port=server.getsockname()[1], token='abcdef123456', timeout=1, save_depth=True)
            folder, preview = Path(directory), c.Preview()
            c.capture(args, folder, preview, threading.Event())
            thread.join(4)
            self.assertFalse(thread.is_alive())
            summary = json.loads((folder / 'summary.json').read_text(encoding='utf-8'))
            self.assertEqual(summary['metrics']['received'], 2)
            self.assertEqual(summary['metrics']['errors'], 1)
            self.assertEqual(summary['metrics']['duplicates'], 1)
            self.assertEqual(len(list(folder.glob('frame-*/depth.f32le'))), 2)
            with (folder / 'measurements.csv').open(encoding='utf-8') as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual([r['outcome'] for r in rows], ['first', 'error', 'duplicate'])
            self.assertTrue(json.loads(preview.encode())['finished'])
            self.assertEqual(observed, [b'TD1 abcdef123456\n']*3)

    def test_http_preview_is_local_and_returns_consistent_frame(self):
        preview = c.Preview()
        server = c.make_server(preview)
        thread = threading.Thread(target=server.serve_forever)
        thread.start()
        try:
            self.assertEqual(server.server_address[0], '127.0.0.1')
            url = f'http://127.0.0.1:{server.server_port}'
            with urlopen(url + '/') as response:
                self.assertIn('CONTINUIDAD', response.read().decode())
            preview.update(status='Completado', finished=True)
            with urlopen(url + '/state') as response:
                self.assertEqual(response.headers['Cache-Control'], 'no-store')
                self.assertTrue(json.load(response)['finished'])
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_persistent_capture_records_stages_and_telemetry(self):
        from test_frame_transport import trailer
        with tempfile.TemporaryDirectory() as directory, socket.socket() as server:
            server.bind(('127.0.0.1', 0))
            server.listen()
            server.settimeout(3)
            observed = []
            def serve():
                with server.accept()[0] as client:
                    client.settimeout(3)
                    with client.makefile('rb') as reader:
                        for i in range(1, 4):
                            observed.append(reader.readline())
                            client.sendall(c.demo_packet() + trailer(i))
            thread = threading.Thread(target=serve)
            thread.start()
            args = SimpleNamespace(duration=.55, fps=5, demo=False, host='127.0.0.1',
                                   port=server.getsockname()[1], token='abcdef123456', timeout=1,
                                   save_depth=False, transport='persistent')
            folder = Path(directory)
            c.capture(args, folder, c.Preview(), threading.Event())
            thread.join(4)
            self.assertFalse(thread.is_alive())
            summary = json.loads((folder / 'summary.json').read_text())
            self.assertEqual(summary['metrics']['received'], 3)
            self.assertEqual(summary['connections'], 1)
            self.assertEqual(summary['reconnects'], 0)
            self.assertEqual(summary['timing_ms']['ios_prepare_ms']['mean'], 2)
            records = [json.loads(line) for line in (folder / 'ios-telemetry.jsonl').read_text().splitlines()]
            self.assertEqual([r['request_id'] for r in records], [1, 2, 3])
            with (folder / 'measurements.csv').open() as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(rows[1]['connect_ms'], '0.0')
            self.assertTrue(all(float(r['transaction_ms']) >= float(r['frame_request_ms']) for r in rows))
            self.assertEqual(len(observed), 3)

    def test_invalid_cli_rates(self):
        for value in ['nan', 'inf', '0', '-1']:
            with self.assertRaises(c.argparse.ArgumentTypeError):
                c.positive(value)


if __name__ == '__main__':
    unittest.main()
