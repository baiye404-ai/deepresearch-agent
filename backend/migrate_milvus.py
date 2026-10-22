"""把 Milvus Lite 里的事实迁移到 Milvus standalone（供 Attu 查看/管理）。

背景：切到 Docker 版 Milvus 后，原来存在 Milvus Lite 里的事实不会自动迁移。
本脚本从 Lite 库读出全部事实，重新写入 standalone，供 Attu 查看。

用法（在 backend 目录下执行）：
    .venv\\Scripts\\python.exe migrate_milvus.py
可覆盖的环境变量：
    LITE_DB_PATH    Milvus Lite 库文件，默认取 .env 的 MILVUS_DB_PATH
    TARGET_URI      目标 Milvus 地址，默认 http://127.0.0.1:19530
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.abspath("src"))

from dotenv import load_dotenv

load_dotenv()

from pymilvus import MilvusClient

from agent.kb import FactStore

COLLECTION = "research_facts"
OUTPUT_FIELDS = [
    "fact_text",
    "source_url",
    "research_topic",
    "confidence",
    "fact_category",
    "created_at",
]

lite_path = os.getenv("LITE_DB_PATH") or os.getenv("MILVUS_DB_PATH")
target_uri = os.getenv("TARGET_URI", "http://127.0.0.1:19530")

if not lite_path:
    print("错误：未找到 Milvus Lite 库路径，请设置 LITE_DB_PATH 或 .env 的 MILVUS_DB_PATH")
    raise SystemExit(1)

print(f"源（Milvus Lite）: {lite_path}")
print(f"目标（standalone）: {target_uri}")

print("\n== 1) 读取源库全部事实 ==")
src_client = MilvusClient(uri=lite_path)
if not src_client.has_collection(COLLECTION):
    print(f"源库没有集合 {COLLECTION}，无需迁移")
    raise SystemExit(0)

src_client.load_collection(COLLECTION)
rows = src_client.query(
    collection_name=COLLECTION,
    filter="id >= 0",
    output_fields=OUTPUT_FIELDS,
    limit=16384,
)
print(f"读到 {len(rows)} 条事实")
if not rows:
    print("源库为空，无需迁移")
    raise SystemExit(0)

print("\n== 2) 写入目标 Milvus（重建向量，需要用 Embedding）==")
os.environ["MILVUS_DB_PATH"] = ""  # 确保 FactStore 走 URI 而不是本地 Lite
os.environ.pop("MILVUS_DB_PATH", None)
target = FactStore(uri=target_uri)
print("目标集合统计（迁移前）:", target.stats())

facts = [
    {
        "fact": r.get("fact_text", ""),
        "source_url": r.get("source_url", ""),
        "research_topic": r.get("research_topic", ""),
        "confidence": r.get("confidence", 1.0),
        "fact_category": r.get("fact_category", "strategy"),
    }
    for r in rows
    if r.get("fact_text")
]

batch = 20
inserted_total = 0
for i in range(0, len(facts), batch):
    chunk = facts[i : i + batch]
    inserted_total += target.add_facts(chunk)
    print(f"  已写入 {inserted_total}/{len(facts)}")

print("\n== 3) 校验 ==")
print("目标集合统计（迁移后）:", target.stats())
hits = target.query("AI芯片市场规模", top_k=3)
print(f"抽样检索命中 {len(hits)} 条：")
for h in hits:
    print("   -", str(h.get("fact"))[:60])

print(f"\n完成：共迁移 {inserted_total} 条事实到 {target_uri}")
print("现在可以在 Attu（http://127.0.0.1:8000）里看到集合 research_facts")
