"""Local repository-wide demonstration; never triggers CI or builds reviewed source."""
import argparse
import hashlib
import json
from pathlib import Path
import time
from ui.client import API


def fixed_metrics(cases):
    """Preserve the original 20-defect/10-safe corpus and visible auxiliary cases."""
    for case in cases:
        case['included_in_fixed_evaluation'] = case['function'] != 'sensorConnected'
    fixed = [c for c in cases if c['included_in_fixed_evaluation']]
    defects = [c for c in fixed if c['expected']['expected_defect']]
    safe = [c for c in fixed if c['expected']['expected_defect'] is None]
    if len(defects) != 20 or len(safe) != 10:
        raise ValueError('Fixed evaluation requires the original 20 defective and 10 safe functions')
    tp = sum(c['correct_defect_found'] for c in defects)
    fp = sum(c['false_positive'] for c in safe)
    return {'defective_functions': len(defects), 'safe_functions': len(safe),
            'true_positives': tp, 'false_negatives': len(defects) - tp, 'false_positives': fp,
            'precision_per_labeled_function': tp / (tp + fp) if tp + fp else None,
            'recall': tp / len(defects), 'safe_false_positive_rate': fp / len(safe),
            'remaining_misses': [c['function'] for c in defects if not c['correct_defect_found']],
            'safe_false_positives': [c['function'] for c in safe if c['false_positive']],
            'auxiliary_functions': [c['function'] for c in cases if not c['included_in_fixed_evaluation']],
            'auxiliary_safe_false_positives': [c['function'] for c in cases
                if not c['included_in_fixed_evaluation'] and c['false_positive']]}


def demonstrate(destination, summary=None):
    root = Path(__file__).resolve().parents[1]
    protected = [root / 'tests/fixtures/expected_defects.json', root / 'rules/coding_rules.md',
                 root / '.local/review-evaluation.json', root / '.local/final-evaluation.json']
    hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
    api = API((root / '.local/demo-token.txt').read_text().strip())
    indexed = api.request('/repositories/index', {'repository': 'demo_ecu'})
    created = api.request('/review/repository', {'repository': 'demo_ecu', 'snapshot': indexed['snapshot']})
    identifier = created['id']
    print(json.dumps({'repository_run': identifier, 'snapshot': indexed['snapshot'], 'scan_seconds': indexed['scan_seconds']}), flush=True)
    previous = -1
    while True:
        progress = api.request('/repository-reviews/' + identifier + '?repository=demo_ecu')
        count = len(progress['results'])
        if count != previous:
            print(json.dumps({'reviewed':count,'total':len(progress['functions']), 'current':progress['current_function'], 'status':progress['status']}),flush=True)
            previous = count
        if progress['status'] != 'RUNNING':
            break
        time.sleep(2)
    document = api.request('/repository-reviews/' + identifier + '/report?repository=demo_ecu')
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(document, indent=2), encoding='utf-8')
    fixtures = json.loads((root / 'tests/fixtures/expected_defects.json').read_text())
    children = {r['function']:r for r in progress['results']}
    docs = {d['run']['id']: d for d in document['function_reports']}
    cases=[]
    for name, expected in fixtures.items():
        result=children.get(name)
        if result is None:
            raise ValueError('Fixed fixture function missing from enumeration')
        findings=docs[result['run_id']]['run']['findings']
        correct=any(f['function']==name and f['file']==expected['expected_file'] and
            f['category']==expected['expected_defect'] and f['start_line']<=expected['expected_range'][1] and f['end_line']>=expected['expected_range'][0] for f in findings)
        false=expected['expected_defect'] is None and any(f['function']==name for f in findings)
        cases.append({'function':name,'expected':expected,'outcome':result['outcome'],'correct_defect_found':correct,'false_positive':false})
    measurements = fixed_metrics(cases)
    assert hashes=={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}, 'Preserved evidence changed'
    public={'created':progress['created'],'repository_run_id':identifier,'snapshot':progress['snapshot'],'status':progress['status'],
            'summary':document['summary'],'coverage':document['coverage'],'scan_seconds':indexed['scan_seconds'],'index_seconds':indexed['index_seconds'],
            'source_files':progress['files'],'analyzer_status':progress['analyzer']['status'],'analyzer_version':progress['analyzer']['version'],
            'model':'qwen2.5-coder:7b','prompt_version':document['function_reports'][0]['run']['prompt_version'],
            'fixed_fixture_comparison':measurements,'cases':cases,'preserved_artifact_hashes':hashes,
            'historical_evidence_used':len(document['historical_evidence_used']),
            'limitations':document['limitations'] + ['This new Docker repository run does not replace the original native fixed evaluations. Precision is per labeled function; extra allegations on defective functions are not exhaustively adjudicated.'],
            'private_report':str(destination),'scope':'Local/private captured source; no CI/build execution, code writes or model training'}
    public_destination = summary or root / 'docs/evaluation/repository-alignment-results.json'
    public_destination.parent.mkdir(parents=True, exist_ok=True)
    public_destination.write_text(json.dumps(public, indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'summary':document['summary'],'fixture_comparison':measurements},indent=2),flush=True)
    if progress['status'] != 'COMPLETED' or len(progress['results']) != len(progress['functions']):
        raise SystemExit('Incomplete repository coverage; report retained')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report',type=Path,default=Path('.local/repository-live.json'))
    parser.add_argument('--summary', type=Path, help='Optional separate public summary; retain earlier evaluation files')
    args = parser.parse_args()
    demonstrate(args.report, args.summary)
