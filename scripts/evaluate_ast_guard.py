"""Back-to-back controlled guard ablations using unchanged fixed scoring."""
import hashlib
import json
from pathlib import Path

from scripts import evaluate_review
from app.review_service import ReviewService
from app.retrieval.embedder import JinaEmbedder


def evaluate():
    original_service, original_embedder = evaluate_review.ReviewService, evaluate_review.JinaEmbedder
    summaries = []
    try:
        for label, quality, policy in [('baseline','baseline','annotation'),('guarded-a','guarded','annotation'),('guarded-b','guarded','strict')]:
            embedding = {'calls': 0, 'texts': 0}
            class MeasuredEmbedder(JinaEmbedder):
                def encode(self, texts):
                    embedding['calls'] += 1; embedding['texts'] += len(texts)
                    return super().encode(texts)
            class MeasuredService(ReviewService):
                def analyze(self, *args, **kwargs):
                    before = embedding['calls']
                    run = super().analyze(*args, **kwargs)
                    run['measured_embedding_calls'] = embedding['calls'] - before
                    return run
            evaluate_review.JinaEmbedder = MeasuredEmbedder
            evaluate_review.ReviewService = lambda *args, **kwargs: MeasuredService(*args, **kwargs, quality=quality, guard_policy=policy)
            result = evaluate_review.evaluate(Path('.local/guard-'+label+'-live.json'))
            runs = result['runs'][:30]
            records = [record for r in runs for record in r.get('ast_guards', [])]
            total = sum(r['seconds'] for r in runs)
            summary = {'mode': label, 'snapshot': result['snapshot'], 'metrics': result['metrics'],
                'cases': result['cases'], 'capabilities': result['capabilities'],
                'performance': {'total_review_seconds': total, 'functions_per_minute': 1800/total,
                    'detector_calls':sum(r['primary_model_calls'] for r in runs), 'verifier_calls':0,
                    'embedding_calls_review':sum(r['measured_embedding_calls'] for r in runs),
                    'embedding_calls_with_index_and_capabilities':embedding['calls'],
                    'guard_seconds':sum(r.get('guard_seconds',0) for r in runs),
                    'guard_seconds_per_function':sum(r.get('guard_seconds',0) for r in runs)/30},
                'guard_counts': {'corroborated':sum(any(c['relation_to_candidate']=='CORROBORATED' for c in r['ast_guard_result']['checks']) for r in records),
                    'potential_contradictions':sum(any(c['relation_to_candidate']=='POTENTIAL_CONTRADICTION' for c in r['ast_guard_result']['checks']) for r in records),
                    'category_warnings':sum(any(c['relation_to_candidate']=='CATEGORY_CONSISTENCY_WARNING' for c in r['ast_guard_result']['checks']) for r in records),
                    'suppressed':sum(r['effective_candidate'] is None for r in records)},
                'guard_records':records,
                'generation_prompt_hashes':[hashlib.sha256(r['prompt'].encode()).hexdigest() for r in result['model_responses']],
                'limitations':['Unchanged fixed synthetic corpus; per-labeled-function scoring, not universal accuracy.',
                    'Live detector outputs may vary despite identical inputs; paired replay isolates guard-only effects.']}
            for case,run in zip(summary['cases'],runs):
                case['findings'] = [{k:f[k] for k in ('category','issue','explanation','start_line','end_line')} for f in run['findings']]
                case['guard_records'] = run.get('ast_guards', [])
            Path('docs/evaluation/guard-'+label+'.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
            summaries.append(summary)
        assert len({s['snapshot'] for s in summaries}) == 1
        comparison = {'modes': summaries,'same_snapshot':True,
            'identical_generation_prompts': all(s['generation_prompt_hashes']==summaries[0]['generation_prompt_hashes'] for s in summaries[1:])}
        review_calls = summaries[0]['performance']['detector_calls']
        comparison['identical_review_generation_prompts'] = all(s['generation_prompt_hashes'][:review_calls]==summaries[0]['generation_prompt_hashes'][:review_calls] for s in summaries[1:])
        comparison['diagnostic_prompt_note'] = 'Imported-at timestamps differ across separate diagnostic imports. Review prompts are compared byte-for-byte including corrective requests.'
        Path('docs/evaluation/guard-live-comparison.json').write_text(json.dumps(comparison,indent=2)+'\n',encoding='utf-8')
    finally:
        evaluate_review.ReviewService, evaluate_review.JinaEmbedder = original_service, original_embedder


if __name__ == '__main__':
    evaluate()
