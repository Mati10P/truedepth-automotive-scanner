"""Successive td-frame/1 requests; local live preview and reproducible measurements."""
import argparse
import base64
import csv
import io
import json
import math
from pathlib import Path
import socket
import threading
import time
import uuid
import webbrowser
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from receive_frame import read_packet, demo_packet
from frame_transport import FrameTransport

TIMING_FIELDS = ['request_id', 'connection_number', 'connect_ms', 'request_send_ms',
                 'rgb_receive_validate_ms',
                 'first_byte_ms', 'header_ms', 'payload_receive_ms', 'validation_ms',
                 'telemetry_ms', 'frame_request_ms', 'ios_queue_ms', 'ios_prepare_ms',
                 'ios_dispatch_ms', 'ios_send_ms', 'ios_connection_id', 'ios_session_id',
                 'transaction_ms', 'failure_stage']


class Metrics:
    def __init__(self):
        self.attempts = self.received = self.errors = self.unique = 0
        self.duplicates = self.skipped = self.resets = 0
        self.previous = None
        self.first_arrival = self.last_arrival = None
        self.latencies = []
        self.sensor_hz = None
        self.max_gap = 0.0

    def accept(self, header, elapsed_ms, arrival):
        self.received += 1
        self.latencies.append(elapsed_ms)
        stamp = header['timestamp']
        current = (header['frame_id'], stamp['value'] / stamp['timescale'])
        event = 'first'
        if self.previous is not None:
            delta = current[0] - self.previous[0]
            dt = current[1] - self.previous[1]
            if current == self.previous:
                self.duplicates += 1
                event = 'duplicate'
            elif delta > 0 and dt > 0:
                self.skipped += delta - 1
                self.sensor_hz = delta / dt
                event = 'new'
            else:
                self.resets += 1
                self.sensor_hz = None
                event = 'discontinuity'
        if event != 'duplicate':
            self.unique += 1
        self.previous = current
        if self.first_arrival is None:
            self.first_arrival = arrival
        if self.last_arrival is not None:
            self.max_gap = max(self.max_gap, arrival - self.last_arrival)
        self.last_arrival = arrival
        return event

    def snapshot(self):
        elapsed = (self.last_arrival or 0) - (self.first_arrival or 0)
        values = sorted(self.latencies)
        return dict(attempts=self.attempts, received=self.received, errors=self.errors,
                    unique=self.unique, duplicates=self.duplicates, skipped_sensor_frames=self.skipped,
                    discontinuities=self.resets, sensor_hz_estimate=self.sensor_hz,
                    max_valid_gap_s=self.max_gap if self.received > 1 else None,
                    error_percent=100 * self.errors / self.attempts if self.attempts else 0,
                    received_hz=(self.received - 1) / elapsed if elapsed > 0 else None,
                    request_ms_mean=sum(values) / len(values) if values else None,
                    request_ms_p95=values[math.ceil(len(values) * .95) - 1] if values else None,
                    request_ms_max=max(values) if values else None)


class Preview:
    def __init__(self):
        self.lock = threading.Lock()
        self.state = dict(status='Esperando primera captura', finished=False, metrics={}, frame=None)
        self.last_unique_arrival = None

    def note_unique(self, arrival):
        with self.lock:
            self.last_unique_arrival = arrival

    def update(self, **fields):
        with self.lock:
            self.state.update(fields)

    def encode(self):
        with self.lock:
            state = dict(self.state)
            state['unique_age_s'] = (max(0, time.perf_counter() - self.last_unique_arrival)
                                     if self.last_unique_arrival is not None else None)
            return json.dumps(state, ensure_ascii=False, allow_nan=False).encode('utf-8')


def make_server(preview, viewer='depth'):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == '/':
                name = {'cloud':'point_cloud.html','rgbd':'rgbd_viewer.html'}.get(viewer,'live_viewer.html')
                body = Path(__file__).with_name(name).read_bytes()
                mime = 'text/html; charset=utf-8'
            elif self.path in ('/point_cloud.js', '/cloud_math.js'):
                body = Path(__file__).with_name(self.path[1:]).read_bytes()
                mime = 'text/javascript; charset=utf-8'
            elif self.path == '/state':
                body, mime = preview.encode(), 'application/json'
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def log_message(self, *_):
            pass

    return ThreadingHTTPServer(('127.0.0.1', 0), Handler)


