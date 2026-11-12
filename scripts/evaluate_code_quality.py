"""Unchanged fixed corpus, explicit ablations, private local-model evidence."""
import argparse
import json
from pathlib import Path

from scripts import evaluate_review
from app.ingestion.indexer import Indexer
from app.review_service import ReviewService


def evaluate(mode, destination, label=None):
    # Existing benchmark labels, prompts and scoring are reused unchanged.
    evaluate_review.Indexer = lambda *args, **kwargs: Indexer(*args, **kwargs, code_aware=True)
    evaluate_review.ReviewService = lambda *args, **kwargs: ReviewService(*args, **kwargs, quality=mode)
    result = evaluate_review.evaluate(destination)
    reviews = result['runs'][:30]
    public = {'mode': mode, 'created': result['created'], 'metrics': result['metrics'], 'cases': result['cases'],
              'capabilities': result['capabilities'], 'model': 'qwen2.5-coder:7b', 'context': 8192,
              'input_budget': 6144, 'output_budget': 1536, 'embedding': 'jinaai/jina-embeddings-v2-base-code',
              'limitations': ['Fixed synthetic corpus only; not universal accuracy. Failed cases remain in denominators.',
                             'Detection mechanisms require inspection; location overlap alone is not a correct diagnosis.']}
    for case, run in zip(public['cases'], reviews):
        case['findings'] = [{k: f[k] for k in ('category', 'issue', 'explanation', 'start_line', 'end_line')} for f in run['findings']]
        case['verifications'] = run.get('candidate_verifications', [])
        case['failure_type'] = ('FALSE_POSITIVE' if case['false_positive'] else 'MATCHED' if case['correct_defect_found'] else
            'INSUFFICIENT' if run['outcome'] in ('FAILED', 'INSUFFICIENT_EVIDENCE') else
            'WRONG_CATEGORY' if case['expected']['expected_defect'] and run['findings'] else
            'VERIFIER_REJECTED' if case['expected']['expected_defect'] and run.get('candidate_verifications') else
            'COMPLETE_MISS' if case['expected']['expected_defect'] else 'SAFE_NO_SUPPORTED_FINDING')
        case['support'] = [f['support'] for f in run['findings']]
    primary = [s for r in reviews for s in r.get('primary_generation_seconds', [])]
    verifier = [s for r in reviews for s in r.get('verifier_metrics', {}).get('seconds', [])]
    tokens = [r['input_tokens'] for r in reviews if type(r.get('input_tokens')) is int] + [t for r in reviews for t in r.get('verifier_metrics', {}).get('input_tokens', [])]
    public['performance'] = {'total_review_seconds': sum(r['seconds'] for r in reviews),
        'primary_calls': sum(r.get('primary_model_calls', r.get('model_attempts', 0)) for r in reviews),
        'verifier_calls': sum(r.get('verifier_metrics', {}).get('calls', 0) for r in reviews),
        'mean_primary_seconds': sum(primary)/len(primary) if primary else None,
        'mean_verifier_seconds': sum(verifier)/len(verifier) if verifier else None,
        'mean_retrieval_seconds': sum(r.get('retrieval_seconds', 0) for r in reviews)/30,
        'total_input_tokens_all_calls': sum(r['input_tokens'] or 0 for r in result['model_responses']),
        'max_input_tokens_all_calls': max(r['input_tokens'] or 0 for r in result['model_responses']),
        'functions_per_minute': 1800/sum(r['seconds'] for r in reviews)}
    path = Path('docs/evaluation') / ('quality-' + (label or mode) + '.json')
    path.write_text(json.dumps(public, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(public['performance'], indent=2), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=['ast', 'hybrid', 'verified'], required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--label', choices=['ast-corrected', 'hybrid-corrected', 'verified-corrected', 'verified-ordered', 'verified-final'])
    args = parser.parse_args()
    evaluate(args.mode, args.report, args.label)
