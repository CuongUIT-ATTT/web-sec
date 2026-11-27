"""Deterministic content-only exports; no paths, artifact reads or writes."""
import csv
import io
import json
from dataclasses import asdict
from .metrics import MetricsResult


def _safe(value):
    text = '' if value is None else str(value)
    return "'" + text if text.lstrip().startswith(('=', '+', '-', '@')) else text


def _records(result):
    if type(result) is not MetricsResult:
        raise ValueError('MetricsResult required')
    return [dict(manifest_digest=result.manifest.content_digest,
                 manifest_version=result.manifest.version, **asdict(row)) for row in result.rows]


def comparison_csv(result):
    records = _records(result)
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=list(records[0]), lineterminator='\n')
    writer.writeheader()
    writer.writerows({k: _safe(v) for k, v in row.items()} for row in records)
    return stream.getvalue()


def _markdown(value):
    return (_safe(value).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            .replace('\\', '&#92;').replace('|', '&#124;').replace('`', '&#96;')
            .replace('\r', '&#13;').replace('\n', '<br>'))


def comparison_markdown(result):
    records = _records(result)
    keys = list(records[0])
    lines = ['| ' + ' | '.join(keys) + ' |', '| ' + ' | '.join('---' for _ in keys) + ' |']
    lines += ['| ' + ' | '.join(_markdown(row[k]) for k in keys) + ' |' for row in records]
    return '\n'.join(lines) + '\n'


def evidence_index(result):
    return json.dumps(dict(schema_version=1, cases=_records(result), summaries=result.summary()),
                      sort_keys=True, separators=(',', ':'), ensure_ascii=True) + '\n'


def metrics_csv(result):
    """One summary per explicit method/execution; null ratios export as empty."""
    _records(result)
    records = result.summary()
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=['manifest_digest', 'manifest_version', *records[0]], lineterminator='\n')
    writer.writeheader()
    for row in records:
        writer.writerow({k: _safe(v) for k, v in dict(manifest_digest=result.manifest.content_digest,
            manifest_version=result.manifest.version, **row).items()})
    return stream.getvalue()
