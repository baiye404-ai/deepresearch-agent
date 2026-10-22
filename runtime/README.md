# 本地完整部署运行时

本目录存放本地开发所需的启动脚本、配置和日志。**中间件本体不在项目内**（原因见下文"中文路径限制"）。

## 组件总览

| 组件 | 端口 | 位置 | 角色 |
|---|---|---|---|
| PostgreSQL 17.11（便携版） | 5432 | `C:\dr-runtime\pg\pgsql`<br>数据目录 `C:\dr-runtime\pgdata` | 用户表 `users`、`user_threads`、LangGraph checkpoint 表 |
| Memurai 4.1.2（Redis 7.2 兼容） | 6379 | `C:\dr-runtime\memurai` | 登录会话、任务队列（Streams）、事件流、搜索缓存 |
| Milvus Lite（嵌入式） | 无端口 | 库文件 `C:\dr-runtime\milvus\milvus.db` | 知识库 `research_facts` 集合 |
| 后端 FastAPI | 2024 | `backend/` | 应用服务 |
| 前端 Vite | 5173 | `frontend/` | 开发服务器，`/api` 反代到 2024 |

全部**免管理员**运行，不注册 Windows 服务。

## 用 Attu 管理知识库（替代 Milvus Lite）

**Attu 连不上 Milvus Lite**——Attu 通过 gRPC 网络端口连 Milvus，而 Milvus Lite 是嵌入
在 Python 进程里的库，实测打开期间**不监听任何端口**。要用 Attu 必须起真正的
Milvus standalone（Milvus 官方不提供 Windows 二进制，只能用 Docker）。

### 一次性前置（需要管理员 + 重启）

管理员 PowerShell 执行：

```powershell
wsl --install --no-distribution
```

完成后**重启电脑**。重启后验证：

```powershell
wsl --status          # 不应再报"未启用虚拟化"
wsl -d docker-desktop echo ok
```

若 `wsl --install --no-distribution` 报错，改用 dism：

```powershell
dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart
dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart
# 重启后：wsl --update
```

### 启动 Milvus + Attu

确认 Docker Desktop 已启动，然后：

```powershell
powershell -ExecutionPolicy Bypass -File runtime\start_milvus_stack.ps1
```

脚本会起 4 个容器（配置见 [milvus-stack.yaml](milvus-stack.yaml)）：

| 服务 | 镜像 | 端口 |
|---|---|---|
| etcd | `quay.io/coreos/etcd:v3.5.25` | 内部 2379 |
| MinIO | `milvusdb/minio:RELEASE.2024-12-18T13-15-44Z` | 9000 / 9001 |
| Milvus standalone | `milvusdb/milvus:v3.0.2` | 19530 / 9091 |
| Attu | `zilliz/attu:v3.0.1` | 8000 → 容器 3000 |

访问 **http://127.0.0.1:8000** ，Milvus 地址填 `127.0.0.1:19530`。

> 镜像版本已逐个核实存在。注意本机 **Docker Hub 直连不通**，依赖
> `~/.docker/daemon.json` 里已配的 5 个国内镜像源；`milvusdb/minio` 在镜像站上
> 只有 2 个 tag，务必保留 `RELEASE.2024-12-18T13-15-44Z` 这个版本。

### 把后端切到 standalone Milvus

改 `backend/.env`：

```ini
# 注释掉本地嵌入式库
# MILVUS_DB_PATH=C:/dr-runtime/milvus/milvus.db
MILVUS_URI=http://localhost:19530
```

然后把 Lite 里已有的事实迁过去（否则 Attu 里是空的）：

```powershell
cd backend
.venv\Scripts\python.exe migrate_milvus.py
```

迁移脚本会从 Lite 读出全部事实、重新计算向量、写入 standalone，并做抽样校验。

### 停止

```powershell
cd runtime
docker compose -f milvus-stack.yaml down        # 保留数据（在 D:\dr-runtime\milvus-stack）
docker compose -f milvus-stack.yaml down -v     # 清空数据
```

## 启动 / 停止

```bat
runtime\start_postgres.bat   :: 启动 PostgreSQL（首次会自动 initdb）
runtime\start_memurai.bat    :: 启动 Memurai
run_backend_local.bat        :: 启动后端（项目根目录，必须用这个，不要用 uvicorn 命令）
cd frontend && npm run dev   :: 启动前端

runtime\stop_services.bat    :: 停止 PostgreSQL + Memurai
```

默认账号：`zhangsan/zhangsan`、`lisi/lisi`（密码同用户名，bcrypt 存储于 Postgres）。

访问 http://127.0.0.1:5173/app/

## 本机踩过的坑（重要）

下面每一条都是实测撞到过的，改动前请先读。

### 1. 中文路径限制（项目目录名含"全面版"）

- **Memurai 的配置文件解析器只接受 ASCII 路径**，`dir`/`logfile` 写中文路径会直接
  `FATAL CONFIG FILE ERROR: Illegal byte sequence` 并退出。因此 Memurai 的程序和数据
  都放在 `C:\dr-runtime`。
