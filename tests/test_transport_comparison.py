import csv
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from compare_transport import read_run, compare


class ComparisonTests(unittest.TestCase):
    def test_trailing_outage_and_legacy_summary(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            (folder / 'summary.json').write_text(json.dumps(dict(synthetic=False, duration_s=70)))
            with (folder / 'measurements.csv').open('w', newline='') as file:
                writer = csv.DictWriter(file, fieldnames=['elapsed_s', 'outcome', 'request_ms'])
                writer.writeheader()
                writer.writerows([dict(elapsed_s=1, outcome='first', request_ms=10),
                                  dict(elapsed_s=3, outcome='new', request_ms=20),
                                  dict(elapsed_s=65, outcome='error', request_ms=5000)])
            run = read_run(folder)
            self.assertEqual(run['transport'], 'legacy')
            self.assertEqual(run['max_valid_gap_s'], 2)
            self.assertEqual(run['max_silence_including_edges_s'], 67)
            self.assertEqual(run['received_hz'], .5)
            self.assertEqual(run['by_minute'][1]['errors'], 1)
            self.assertEqual(compare(run, run)['delta']['max_valid_gap_s'], 0)


if __name__ == '__main__':
    unittest.main()
