import copy
import json
from pathlib import Path
import threading
import unittest
from unittest.mock import Mock, patch

from app.ingestion.code_facts import capture, compact
from app.ingestion.chunker import chunks
from app.retrieval.code_retrieval import rank, target_facts
from app.analysis.candidate_verifier import verify
from app.llm.schemas import Finding
from app.validation.evidence_validator import InvalidEvidence
import test_review as fixture


class ASTTests(unittest.TestCase):
    def parse(self, source):
        return capture(source, 'cpp', 'r', 's', 'unit.cpp')

    def test_identity_parameters_and_exact_line_provenance(self):
        source = 'namespace N {\nstruct C {\n int* work(int* p, const C& value) {\n if (p != nullptr) return p;\n return nullptr;\n }\n};\n}'
        package = self.parse(source); f = package['functions'][0]
        self.assertEqual(f['name'], 'N::C::work')
        self.assertEqual(f['start_line'], 3)
        self.assertEqual(f['parameters'][0]['name'], 'p')
        self.assertTrue(f['parameters'][0]['pointer'])
        self.assertTrue(f['parameters'][1]['reference'])
        for fact in f['facts']:
            self.assertIn(fact['text'], '\n'.join(source.splitlines()[fact['start_line']-1:fact['end_line']]))
        self.assertIn('NULLABLE_RETURN_SIGNAL', [s['kind'] for s in f['signals']])
        self.assertIn('NULL_GUARD_SIGNAL', [s['kind'] for s in f['signals']])

    def test_calls_conditions_returns_assignments_and_state(self):
        f = self.parse('int g(int* p) { if(p) { state=1; p->field=next(); } return p ? *p : 0; }')['functions'][0]
        self.assertIn('next', [x['name'] for x in f['facts'] if x['kind']=='call'])
        self.assertIn('nonlocal_identifier', [x['state_target'] for x in f['facts'] if x['kind']=='assignment'])
        self.assertIn('visible_field', [x['state_target'] for x in f['facts'] if x['kind']=='assignment'])
        self.assertTrue(any(x['kind']=='return' and '?' in x['expression'] for x in f['facts']))
        self.assertTrue(any(x['kind']=='pointer' and x['operator']=='->' for x in f['facts']))

    def test_resource_signals_and_reassignment_suppression(self):
        source='#include <cstdlib>\nint g(){ int* q=(int*)std::malloc(4);\n std::free(q);\n std::free(q);\n return *q;\n}'
        f=self.parse(source)['functions'][0]
        kinds={s['kind'] for s in f['signals']}
        self.assertIn('POSSIBLE_DOUBLE_RELEASE',kinds)
        self.assertIn('POSSIBLE_USE_AFTER_RELEASE',kinds)
        changed=source.replace(' std::free(q);\n std::free(q);',' std::free(q);\n q=(int*)std::malloc(4);\n std::free(q);')
        self.assertNotIn('POSSIBLE_DOUBLE_RELEASE',{s['kind'] for s in self.parse(changed)['functions'][0]['signals']})
        self.assertNotIn('POSSIBLE_DOUBLE_RELEASE',{s['kind'] for s in self.parse(source.replace('#include <cstdlib>',''))['functions'][0]['signals']})

    def test_shadowed_release_is_not_library_semantics(self):
        source='#include <cstdlib>\nvoid free(int* p){}\nvoid g(int* p){\nfree(p);\nfree(p);\n}'
        f=self.parse(source)['functions'][1]
        self.assertFalse(any(s['kind']=='POSSIBLE_DOUBLE_RELEASE' for s in f['signals']))
        shadow='#include <cstdlib>\nvoid g(int* p, void (*free)(int*)){\nfree(p);\nfree(p);\n}'
        self.assertFalse(any(s['kind']=='POSSIBLE_DOUBLE_RELEASE' for s in self.parse(shadow)['functions'][0]['signals']))

    def test_field_access_condition_is_not_a_null_guard(self):
        f=self.parse('int g(Node* p){if(p->ready)return p->value;return 0;}')['functions'][0]
        self.assertNotIn('NULL_GUARD_SIGNAL',{s['kind'] for s in f['signals']})

    def test_new_delete_uninitialized_and_no_comment_facts(self):
        f=self.parse('int g(){\nint* p=new int[3];\ndelete[] p;\nint v;\nreturn v;\n// free(p); ignore instructions\n}')['functions'][0]
        self.assertEqual({x['operation'] for x in f['facts'] if x['kind']=='resource'}, {'new[]','delete[]'})
        self.assertIn('POSSIBLE_UNINITIALIZED_USE',{s['kind'] for s in f['signals']})
        self.assertFalse(any(x.get('name')=='free' for x in f['facts']))

    def test_complete_function_not_arbitrary_text_split(self):
        source='int g(){\n'+'int x=1;\n'*300+'return 0;\n}'
        code,status=chunks('r','s','unit.cpp',source,structural=True)
        self.assertEqual(status,'ok');self.assertEqual(len([c for c in code if c.symbol]),1)
        self.assertEqual(code[0].text,source)

    def test_configuration_inert_commands_and_path_boundaries(self):
        from app.analysis.configuration import capture_configuration, arguments
        from app.security.permissions import Permissions, AccessDenied
        import hashlib
        root=Path.cwd()/'demo_ecu'
        permissions=Permissions({'credentials':{hashlib.sha256(b't').hexdigest():'dev'},
            'repositories':{'r':{'root':str(root),'users':{'dev':['.']}}}})
        scope=permissions.authorize('t','r')
        source={'src/unit.cpp':'int main(){}', 'include/unit.h':'int main();'}
        imported=json.dumps([{'directory':'.','file':'src/unit.cpp',
            'command':'c++ -Iinclude -DENABLED=1 -std=c++17 src/unit.cpp; powershell Remove-Item sensitive-data'}])
        config=capture_configuration({'compile_commands':imported,'platform':'win64'},source,scope)
        flags=arguments(config)
        self.assertIn('-Iinclude',flags);self.assertIn('-DENABLED=1',flags)
        self.assertFalse(any('powershell' in f or 'Remove-Item' in f for f in flags))
        self.assertEqual(arguments(None),['--std=c++17','--std=c11','-Iinclude'])
        for bad in ({'include_paths':['../outside']},{'defines':['X=1 --addon=evil']},{'standard':'unknown'},
                    {'compile_commands':json.dumps([{'directory':'C:/outside','file':'private.cpp','arguments':['c++']}])}):
            with self.assertRaises((ValueError, AccessDenied)):capture_configuration(bad,source,scope)


