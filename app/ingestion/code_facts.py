"""Bounded syntactic observations. No compilation, call graph or defect verdicts."""
import copy
from functools import lru_cache
import hashlib
import re
from importlib.metadata import version

from tree_sitter import Language, Parser
import tree_sitter_c
import tree_sitter_cpp

VERSION = 'tree-sitter-facts-v1'


def descendants(node):
    yield node
    for child in node.named_children:
        if child.type not in ('lambda_expression',):
            yield from descendants(child)


def text(node):
    return node.text.decode('utf-8') if node else ''


def identifier(node):
    if node is None:
        return ''
    if node.type in ('identifier', 'field_identifier', 'qualified_identifier'):
        return text(node)
    child = node.child_by_field_name('declarator')
    if child is None and node.type in ('parenthesized_declarator', 'reference_declarator'):
        child = next(iter(node.named_children), None)
    return identifier(child)


def observation(node, kind, **fields):
    return dict(kind=kind, text=text(node), start_line=node.start_point.row + 1,
                end_line=node.end_point.row + 1, start_byte=node.start_byte, end_byte=node.end_byte, **fields)


def local_path(node, body):
    """Visible branch ancestry only; does not establish program-wide dominance."""
    path, child = [], node
    while child.parent and child.parent != body:
        parent = child.parent
        if parent.type in ('if_statement', 'conditional_expression'):
            for field, truth in (('consequence', True), ('alternative', False)):
                branch = parent.child_by_field_name(field)
                if branch and branch.start_byte <= node.start_byte < branch.end_byte:
                    condition = parent.child_by_field_name('condition')
                    path.append(observation(condition, 'branch_guard', truth=truth))
        child = parent
    return path


