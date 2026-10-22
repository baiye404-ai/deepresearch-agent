"""临时验证脚本：端到端跑一个真实研究任务（验证 Postgres + Redis Streams + LLM + KB）。"""

import json
import re
import sys
import time
import urllib.request
import http.cookiejar

BASE = "http://127.0.0.1:5173"

cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))


def post_json(path: str, payload: dict) -> dict:
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with opener.open(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


print("== 1) 登录 ==")
print(post_json("/api/login", {"username": "zhangsan", "password": "zhangsan"}))

print("== 2) 提交研究任务（最小规模：1 条初始查询 / 1 轮）==")
task = post_json("/api/research", {
    "messages": [{"type": "human", "content": "用一句话说明 2025 年 AI 芯片市场的规模"}],
    "initial_search_query_count": 1,
    "max_research_loops": 1,
    "reasoning_model": "qwen3.6-flash",
})
task_id = task["task_id"]
print("   task_id =", task_id, "| stream =", task["stream_url"])

print("== 3) 订阅 SSE 事件流 ==")
req = urllib.request.Request(BASE + task["stream_url"])
event_count = 0
nodes = []
start = time.time()
deadline = start + 420  # 最多等 7 分钟

try:
    with opener.open(req, timeout=deadline - start) as resp:
        for raw in resp:
            if time.time() > deadline:
                print("   [超时] 达到 7 分钟上限")
                break
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data: "):
                continue
            event_count += 1
            body = line[6:]
            try:
                ev = json.loads(body)
            except json.JSONDecodeError:
                continue
            for key in ev:
                if key not in nodes:
                    nodes.append(key)
            if event_count <= 12:
                print(f"   [{event_count:>3}] {body[:150]}")
            if any(k in ev for k in ("error", "finalize_answer", "task_paused")):
                print(f"   [终止] 收到 {[k for k in ev if k in ('error','finalize_answer','task_paused')]}")
                break
finally:
    pass

print(f"== 4) 汇总：事件数={event_count} 耗时={time.time()-start:.1f}s ==")
print("   事件类型:", nodes)
