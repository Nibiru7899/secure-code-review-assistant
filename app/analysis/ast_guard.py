"""Post-candidate local syntax checks. No inference or independent defect search."""
import re
from time import perf_counter

from app.ingestion.code_facts import capture
from app.validation.evidence_validator import InvalidEvidence

VERSION = 'local-ast-guard-v1'


def named(prose, symbol):
    return bool(re.search(r'(?<![\w])' + re.escape(symbol) + r'(?![\w])', prose))


def nonnull(condition, symbol, truth):
    condition = condition.strip().strip('()').strip()
    p = re.escape(symbol)
    positive = (condition == symbol or bool(re.fullmatch(p + r'\s*!=\s*(nullptr|NULL|0)|(nullptr|NULL|0)\s*!=\s*' + p, condition)))
    negative = (condition == '!' + symbol or bool(re.fullmatch(p + r'\s*==\s*(nullptr|NULL|0)|(nullptr|NULL|0)\s*==\s*' + p, condition)))
    return (truth and positive) or (not truth and negative)


def unchecked_pointer(prose, symbol):
    """An absence assertion about this operand, not an unrelated missing check."""
    for sentence in re.split(r'[.\n]', prose):
        if not named(sentence, symbol):continue
        lower = sentence.lower()
        if not re.search(r'pointer|dereferenc|null', lower):continue
        if re.search(r'without (?:checking|a null check)|no null check', lower):
            return True
        match = re.search(r'(?:does not|never|not) checks?\s+(.+)', sentence, re.I)
        if match and named(match.group(1), symbol) and re.search(r'null|pointer|dereferenc', match.group(1), re.I):
            return True
    return False


