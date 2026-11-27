"""Synthetic only: asserted reviews are not real human attestation."""
from dataclasses import replace
import unittest
from authz_lab.evaluation.case_manifest import CaseDefinition, CaseManifest
from authz_lab.evaluation.observations import Observation, ObservationSet, Provenance
from authz_lab.evaluation.metrics import ReviewedTruth, ValidatedPrediction, Selection, evaluate


def fixture():
    cases = [CaseDefinition('GET','/items/{item}', 'actor-'+hex(i)[2:]*32,
        'reader','owner-'+'b'*32,'OTHER','v1','c'*64,'policy','v1','DENY') for i in range(1,5)]
    manifest = CaseManifest.build(cases)
    obs = [Observation('T18',manifest.content_digest,manifest.version,c,'execution-'+'d'*32,
        'COMPLETED','ACCESS_ALLOWED',Provenance('artifact-'+'e'*32,'f'*64,'AUTOMATED_VERIFIER','v1',None)) for c in manifest.cases]
    truths = [ReviewedTruth(manifest.content_digest,manifest.version,o.case_revision,
        t,True,'artifact-'+'1'*32,'2'*64) for o,t in zip(obs,['POSITIVE','NEGATIVE','POSITIVE','NEGATIVE'])]
    preds = [ValidatedPrediction(o.content_digest,p,True,True,True,True,'artifact-'+'3'*32,'4'*64)
             for o,p in zip(obs,['POSITIVE','POSITIVE','NEGATIVE','NEGATIVE'])]
    return ObservationSet.build(manifest,obs), truths, preds, [Selection('T18','execution-'+'d'*32)]


class MetricsTests(unittest.TestCase):
    def test_four_cells_and_deterministic_order(self):
        o,t,p,s = fixture()
        r = evaluate(o,t,p,s)
        self.assertEqual([x.cell for x in r.rows], ['TP','FP','FN','TN'])
        self.assertEqual(r,evaluate(o,reversed(t),reversed(p),s))
        summary = r.summary()[0]
        for name in ('TP','FP','FN','TN'):
            self.assertEqual(summary[name],1)
        for name in ('precision','recall','accuracy'):
            self.assertEqual(summary[name],0.5)
        self.assertEqual(summary['eligible_count'],4)

    def test_exclusion_gates_and_null_denominators(self):
        o,t,p,s = fixture()
        for field,reason in [('source_validated','SOURCE_VALIDATED_REQUIRED'),
                ('baseline_validated','BASELINE_VALIDATED_REQUIRED'),
                ('protected_field_validated','PROTECTED_FIELD_VALIDATED_REQUIRED'),
                ('policy_eligible','POLICY_ELIGIBLE_REQUIRED')]:
            with self.subTest(field=field):
                r = evaluate(o,t,[replace(v,**{field:False}) for v in p],s)
                self.assertEqual({x.exclusion_reason for x in r.rows},{reason})
                self.assertEqual(r.summary()[0]['eligible_count'],0)
                self.assertIsNone(r.summary()[0]['accuracy'])
        for truths,preds,reason in [([],p,'UNREVIEWED_TRUTH'),
                ([replace(v,reviewed=False) for v in t],p,'UNREVIEWED_TRUTH'),
                ([replace(v,decision='UNKNOWN') for v in t],p,'UNKNOWN_TRUTH'),
                (t,[],'UNVALIDATED_PREDICTION'),
                (t,[replace(v,decision='UNKNOWN') for v in p],'UNKNOWN_PREDICTION')]:
            with self.subTest(reason=reason):
                self.assertEqual({x.exclusion_reason for x in evaluate(o,truths,preds,s).rows},{reason})

    def test_statuses_missing_source_execution_and_absent(self):
        o,t,p,s = fixture()
        for status in ('NOT_RUN','INVALID','UNKNOWN','BLOCKED'):
            with self.subTest(status=status):
                changed = ObservationSet.build(o.manifest,[replace(v,execution_status=status,signal='UNKNOWN') for v in o.observations])
                r = evaluate(changed,t,[],s)
                self.assertEqual({x.exclusion_reason for x in r.rows},{status})
                self.assertEqual(r.summary()[0]['TN'],0)
        changed = ObservationSet.build(o.manifest,[replace(v,provenance=None) for v in o.observations])
        self.assertEqual({x.exclusion_reason for x in evaluate(changed,t,[],s).rows},{'UNVERIFIED_SOURCE'})
        self.assertEqual({x.exclusion_reason for x in evaluate(o,t,p,[replace(s[0],execution_id='execution-'+'9'*32)]).rows},{'EXECUTION_MISMATCH'})
        self.assertEqual({x.exclusion_reason for x in evaluate(ObservationSet.build(o.manifest,[]),t,[],s).rows},{'NOT_RUN'})

    def test_signals_and_human_metadata_never_predict(self):
        o,t,p,s = fixture()
        for method,kind,signal in [('ZAP','ZAP','ILLEGAL'),('MANUAL','HUMAN','ACCESS_ALLOWED')]:
            with self.subTest(method=method):
                changed = ObservationSet.build(o.manifest,[replace(v,method=method,signal=signal,
                    provenance=replace(v.provenance,producer_kind=kind,operator_alias='operator-'+'5'*32 if kind=='HUMAN' else None)) for v in o.observations])
                r = evaluate(changed,t,[],[replace(s[0],method=method)])
                self.assertEqual({x.exclusion_reason for x in r.rows},{'UNVALIDATED_PREDICTION'})

    def test_reject_duplicate_unknown_malformed_mismatch(self):
        o,t,p,s = fixture()
        for truths,preds,selections in [(t+t[:1],p,s),(t,p+p[:1],s),(t,p,s+s),
                (t,p,[]),(t,[replace(p[0],observation_digest='0'*64)],s),
                ([replace(t[0],manifest_digest='0'*64,manifest_version='sha256:'+'0'*64)],p,s),
                ([None],p,s),(t,[None],s),(t,p,[None])]:
            with self.subTest(truths=len(truths),preds=len(preds),selections=len(selections)), self.assertRaises(ValueError):
                evaluate(o,truths,preds,selections)
        for value in (None,1,'yes',[]):
            with self.subTest(value=value), self.assertRaises(ValueError):
                replace(p[0],baseline_validated=value)
        for field,value in [('decision','ALLOW'),('validation_artifact_ref','/tmp/file'),
                            ('validation_artifact_hash','secret')]:
            with self.subTest(field=field), self.assertRaises(ValueError):
                replace(p[0],**{field:value})
        with self.assertRaises(ValueError):
            evaluate(o,[replace(t[0],case_revision=replace(t[0].case_revision,actor_role='admin'))],p,s)

    def test_result_rejects_unsafe_or_incomplete_export_rows(self):
        o,t,p,s = fixture()
        result = evaluate(o,t,p,s)
        for row in (replace(result.rows[0],source_artifact_ref='/tmp/secret'),
                    replace(result.rows[0],exclusion_reason='=cmd'),
                    replace(result.rows[0],cell='UNKNOWN'),
                    replace(result.rows[0],source_artifact_hash=None)):
            with self.subTest(row=row), self.assertRaises(ValueError):
                replace(result,rows=(row,*result.rows[1:]))
        with self.assertRaises(ValueError):
            replace(result,rows=result.rows[:-1])
        with self.assertRaises(ValueError):
            replace(result,rows=result.rows+result.rows[:1])
