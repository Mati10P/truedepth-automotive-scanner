"""Compare two recorded runs, including the pre-telemetry baseline CSV."""
import argparse
import csv
import json
from pathlib import Path


def read_run(folder):
    summary = json.loads((folder / 'summary.json').read_text(encoding='utf-8'))
    with (folder / 'measurements.csv').open(encoding='utf-8', newline='') as stream:
        rows = list(csv.DictReader(stream))
    valid = [float(row['elapsed_s']) for row in rows if row['outcome'] != 'error']
    gaps = [b-a for a, b in zip(valid, valid[1:])]
    errors = [row for row in rows if row['outcome'] == 'error']
    duration = summary['duration_s']
    return dict(folder=str(folder.resolve()), synthetic=summary['synthetic'],
                transport=summary.get('transport', 'legacy'), duration_s=duration,
                attempts=len(rows), received=len(valid), errors=len(errors),
                error_percent=100*len(errors)/len(rows) if rows else None,
                received_hz=(len(valid)-1)/(valid[-1]-valid[0]) if len(valid)>1 and valid[-1]>valid[0] else None,
                max_valid_gap_s=max(gaps) if gaps else None,
                max_silence_including_edges_s=max([*gaps, valid[0], duration-valid[-1]]) if valid else duration,
                connections=summary.get('connections'), reconnects=summary.get('reconnects'),
                timing_ms=summary.get('timing_ms', {}))


def compare(before, after):
    keys = ('received_hz', 'error_percent', 'max_valid_gap_s', 'max_silence_including_edges_s')
    return dict(before=before, after=after,
                delta={key: after[key]-before[key] if before[key] is not None and after[key] is not None else None
                       for key in keys},
                note='Difference is after minus before. Synthetic data does not validate physical transport.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('baseline', type=Path)
    parser.add_argument('candidate', type=Path)
    args = parser.parse_args()
    result = compare(read_run(args.baseline), read_run(args.candidate))
    target = args.candidate / 'comparison.json'
    target.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
