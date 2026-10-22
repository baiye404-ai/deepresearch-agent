"""临时验证：MILVUS_URI 本地文件模式的正确写法（pymilvus 3.0.2 要求带协议前缀）。"""
import os
import sys
import traceback

DB = os.path.abspath("../runtime/milvus_uri_test.db")
os.makedirs(os.path.dirname(DB), exist_ok=True)
for suffix in ("", ".lock"):
    if os.path.exists(DB + suffix):
        os.remove(DB + suffix)

candidates = [
    f"file:///{DB.replace(os.sep, '/')}",
    f"sqlite:///{DB.replace(os.sep, '/')}",
]

for uri in candidates:
    print(f"\n==== 尝试 uri = {uri} ====")
    # pymilvus 在 import 时读取环境变量，所以每个候选都要独立子进程
    code = (
        "import os, sys;"
        f"os.environ['MILVUS_URI'] = {uri!r};"
        "sys.path.insert(0, 'src');"
        "from pymilvus import MilvusClient;"
        "c = MilvusClient(uri=os.environ['MILVUS_URI']);"
        "c.create_collection(collection_name='probe', dimension=1024, metric_type='COSINE');"
        "print('  结果: OK, collections =', c.list_collections());"
        "c.close()"
    )
    import subprocess

    p = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=180)
    if p.returncode == 0:
        print(p.stdout.strip())
    else:
        err = (p.stderr or "").strip().splitlines()
        print("  结果: 失败 ->", err[-1] if err else "未知错误")

for suffix in ("", ".lock"):
    if os.path.exists(DB + suffix):
        os.remove(DB + suffix)
