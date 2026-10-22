"""Authenticated v9 focus control; accepts confirmed stable actual position, reports requested and actual."""
import argparse
import json
import math
import socket
import time


def request(host, token, command, port=8765):
    if len(token) != 12 or any(c not in '0123456789abcdef' for c in token):
        raise ValueError('Invalid app code')
    with socket.create_connection((host, port), timeout=8) as sock:
        sock.sendall(f'TDF {token} {command}\n'.encode('ascii'))
        data = bytearray()
        while not data.endswith(b'\n'):
            chunk = sock.recv(1024)
            if not chunk:
                raise RuntimeError('No control response; v9 is required')
            data.extend(chunk)
            if len(data) > 16384:
                raise RuntimeError('Oversized control response')
    result = json.loads(data)
    if result.get('ok') is not True:
        raise RuntimeError(result.get('error', 'Control failed'))
    return result


def set_focus(host, token, position, port=8765):
    if not math.isfinite(position) or not 0 <= position <= 1:
        raise ValueError('Lens position must be finite and within 0..1')
    result = request(host, token, f'set:{position:.17g}', port)
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        if (result.get('lock_confirmed') is True and result.get('state') == 'locked'
                and result.get('is_adjusting') is False
                and math.isfinite(result.get('lens_position', float('nan')))
                and 0 <= result['lens_position'] <= 1):
            return result
        if result.get('state') in ('failed', 'invalidated', 'unsupported'):
            raise RuntimeError(f'Focus failed: {result}')
        time.sleep(.25)
        result = request(host, token, 'status', port)
    raise TimeoutError(f'Focus not confirmed at requested position: {result}')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--host', required=True)
    p.add_argument('--token', required=True)
    p.add_argument('--position', type=float)
    a = p.parse_args()
    result = request(a.host, a.token, 'status') if a.position is None else set_focus(a.host, a.token, a.position)
    print(json.dumps(result, indent=2))