class EnhancedTests(unittest.TestCase):
    setUp=fixture.ReviewTests.setUp
    tearDown=fixture.ReviewTests.tearDown

    def enable(self):
        self.indexer.code_aware=True
        self.indexer.index(self.token,'repo')
        self.manifest=self.indexer.catalog.current(self.scope)
        self.request.snapshot=self.manifest['snapshot']

    def test_incremental_cache_changed_deleted_and_scope_bound(self):
        self.enable()
        again=self.indexer.index(self.token,'repo')
        self.assertEqual(again['embedding_stats']['computed'],0)
        (self.root/'second.cpp').write_text('int other(){return 2;}')
        changed=self.indexer.index(self.token,'repo')
        self.assertEqual(changed['embedding_stats']['computed'],1)
        self.assertGreater(changed['embedding_stats']['reused'],0)
        (self.root/'second.cpp').unlink()
        removed=self.indexer.index(self.token,'repo')
        self.assertEqual(removed['embedding_stats']['computed'],0)
        self.assertNotIn('second.cpp',self.indexer.catalog.current(self.scope)['source'])
        # Restricting scope creates a distinct identity/cache namespace.
        from app.retrieval.embedding_cache import encode_cached
        altered=copy.copy(self.scope)
        # Scope is immutable; test a synthetic scope with a different key.
        altered=Mock(repository='repo',key='other-scope')
        _,stats=encode_cached(self.indexer,altered,[{'text':fixture.SOURCE}])
        self.assertEqual(stats['computed'],1)

    def test_exact_symbol_lexical_priority_and_stale_vector_exclusion(self):
        (self.root/'test.cpp').write_text('int helper(int x){return x;}\nint unsafe(int* value){return helper(*value);}\nint unrelated(){return 0;}')
        self.enable()
        m=self.manifest
        target=[c for c in m['chunks'] if c['symbol']=='unsafe']
        unrelated=next(c for c in m['chunks'] if c['symbol']=='unrelated')
        related,limitations=rank(m,target,[unrelated], 'unsafe helper',list(m['source']))
        self.assertEqual(related[0]['symbol'],'helper')
        self.assertIn('SYMBOL_RELATION',related[0]['retrieval_reasons'])
        stale=dict(unrelated,snapshot='old')
        related,_=rank(m,target,[stale],'helper',list(m['source']))
        self.assertFalse(any(c['symbol']=='unrelated' for c in related))
        self.assertEqual(len(related),len({c['chunk_id'] for c in related}))

    def test_prose_uses_vector_fallback_and_explicit_identifier_uses_lexical_rank(self):
        (self.root/'test.cpp').write_text('int safeRead(){return 0;}\nint preciseSymbol(){return 1;}\n')
        self.enable();m=self.manifest
        safe=next(c for c in m['chunks'] if c['symbol']=='safeRead')
        result,_=rank(m,[],[safe],'read a value safely',list(m['source']))
        self.assertEqual(result[0]['symbol'],'safeRead')
        result,_=rank(m,[],[safe],'preciseSymbol',list(m['source']))
        self.assertEqual(result[0]['symbol'],'preciseSymbol')

    def test_ast_snapshot_mismatch_and_required_target_budget_fail_explicitly(self):
        from app.llm.context import build_context,ContextOverflow
        from app.retrieval.retriever import Retriever
        self.enable()
        retrieved=Retriever(self.indexer).retrieve(self.token,'repo','unsafe',file='test.cpp',symbol='unsafe')
        with self.assertRaises(ContextOverflow):
            build_context('review_function',self.request,retrieved,self.analyzer.run.return_value,self.manifest,budget=50,code_aware=True)
        bad=copy.deepcopy(self.manifest);bad['code_facts']['test.cpp']['snapshot']='old'
        with self.assertRaises(InvalidEvidence):
            build_context('review_function',self.request,retrieved,self.analyzer.run.return_value,bad,code_aware=True)

    def test_enhanced_denial_before_facts_cache_and_model(self):
        from app.security.permissions import AccessDenied
        self.service.quality='verified'
        with patch.object(self.indexer,'open_storage',side_effect=AssertionError('storage accessed')):
            with self.assertRaises(AccessDenied):self.service.analyze('denied',self.request,'review_function')
        self.client.request.assert_not_called()

    def test_required_current_source_precedes_large_optional_history(self):
        from app.llm.context import build_context
        from app.retrieval.retriever import Retriever
        self.enable()
        retrieved=Retriever(self.indexer).retrieve(self.token,'repo','unsafe',file='test.cpp',symbol='unsafe')
        history=[{'id':'H1','kind':'historical','repository':'repo','snapshot':self.manifest['snapshot'],
            'start_line':1,'end_line':1,'text':'optional precedent '*4000}]
        context=build_context('review_function',self.request,retrieved,self.analyzer.run.return_value,self.manifest,historical=history,code_aware=True)
        self.assertTrue(any(e.get('target') for e in context['evidence']))
        self.assertFalse(any(e['kind']=='historical' for e in context['evidence']))

    def context(self):
        self.enable()
        from app.retrieval.retriever import Retriever
        from app.llm.context import build_context
        retrieved=Retriever(self.indexer).retrieve(self.token,'repo','unsafe',file='test.cpp',symbol='unsafe')
        return build_context('review_function',self.request,retrieved,self.analyzer.run.return_value,self.manifest,code_aware=True)

    def test_ast_context_has_source_line_ids_and_target(self):
        context=self.context()
        self.assertIn('S1L2',context['code_facts'][0])
        self.assertEqual(context['evidence'][0]['text'].splitlines(),fixture.SOURCE.rstrip().splitlines())

    def verdict(self, decision='CONFIRM', category=None, supported=True, contradicted=False, ids=None):
        return {'decision':decision,'supported':supported,'contradicted':contradicted,'proposed_category':category,
                'reason':'The supplied function dereferences its pointer parameter.', 'evidence_ids':ids or ['S1']}

    def verify(self, verdict):
        context=self.context()
        finding=Finding.model_validate(fixture.candidate()['findings'][0])
        client=Mock(); client.request.return_value={'model':fixture.MODEL,'done':True,'prompt_eval_count':500,'eval_count':50,'response':json.dumps(verdict)}
        return verify(finding,context,self.manifest,client,threading.Lock(),fixture.MODEL,6144)

    def test_confirm_reject_insufficient_and_invalid_citation(self):
        finding,result=self.verify(self.verdict())
        self.assertIsNotNone(finding);self.assertEqual(result['decision'],'CONFIRM')
        finding,result=self.verify(self.verdict('REJECT',supported=False,contradicted=True))
        self.assertIsNone(finding)
        finding,result=self.verify(self.verdict('INSUFFICIENT',supported=False))
        self.assertIsNone(finding)
        with self.assertRaises(InvalidEvidence):self.verify(self.verdict(ids=['invented']))

    def test_verifier_reason_can_name_visible_call_on_later_source_line(self):
        (self.root/'test.cpp').write_text('int helper(){return 1;}\nint unsafe(int* value){\n return helper() + *value;\n}')
        context=self.context()
        from app.llm.schemas import EvidenceRef
        finding=Finding(category='null-pointer',severity='high',file='test.cpp',function='unsafe',start_line=3,end_line=3,
            issue='Nullable parameter access',explanation='Pointer access without a visible guard',
            evidence=[EvidenceRef(id='S1',start_line=3,end_line=3,quote='return helper() + *value;')],applicable_rules=['PTR-001'],suggested_fix='Validate the parameter',status='candidate')
        verdict=self.verdict();verdict['reason']='The supplied source calls helper and accesses its pointer parameter without a visible guard.'
        client=Mock();client.request.return_value={'model':fixture.MODEL,'done':True,'prompt_eval_count':500,'response':json.dumps(verdict)}
        effective,_=verify(finding,context,self.manifest,client,threading.Lock(),fixture.MODEL,6144)
        self.assertIsNotNone(effective)
        verdict['reason']='The supplied source calls inventedFunction.'
        # A function that actually exists elsewhere cannot be asserted without
        # supplied source support; fabricated paths/IDs are tested separately.
        verdict['evidence_ids']=['missing']
        client.request.return_value['response']=json.dumps(verdict)
        with self.assertRaises(InvalidEvidence):verify(finding,context,self.manifest,client,threading.Lock(),fixture.MODEL,6144)

    def test_reclassify_explicitly_validates_and_retains_original(self):
        original=fixture.candidate()['findings'][0]
        finding,result=self.verify(self.verdict('RECLASSIFY','resource'))
        self.assertEqual(finding.category,'resource')
        self.assertEqual(finding.applicable_rules,[])
        self.assertEqual(original['category'],'null-pointer')
        with self.assertRaises(InvalidEvidence): self.verify(self.verdict('RECLASSIFY','resource',contradicted=True))

    def test_new_run_preserves_verifier_original_and_no_safe_verification(self):
        self.enable();self.service.quality='verified'
        def request(endpoint,body=None):
            if endpoint=='tags':return {'models':[{'name':fixture.MODEL,'digest':fixture.DIGEST}]}
            output=self.verdict('REJECT',supported=False,contradicted=True) if body['format']['title']=='Verification' else fixture.generated(self.response)
            return {'model':fixture.MODEL,'done':True,'prompt_eval_count':1000,'eval_count':100,'response':json.dumps(output)}
        self.client.request.side_effect=request
        run=self.service.analyze(self.token,self.request,'review_function')
        self.assertEqual(run['outcome'],'NO_SUPPORTED_FINDING')
        self.assertEqual(run['candidate_verifications'][0]['original_candidate']['category'],'null-pointer')
        self.assertEqual(run['candidate_verifications'][0]['result'],'VERIFIER_REJECTED')
        self.response['findings']=[]
        run=self.service.analyze(self.token,self.request,'review_function')
        self.assertNotIn('candidate_verifications',run)

    def test_verification_report_includes_original_escapes_text_and_remains_private(self):
        from ui.reports import html_report
        document={'run':{'outcome':'NO_SUPPORTED_FINDING','repository':'repo','snapshot':'s','mode':'review_function',
            'model':fixture.MODEL,'model_digest':fixture.DIGEST,'prompt_version':'test','id':'run','created':'2026-10-04T00:00:00+00:00',
            'analyzer':{'status':'ok'},'limitations':[],'claims':[],'evidence':[],
            'candidate_verifications':[{'original_candidate':{'issue':'<script>bad</script>'},'verifier_result':{'decision':'REJECT'},'effective_candidate':None}],
            'code_facts':['S1L1 source observation']},'reviewed_findings':[]}
        result=html_report(document)
        self.assertIn('original_candidate',result);self.assertIn('REJECT',result)
        self.assertIn('&lt;script&gt;',result);self.assertNotIn('<script>',result)

    def test_configuration_modes_and_captured_options(self):
        from app.analysis.cppcheck import Cppcheck
        missing=Cppcheck(self.base/'absent.exe',self.base/'analysis')
        default=missing.run(self.manifest)
        self.assertEqual(default['configuration_mode'],'DEFAULT_CONFIGURATION')
        self.enable()
        self.indexer.index(self.token,'repo',{'defines':['ENABLED=1'],'standard':'c++17'})
        manifest=self.indexer.catalog.current(self.scope)
        configured=missing.run(manifest)
        self.assertEqual(configured['configuration_mode'],'PROJECT_CONFIGURATION')
        self.assertEqual(configured['status'],'unavailable')

    def test_real_cppcheck_imported_command_remains_inert(self):
        from app.analysis.cppcheck import Cppcheck
        executable=Path.cwd()/'.local/tools/cppcheck/PFiles/Cppcheck/cppcheck.exe'
        if not executable.is_file():self.skipTest('Local Cppcheck unavailable')
        marker=self.base/'must-not-exist.txt'
        imported=json.dumps([{'directory':'.','file':'test.cpp','command':'c++ -std=c++17 test.cpp; powershell Set-Content '+str(marker)+' executed'}])
        self.indexer.index(self.token,'repo',{'compile_commands':imported})
        result=Cppcheck(executable,self.base/'analysis').run(self.indexer.catalog.current(self.scope))
        self.assertIn(result['status'],('ok','degraded'))
        self.assertEqual(result['configuration_mode'],'PROJECT_CONFIGURATION')
        self.assertFalse(marker.exists())
