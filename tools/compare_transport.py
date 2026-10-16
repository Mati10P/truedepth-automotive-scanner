"""Compare two recorded runs, including the pre-telemetry baseline CSV."""
import argparse
import csv
import json
import math
from pathlib import Path


def read_run(folder):
    summary = json.loads((folder / 'summary.json').read_text(encoding='utf-8'))
    with (folder / 'measurements.csv').open(encoding='utf-8', newline='') as stream:
        rows = list(csv.DictReader(stream))
    valid = [float(row['elapsed_s']) for row in rows if row['outcome'] != 'error']
    gaps = [b-a for a, b in zip(valid, valid[1:])]
    errors = [row for row in rows if row['outcome'] == 'error']
    duration = summary['duration_s']
    by_minute = [dict(minute=i+1, received=0, errors=0) for i in range(max(1, math.ceil(duration/60)))]
    for row in rows:
        bucket = min(int(float(row['elapsed_s'])//60), len(by_minute)-1)
        by_minute[bucket]['errors' if row['outcome'] == 'error' else 'received'] += 1
    timing_keys = ('request_ms', 'first_byte_ms', 'payload_receive_ms', 'validation_ms',
                   'ios_queue_ms', 'ios_prepare_ms', 'ios_dispatch_ms', 'ios_send_ms', 'telemetry_ms')
    slowest = []
    for row in sorted(rows, key=lambda r: float(r['request_ms']), reverse=True)[:10]:
        item = {key: row.get(key, '') for key in ('attempt', 'outcome', 'error', 'failure_stage')}
        item.update({key: float(row[key]) for key in timing_keys if row.get(key)})
        slowest.append(item)
    return dict(folder=str(folder.resolve()), synthetic=summary['synthetic'],
                transport=summary.get('transport', 'legacy'), duration_s=duration,
                attempts=len(rows), received=len(valid), errors=len(errors),
                error_percent=100*len(errors)/len(rows) if rows else None,
                received_hz=(len(valid)-1)/(valid[-1]-valid[0]) if len(valid)>1 and valid[-1]>valid[0] else None,
                max_valid_gap_s=max(gaps) if gaps else None,
                max_silence_including_edges_s=max([*gaps, valid[0], duration-valid[-1]]) if valid else duration,
                connections=summary.get('connections'), reconnects=summary.get('reconnects'),
                timing_ms=summary.get('timing_ms', {}), errors_by_message=summary.get('errors_by_message', {}),
                by_minute=by_minute, slowest_requests=slowest)


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
