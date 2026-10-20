def find(tree):
    sink = []
    def walk(node, ctx):
        if isinstance(node, list):
            if len(node) >= 2 and node[0] == "Command" and isinstance(node[1], list) and node[1] and node[1][0] == "ShowEffect":
                sink.append((node[1], list(ctx)))
            ctx2 = ctx + [node[0]] if node and isinstance(node[0], str) and node[0].startswith("Conditionals") else ctx
            for ch in node:
                walk(ch, ctx2)
        elif isinstance(node, dict):
            for v in node.values():
                walk(v, ctx)
    walk(tree, [])
    return sink