- **`.bat` 文件必须是纯 ASCII**：cmd.exe 按 OEM 代码页解析批处理，脚本里写中文注释
  会把命令拆坏（表现为 `'═══' is not recognized as an internal or external command`）。
  需要 emoji/中文说明请写 `.md` 文件。
- **`.ps1` 文件也必须是纯 ASCII**：Windows PowerShell 5.1 在文件没有 BOM 时按
  ANSI/GBK 读取，中文注释会被解析错乱（表现为一堆莫名的
  `缺少右"}"` / `字符串缺少终止符` 语法错误，而脚本本身其实是对的）。
  `start_milvus_stack.ps1` 因此也是纯 ASCII。
- 8.3 短路径在本机不可用，无法用 `DEEPRE~1` 之类绕过中文路径。

### 2. 必须用 `run_server.py`，不能用 `uvicorn` 命令

`langgraph-checkpoint-postgres` 用 psycopg 的异步模式，而 psycopg 明确不支持
Windows 默认的 `ProactorEventLoop`：

```
InterfaceError: Psycopg cannot use the 'ProactorEventLoop' to run in async mode.
```

`backend/run_server.py` 覆盖 `uvicorn.Config.get_loop_factory` 强制使用
`SelectorEventLoop`。（注意：只调 `asyncio.set_event_loop_policy()` 无效，
uvicorn 会自行重设；uvicorn 0.54 通过字符串动态解析循环工厂。）

副作用：Selector 循环在 Windows 上不支持 asyncio 子进程，本项目未使用，无影响。

### 3. Memurai 不支持 Redis 模块 → checkpoint 必须用 Postgres

`AsyncRedisSaver` 依赖 RediSearch + RedisJSON（`FT.INFO` 等命令），
Memurai Developer 的 `MODULE LIST` 为空、无法加载这些模块，选 redis 会报：

```
unknown command 'FT.INFO'
```

因此 `.env` 里 `CHECKPOINT_BACKEND=postgres`。代码在
`backend/src/agent/task_queue.py::_make_checkpointer` 里按
`redis → postgres → memory` 自动回退。

### 4. Redis 阻塞读的超时设置

任务队列用 `XREADGROUP ... BLOCK 5000`。redis-py 默认 5 秒 socket 读超时会先于
阻塞结束触发，导致日志刷 `TimeoutError: Timeout reading from localhost:6379`。
`backend/src/agent/redis_client.py` 里建连时设了 `socket_timeout=None`。

另外：**内存降级后端（fakeredis）不实现 BLOCK 语义**，会立即返回空。
`task_queue.py` 在两处（`_process_one_task`、`read_task_events`）对空结果做了
`sleep(0.05)`，否则是忙等，会占满事件循环导致所有 HTTP 请求超时。

### 5. Milvus Lite 的两个约束

- **本地文件模式不能用 `MILVUS_URI` 环境变量**：pymilvus 在 import 期用
  `Connections` 校验该变量，只接受 `http(s)://` 形式，写文件路径会报 `Illegal uri`。
  本地模式改用 `MILVUS_DB_PATH`（代码见 `fact_store.py::_resolve_milvus_uri`）。
- **集合 `released` 状态**：Milvus 重启或进程重连后集合处于 released，
  `search` 会报 `call load() before search`。`FactStore._ensure_collection()` 在集合
  已存在时也会 `load_collection`，重复 load 抛的 "already loaded" 被忽略。

> `milvus.db` 文件大小会一直是 0——Milvus Lite 的数据由内嵌服务管理，
> 不能按文件大小判断是否有数据，请用 `FactStore.stats()` 或 `query()` 验证。

### 6. PostgreSQL 进程被控制台信号误杀

症状：Postgres 无预警消失，日志里是

```
server process (PID xxxx) was terminated by exception 0xC000013A
```

`0xC000013A` 是 Ctrl+C / 控制台进程组中止。原因是 `pg_ctl` 若直接被
`cmd /c` 或 WMI 启动，postgres 子进程会继承调用方的控制台进程组，
该会话里任何 Ctrl+C 或进程组清理都会把它带走。

因此 `start_postgres.bat` 通过 `powershell Start-Process` 启动 `pg_ctl`，
让它拿到独立控制台。重启服务后数据不会丢（崩溃恢复会重放 WAL）。
`start_memurai.bat` 同样改成 `Start-Process`（原先用 `start /b`，
会继承调用方控制台，同样会被会话级进程树清理带走）。

### 7. 启动脚本里的 `timeout` 陷阱

`timeout /t 1 /nobreak` 在 **stdin 被重定向**时会直接报
`ERROR: Input redirection is not supported` 并退出，导致就绪轮询循环失效、
脚本误报"启动失败"（实际服务已经起来了）。两个 `.bat` 已改用
`ping -n 2 127.0.0.1 >nul` 等待。

