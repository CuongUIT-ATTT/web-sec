"""Synthetic exports, no source artifact access."""
import csv
import io
import json
import tempfile
from pathlib import Path
import unittest
from .test_metrics import fixture
from authz_lab.evaluation.metrics import evaluate
from authz_lab.evaluation.exports import comparison_csv, comparison_markdown, evidence_index, metrics_csv, _safe, _markdown


class ExportTests(unittest.TestCase):
    def test_consistent_identity_hash_and_determinism(self):
        o,t,p,s = fixture()
        result = evaluate(o,t,p,s)
        records = list(csv.DictReader(io.StringIO(comparison_csv(result))))
        index = json.loads(evidence_index(result))
        self.assertEqual(len(records),4)
        for row,entry in zip(records,index['cases']):
            for key in ('case_id','method','execution_id','observation_digest','source_artifact_hash',
                        'review_artifact_hash','validation_artifact_hash','manifest_digest','manifest_version'):
                with self.subTest(key=key):
                    self.assertEqual(row[key],entry[key])
                    self.assertIn(row[key],comparison_markdown(result))
        for exporter in (comparison_csv,comparison_markdown,evidence_index):
            with self.subTest(exporter=exporter.__name__), tempfile.TemporaryDirectory(prefix='cmp04-') as tmp:
                content = exporter(result)
                path = Path(tmp)/'synthetic.txt'
                path.write_text(content)
                self.assertEqual(path.read_text(),exporter(evaluate(o,reversed(t),reversed(p),s)))
                self.assertNotIn('/items/',content)

    def test_escape_formula_and_markdown(self):
        for value in ('=SUM(A1)', '+cmd', '-cmd', '@cmd', '  =cmd', '\t@cmd'):
            with self.subTest(value=value):
                self.assertTrue(_safe(value).startswith("'"))
        value = _markdown('<script>|`\\\r\n')
        self.assertNotIn('<script>',value)
        self.assertNotIn('|',value)
        self.assertNotIn('`',value)
        self.assertNotIn('\n',value)

    def test_null_exclusions_exported_without_negative(self):
        o,t,p,s = fixture()
        result = evaluate(o,[],[],s)
        index = json.loads(evidence_index(result))
        self.assertTrue(all(v['cell'] is None for v in index['cases']))
        self.assertEqual(index['summaries'][0]['TN'],0)
        self.assertIsNone(index['summaries'][0]['precision'])
        self.assertIn('UNREVIEWED_TRUTH',comparison_csv(result))
        for exporter in (comparison_csv,comparison_markdown,evidence_index):
            with self.subTest(exporter=exporter.__name__), self.assertRaises(ValueError):
                exporter({})

    def test_summary_csv_denominators_and_null(self):
        o,t,p,s = fixture()
        row = list(csv.DictReader(io.StringIO(metrics_csv(evaluate(o,t,p,s)))))[0]
        self.assertEqual(row['precision_denominator'],'2')
        self.assertEqual(row['precision'],'0.5')
        row = list(csv.DictReader(io.StringIO(metrics_csv(evaluate(o,[],[],s)))))[0]
        self.assertEqual(row['accuracy'],'')
        self.assertEqual(row['accuracy_denominator'],'0')
