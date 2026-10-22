import json
p = "eval_report_20260613_142601.json"
d = json.load(open(p, encoding="utf-8"))
print("顶层字段:", list(d.keys()))
def peek(o, depth=0, maxd=3):
    pad = "  " * depth
    if depth > maxd: return
    if isinstance(o, dict):
        for k, v in list(o.items())[:14]:
            if isinstance(v, (dict, list)):
                print(f"{pad}{k}: {type(v).__name__}({len(v)})")
                peek(v, depth+1, maxd)
            else:
                print(f"{pad}{k}: {str(v)[:100]}")
    elif isinstance(o, list) and o:
        print(f"{pad}[0]:")
        peek(o[0], depth+1, maxd)
peek(d)