def check(finding, manifest):
    started = perf_counter()
    result = {'version': VERSION, 'repository': manifest['repository'], 'snapshot': manifest['snapshot'],
              'file': finding.file, 'function': finding.function, 'guard_status': 'NOT_APPLICABLE', 'checks': []}
    source = manifest['source'].get(finding.file)
    if source is None:
        raise InvalidEvidence('Guard source absent from authorized captured snapshot')
    try:
        package = capture(source, 'c' if finding.file.endswith('.c') else 'cpp', manifest['repository'], manifest['snapshot'], finding.file)
    except ValueError:
        result['limitation'] = 'Syntax facts unavailable; original candidate retained'
        result['seconds'] = round(perf_counter() - started, 6)
        return result
    functions = [f for f in package['functions'] if f['name'] == finding.function and f['start_line'] <= finding.start_line <= finding.end_line <= f['end_line']]
    if len(functions) != 1:
        result['limitation'] = 'No unique local function facts; original candidate retained'
        result['seconds'] = round(perf_counter() - started, 6)
        return result
    function = functions[0]
    result['signature'] = function['complete_signature']
    result['parser_version'] = package['parser_version']
    result['schema_version'] = package['version']
    if function.get('guard_unsupported_syntax'):
        result['limitation'] = 'Unsupported local control/side-effect syntax; original candidate retained'
        result['seconds'] = round(perf_counter() - started, 6)
        return result
    prose = finding.issue + '\n' + finding.explanation
    lower = prose.lower()
    checks = result['checks']
    def cited(fact):
        return finding.start_line <= fact['end_line'] and fact['start_line'] <= finding.end_line
    def add(kind, symbol, facts, observation, relation, strict=False, family=None):
        refs = [{'start_line': f['start_line'], 'end_line': f['end_line'], 'quote': '\n'.join(f['text'].splitlines())} for f in facts]
        for ref in refs:
            selected = '\n'.join(source.splitlines()[ref['start_line']-1:ref['end_line']])
            if not ref['quote'] or ref['quote'] not in selected:
                raise InvalidEvidence('Guard observation does not match captured source lines')
        checks.append({'check_type': kind, 'symbol': symbol, 'source_lines': refs,
            'observation': observation, 'relation_to_candidate': relation, 'confidence': 'DETERMINISTIC_PATTERN',
            'strict_eligible': strict, 'suggested_category_family': family})
    # Exact operands, cited pointer use, visible branch, no alias assumptions.
    pointers = [p['name'] for p in function['parameters'] if p['pointer']]
    pointer_uses = [f for f in function['facts'] if f['kind'] == 'pointer' and f['operator'] in ('*', '->')]
    if finding.category == 'null-pointer':
        for symbol in pointers:
            if not unchecked_pointer(prose, symbol) or sum(x['name'] == symbol for x in function['parameters'] + function['locals']) != 1:
                continue
            uses = [f for f in pointer_uses if f['operand'] == symbol]
            relevant = [f for f in uses if cited(f)]
            guarded = []
            for use in uses:
                for guard in use.get('local_path', []):
                    intervening = [f for f in function['facts'] if guard['end_byte'] <= f['start_byte'] < use['start_byte']]
                    uncertain = any(f['kind'] in ('assignment', 'call', 'resource') for f in intervening)
                    if nonnull(guard['text'], symbol, guard['truth']) and not uncertain:
                        guarded.append((use, guard));break
            if relevant and all(any(u == use for u, _ in guarded) for use in relevant):
                refs = [f for u,g in guarded if u in relevant for f in (g,u)]
                strict = len(guarded) == len(uses) and not re.search(r'overflow|boundary|leak|double.free|use.after|out.of.bounds', lower)
                add('EXPLICIT_NULL_GUARD', symbol, refs, 'The cited access is inside an explicit non-null branch for this exact parameter.',
                    'POTENTIAL_CONTRADICTION', strict)
    mechanisms = [('POSSIBLE_DOUBLE_RELEASE', r'double.?free|duplicate release|released twice|free.*twice', 'REPEATED_RELEASE'),
                  ('POSSIBLE_USE_AFTER_RELEASE', r'use.after.free|use.after.release|after (?:freeing|it is (?:freed|deallocated|released))|after.*(?:deallocated|released)', 'ACCESS_AFTER_RELEASE')]
    for signal_name, pattern, kind in mechanisms:
        if not re.search(pattern, lower):continue
        for signal in function['signals']:
            if signal['kind'] != signal_name or not any(finding.start_line <= line <= finding.end_line for line in signal['lines']):continue
            facts = [f for f in function['facts'] if f['text'] in signal['source_text'] and f['start_line'] in signal['lines'] and f['kind'] in ('resource','pointer')]
            operands = {f.get('operand') for f in facts}
            if len(operands) != 1 or not facts:continue
            symbol = next(iter(operands))
            if not re.fullmatch(r'[A-Za-z_]\w*', symbol or ''):continue
            first,last = min(f['end_byte'] for f in facts),max(f['start_byte'] for f in facts)
            if any(f['kind']=='call' and first <= f['start_byte'] < last and f['text'] not in signal['source_text'] for f in function['facts']):continue
            add(kind, symbol, facts, 'The same exact local expression has the captured release/access sequence.', 'CORROBORATED')
            if finding.category != 'resource':
                add('CATEGORY_CONSISTENCY', symbol, facts, 'Candidate category '+finding.category+' differs from the visible resource-lifetime mechanism.',
                    'CATEGORY_CONSISTENCY_WARNING', family='resource')
    if finding.category == 'initialization' and re.search(r'never initialized|not initialized|uninitialized|without initializing', lower):
        for local in function['locals']:
            symbol = local['name']
            if not named(prose,symbol) or not local['initialized'] or not local.get('direct_body'):continue
            if sum(x['name']==symbol for x in function['parameters']+function['locals']) != 1:continue
            uses = [f for f in function['facts'] if cited(f) and f['kind']=='return' and f['expression']==symbol and f.get('direct_body') and local['end_byte'] < f['start_byte']]
            for use in uses:
                between = [f for f in function['facts'] if local['end_byte'] <= f['start_byte'] < use['start_byte']]
                if between:continue
                # Only a literal initializer; no deferred calls or self-initialization.
                if not re.search(r'=\s*(?:[0-9]+|true|false)\s*;',local['text']):continue
                if re.search(r'overflow|boundary|leak|double.free|use.after|out.of.bounds', lower):continue
                add('VISIBLE_INITIALIZATION',symbol,[local,use],'A direct literal initialization precedes this local return with no intervening observations.', 'POTENTIAL_CONTRADICTION',True)
    if re.search(r'(?:never|does not|not) checks?\b',lower):
        for condition in function['facts']:
            if condition['kind']!='condition' or condition['start_line']>finding.end_line:continue
            # Require an explicitly quoted exact expression in the allegation.
            related = condition.get('direct_statement') or any(cited(f) and any(g['start_byte']==condition['start_byte'] for g in f.get('local_path',[])) for f in function['facts'])
            if not related:continue
            expressions = set(re.findall(r'`([^`]+)`',prose))
            for symbol in expressions:
                if not re.fullmatch(r'[A-Za-z_]\w*(?:(?:->|\.)[A-Za-z_]\w*)?',symbol) or symbol not in condition.get('referenced_expressions',[]):continue
                if symbol not in function['identifiers'] and '->' not in symbol and '.' not in symbol:continue
                add('VISIBLE_CONDITION',symbol,[condition],'An explicit local condition contains the exact referenced expression.', 'POTENTIAL_CONTRADICTION',False)
    relations = {c['relation_to_candidate'] for c in checks}
    result['guard_status'] = next((s for s in ('POTENTIAL_CONTRADICTION','CATEGORY_CONSISTENCY_WARNING','CORROBORATED') if s in relations), 'NOT_APPLICABLE')
    result['seconds'] = round(perf_counter()-started,6)
    return result


def apply(response, manifest, policy):
    if policy not in ('annotation','strict'):raise ValueError('Unknown AST guard policy')
    records,effective = [],[]
    for finding in response.findings:
        guard = check(finding,manifest)
        suppressed = policy=='strict' and any(c['strict_eligible'] and c['relation_to_candidate']=='POTENTIAL_CONTRADICTION' for c in guard['checks'])
        if not suppressed:effective.append(finding)
        records.append({'original_candidate':finding.model_dump(),'ast_guard_result':guard,
            'effective_candidate':None if suppressed else finding.model_dump(),'effective_status':'SUPPRESSED_LOCAL_CONTRADICTION' if suppressed else 'RETAINED_CANDIDATE', 'policy':policy})
    outcome = response.outcome if effective or not response.findings else 'NO_SUPPORTED_FINDING'
    return response.model_copy(update={'findings':effective,'outcome':outcome}), records
