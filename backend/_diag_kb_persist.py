"""临时验证脚本：知识库在正式 .env 配置下能否写入并持久化。

与 _diag_kb.py 的区别：完全走 backend/.env 的 MILVUS_DB_PATH，
不手动覆盖任何环境变量，并验证数据在重新打开后仍然存在（真正落盘）。
"""

import os
import sys

sys.path.insert(0, os.path.abspath("src"))

from dotenv import load_dotenv

load_dotenv()

from agent.kb import FactStore

path = os.environ["MILVUS_DB_PATH"]
print("MILVUS_DB_PATH =", path)
print("写前文件大小 =", os.path.getsize(path) if os.path.exists(path) else "不存在")

print("\n== 第一次打开：写入 2 条事实 ==")
store = FactStore()
n = store.add_facts([
    {
        "fact": "2025 年全球 AI 芯片市场规模约 1200 亿美元。",
        "source_url": "https://example.com/a",
        "research_topic": "AI芯片市场",
        "confidence": 0.9,
        "fact_category": "market",
    },
    {
        "fact": "数据中心 GPU 市场由英伟达主导。",
        "source_url": "https://example.com/b",
        "research_topic": "AI芯片市场",
        "confidence": 0.8,
        "fact_category": "market",
    },
])
print("写入条数 =", n)
print("统计 =", store.stats())
print("写后文件大小 =", os.path.getsize(path))
store.client.close()

print("\n== 第二次打开：验证数据是否真正落盘 ==")
import time

time.sleep(2)
store2 = FactStore()
print("统计 =", store2.stats())
hits = store2.query("AI芯片市场规模", top_k=3)
print(f"检索命中 {len(hits)} 条:")
for h in hits:
    print("   -", str(h.get("fact"))[:60])
store2.client.close()
