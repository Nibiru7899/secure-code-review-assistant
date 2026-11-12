"""Same fixed questions; compare vector related context and measured fusion ranks."""
import argparse
from contextlib import ExitStack
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
from time import perf_counter
from unittest.mock import patch

from app.ingestion.indexer import Indexer
from app.retrieval.embedder import JinaEmbedder
from app.retrieval.retriever import Retriever
from app.retrieval.code_retrieval import RANKING
from app.security.permissions import Permissions


def evaluate(destination):
    project=Path.cwd()
    cases=json.loads((project/'tests/fixtures/retrieval_questions.json').read_text())
    with tempfile.TemporaryDirectory(prefix='code-retrieval-',dir=project/'.local') as temp:
        base=Path(temp);root=base/'repo';shutil.copytree(project/'demo_ecu',root)
        token='evaluation-only-token'
        permissions=Permissions({'credentials':{hashlib.sha256(token.encode()).hexdigest():'dev'},
            'repositories':{'repo':{'root':str(root),'users':{'dev':['.']}}}})
        indexer=Indexer(permissions,base/'data',JinaEmbedder(project/'.local/models/jina-code'),project/'rules/coding_rules.md',code_aware=True)
        try:
            cold=indexer.index(token,'repo'); unchanged=indexer.index(token,'repo')
            scope=permissions.authorize(token,'repo');manifest=indexer.catalog.current(scope)
            retriever=Retriever(indexer);reports=[]
            for label, weights in [('VECTOR_RELATED',None),('HYBRID_1_1',(1,1)),('HYBRID_2_1',(2,1)),('HYBRID_3_1',(3,1))]:
                measured=[];contexts=[]
                if weights: RANKING.update(lexical_weight=weights[0],vector_weight=weights[1])
                for case in cases:
                    started=perf_counter();result=retriever.retrieve(token,'repo',case['query'],symbol=case.get('symbol'),hybrid=weights is not None)
                    items=result.get('target',[])+result.get('related_code',[])
                    success=(result['retrieval_status']==case['expect_status'] if 'expect_status' in case else
                        case['expect_symbol'] in [c['symbol'] for c in items] if 'expect_symbol' in case else
                        case['expect_rule'] in [c['rule_id'] for c in result.get('rules',[])])
                    measured.append(dict(case,passed=success,seconds=perf_counter()-started,
                        symbols=[c['symbol'] for c in items],duplicates=len(items)-len({c['chunk_id'] for c in items}),
                        stale=sum(c['snapshot']!=manifest['snapshot'] for c in items)))
                structural=[]
                for file,package in manifest['code_facts'].items():
                    for function in package['functions']:
                        expected_calls=[]
                        for call in function['facts']:
                            if call['kind']!='call' or call['receiver']:continue
                            matches=[f for p in manifest['code_facts'].values() for f in p['functions'] if f['name']==call['name']]
                            if len(matches)==1 and matches[0]['name']!=function['name']:expected_calls.append(matches[0]['name'])
                        if not expected_calls:continue
                        result=retriever.retrieve(token,'repo',function['name'],file=file,symbol=function['name'],hybrid=weights is not None)
                        found=[c['symbol'] for c in result['related_code']]
                        structural.append({'file':file,'function':function['name'],'expected_calls':sorted(set(expected_calls)),
                            'found':found,'hits':len(set(expected_calls)&set(found)),'total':len(set(expected_calls))})
                exact=[c for c in measured if 'symbol' in c and 'expect_status' not in c]
                semantic=[c for c in measured if 'symbol' not in c]
                reports.append({'mode':label,'ranking':dict(RANKING) if weights else None,'cases':measured,'symbol_context_cases':structural,
                    'exact_target_recall':sum(c['passed'] for c in exact)/len(exact),
                    'relevant_top_k':sum(c['passed'] for c in semantic)/len(semantic),
                    'deterministic_symbol_context_recall':sum(c['hits'] for c in structural)/sum(c['total'] for c in structural),
                    'mean_retrieval_seconds':sum(c['seconds'] for c in measured)/len(measured),
                    'duplicates':sum(c['duplicates'] for c in measured),'stale':sum(c['stale'] for c in measured)})
            RANKING.update(lexical_weight=2,vector_weight=1)
            file=root/'src/brake_control.cpp';file.write_text(file.read_text().replace('value < 0 ? 0 : value','value < 0 ? 0 : value + 1'))
            changed=indexer.index(token,'repo')
            (root/'src/diagnostics.cpp').unlink();deleted=indexer.index(token,'repo')
            assert retriever.retrieve(token,'repo','safeDiagnostic',symbol='safeDiagnostic')['retrieval_status']=='not_found'
            result={'fixed_questions_unchanged':True,'configurations':reports,'indexing':{'cold':cold,'unchanged':unchanged,'changed':changed,'deleted':deleted},
                'limitations':['Vector-related control retains exact target selection, as required; it is not vector-only target selection.',
                    'Syntactic direct-call tests do not prove overload binding or whole-program resolution.'],
                'selected_ranking':dict(RANKING)}
            destination.write_text(json.dumps(result,indent=2)+'\n')
            print(json.dumps({r['mode']:{k:r[k] for k in ('exact_target_recall','relevant_top_k','deterministic_symbol_context_recall','mean_retrieval_seconds','duplicates','stale')} for r in reports},indent=2))
        finally:
            if indexer.store:indexer.store.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--report',type=Path,required=True)
    evaluate(parser.parse_args().report)
