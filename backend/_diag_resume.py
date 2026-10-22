"""临时验证脚本：完整 HITL 流程（计划确认 → 研究 → 写作 → 最终答案）。

关键点：confirm_plan 的语义检查要求用户消息包含"开始研究"（或 LLM 评估通过），
因此确认时必须把该措辞作为新的 human 消息带上。
"""

import http.cookiejar
import json
import time
import urllib.request

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
    with opener.open(req, timeout=60) as resp:
        return json.loads(resp.read().decode())


def last_event_id(task_id: str) -> str:
    """读取 Redis 事件流当前最后一条消息 ID（用于 SSE 断点续传）。"""
    import subprocess

    cli = r"C:\dr-runtime\memurai\extracted\Memurai\memurai-cli.exe"
    out = subprocess.run(
        [cli, "-h", "127.0.0.1", "-p", "6379", "XREVRANGE",
         f"research:events:{task_id}", "+", "-", "COUNT", "1"],
        capture_output=True, text=True, timeout=30,
    ).stdout.split()
    return out[0] if out else "0"


def stream(path: str, limit_seconds: int = 420, last_id: str | None = None) -> tuple[list[str], dict]:
    kinds: list[str] = []
    summary: dict = {}
    counts: dict[str, int] = {}
    headers = {"Last-Event-ID": last_id} if last_id else {}
    req = urllib.request.Request(BASE + path, headers=headers)
    start = time.time()
    with opener.open(req, timeout=limit_seconds) as resp:
        for raw in resp:
            if time.time() - start > limit_seconds:
                summary["timeout"] = True
                break
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data: "):
                continue
            try:
                ev = json.loads(line[6:])
            except json.JSONDecodeError:
                continue
            for key in ev:
                counts[key] = counts.get(key, 0) + 1
                if key not in kinds:
                    kinds.append(key)
                if key == "finalize_answer":
                    summary["final_answer"] = str(ev[key])[:300]
                if key == "error":
                    summary["error"] = str(ev[key])[:400]
            if any(k in ev for k in ("error", "finalize_answer", "task_paused")):
                break
    summary["elapsed"] = round(time.time() - start, 1)
    summary["event_counts"] = counts
    return kinds, summary


print("== 1) 登录 ==")
print(post_json("/api/login", {"username": "zhangsan", "password": "zhangsan"}))

topic = "2025 年 AI 芯片市场规模"
print("== 2) 首次提交，等待计划确认 ==")
task = post_json("/api/research", {
    "messages": [{"type": "human", "content": topic}],
    "initial_search_query_count": 1,
    "max_research_loops": 1,
    "reasoning_model": "qwen3.6-flash",
})
kinds1, sum1 = stream(task["stream_url"], limit_seconds=180)
print("   事件类型:", kinds1)
print("   汇总:", {k: v for k, v in sum1.items() if k != "plan_preview"})
if sum1.get("error"):
    print("!! 首次提交失败:", sum1["error"])
    raise SystemExit(1)

print("== 3) 确认计划（带『开始研究』措辞，回传同一 task_id）==")
# 记录当前事件流末尾，稍后只读增量，避免把上一轮的缓存事件当成续跑结果
resume_from = last_event_id(task["task_id"])
print("   SSE 断点 Last-Event-ID =", resume_from)
payload2 = {
    "messages": [
        {"type": "human", "content": topic},
        {"type": "ai", "content": "已生成研究计划"},
        {"type": "human", "content": "开始研究"},
    ],
    "initial_search_query_count": 1,
    "max_research_loops": 1,
    "reasoning_model": "qwen3.6-flash",
    "plan": "1. 检索 AI 芯片市场规模数据\n2. 汇总并给出结论",
    "plan_status": "confirmed",
    "task_id": task["task_id"],
}
task2 = post_json("/api/research", payload2)
print("   task_id 复用:", task2["task_id"] == task["task_id"])

print("== 4) 订阅续跑事件流（研究 → 写作 → 最终答案）==")
kinds2, sum2 = stream(task2["stream_url"], limit_seconds=420, last_id=resume_from)
print("   事件类型:", kinds2)
print("   事件计数:", sum2.get("event_counts"))
print("   耗时:", sum2.get("elapsed"), "秒")
if sum2.get("final_answer"):
    print("   最终答案预览:", sum2["final_answer"][:200])

print()
print("== 结论 ==")
if sum2.get("error"):
    print("   失败:", sum2["error"])
elif "finalize_answer" in kinds2:
    print("   成功：完整跑通 计划确认 → 研究 → 写作 → 最终答案")
else:
    print("   未跑到 finalize_answer，事件类型:", kinds2)
