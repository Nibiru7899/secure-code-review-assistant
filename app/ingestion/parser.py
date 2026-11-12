from dataclasses import dataclass

import tree_sitter_c
import tree_sitter_cpp
from tree_sitter import Language, Parser


@dataclass(frozen=True)
class Unit:
    symbol: str
    signature: str
    start_byte: int
    end_byte: int


def units(source, language):
    grammar = tree_sitter_c.language() if language == "c" else tree_sitter_cpp.language()
    tree = Parser(Language(grammar)).parse(source)
    if tree.root_node.has_error:
        raise ValueError("Tree-sitter found syntax errors")
    found = []

    def walk(node, parents=()):
        name = node.child_by_field_name("name")
        if node.type in ("namespace_definition", "class_specifier", "struct_specifier") and name:
            parents = parents + (source[name.start_byte:name.end_byte].decode("utf-8"),)
        if node.type == "function_definition":
            declarator = node.child_by_field_name("declarator")
            current = declarator
            while current and current.type != "function_declarator":
                current = current.child_by_field_name("declarator")
            identifier = current.child_by_field_name("declarator") if current else None
            if identifier is None:
                raise ValueError("Unresolved function declarator")
            symbol = source[identifier.start_byte:identifier.end_byte].decode("utf-8")
            if parents:
                symbol = "::".join(parents + (symbol,))
            signature = source[declarator.start_byte:declarator.end_byte].decode("utf-8")
            found.append(Unit(symbol, signature, node.start_byte, node.end_byte))
            return
        for child in node.children:
            walk(child, parents)

    walk(tree.root_node)
    return found