def request_frame(host, port, token, timeout):
    with socket.create_connection((host, port), timeout=timeout) as sock:
        sock.sendall(f'TD1 {token}\n'.encode('ascii'))
        return read_packet(sock)


def synthetic_frame(index, seconds):
    class MemorySocket:
        def __init__(self): self.data = io.BytesIO(demo_packet())
        def recv(self, count): return self.data.read(count)
    header, raw = read_packet(MemorySocket())
    header['frame_id'] = index
    header['timestamp'] = dict(value=round(seconds * 1_000_000), timescale=1_000_000, clock='synthetic')
    header['calibration'] = dict(intrinsic_matrix_rows=[[140, 0, 80], [0, 140, 60], [0, 0, 1]],
                                 intrinsic_reference_width=160, intrinsic_reference_height=120,
                                 synthetic=True)
    return header, raw


def capture(args, folder, preview, stop):
    metrics = Metrics()
    start = time.perf_counter()
    deadline = start + args.duration
    status = 'Completado'
    mode = getattr(args, 'transport', 'legacy')
    transport = None if args.demo else FrameTransport(args.host, args.port, args.token, mode)
    stages = {name: [] for name in TIMING_FIELDS if name.endswith('_ms')}
    errors = {}
    fields = ['attempt', 'received_at_utc', 'elapsed_s', 'request_ms', 'outcome', 'frame_id', 'timestamp_s', 'error'] + TIMING_FIELDS
    try:
        with (folder / 'measurements.csv').open('w', newline='', encoding='utf-8') as log, \
                (folder / 'ios-telemetry.jsonl').open('w', encoding='utf-8') as ios_log:
            writer = csv.DictWriter(log, fieldnames=fields)
            writer.writeheader()
            while not stop.is_set() and time.perf_counter() < deadline:
                began = time.perf_counter()
                metrics.attempts += 1
                row = dict(attempt=metrics.attempts)
                timings = {}
                try:
                    if args.demo:
                        header, raw = synthetic_frame(metrics.attempts, began - start)
                    else:
                        header, raw, telemetry = transport.request(
                            min(args.timeout, max(.001, deadline - began)), timings)
                        if telemetry is not None:
                            try:
                                ios_log.write(json.dumps(telemetry) + '\n')
                                ios_log.flush()
                            except OSError as exc:
                                raise RuntimeError(f'No se pudo guardar telemetría: {exc}') from exc
                    arrived = timings.get('frame_arrival', time.perf_counter())
                    elapsed_ms = (arrived - began) * 1000
                    # Legacy td-frame/1 validation does not require a sequence ID.
                    if type(header.get('frame_id')) is not int or header['frame_id'] < 0:
                        raise ValueError('frame_id inválido para medir continuidad')
                    event = metrics.accept(header, elapsed_ms, arrived)
                    if event != 'duplicate':
                        preview.note_unique(arrived)
                    for name in stages:
                        if name in timings:
                            stages[name].append(timings[name])
                    utc = datetime.now(timezone.utc).isoformat()
                    row.update(received_at_utc=utc, elapsed_s=arrived - start, request_ms=elapsed_ms,
                               outcome=event, frame_id=header['frame_id'],
                               timestamp_s=header['timestamp']['value'] / header['timestamp']['timescale'])
                    if args.save_depth:
                        try:
                            frame_dir = folder / f'frame-{metrics.attempts:06d}'
                            frame_dir.mkdir()
                            (frame_dir / 'depth.f32le').write_bytes(raw)
                            if transport and transport.rgb is not None:
                                (frame_dir / 'rgb.png').write_bytes(transport.rgb)
                            (frame_dir / 'metadata.json').write_text(json.dumps(header, indent=2), encoding='utf-8')
                        except OSError as exc:
                            raise RuntimeError(f'No se pudo guardar el frame: {exc}') from exc
                    preview.update(status='Recibiendo', frame=dict(header=header,
                                   raw=base64.b64encode(raw).decode('ascii'), attempt=metrics.attempts,
                                   rgb=base64.b64encode(transport.rgb).decode('ascii') if transport and transport.rgb is not None else None,
                                   received_at_utc=utc), metrics=metrics.snapshot(),
                                   frame_event=event,
                                   transport=mode, connections=transport.connections if transport else 0,
                                   timings={k: v for k, v in timings.items() if k in TIMING_FIELDS})
                except (OSError, ValueError, KeyError, TypeError) as exc:
                    if transport:
                        transport.close()
                    metrics.errors += 1
                    errors[str(exc)] = errors.get(str(exc), 0) + 1
                    row.update(outcome='error', error=str(exc), elapsed_s=time.perf_counter() - start,
                               request_ms=(time.perf_counter() - began) * 1000)
                    preview.update(status=f'Error de solicitud: {exc}', metrics=metrics.snapshot())
                row.update({key: value for key, value in timings.items() if key in TIMING_FIELDS})
                writer.writerow(row)
                log.flush()
                # One request in flight; never build a queue or burst to catch up.
                stop.wait(max(0, min(deadline - time.perf_counter(), 1 / args.fps - (time.perf_counter() - began))))
    except Exception as exc:
        status = f'Interrumpido por error: {exc}'
    finally:
        if transport:
            transport.close()
        if stop.is_set():
            status = 'Detenido'
        elif status == 'Completado' and metrics.errors:
            status = 'Completado con errores' if metrics.received else 'Sin capturas válidas'
        stage_summary = {name: dict(mean=sum(v)/len(v), p95=sorted(v)[math.ceil(len(v)*.95)-1],
                                   maximum=max(v), count=len(v)) for name, v in stages.items() if v}
        summary = dict(status=status, synthetic=args.demo, duration_s=time.perf_counter() - start,
                       transport=mode, connections=transport.connections if transport else 0,
                       reconnects=max(0, transport.connections - 1) if transport and mode != 'legacy' else 0,
                       timing_ms=stage_summary, errors_by_message=errors,
                       target_hz=args.fps, saved_depth=args.save_depth, metrics=metrics.snapshot(),
                       latency_definition='Request start to complete validated depth/RGB payloads; not sensor-to-screen latency',
                       skipped_definition='Sensor sequence IDs between requests, not network packet loss')
        (folder / 'summary.json').write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding='utf-8')
        preview.update(status=status, finished=True, metrics=metrics.snapshot())
        print(json.dumps(summary, indent=2, ensure_ascii=False), flush=True)


