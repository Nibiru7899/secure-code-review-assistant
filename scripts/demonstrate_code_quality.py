"""Real read-only original-repository demonstration in separate persistent storage."""
import json
import argparse
from pathlib import Path
from collections import Counter
from time import perf_counter

from app.analysis.cppcheck import Cppcheck
from app.ingestion.indexer import Indexer
from app.llm.ollama_client import OllamaClient
from app.llm.schemas import TargetRequest
from app.repository_review import RepositoryReview
from app.review_service import ReviewService
from app.security.permissions import Permissions
from app.retrieval.embedder import JinaEmbedder
from scripts.demo_repository_review import fixed_metrics
from ui.reports import html_report


def demonstrate(label='final'):
    project=Path.cwd();data=project/'.local/quality-repository-data'
    token=(project/'.local/demo-token.txt').read_text().strip()
    permissions=Permissions.load(project/'.local/access.json')
    scope=permissions.authorize(token,'demo_ecu')
    indexer=Indexer(permissions,data,JinaEmbedder(project/'.local/models/jina-code'),project/'rules/coding_rules.md',code_aware=True)
    try:
        indexed=indexer.index(token,'demo_ecu')
        client=OllamaClient(timeout=120); model_calls=[];original_request=client.request
        def measured_request(endpoint,body=None):
            started=perf_counter();response=original_request(endpoint,body)
            if endpoint=='generate':
                model_calls.append({'role':'verifier' if body['format']['title']=='Verification' else 'primary',
                    'seconds':round(perf_counter()-started,4),'input_tokens':response.get('prompt_eval_count'),
                    'output_tokens':response.get('eval_count')})
            return response
        client.request=measured_request
        service=ReviewService(indexer,Cppcheck(project/'.local/tools/cppcheck/PFiles/Cppcheck/cppcheck.exe',data/'analysis'),client,quality='verified')
        reviews=RepositoryReview(service)
        run=reviews.start(token,TargetRequest(repository='demo_ecu',snapshot=indexed['snapshot']),background=False)
        document=reviews.document(token,'demo_ecu',run['id'])
        private_report = '.local/quality-repository-' + label + '-report.json'
        printable_report = 'docs/demonstrations/quality-repository-' + label + '-report.html'
        Path(private_report).write_text(json.dumps(document,indent=2),encoding='utf-8')
        Path(printable_report).write_text(html_report(document),encoding='utf-8')
        cases=[];fixtures=json.loads(Path('tests/fixtures/expected_defects.json').read_text())
        for name,expected in fixtures.items():
            child=next(d for d in document['function_reports'] if any(e.get('function')==name and e.get('target') for e in d['run']['evidence']))
            findings=[f for f in child['run']['findings'] if f['function']==name]
            correct=any(f['file']==expected['expected_file'] and f['category']==expected['expected_defect'] and f['start_line']<=expected['expected_range'][1] and f['end_line']>=expected['expected_range'][0] for f in findings)
            cases.append({'function':name,'expected':expected,'outcome':child['run']['outcome'],'correct_defect_found':correct,
                'false_positive':expected['expected_defect'] is None and bool(findings),
                'findings':[{k:f[k] for k in ('category','issue','explanation')} for f in findings]})
        provenance=Counter(f['current_validation_status'] for d in document['function_reports'] for f in d['reviewed_findings'])
        quotes=0
        for d in document['function_reports']:
            for f in d['run']['findings']:
                for ref in f['evidence']:
                    e=next(e for e in d['run']['evidence'] if e['id']==ref['id'])
                    if e['kind']=='source':
                        lines=(scope.root/e['file']).read_text(encoding='utf-8').splitlines()
                        assert ref['quote'] in '\n'.join(lines[ref['start_line']-1:ref['end_line']])
                        quotes+=1
        public={'scope':'Original authorized demo_ecu; separate persistent evaluation storage, no source edits or operational history changes',
            'mode':'verified','repository_run_id':run['id'],'snapshot':run['snapshot'],'status':run['status'],
            'summary':document['summary'],'indexing':indexed,'cases':cases,'metrics':fixed_metrics(cases),
            'provenance':dict(provenance),'source_quotes_checked_against_original':quotes,
            'primary_model_calls':sum(d['run'].get('primary_model_calls',0) for d in document['function_reports']),
            'verifier_model_calls':sum(d['run'].get('verifier_metrics',{}).get('calls',0) for d in document['function_reports']),
            'measured_model_calls':model_calls,'total_input_tokens':sum(m['input_tokens'] or 0 for m in model_calls),
            'max_input_tokens':max(m['input_tokens'] or 0 for m in model_calls),
            'limitations':document['limitations'],'private_report':private_report,
            'printable_report':printable_report}
        Path('docs/evaluation/quality-repository-' + label + '.json').write_text(json.dumps(public,indent=2)+'\n',encoding='utf-8')
        print(json.dumps({'summary':public['summary'],'metrics':public['metrics'],'provenance':public['provenance']},indent=2))
        assert document['repository_review']['status']=='COMPLETED' and len(document['repository_review']['results'])==31
    finally:
        if indexer.store:indexer.store.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--label',choices=['final'],default='final')
    demonstrate(parser.parse_args().label)
