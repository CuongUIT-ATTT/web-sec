"""Pure CMP-04 contracts. Review/validation assertions require upstream attestation.

No artifact resolution, timing, execution, inferred predictions or historical joins.
"""
from dataclasses import dataclass
from .case_manifest import CaseDefinition, CaseManifest
from .observations import ObservationSet, METHODS, _opaque, _match, _HASH


@dataclass(frozen=True, slots=True)
class ReviewedTruth:
    manifest_digest: str
    manifest_version: str
    case_revision: CaseDefinition
    decision: str
    reviewed: bool
    review_artifact_ref: str
    review_artifact_hash: str

    def __post_init__(self):
        _binding(self.manifest_digest, self.manifest_version, self.case_revision)
        _decision(self.decision)
        if type(self.reviewed) is not bool:
            raise ValueError('Explicit review required')
        _opaque(self.review_artifact_ref, 'artifact')
        _match(_HASH, self.review_artifact_hash)


def _binding(digest, version, case):
    _match(_HASH, digest)
    if version != 'sha256:' + digest or type(case) is not CaseDefinition:
        raise ValueError('Invalid revision binding')


def _decision(value):
    if not isinstance(value, str) or value not in ('POSITIVE', 'NEGATIVE', 'UNKNOWN'):
        raise ValueError('Invalid vulnerability decision')


@dataclass(frozen=True, slots=True)
class ValidatedPrediction:
    observation_digest: str
    decision: str
    baseline_validated: bool
    protected_field_validated: bool
    policy_eligible: bool
    source_validated: bool
    validation_artifact_ref: str
    validation_artifact_hash: str

    def __post_init__(self):
        _match(_HASH, self.observation_digest)
        _decision(self.decision)
        for key in ('baseline_validated', 'protected_field_validated', 'policy_eligible', 'source_validated'):
            if type(getattr(self, key)) is not bool:
                raise ValueError('Explicit boolean validation required')
        _opaque(self.validation_artifact_ref, 'artifact')
        _match(_HASH, self.validation_artifact_hash)


@dataclass(frozen=True, slots=True)
class Selection:
    method: str
    execution_id: str

    def __post_init__(self):
        if not isinstance(self.method, str) or self.method not in METHODS:
            raise ValueError('Invalid method')
        _opaque(self.execution_id, 'execution')


@dataclass(frozen=True, slots=True)
class CaseScore:
    case_id: str
    method: str
    execution_id: str
    observation_digest: str | None
    source_artifact_ref: str | None
    source_artifact_hash: str | None
    review_artifact_ref: str | None
    review_artifact_hash: str | None
    validation_artifact_ref: str | None
    validation_artifact_hash: str | None
    cell: str | None
    exclusion_reason: str | None


@dataclass(frozen=True, slots=True)
class MetricsResult:
    manifest: CaseManifest
    selections: tuple[Selection, ...]
    rows: tuple[CaseScore, ...]

    def __post_init__(self):
        if type(self.manifest) is not CaseManifest or type(self.selections) is not tuple or not self.selections or type(self.rows) is not tuple:
            raise ValueError('Immutable result required')
        if any(type(s) is not Selection for s in self.selections) or len({s.method for s in self.selections}) != len(self.selections):
            raise ValueError('Invalid selections')
        expected = {(s.method, s.execution_id, c.case_id) for s in self.selections for c in self.manifest.cases}
        seen = set()
        reasons = {'EXECUTION_MISMATCH', 'NOT_RUN', 'INVALID', 'UNKNOWN', 'BLOCKED',
                   'UNVERIFIED_SOURCE', 'UNREVIEWED_TRUTH', 'UNKNOWN_TRUTH',
                   'UNVALIDATED_PREDICTION', 'UNKNOWN_PREDICTION',
                   'SOURCE_VALIDATED_REQUIRED', 'BASELINE_VALIDATED_REQUIRED',
                   'PROTECTED_FIELD_VALIDATED_REQUIRED', 'POLICY_ELIGIBLE_REQUIRED'}
        for row in self.rows:
            if type(row) is not CaseScore:
                raise ValueError('Invalid score')
            key = (row.method, row.execution_id, row.case_id)
            if key not in expected or key in seen:
                raise ValueError('Invalid score membership')
            seen.add(key)
            if row.observation_digest is not None:
                _match(_HASH, row.observation_digest)
            for prefix in ('source', 'review', 'validation'):
                ref, digest = getattr(row, prefix+'_artifact_ref'), getattr(row, prefix+'_artifact_hash')
                if ref is None and digest is None:
                    continue
                _opaque(ref, 'artifact')
                _match(_HASH, digest)
            if row.cell is None:
                if row.exclusion_reason not in reasons:
                    raise ValueError('Invalid exclusion')
            elif row.cell not in ('TP', 'FP', 'FN', 'TN') or row.exclusion_reason is not None or any(
                    getattr(row, name) is None for name in ('observation_digest', 'source_artifact_hash',
                                                          'review_artifact_hash', 'validation_artifact_hash')):
                raise ValueError('Invalid eligible score')
        if seen != expected:
            raise ValueError('Incomplete score coverage')

    def summary(self):
        result = []
        for selection in self.selections:
            rows = [r for r in self.rows if (r.method, r.execution_id) == (selection.method, selection.execution_id)]
            counts = {c: sum(r.cell == c for r in rows) for c in ('TP', 'FP', 'FN', 'TN')}
            tp, fp, fn, tn = (counts[c] for c in ('TP', 'FP', 'FN', 'TN'))
            ratio = lambda n, d: n / d if d else None
            result.append(dict(method=selection.method, execution_id=selection.execution_id,
                **counts, cohort_count=len(rows), eligible_count=tp+fp+fn+tn,
                excluded_count=sum(r.cell is None for r in rows),
                precision_denominator=tp+fp, recall_denominator=tp+fn,
                accuracy_denominator=tp+fp+fn+tn, precision=ratio(tp,tp+fp),
                recall=ratio(tp,tp+fn), accuracy=ratio(tp+tn,tp+fp+fn+tn)))
        return result


