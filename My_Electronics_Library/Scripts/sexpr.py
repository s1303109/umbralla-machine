"""Small dependency-free KiCad S-expression reader/writer (no format conversion)."""
import json
import re


class Quoted(str):
    pass


def parse(text):
    tokens = re.findall(r'"(?:\\.|[^"\\])*"|[()]|[^\s()]+', text)
    stack, root = [], None
    for token in tokens:
        if token == '(':
            node = []
            if stack:
                stack[-1].append(node)
            elif root is not None:
                raise ValueError('Multiple roots')
            else:
                root = node
            stack.append(node)
        elif token == ')':
            if not stack:
                raise ValueError('Unexpected closing parenthesis')
            stack.pop()
        else:
            if not stack:
                raise ValueError('Atom outside root')
            stack[-1].append(Quoted(json.loads(token)) if token.startswith('"') else token)
    if stack or root is None:
        raise ValueError('Incomplete S-expression')
    return root


def atom(value):
    return json.dumps(str(value), ensure_ascii=False) if isinstance(value, Quoted) else str(value)


def dumps(node, depth=0):
    if not isinstance(node, list):
        return atom(node)
    first_child = next((i for i, v in enumerate(node) if isinstance(v, list)), len(node))
    start = '(' + ' '.join(atom(v) for v in node[:first_child])
    if first_child == len(node):
        return start + ')'
    return start + '\n' + '\n'.join('  ' * (depth + 1) + dumps(v, depth + 1) for v in node[first_child:]) + '\n' + '  ' * depth + ')'


def children(node, key):
    return [x for x in node if isinstance(x, list) and x and x[0] == key]


def child(node, key, default=None):
    return next(iter(children(node, key)), default)


def walk(node, key):
    if isinstance(node, list):
        if node and node[0] == key:
            yield node
        for value in node:
            if isinstance(value, list):
                yield from walk(value, key)


def properties(node):
    return {str(x[1]): str(x[2]) for x in children(node, 'property')}


def set_property(node, key, value):
    existing = next((x for x in children(node, 'property') if x[1] == key), None)
    if existing:
        existing[2] = Quoted(value)
    else:
        node.insert(2, ['property', Quoted(key), Quoted(value), ['at', '0', '0', '0'],
                        ['effects', ['font', ['size', '1.27', '1.27']], ['hide', 'yes']]])