@lru_cache(maxsize=128)
def parsed_facts(source, language):
    grammar = tree_sitter_c.language() if language == 'c' else tree_sitter_cpp.language()
    tree = Parser(Language(grammar)).parse(source)
    if tree.root_node.has_error:
        raise ValueError('Syntax facts unavailable: parser errors')
    all_nodes = list(descendants(tree.root_node))
    includes = [observation(n, 'include', path=text(n.child_by_field_name('path'))[1:-1])
                for n in all_nodes if n.type == 'preproc_include']
    declared_names = {identifier(n.child_by_field_name('declarator')).split('::')[-1]
                      for n in all_nodes if n.type == 'function_declarator'}
    library_headers = {i['path'] for i in includes}
    functions, declarations, types = [], [], []
    for node in all_nodes:
        if node.type in ('struct_specifier', 'class_specifier', 'enum_specifier'):
            types.append(observation(node, 'type', name=text(node.child_by_field_name('name'))))
        if node.type == 'declaration':
            for child in descendants(node):
                if child.type == 'function_declarator':
                    declarations.append(observation(node, 'declaration', name=identifier(child.child_by_field_name('declarator')),
                                                    signature=text(child)))
        if node.type != 'function_definition':
            continue
        declarator = node.child_by_field_name('declarator')
        function_decl = next((n for n in descendants(declarator) if n.type == 'function_declarator'), None)
        if function_decl is None:
            continue
        name = identifier(function_decl.child_by_field_name('declarator'))
        parents, parent = [], node.parent
        while parent:
            if parent.type in ('namespace_definition', 'class_specifier', 'struct_specifier'):
                parents.insert(0, text(parent.child_by_field_name('name')))
            parent = parent.parent
        qualified = '::'.join(parents + [name]) if parents else name
        return_prefix = source[node.start_byte:function_decl.start_byte].decode('utf-8').strip()
        parameters = []
        for p in function_decl.child_by_field_name('parameters').named_children:
            if p.type not in ('parameter_declaration', 'optional_parameter_declaration'):
                continue
            d = p.child_by_field_name('declarator')
            parameter_name = identifier(d)
            type_text = re.sub(r'\b' + re.escape(parameter_name) + r'\b(?:\s*=.*)?$', '', text(p)).strip() if parameter_name else text(p)
            parameters.append(observation(p, 'parameter', name=parameter_name, type_text=type_text,
                pointer=any(n.type in ('pointer_declarator', 'abstract_pointer_declarator') for n in descendants(p)),
                reference=any(n.type in ('reference_declarator', 'abstract_reference_declarator') for n in descendants(p))))
        body = node.child_by_field_name('body')
        nodes = list(descendants(body))
        facts, locals_ = [], []
        pointer_names = {p['name'] for p in parameters if p['pointer']}
        for n in nodes:
            if n.type == 'declaration':
                for d in n.named_children:
                    if 'declarator' in d.type or d.type == 'identifier':
                        actual = d.child_by_field_name('declarator') if d.type == 'init_declarator' else d
                        name_ = identifier(actual)
                        if name_:
                            locals_.append(observation(n, 'local', name=name_, type_text=text(n.child_by_field_name('type')),
                                initialized=d.type == 'init_declarator', pointer=any(x.type == 'pointer_declarator' for x in descendants(d))))
                            if locals_[-1]['pointer']:
                                pointer_names.add(name_)
            if n.type in ('if_statement', 'switch_statement', 'while_statement', 'for_statement', 'do_statement', 'conditional_expression'):
                c = n.child_by_field_name('condition')
                facts.append(observation(c or n, 'condition', structure=n.type, direct_statement=n.parent == body,
                    referenced_expressions=[text(x) for x in descendants(c or n) if x.type in ('identifier','field_expression')]))
            elif n.type == 'return_statement':
                expression = text(n.named_children[0]) if n.named_children else ''
                facts.append(observation(n, 'return', expression=expression, early=n.parent != body or n.end_byte < body.named_children[-1].end_byte))
            elif n.type == 'call_expression':
                called = n.child_by_field_name('function')
                receiver = text(called.child_by_field_name('argument')) if called and called.type == 'field_expression' else ''
                args = n.child_by_field_name('arguments')
                facts.append(observation(n, 'call', name=text(called), receiver=receiver,
                    arguments=[text(a) for a in args.named_children] if args else []))
            elif n.type == 'assignment_expression':
                facts.append(observation(n, 'assignment', target=text(n.child_by_field_name('left')), expression=text(n.child_by_field_name('right'))))
            elif n.type in ('pointer_expression', 'field_expression'):
                op = text(n.child_by_field_name('operator'))
                if op in ('*', '&', '->'):
                    facts.append(observation(n, 'pointer', operator=op, operand=text(n.child_by_field_name('argument'))))
            elif n.type == 'binary_expression' and text(n.child_by_field_name('operator')) in ('==', '!='):
                left, right = text(n.child_by_field_name('left')), text(n.child_by_field_name('right'))
                if (left in pointer_names and right in ('nullptr', 'NULL', '0')) or (right in pointer_names and left in ('nullptr', 'NULL', '0')):
                    facts.append(observation(n, 'null_comparison'))
                else:
                    facts.append(observation(n, 'comparison'))
            elif n.type == 'binary_expression' and text(n.child_by_field_name('operator')) == '&&':
                left = n.child_by_field_name('left')
                if text(left) in pointer_names:
                    facts.append(observation(left, 'condition', structure='short_circuit_and'))
            if n.type in ('new_expression', 'delete_expression'):
                facts.append(observation(n, 'resource', operation=('new' if n.type == 'new_expression' else 'delete') + ('[]' if '[' in text(n) else ''),
                                         operand=text(n.named_children[-1]), direct=n.parent.type == 'expression_statement' and n.parent.parent == body))
        for f in list(facts):
            if f['kind'] == 'call':
                operation = f['name'].removeprefix('std::')
                standard = operation in ('malloc', 'calloc', 'realloc', 'free', 'fopen', 'fclose', 'scanf')
                header = bool(library_headers & ({'cstdlib', 'stdlib.h'} if operation in ('malloc', 'calloc', 'realloc', 'free') else {'cstdio', 'stdio.h'}))
                shadowed = {p['name'] for p in parameters} | {local['name'] for local in locals_}
                if standard and header and f['name'] in (operation, 'std::' + operation) and operation not in declared_names | shadowed:
                    call_node = next(n for n in nodes if n.type == 'call_expression' and n.start_point.row + 1 == f['start_line'] and text(n) == f['text'])
                    facts.append(dict(f, kind='resource', operation=operation,
                        operand=f['arguments'][0] if f['arguments'] else '', direct=call_node.parent.type == 'expression_statement' and call_node.parent.parent == body))
        signals = []
        def signal(kind, refs):
            signals.append({'kind': kind, 'lines': sorted({f['start_line'] for f in refs}), 'source_text': [f['text'] for f in refs]})
        for f in facts:
            if f['kind'] == 'return' and re.search(r'\b(nullptr|NULL)\b', f['expression']):
                signal('NULLABLE_RETURN_SIGNAL', [f])
            if f['kind'] == 'pointer' and f['operator'] in ('*', '->') and f['operand'] in {p['name'] for p in parameters if p['pointer']}:
                signal('POINTER_USE_SIGNAL', [f])
            if f['kind'] == 'condition':
                terms = [part.strip().strip('()').strip() for part in re.split(r'&&|\|\|', f['text'])]
                patterns = [r'!?\s*' + re.escape(p) + r'|'+re.escape(p)+r'\s*(?:==|!=)\s*(?:nullptr|NULL|0)|(?:nullptr|NULL|0)\s*(?:==|!=)\s*'+re.escape(p) for p in pointer_names]
                if any(re.fullmatch(pattern, term) for pattern in patterns for term in terms):
                    signal('NULL_GUARD_SIGNAL', [f])
        releases = [f for f in facts if f['kind'] == 'resource' and f['operation'] in ('free', 'fclose', 'delete', 'delete[]') and f['direct'] and re.fullmatch(r'[A-Za-z_]\w*', f['operand'])]
        for release in releases:
            for later in facts:
                if later['start_line'] <= release['end_line']:
                    continue
                between = [n for n in nodes if release['end_line'] < n.start_point.row + 1 < later['start_line']]
                if any(n.type in ('if_statement', 'switch_statement', 'for_statement', 'while_statement', 'do_statement', 'assignment_expression', 'declaration', 'return_statement') for n in between):
                    continue
                same = later.get('operand') == release['operand']
                if same and later.get('operation') == release['operation'] and later.get('direct'):
                    signal('POSSIBLE_DOUBLE_RELEASE', [release, later])
                elif same and later['kind'] == 'pointer' and later['operator'] in ('*', '->'):
                    signal('POSSIBLE_USE_AFTER_RELEASE', [release, later])
        for local in locals_:
            if not local['initialized']:
                following = [f for f in facts if f['start_line'] > local['end_line']]
                if following and following[0]['kind'] == 'return' and following[0]['expression'] == local['name']:
                    signal('POSSIBLE_UNINITIALIZED_USE', [local, following[0]])
        for f in facts:
            if f['kind'] == 'resource' and f['operation'] in ('scanf', 'fclose') and f.get('direct'):
                signal('POSSIBLE_UNCHECKED_RESULT', [f])
        local_names = {p['name'] for p in parameters} | {p['name'] for p in locals_}
        for f in facts:
            if f['kind'] == 'assignment':
                f['state_target'] = 'visible_field' if '.' in f['target'] or '->' in f['target'] else ('nonlocal_identifier' if f['target'] not in local_names else 'local_identifier')
        by_range = {(n.start_byte, n.end_byte): n for n in nodes}
        for f in facts + locals_:
            syntax = by_range.get((f['start_byte'], f['end_byte']))
            if syntax:
                f['local_path'] = local_path(syntax, body)
                f['direct_body'] = syntax.parent == body or (syntax.parent.type == 'expression_statement' and syntax.parent.parent == body)
        functions.append(dict(name=qualified, signature=text(declarator), complete_signature=return_prefix + ' ' + text(function_decl),
            return_type=return_prefix, scope=parents, start_line=node.start_point.row + 1, end_line=node.end_point.row + 1,
            parameters=parameters, locals=locals_, facts=facts, signals=signals,
            guard_unsupported_syntax=sorted({n.type for n in nodes if n.type in ('update_expression','goto_statement','asm_statement','try_statement')}),
            identifiers=sorted({text(n) for n in descendants(node) if n.type in ('identifier', 'field_identifier', 'type_identifier')})))
    return {'version': VERSION, 'content_hash': hashlib.sha256(source).hexdigest(), 'functions': functions,
            'declarations': declarations, 'types': types, 'includes': includes}


def capture(source, language, repository, snapshot, file):
    result = copy.deepcopy(parsed_facts(source.encode('utf-8'), language))
    result.update(repository=repository, snapshot=snapshot, file=file)
    result['parser_version'] = version('tree-sitter')
    result['grammar_version'] = version('tree-sitter-c' if language == 'c' else 'tree-sitter-cpp')
    return result


def compact(function, prefix=''):
    """Small model-facing syntax summary; full facts remain in captured manifest."""
    lines = [function['complete_signature']]
    lines += [f"{prefix}L{p['start_line']} parameter {p['type_text']}" for p in function['parameters']]
    lines += [f"{prefix}L{p['start_line']} local {p['text']} initialized={p['initialized']}" for p in function['locals'][:10]]
    selected = [f for f in function['facts'] if f['kind'] in ('condition', 'return', 'assignment', 'resource', 'pointer', 'call', 'comparison')]
    lines += [f"{prefix}L{f['start_line']} {f['kind']}: {f['text']}" for f in selected[:24]]
    lines += [f"{s['kind']} lines {','.join(map(str,s['lines']))}" for s in function['signals']]
    if len(selected) > 24:
        lines.append('Additional syntax observations omitted from compact summary; source coverage is unchanged.')
    return '\n'.join(lines)