def evaluate(observations, truths, predictions, selections):
    """Score selected executions only; callers explicitly supply reviewed/validated claims.

    Access signals and human metadata are deliberately never used as decisions.
    Unselected observations remain inventory and cannot become negative predictions.
    """
    if type(observations) is not ObservationSet:
        raise ValueError('ObservationSet required')
    manifest = observations.manifest
    truth_map, prediction_map, selected = {}, {}, {}
    for truth in truths:
        if type(truth) is not ReviewedTruth:
            raise ValueError('ReviewedTruth required')
        if (truth.manifest_digest != manifest.content_digest or truth.manifest_version != manifest.version
                or manifest.require_case(truth.case_revision.case_id) != truth.case_revision):
            raise ValueError('Truth cohort/revision mismatch')
        key = truth.case_revision.case_id
        if key in truth_map:
            raise ValueError('Duplicate truth')
        truth_map[key] = truth
    known = {o.content_digest: o for o in observations.observations}
    for prediction in predictions:
        if type(prediction) is not ValidatedPrediction or prediction.observation_digest not in known:
            raise ValueError('Unknown prediction observation')
        if prediction.observation_digest in prediction_map:
            raise ValueError('Duplicate prediction')
        prediction_map[prediction.observation_digest] = prediction
    for selection in selections:
        if type(selection) is not Selection or selection.method in selected:
            raise ValueError('Select exactly one execution per method')
        selected[selection.method] = selection
    if not selected:
        raise ValueError('Explicit execution selection required')
    rows = []
    for selection in sorted(selected.values(), key=lambda s: s.method):
        inventory = {o.case_id: o for o in observations.observations
                     if o.method == selection.method and o.execution_id == selection.execution_id}
        for case in manifest.cases:
            obs = inventory.get(case.case_id)
            truth = truth_map.get(case.case_id)
            pred = prediction_map.get(obs.content_digest) if obs else None
            reason = None
            if obs is None:
                reason = 'EXECUTION_MISMATCH' if any(o.method == selection.method and o.case_id == case.case_id for o in observations.observations) else 'NOT_RUN'
            elif obs.execution_status != 'COMPLETED':
                reason = obs.execution_status
            elif obs.provenance is None:
                reason = 'UNVERIFIED_SOURCE'
            elif truth is None or not truth.reviewed:
                reason = 'UNREVIEWED_TRUTH'
            elif truth.decision == 'UNKNOWN':
                reason = 'UNKNOWN_TRUTH'
            elif pred is None:
                reason = 'UNVALIDATED_PREDICTION'
            else:
                for field in ('source_validated', 'baseline_validated', 'protected_field_validated', 'policy_eligible'):
                    if not getattr(pred, field):
                        reason = field.upper() + '_REQUIRED'
                        break
                if reason is None and pred.decision == 'UNKNOWN':
                    reason = 'UNKNOWN_PREDICTION'
            cell = None if reason else {('POSITIVE','POSITIVE'):'TP', ('NEGATIVE','POSITIVE'):'FP',
                ('POSITIVE','NEGATIVE'):'FN', ('NEGATIVE','NEGATIVE'):'TN'}[(truth.decision,pred.decision)]
            rows.append(CaseScore(case.case_id, selection.method, selection.execution_id,
                obs.content_digest if obs else None,
                obs.provenance.artifact_ref if obs and obs.provenance else None,
                obs.provenance.artifact_hash if obs and obs.provenance else None,
                truth.review_artifact_ref if truth else None, truth.review_artifact_hash if truth else None,
                pred.validation_artifact_ref if pred else None, pred.validation_artifact_hash if pred else None,
                cell, reason))
    return MetricsResult(manifest, tuple(sorted(selected.values(), key=lambda s: s.method)), tuple(rows))