另外 **Postgres 冷启动可能超过 20 秒**：非正常关闭后要先重放 WAL，
日志里会出现大量 `FATAL: the database system is starting up`（属正常现象），
就绪等待已放宽到 60 秒。

## 并发模型（实测结论）

**提交是异步的，消费是串行的。** 实测：0.01 秒内连续提交 2 个任务，从事件流
ID 的毫秒时间戳看，两个任务的执行区间**完全不重叠**：

```
任务A: |############|                  (0.0s → 12.2s)   344 个事件
任务B:              |#############|    (13.1s → 26.3s)  365 个事件
                    ↑
              B 在 A 结束 0.9 秒后才开始
```

原因是 worker 循环用 `XREADGROUP ... COUNT 1`，一次只取一条、跑完才取下一条。
所以第 2 个用户的任务会在 Redis Stream 里排队，其 SSE 连接长时间收不到事件
（前端表现为"一直在等"），但不会报错。

`await` 只保证 I/O 等待期间事件循环能处理其他 HTTP 请求（登录、列表查询不受影响），
**不等于任务被并行消费**。注意区分：单个任务内部用 `Send` fan-out 出去的
3 路搜索是**真并行**，但那发生在任务内部，不影响"任务之间串行"的结论。

扩容路径：Redis Streams consumer group + **多个 worker 进程、每个唯一 consumer name**。
配套要同步调整 `WEB_SEARCH_MAX_QPS`（否则并行任务会一起打爆外部搜索 API）；
生产环境还应把 worker 从 Web 进程里拆出去，避免与请求处理争抢资源。

## 诊断脚本

`backend/_diag_*.py` 是可选的验证脚本，用于确认各条链路是否正常：

| 脚本 | 验证内容 | 消耗 |
|---|---|---|
| `_diag_worker.py` | 已删除（fakeredis BLOCK 行为，一次性） | - |
| `_diag_milvus_uri.py` | `MILVUS_URI` 与本地文件模式的差异 | 无 |
| `_diag_milvus_lock.py` | Milvus Lite 打开/并发/落盘行为 | 无 |
| `_diag_kb_persist.py` | 知识库写入 + 跨进程持久化 | 少量 Embedding 调用 |
| `_diag_e2e_research.py` | 提交任务 → SSE 事件流（到计划确认暂停） | 1 次 LLM 调用 |
| `_diag_resume.py` | 计划确认 → 研究 → 写作 → 最终答案（完整 HITL） | 约 4 分钟、多次 LLM + Web 搜索 |
| `_diag_concurrency.py` | 两个任务同时提交时的串行/并行行为（读事件流 ID 时间戳） | 2 次 LLM 调用 |

运行方式：`cd backend && .venv\Scripts\python.exe _diag_xxx.py`（需先启动全部服务）。

## 重新安装中间件

如果 `C:\dr-runtime` 被清理，按下面步骤重建（都不需要管理员）：

```powershell
# PostgreSQL 17 便携版
Invoke-WebRequest "https://get.enterprisedb.com/postgresql/postgresql-17.11-5-windows-x64-binaries.zip" -OutFile C:\dr-runtime\pg\pgsql.zip
Expand-Archive C:\dr-runtime\pg\pgsql.zip -DestinationPath C:\dr-runtime\pg

# Memurai（解包 MSI，不注册服务）
Invoke-WebRequest "https://dist.memurai.com/releases/Memurai-Developer/4.1.2/Memurai-Developer-v4.1.2.msi" -OutFile $env:TEMP\memurai.msi
msiexec /a $env:TEMP\memurai.msi /qn TARGETDIR=C:\dr-runtime\memurai\extracted
```

然后依次跑 `runtime\start_postgres.bat`、`runtime\start_memurai.bat`，
再执行一次建库和建表：

```powershell
& C:\dr-runtime\pg\pgsql\bin\createdb.exe -h 127.0.0.1 -p 5432 -U postgres deepresearch
cd backend; .venv\Scripts\python.exe -m agent.db.init_db
```

## 与生产配置的差异

| 项 | 本地 | 生产/默认 |
|---|---|---|
| 数据库 | Postgres 便携版，locale=C，仅监听 127.0.0.1 | 服务器 Postgres |
| Redis | Memurai Developer（10 天后自动停止，需重启） | Redis Stack（含 RediSearch，可用 Redis checkpoint） |
| 知识库 | Milvus Lite 嵌入式（单进程） | Milvus standalone（多实例） |
| checkpoint | PostgreSQL | Redis（需 RediSearch） |
| 认证 | 本地 http | 生产需 HTTPS（Cookie 未设 Secure） |

`Memurai Developer` 每 10 天会自动关停一次，重启 `runtime\start_memurai.bat` 即可；
若需要长期稳定，请改用 Redis Stack（Docker/WSL，见项目根 README 的 Docker 方案）。
