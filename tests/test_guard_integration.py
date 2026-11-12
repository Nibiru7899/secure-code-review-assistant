import json,unittest
from unittest.mock import patch
from app.review_service import ReviewService
from app.llm.schemas import TargetRequest
from app.security.permissions import AccessDenied
import test_review as fixture
from app.reviewer import report
from ui.reports import html_report

class GuardIntegration(unittest.TestCase):
 setUp=fixture.ReviewTests.setUp
 tearDown=fixture.ReviewTests.tearDown
 def test_prompt_retrieval_calls_history_and_guard_persistence(self):
  self.response['findings'][0]['explanation']='Pointer value is dereferenced without checking value.'
  baseline=ReviewService(self.indexer,self.analyzer,self.client).analyze(self.token,self.request,'review_function')
  payload=self.client.request.call_args_list[-1].args[1]
  prior=json.dumps(report(self.indexer,self.token,'repo',baseline['id'])['run'],sort_keys=True)
  self.client.request.reset_mock()
  guarded=ReviewService(self.indexer,self.analyzer,self.client,quality='guarded').analyze(self.token,self.request,'review_function')
  self.assertEqual(payload,self.client.request.call_args_list[-1].args[1]);self.assertEqual(guarded['primary_model_calls'],baseline['primary_model_calls']);self.assertNotIn('candidate_verifications',guarded)
  self.assertEqual(guarded['evidence'],baseline['evidence']);self.assertNotIn('code_facts',guarded)
  self.assertEqual(guarded['ast_guards'][0]['original_candidate'],guarded['ast_guards'][0]['effective_candidate'])
  document=report(self.indexer,self.token,'repo',guarded['id']);self.assertEqual(document['run']['ast_guards'],guarded['ast_guards'])
  self.assertEqual(prior,json.dumps(report(self.indexer,self.token,'repo',baseline['id'])['run'],sort_keys=True))
  document['run']['ast_guards'][0]['ast_guard_result']['checks']=[{'observation':'<script>private()</script>'}]
  rendered=html_report(document);self.assertIn('Deterministic code checks',rendered);self.assertNotIn('<script>',rendered);self.assertIn('&lt;script&gt;',rendered)
 def test_denial_stale_snapshot_no_guard_or_extra_inference(self):
  svc=ReviewService(self.indexer,self.analyzer,self.client,quality='guarded')
  with patch('app.analysis.ast_guard.capture') as facts:
   with self.assertRaises(AccessDenied):svc.analyze('unknown',self.request,'review_function')
   facts.assert_not_called();self.client.request.assert_not_called()
   with self.assertRaises(ValueError):svc.analyze(self.token,self.request.model_copy(update={'snapshot':'missing'}),'review_function')
   facts.assert_not_called();self.client.request.assert_not_called()
 def test_unrelated_missing_check_cannot_suppress_pointer_finding(self):
  from test_ast_guard import fixture
  from app.analysis.ast_guard import check
  f,m=fixture('int inspect(int* p) {\n if(p) {\n return *p;\n }\n return 0;\n}',explanation='Pointer p is accessed. The function does not check capacity.')
  self.assertEqual(check(f,m)['guard_status'],'NOT_APPLICABLE')

 def test_guard_detail_ui_renders_without_inference(self):
  from streamlit.testing.v1 import AppTest
  self.response['findings'][0]['explanation']='Pointer value is dereferenced without checking value.'
  run=ReviewService(self.indexer,self.analyzer,self.client,quality='guarded').analyze(self.token,self.request,'review_function')
  document=report(self.indexer,self.token,'repo',run['id'])
  path=self.base/'document.json';path.write_text(json.dumps(document))
  script=self.base/'preview.py'
  script.write_text("import json\nfrom unittest.mock import Mock\nfrom pathlib import Path\nfrom ui.components import show_report\ndocument=json.loads(Path("+repr(str(path))+").read_text())\nshow_report(Mock(),document,'repo')\n")
  calls=self.client.request.call_count
  app=AppTest.from_file(str(script)).run()
  self.assertFalse(app.exception)
  self.assertIn('Deterministic code checks',[e.label for e in app.expander])
  self.assertEqual(self.client.request.call_count,calls)
