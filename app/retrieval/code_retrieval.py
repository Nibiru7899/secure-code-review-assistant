"""Transparent exact-symbol tiers and identifier/vector reciprocal ranks."""
import re
from pathlib import PurePosixPath

RANKING = {'lexical_weight': 2, 'vector_weight': 1, 'rrf_constant': 20}
KEYWORDS = set('int void return if else const static bool nullptr NULL true false struct class include std unsigned char float double auto'.split())


def identifiers(text):
    # Strip comments and strings so instruction prose cannot boost lexical rank.
    clean = re.sub(r'//[^\n]*|/\*.*?\*/|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'', ' ', text, flags=re.S)
    return set(re.findall(r'\b[A-Za-z_]\w*\b', clean)) - KEYWORDS


def target_facts(manifest, targets):
    selected = {(c['file'], c['symbol'], c['signature']) for c in targets}
    return [dict(f, file=file) for file, package in manifest.get('code_facts', {}).items()
            for f in package['functions'] if (file, f['name'], f['signature']) in selected]


def code_query(query, targets, facts):
    parts = [query[:1200]]
    parts += [f['complete_signature'] for f in facts[:3]]
    names = sorted({i for f in facts for i in f['identifiers']})[:35]
    parts.append('identifiers: ' + ' '.join(names))
    value = '\n'.join(parts)
    while len(value.encode()) > 1800:
        value = value[:-1]
    return value


def rank(manifest, targets, vector_results, query, allowed, config=None):
    config = config or RANKING
    facts = target_facts(manifest, targets)
    target_ids = {c['chunk_id'] for c in targets}
    available = [c for c in manifest['chunks'] if c['file'] in allowed and c['chunk_id'] not in target_ids]
    reasons = {}
    relations = set()
    limitations = []
    calls = {f['name'] for fn in facts for f in fn['facts'] if f['kind'] == 'call' and not f['receiver']}
    for name in sorted(calls):
        matches = [c for c in available if c['symbol'] == name or (not '::' in name and c['symbol'].split('::')[-1] == name)]
        identities = {(c['file'], c['signature']) for c in matches}
        if len(identities) == 1:
            relations.update(c['chunk_id'] for c in matches)
        elif len(identities) > 1:
            limitations.append('Syntactic call is ambiguous; overload/receiver resolution unavailable: ' + name)
    for target in targets:
        package = manifest.get('code_facts', {}).get(target['file'], {})
        includes = {f['path'] for f in package.get('includes', [])}
        stem = PurePosixPath(target['file']).stem
        for chunk in available:
            # A captured, uniquely named include and source/header pair supply
            # associated context, not proof of overload resolution.
            basename = PurePosixPath(chunk['file']).name
            unique_header = basename in includes and sum(PurePosixPath(p).name == basename for p in allowed) == 1
            paired_header = PurePosixPath(chunk['file']).stem == stem and chunk['file'].endswith(('.h', '.hpp'))
            if unique_header or paired_header:
                relations.add(chunk['chunk_id'])
    referenced = {i for f in facts for i in f['identifiers']}
    for name in sorted(referenced):
        definitions = [(file, t) for file, package in manifest.get('code_facts', {}).items() if file in allowed
                       for t in package['types'] if t['name'] == name]
        if len(definitions) == 1:
            file, definition = definitions[0]
            relations.update(c['chunk_id'] for c in available if c['file'] == file and
                c['start_line'] <= definition['start_line'] <= c['end_line'])
    terms = identifiers(query) | {i for f in facts for i in f['identifiers']}
    if not targets:
        # English words that happen to equal ubiquitous variables are not
        # evidence of a code relationship. Preserve vector fallback for prose;
        # explicit symbols/types/constants still receive lexical priority.
        symbols = {c['symbol'].split('::')[-1] for c in available if c['symbol']}
        terms = {term for term in terms if term in symbols or re.search(r'[A-Z_]', term)}
    lexical = sorted([(len(terms & identifiers(c['text'])) + 3 * int(c['symbol'].split('::')[-1] in terms), c) for c in available],
                     key=lambda pair: (-pair[0], pair[1]['file'], pair[1]['start_line']))
    lexical = [c for score, c in lexical if score > 0]
    lr = {c['chunk_id']: i + 1 for i, c in enumerate(lexical)}
    vr = {c['chunk_id']: i + 1 for i, c in enumerate(vector_results) if c['file'] in allowed and c['snapshot'] == manifest['snapshot']}
    scored = []
    for c in available:
        key = c['chunk_id']; why = []
        if key in relations: why.append('SYMBOL_RELATION')
        if key in lr: why.append('IDENTIFIER_MATCH')
        if key in vr: why.append('VECTOR_SIMILARITY')
        if not why: continue
        score = (config['lexical_weight'] / (config['rrf_constant'] + lr[key]) if key in lr else 0) + (config['vector_weight'] / (config['rrf_constant'] + vr[key]) if key in vr else 0)
        scored.append(dict(c, retrieval_reasons=why, hybrid_score=round(score, 8)))
    return sorted(scored, key=lambda c: ('SYMBOL_RELATION' not in c['retrieval_reasons'], -c['hybrid_score'], c['file'], c['start_line'])), limitations
