"""Guard-only replay of identical recorded baseline candidates; no inference."""
import copy
import json
from pathlib import Path
from time import perf_counter

from app.analysis.ast_guard import apply
from app.llm.schemas import Finding, ModelResponse
from app.validation.evidence_validator import validate
from ui.reports import html_report


def replay():
    baseline = json.loads(Path('.local/guard-baseline-live.json').read_text())
    source = {str(p.relative_to('demo_ecu')).replace('\\','/'):p.read_bytes().decode('utf-8')
              for p in Path('demo_ecu').rglob('*') if p.suffix in ('.cpp','.c','.h','.hpp')}
    manifest = {'source':source,'repository':'demo_ecu','snapshot':baseline['snapshot'],
                'chunks':[dict(symbol=e['function']) for r in baseline['runs'] for e in r['evidence'] if e['kind']=='source']}
    modes = []
    for policy in ('annotation','strict'):
        cases,records,seconds = [],[],0
        for case,run in zip(baseline['cases'],baseline['runs'][:30]):
            if run['outcome'] == 'FAILED':
                cases.append(copy.deepcopy(case) | {'guard_records':[]})
                continue  # Retained miss in the same denominator; no valid candidate to guard.
            response = ModelResponse(outcome=run['outcome'],findings=[Finding.model_validate({k:f[k] for k in Finding.model_fields}) for f in run['findings']],claims=[],limitations=[])
            started = perf_counter()
            response, checks = apply(response,manifest,policy)
            validate(response,{'task':run['mode'],'evidence':run['evidence']},manifest)
            seconds += perf_counter()-started
            records += checks
            revised = copy.deepcopy(case)
            revised.update(outcome=response.outcome,categories=[f.category for f in response.findings],
                correct_defect_found=any(f.category==case['expected']['expected_defect'] for f in response.findings),
                false_positive=case['expected']['expected_defect'] is None and bool(response.findings),guard_records=checks)
            cases.append(revised)
        tp=sum(c['correct_defect_found'] for c in cases if c['expected']['expected_defect'])
        fp=sum(c['false_positive'] for c in cases)
        suppressed=[r for r in records if r['effective_candidate'] is None]
        labels={c['function']:c['expected']['expected_defect'] for c in cases}
        modes.append({'policy':policy,'cases':cases,'records':records,'guard_and_validation_seconds':seconds,
            'metrics':{'true_positives':tp,'false_negatives':20-tp,'safe_false_positives':fp,'precision':tp/(tp+fp) if tp+fp else 0,'strict_recall':tp/20,'safe_fp_rate':fp/10},
            'suppressed_true_positive_candidates':sum(labels[r['original_candidate']['function']]==r['original_candidate']['category'] for r in suppressed),
            'suppressed_safe_false_positive_candidates':sum(labels[r['original_candidate']['function']] is None for r in suppressed),
            'suppressed_candidates':len(suppressed),'model_calls':0,'embedding_calls':0})
    result={'source':'Identical saved baseline candidates; final deterministic guard implementation; no inference or operational writes',
            'snapshot':manifest['snapshot'],'modes':modes}
    Path('docs/evaluation/guard-paired-replay.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    # Real guarded benchmark reports, not simulated reviewer decisions.
    for label in ('guarded-a','guarded-b'):
        live=json.loads(Path('.local/guard-'+label+'-live.json').read_text())
        run=next(r for r in live['runs'] if any(g['ast_guard_result']['checks'] for g in r.get('ast_guards',[])))
        document={'report_version':1,'run':run,'notice':'Fixed synthetic benchmark run; decisions remain pending.',
            'reviewed_findings':[{'original':f,'effective_finding':f,'history':[],'disposition':'PENDING','revision':0,
                'current_validation_status':'VALID_PROVENANCE','evidence_support':f['evidence_support']} for f in run['findings']]}
        validate(ModelResponse(outcome=run['outcome'],findings=[Finding.model_validate({k:f[k] for k in Finding.model_fields}) for f in run['findings']],claims=[],limitations=[]),
                 {'task':run['mode'],'evidence':run['evidence']},manifest)
        Path('.local/guard-'+label+'-report.json').write_text(json.dumps(document,indent=2),encoding='utf-8')
        Path('docs/demonstrations/guard-'+label+'-report.html').write_text(html_report(document),encoding='utf-8')
    print(json.dumps({m['policy']:{k:v for k,v in m.items() if k not in ('cases','records')} for m in modes},indent=2))


if __name__ == '__main__':
    replay()