def positive(value):
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError('Debe ser un número positivo finito')
    return number


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--token')
    parser.add_argument('--demo', action='store_true')
    parser.add_argument('--viewer', choices=['depth', 'cloud', 'rgbd'], default='depth')
    parser.add_argument('--transport', choices=['persistent', 'legacy', 'rgbd'], default='persistent',
                        help='persistent requiere la app transporte v2; legacy usa una conexión por frame')
    parser.add_argument('--fps', type=positive, default=5)
    parser.add_argument('--duration', type=positive, default=600)
    parser.add_argument('--timeout', type=positive, default=5)
    parser.add_argument('--save-depth', action='store_true', help='Guardar todos los originales; puede ocupar varios GB')
    parser.add_argument('--no-open', action='store_true')
    parser.add_argument('--exit-on-complete', action='store_true')
    parser.add_argument('--output', type=Path, default=Path(__file__).resolve().parents[2] / 'captures')
    args = parser.parse_args()
    if args.transport == 'rgbd':
        args.viewer = 'rgbd'
        args.save_depth = True
        if args.demo:
            parser.error('La demo existente es depth-only; no simula sincronización RGB-D')
    if not args.demo:
        args.host = args.host or input('IP Wi-Fi del iPhone: ').strip()
        args.token = (args.token or input('Código de la app: ')).strip().lower()
        if len(args.token) != 12 or any(c not in '0123456789abcdef' for c in args.token):
            parser.error('El código debe tener 12 caracteres hexadecimales')
    folder = args.output.resolve() / ('sequence-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8])
    folder.mkdir(parents=True)
    preview, stop = Preview(), threading.Event()
    server = make_server(preview, args.viewer)
    serving = threading.Thread(target=server.serve_forever, daemon=True)
    serving.start()
    url = f'http://127.0.0.1:{server.server_port}/'
    print(f'Visor: {url}\nMediciones: {folder}\nCtrl+C para detener. Sin reconstrucción 3D.', flush=True)
    if not args.no_open:
        webbrowser.open(url)
    worker = threading.Thread(target=capture, args=(args, folder, preview, stop))
    worker.start()
    try:
        while worker.is_alive():
            worker.join(.2)
        if not args.exit_on_complete:
            print('Medición terminada. El visor sigue disponible; Ctrl+C para cerrar.', flush=True)
            while True:
                time.sleep(.2)
    except KeyboardInterrupt:
        stop.set()
        worker.join()
    finally:
        server.shutdown()
        server.server_close()


if __name__ == '__main__':
    main()
