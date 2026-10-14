"""Read-only EXStar inventory: hashes, topics and controller/library mappings."""

import argparse
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def inventory(source):
    # Only installation binaries at the top level: omit logs and user projects.
    binaries = [
        {"name": path.name, "bytes": path.stat().st_size, "sha256": sha256(path)}
        for path in sorted(source.iterdir(), key=lambda p: p.name.lower())
        if path.is_file() and path.suffix.lower() in {".exe", ".dll"}
    ]
    configurations = []
    for name in ("App_EA.xml", "ScanService.xml"):
        path = source / name
        root = ET.parse(path).getroot()
        topics = []
        for topic in root.findall("./topics/topic"):
            topics.append({
                "name": topic.findtext("name"),
                "type": topic.findtext("type"),
                "publishers": [p.findtext("name") for p in topic.findall("./publishers/publisher")],
                "subscribers": [p.findtext("name") for p in topic.findall("./subscribers/subscriber")],
            })
        # Explicit allowlist: never serialize whole elements or other settings.
        controllers = [
            {"name": controller.findtext("name"), "library": controller.findtext("libpath")}
            for controller in root.findall(".//controllerobject")
        ]
        configurations.append({"name": name, "sha256": sha256(path),
                               "topics": topics, "controllers": controllers})
    return {"schema_version": 2, "scope": "root EXE/DLL files and explicit topic/controller allowlists",
            "binaries": binaries, "configurations": configurations}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source, output = args.source.resolve(), args.output.resolve()
    if not (source / "EXStar.exe").is_file():
        parser.error("Source must contain EXStar.exe")
    if output == source or source in output.parents:
        parser.error("Output must be outside the EXStar installation")
    if output.exists():
        parser.error("Output exists; choose a new evidence file")
    result = inventory(source)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(f"Inventoried {len(result['binaries'])} binaries and "
          f"{sum(len(c['topics']) for c in result['configurations'])} topics: {output}")


if __name__ == "__main__":
    main()
