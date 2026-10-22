"""实测：两个任务同时提交时，worker 是并行消费还是串行消费。

方法：
  在 1 秒内提交 2 个任务，然后读取各自事件流（research:events:{task_id}）
  的首/末消息 ID。Redis Stream ID 的格式是 `<毫秒时间戳>-<序号>`，
  所以能直接从 ID 还原出每个任务的开始与结束时刻。

  若两任务时间区间不重叠（B 的开始 > A 的结束）→ 串行消费
  若区间重叠 → 并行消费
"""

import http.cookiejar
import json
import time
import urllib.request

BASE = "http://127.0.0.1:5173"
CLI = r"C:\dr-runtime\memurai\extracted\Memurai\memurai-cli.exe"

cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))


def post_json(path, payload):
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with opener.open(req, timeout=60) as resp:
        return json.loads(resp.read().decode())


def redis(*args):
    import subprocess

    # 事件流里含中文，必须显式 utf-8 + errors=replace，
    # 否则 Windows 默认 GBK 解码会抛 UnicodeDecodeError
    out = subprocess.run(
        [CLI, "-h", "127.0.0.1", "-p", "6379", *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
    ).stdout or ""
    return out.strip()


def stream_span(task_id):
    """返回 (首条ID, 末条ID, 事件数)"""
    key = f"research:events:{task_id}"
    n = redis("XLEN", key)
    first = redis("XRANGE", key, "-", "+", "COUNT", "1").split()
    last = redis("XREVRANGE", key, "+", "-", "COUNT", "1").split()
    return (
        first[0] if first else None,
        last[0] if last else None,
        int(n) if n.isdigit() else 0,
    )


def ts(msg_id):
    """从 stream ID 提取毫秒时间戳"""
    return int(msg_id.split("-")[0]) / 1000.0


print("== 1) 登录 ==")
print(post_json("/api/login", {"username": "zhangsan", "password": "zhangsan"}))

topic = "2025 年 AI 芯片市场规模"
payload = {
    "messages": [{"type": "human", "content": topic}],
    "initial_search_query_count": 1,
    "max_research_loops": 1,
    "reasoning_model": "qwen3.6-flash",
}

print("\n== 2) 在 1 秒内连续提交 2 个任务 ==")
t_submit = time.time()
a = post_json("/api/research", payload)
b = post_json("/api/research", payload)
print(f"  任务A task_id = {a['task_id']}")
print(f"  任务B task_id = {b['task_id']}")
print(f"  两次提交间隔 = {time.time() - t_submit:.2f} 秒")

print("\n== 3) 等待两个任务都跑到「计划确认暂停」（每个任务约 10 秒）==")
deadline = time.time() + 300
final = {}
while time.time() < deadline:
    done = True
    for label, task in (("A", a), ("B", b)):
        key = f"research:events:{task['task_id']}"
        body = redis("XREVRANGE", key, "+", "-", "COUNT", "1")
        if "task_paused" not in body and "error" not in body:
            done = False
    if done:
        break
    time.sleep(3)

print("\n== 4) 两个任务的事件流时间区间 ==")
rows = []
for label, task in (("A", a), ("B", b)):
    first, last, n = stream_span(task["task_id"])
    if not first:
        print(f"  任务{label}: 无事件")
        continue
    rows.append((label, ts(first), ts(last), n))
    print(f"  任务{label}: 首条 {first} → 末条 {last}, 事件数 {n}, "
          f"耗时 {ts(last) - ts(first):.1f} 秒")

if len(rows) == 2:
    (la, sa, ea, _), (lb, sb, eb, _) = rows
    base = min(sa, sb)
    print("\n== 5) 时间轴（相对首个任务的开始）==")
    for label, s, e, _ in rows:
        bar_start = int((s - base))
        bar_len = max(1, int(e - s))
        print(f"  任务{label}: {' ' * bar_start}|{'#' * bar_len}|  ({s - base:.1f}s → {e - base:.1f}s)")

    print("\n== 6) 结论 ==")
    if sb >= ea:
        print(f"  【串行】任务B 在 {sb - ea:.1f} 秒后才开始，任务A 早已结束")
    elif sa >= eb:
        print(f"  【串行】任务A 在 {sa - eb:.1f} 秒后才开始，任务B 早已结束")
    else:
        overlap = min(ea, eb) - max(sa, sb)
        print(f"  【并行】两任务时间区间重叠 {overlap:.1f} 秒")
