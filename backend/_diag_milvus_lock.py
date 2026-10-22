"""临时诊断：Milvus Lite 本地库的打开/并发行为。

验证三件事：
  1) 新鲜路径首次打开能否建表写入
  2) 关闭后再次打开，数据是否还在（落盘）
  3) 两个客户端同时打开同一路径会怎样（是否文件锁冲突）
"""

import glob
import os
import shutil
import time

from pymilvus import MilvusClient

DB = r"C:/dr-runtime/milvus/probe.db"
for p in glob.glob(DB + "*"):
    try:
        os.remove(p)
    except OSError as e:
        print("清理失败:", p, e)


def open_client(tag: str) -> MilvusClient:
    c = MilvusClient(uri=DB)
    print(f"[{tag}] 打开成功")
    return c


print("== 1) 首次打开 + 建表 + 写入 ==")
c1 = open_client("first")
c1.create_collection(collection_name="t", dimension=8, metric_type="COSINE")
c1.insert(collection_name="t", data=[{"id": 1, "vector": [0.1] * 8}])
print("[first] 行数 =", c1.query(collection_name="t", filter="id >= 0"))
c1.close()
print("[first] 已关闭")
print("文件:", [(os.path.basename(p), os.path.getsize(p)) for p in glob.glob(DB + "*")])

print("\n== 2) 重新打开，验证落盘 ==")
time.sleep(1)
try:
    c2 = open_client("second")
    print("[second] collections =", c2.list_collections())
    print("[second] 行数 =", c2.query(collection_name="t", filter="id >= 0"))
except Exception as e:
    print("[second] 失败:", type(e).__name__, e)
    c2 = None

print("\n== 3) 同时再开一个客户端（模拟并发）==")
try:
    c3 = open_client("concurrent")
    print("[concurrent] collections =", c3.list_collections())
    c3.close()
except Exception as e:
    print("[concurrent] 失败:", type(e).__name__, e)

if c2 is not None:
    c2.close()
print("\n完成")
