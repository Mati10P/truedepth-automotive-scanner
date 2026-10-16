"""One-shot TrueDepth receiver and offline viewer. Python 3.11+, standard library."""
import argparse
import base64
import hashlib
import html
import json
import math
from pathlib import Path
import socket
import struct
import time
import uuid
import webbrowser
from datetime import datetime, timezone

MAX_HEADER = 1024 * 1024
MAX_PIXELS = 2048 * 2048


def exact(sock, count):
    result = bytearray()
    while len(result) < count:
        part = sock.recv(min(65536, count - len(result)))
        if not part:
            raise ValueError("Conexión cerrada antes de completar el frame (código incorrecto o sensor inactivo).")
        result.extend(part)
    return bytes(result)


def validate_header(header):
    if not isinstance(header, dict) or header.get("protocol") != "td-frame/1":
        raise ValueError("Protocolo no compatible")
    w, h = header.get("width"), header.get("height")
    if type(w) is not int or type(h) is not int or not (0 < w <= 2048 and 0 < h <= 2048 and w * h <= MAX_PIXELS):
        raise ValueError("Dimensiones inválidas")
    if header.get("encoding") != "float32-le" or header.get("units") != "meters":
        raise ValueError("Codificación/unidades no compatibles")
    if header.get("payload_bytes") != w * h * 4:
        raise ValueError("Tamaño de payload incorrecto")
    if header.get("source") not in ("iphone-truedepth", "synthetic-demo"):
        raise ValueError("Origen desconocido")
    ts = header.get("timestamp")
    if not isinstance(ts, dict) or type(ts.get("timescale")) is not int or ts["timescale"] <= 0 or type(ts.get("value")) is not int:
        raise ValueError("Timestamp inválido")
    if not isinstance(header.get("sha256"), str) or len(header["sha256"]) != 64:
        raise ValueError("Checksum inválido")
    if "calibration" not in header:
        raise ValueError("Falta estado de calibración")


def read_packet(sock, timings=None):
    began = time.perf_counter()
    size = struct.unpack(">I", exact(sock, 4))[0]
    if not 0 < size <= MAX_HEADER:
        raise ValueError("Cabecera demasiado grande o vacía")
    header = json.loads(exact(sock, size))
    validate_header(header)
    payload_start = time.perf_counter()
    raw = exact(sock, header["payload_bytes"])
    payload_end = time.perf_counter()
    if hashlib.sha256(raw).hexdigest() != header["sha256"]:
        raise ValueError("SHA-256 incorrecto: se rechaza el frame")
    if timings is not None:
        timings.update(header_ms=(payload_start - began) * 1000,
                       payload_receive_ms=(payload_end - payload_start) * 1000,
                       validation_ms=(time.perf_counter() - payload_end) * 1000,
                       frame_arrival= time.perf_counter())
    return header, raw


def demo_packet():
    w, h = 160, 120
    values = [float("nan") if x < 8 else 0.35 + 0.3 * x / w + 0.06 * math.sin(y / 12)
              for y in range(h) for x in range(w)]
    raw = struct.pack(f"<{len(values)}f", *values)
    header = {"protocol": "td-frame/1", "source": "synthetic-demo", "frame_id": 0,
              "width": w, "height": h, "encoding": "float32-le", "units": "meters",
              "payload_bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
              "timestamp": {"value": 0, "timescale": 1, "seconds": 0, "clock": "synthetic"},
              "calibration": None, "orientation": "synthetic"}
    encoded = json.dumps(header).encode()
    return struct.pack(">I", len(encoded)) + encoded + raw


def save_frame(header, raw, root):
    folder = root.resolve() / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8])
    folder.mkdir(parents=True, exist_ok=False)
    # No lossy conversion: persist original sensor bytes and metadata before preview.
    (folder / "depth.f32le").write_bytes(raw)
    (folder / "metadata.json").write_text(json.dumps(header, indent=2, ensure_ascii=False), encoding="utf-8")
    values = [v[0] for v in struct.iter_unpack("<f", raw)]
    valid = [v for v in values if math.isfinite(v) and v > 0]
    info = {"valid_pixels": len(valid), "total_pixels": len(values),
            "minimum_m": min(valid) if valid else None, "maximum_m": max(valid) if valid else None,
            "received_at_utc": datetime.now(timezone.utc).isoformat()}
    (folder / "receipt.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
    title = "DEMO SINTÉTICA · no es una captura del iPhone" if header["source"] == "synthetic-demo" else "Frame recibido · iPhone TrueDepth"
    metadata = html.escape(json.dumps(header, indent=2, ensure_ascii=False))
    calibration = "Calibración disponible (ver metadatos)" if header["calibration"] is not None else "SIN CALIBRACIÓN · hito físico incompleto"
    template = Path(__file__).with_name("viewer.html").read_text(encoding="utf-8")
    replacements = {"TITLE": title, "WIDTH": str(header["width"]), "HEIGHT": str(header["height"]),
                    "VALID": f"{len(valid)}/{len(values)}", "CALIBRATION": calibration,
                    "TIMESTAMP": html.escape(str(header["timestamp"])), "METADATA": metadata,
                    "BASE64": base64.b64encode(raw).decode("ascii")}
    for key, value in replacements.items():
        template = template.replace("{{" + key + "}}", value)
    viewer = folder / "frame.html"
    viewer.write_text(template, encoding="utf-8")
    return viewer


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", help="IP Wi-Fi del iPhone")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--token", help="Código visible en la app; se pregunta si se omite")
    parser.add_argument("--demo", action="store_true", help="Prueba sintética, sin iPhone")
    parser.add_argument("--no-open", action="store_true")
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[2] / "captures")
    args = parser.parse_args()
    try:
        if args.demo:
            # Same decoder as a device, including length and SHA validation.
            import io
            class MemorySocket:
                def __init__(self, data): self.data = io.BytesIO(data)
                def recv(self, count): return self.data.read(count)
            header, raw = read_packet(MemorySocket(demo_packet()))
        else:
            host = args.host or input("IP Wi-Fi del iPhone: ").strip()
            token = args.token or input("Código de la app: ").strip().lower()
            if len(token) != 12 or any(c not in "0123456789abcdef" for c in token):
                raise ValueError("El código debe tener 12 caracteres hexadecimales")
            with socket.create_connection((host, args.port), timeout=15) as sock:
                sock.sendall(f"TD1 {token}\n".encode("ascii"))
                header, raw = read_packet(sock)
        viewer = save_frame(header, raw, args.output)
        print(f"SHA-256 verificado. Frame {header['width']} x {header['height']}")
        print(f"Origen: {header['source']}")
        print(f"Visor: {viewer}")
        if not args.no_open:
            webbrowser.open(viewer.as_uri())
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(1, f"No se recibió un frame válido: {exc}\n")


if __name__ == "__main__":
    main()
