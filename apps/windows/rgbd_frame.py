"""TD3 RGB extension. Depth retains the td-frame/1 layout and checksum."""
import hashlib
import math
import struct
from fractions import Fraction

from receive_frame import exact

MAX_RGB_BYTES = 32 * 1024 * 1024


def timestamp(value):
    if (not isinstance(value, dict) or type(value.get('value')) is not int
            or type(value.get('timescale')) is not int or value['timescale'] <= 0
            or value.get('clock') != 'capture-session'):
        raise ValueError('Timestamp RGB-D inválido')
    return Fraction(value['value'], value['timescale'])


def validate_rgb_header(header):
    rgb = header.get('rgb')
    sync = header.get('synchronization')
    if not isinstance(rgb, dict) or rgb.get('protocol') != 'td-rgb/1' or rgb.get('encoding') != 'png':
        raise ValueError('Falta RGB PNG compatible; se requiere app RGB-D v3')
    if (type(rgb.get('frame_id')) is not int or type(header.get('frame_id')) is not int
            or rgb['frame_id'] != header['frame_id']):
        raise ValueError('RGB y depth pertenecen a frames diferentes')
    w, h = rgb.get('width'), rgb.get('height')
    if (type(w) is not int or type(h) is not int or not (0 < w <= 8192 and 0 < h <= 8192)
            or w*h > 20_000_000):
        raise ValueError('Dimensiones RGB inválidas')
    size = rgb.get('payload_bytes')
    if type(size) is not int or not 24 <= size <= MAX_RGB_BYTES:
        raise ValueError('Tamaño RGB inválido')
    checksum = rgb.get('sha256')
    if not isinstance(checksum, str) or len(checksum) != 64 or any(c not in '0123456789abcdef' for c in checksum):
        raise ValueError('Checksum RGB inválido')
    if (not isinstance(sync, dict) or sync.get('method') != 'AVCaptureDataOutputSynchronizer'
            or sync.get('depth_dropped') is not False or sync.get('rgb_dropped') is not False):
        raise ValueError('Par incompleto o no sincronizado')
    delta = float((timestamp(rgb.get('timestamp'))-timestamp(header.get('timestamp')))*1000)
    declared = sync.get('timestamp_delta_ms')
    if (abs(delta) > 1 or type(declared) not in (int,float) or not math.isfinite(declared)
            or abs(delta-declared) > .00001):
        raise ValueError('RGB y depth no cumplen el límite de sincronización de 1 ms')
    return rgb


def read_rgb(sock, header):
    rgb = validate_rgb_header(header)
    data = exact(sock, rgb['payload_bytes'])
    if hashlib.sha256(data).hexdigest() != rgb['sha256']:
        raise ValueError('SHA-256 RGB incorrecto')
    if (data[:8] != b'\x89PNG\r\n\x1a\n' or data[12:16] != b'IHDR'
            or struct.unpack('>II',data[16:24]) != (rgb['width'],rgb['height'])):
        raise ValueError('Cabecera PNG no coincide con los metadatos RGB')
    return data
