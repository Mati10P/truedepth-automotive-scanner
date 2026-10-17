"""Sequential TCP requests with a whole-request deadline and TD2 telemetry."""
import json
import math
import socket
import struct
import time

from receive_frame import exact, read_packet
from rgbd_frame import read_rgb


class DeadlineSocket:
    def __init__(self, sock, deadline, timings):
        self.sock, self.deadline, self.timings = sock, deadline, timings
        self.started = time.perf_counter()

    def recv(self, count):
        remaining = self.deadline - time.perf_counter()
        if remaining <= 0:
            raise TimeoutError('Plazo total de solicitud agotado')
        self.sock.settimeout(remaining)
        data = self.sock.recv(count)
        if data and 'first_byte_ms' not in self.timings:
            self.timings['first_byte_ms'] = (time.perf_counter() - self.started) * 1000
        return data


class FrameTransport:
    def __init__(self, host, port, token, mode='persistent'):
        if mode not in ('persistent', 'legacy', 'rgbd'):
            raise ValueError('Transporte desconocido')
        self.host, self.port, self.token, self.mode = host, port, token, mode
        self.sock = None
        self.connections = 0
        self.request_id = 0
        self.rgb = None

    def close(self):
        if self.sock is not None:
            self.sock.close()
            self.sock = None

    def request(self, timeout, timings):
        self.rgb = None
        start = time.perf_counter()
        deadline = start + timeout
        self.request_id += 1
        timings.update(request_id=self.request_id, connect_ms=0.0)
        try:
            timings['failure_stage'] = 'connect'
            if self.sock is None:
                self.sock = socket.create_connection((self.host, self.port), timeout=timeout)
                self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                self.connections += 1
                timings['connect_ms'] = (time.perf_counter() - start) * 1000
            timings['connection_number'] = self.connections
            remaining = deadline - time.perf_counter()
            if remaining <= 0:
                raise TimeoutError('Plazo total de conexión agotado')
            self.sock.settimeout(remaining)
            command = (f'{"TD3" if self.mode == "rgbd" else "TD2"} {self.token} {self.request_id}\n' if self.mode != 'legacy'
                       else f'TD1 {self.token}\n')
            timings['failure_stage'] = 'request_send'
            sent = time.perf_counter()
            self.sock.sendall(command.encode('ascii'))
            timings['request_send_ms'] = (time.perf_counter() - sent) * 1000
            source = DeadlineSocket(self.sock, deadline, timings)
            timings['failure_stage'] = 'frame_receive_or_validate'
            header, raw = read_packet(source, timings)
            color = None
            if self.mode == 'rgbd':
                began_rgb = time.perf_counter()
                color = read_rgb(source, header)
                timings['rgb_receive_validate_ms'] = (time.perf_counter()-began_rgb)*1000
                timings['frame_arrival'] = time.perf_counter()
            elif 'rgb' in header:
                raise ValueError('RGB no solicitado en transporte depth')
            telemetry = None
            if self.mode != 'legacy':
                timings['failure_stage'] = 'telemetry_receive_or_validate'
                trailer_start = time.perf_counter()
                size = struct.unpack('>I', exact(source, 4))[0]
                if not 0 < size <= 16384:
                    raise ValueError('Tamaño de telemetría inválido')
                telemetry = json.loads(exact(source, size))
                if (not isinstance(telemetry, dict) or telemetry.get('protocol') != 'td-telemetry/1'
                        or type(telemetry.get('request_id')) is not int
                        or telemetry['request_id'] != self.request_id):
                    raise ValueError('Telemetría no corresponde a la solicitud TD2')
                for key in ('queue_ms', 'prepare_ms', 'dispatch_ms', 'send_ms'):
                    value = telemetry.get(key)
                    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
                        raise ValueError(f'Telemetría inválida: {key}')
                    timings['ios_' + key] = value
                for key in ('connection_id', 'session_id'):
                    if not isinstance(telemetry.get(key), str) or not telemetry[key]:
                        raise ValueError(f'Telemetría inválida: {key}')
                    timings['ios_' + key] = telemetry[key]
                timings['telemetry_ms'] = (time.perf_counter() - trailer_start) * 1000
            timings['frame_request_ms'] = (timings['frame_arrival'] - start) * 1000
            timings['transaction_ms'] = (time.perf_counter() - start) * 1000
            timings['failure_stage'] = ''
            self.rgb = color  # Only expose the pair after telemetry is verified too.
            return header, raw, telemetry
        except Exception:
            # No in-place retry: each failure gets its own CSV row, then reconnect.
            self.close()
            raise
        finally:
            if self.mode == 'legacy':
                self.close()
