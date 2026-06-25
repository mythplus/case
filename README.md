# Case 标注平台

本平台通过 Case 的 **录入 → 标注 → 统计 → 导出** 流程，实现 Agent 输出的质量度量与持续优化。

### 整体流程

```
┌─────────────────────────────────────────────────────────────┐
│                    第一阶段：数据录入                          │
│  Agent 完成分析 → POST /api/cases → 数据写入数据库           │
│                              │                              │
│                              ▼                              │
│                    原始 Case 数据集（未标注）                 │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼ 企微通知
┌─────────────────────────────────────────────────────────────┐
│                    第二阶段：人工标注                          │
│  标注人员收到通知 → 点击链接 → 7维度评价                     │
│                              │                              │
│                              ▼                              │
│                    已标注 Case 数据集                         │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    第三阶段：数据集维护                        │
│  • 统计看板：平均分趋势、分类分布、低分 Case 列表            │
│  • 数据导出：CSV / JSON                                     │
│  • 数据驱动：Prompt 调优 / Skill 优化 / 质量追踪            │
└─────────────────────────────────────────────────────────────┘
```

---

## 二、功能特性

### 2.1 核心功能

| 功能模块 | 说明 |
|---------|------|
| **Case 录入** | Agent 通过 API 自动提交分析结果，录入后自动推送企微通知 |
| **人工标注** | 7 维度评价：根因、准确度、可操作性、可读性、整体分、优化方向、备注 |
| **统计看板** | 标注完成率、各维度平均分、分类分布、低分 Case 列表 |
| **数据导出** | 支持 CSV / JSON 格式，可按条件筛选或按 ID 批量导出 |
| **操作审计** | 所有标注、删除等操作均记录审计日志 |
| **企微通知** | 新 Case 录入后自动推送 Markdown 格式通知 |
| **Webhook 管理** | 支持多 Webhook 配置、启用/禁用、连通性测试 |

---

## 三、技术栈

| 类别 | 技术 |
|------|------|
| 后端框架 | Flask 3.1 + Python 3.13 |
| ORM | Flask-SQLAlchemy 3.1 |
| 数据库 | SQLite（WAL 模式，避免并发锁） |
| 数据库迁移 | Flask-Migrate (Alembic) |
| 跨域 | Flask-CORS |
| 限流 | Flask-Limiter（60 req/min） |
| 前端 | 原生 HTML / CSS / JavaScript |
| WSGI 服务器 | Gunicorn |
| 容器化 | Docker + Docker Compose |

---
## 四、项目结构

```
case/
├── app/                            # 应用主目录
│   ├── __init__.py                 # Flask 应用工厂、扩展初始化、路由注册
│   ├── models.py                   # 数据模型 (Case, Annotation, WebhookConfig, AuditLog)
│   ├── routes/                     # API 路由
│   │   ├── __init__.py
│   │   ├── cases.py                # Case CRUD + 列表查询 + 详情
│   │   ├── annotations.py          # 标注 CRUD + 查询筛选 + 乐观锁
│   │   ├── export_stats.py         # 数据导出(CSV/JSON) + 统计接口
│   │   ├── webhooks.py             # 企微 Webhook 管理 + 测试
│   │   ├── audit_logs.py           # 审计日志查询
│   │   └── pages.py                # 页面路由 + 健康检查
│   ├── utils/                      # 工具模块
│   │   ├── __init__.py
│   │   ├── wecom.py                # 企微 Markdown 消息推送（异步线程）
│   │   └── audit.py                # 操作日志记录
│   ├── templates/                  # Jinja2 页面模板
│   │   ├── base.html               # 基础布局（导航栏、深色模式）
│   │   ├── cases.html              # Case 列表页（筛选、分页、多选）
│   │   ├── annotate.html           # 标注页（Case 信息 + 7维度表单）
│   │   ├── dashboard.html          # 统计看板 + Webhook 管理弹窗
│   │   └── audit_logs.html         # 审计日志页（预留）
│   └── static/                     # 静态资源
│       ├── css/
│       │   └── style.css           # 样式文件（约2054行，含深色模式）
│       └── js/
├── data/                           # SQLite 数据库文件（运行时生成）
│   ├── annotation.db
│   ├── annotation.db-shm
│   └── annotation.db-wal
├── migrations/                     # Alembic 数据库迁移
│   ├── alembic.ini
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       └── 8b730e8d5d54_add_use_sliding_window_to_case.py
├── Dockerfile                      # Docker 镜像构建
├── docker-compose.yml              # Docker Compose 编排
├── requirements.txt                # Python 依赖
├── run.py                          # 应用入口
├── README.md                       # 原始 README
└── 标注平台—需求规划文档.md          # 需求规划文档
```

---

## 五、数据模型

### 5.1 Case（原始录入）

| 字段 | 类型 | 说明 |
|------|------|------|
| `case_id` | STRING (PK) | UUID 格式唯一标识 |
| `run_time_ms` | INTEGER | 运行时间(ms) |
| `tokens_consumed` | INTEGER | Tokens 消耗 |
| `source` | TEXT | 来源链接 |
| `description` | TEXT | Case 描述 |
| `category` | STRING | 分类 |
| `use_sliding_window` | BOOLEAN | 是否使用滑动窗口 |
| `agent_input` | TEXT | Agent 输入 (query) |
| `agent_output` | TEXT | Agent 输出 (answer) |
| `status` | STRING | `pending` / `annotated` |
| `created_at` | DATETIME | 创建时间 |
| `updated_at` | DATETIME | 更新时间 |

### 5.2 Annotation（标注）

| 字段 | 类型 | 说明 |
|------|------|------|
| `annotation_id` | STRING (PK) | UUID 格式唯一标识 |
| `case_id` | STRING (FK) | 关联 Case |
| `root_cause` | TEXT | 问题根因 |
| `accuracy_score` | INTEGER | 准确度: 0=不合格 / 1=合格 / 2=优秀 |
| `operability_score` | INTEGER | 可操作性: 0/1/2 |
| `readability_score` | INTEGER | 可读性: 0/1/2 |
| `overall_score` | FLOAT | 整体分数（三项平均，自动计算） |
| `remark` | TEXT | 备注 |
| `optimization_direction` | TEXT | 优化方向 |
| `created_at` | DATETIME | 标注时间 |

---

## 六、部署

### 6.1 Docker Compose（推荐）

```bash
# 构建并启动
docker-compose up -d --build

# 查看日志
docker-compose logs -f

# 停止
docker-compose down
```

### 6.2 手动启动

```bash
# 安装依赖
pip install -r requirements.txt

# 初始化数据库
python -c "from app import create_app; app = create_app(); print('OK')"

# 开发模式
FLASK_DEBUG=1 BASE_URL=http://localhost:5000 python run.py

# 生产模式
BASE_URL=http://your-domain:5000 gunicorn --bind 0.0.0.0:5000 --workers 2 --timeout 120 run:app
```

---

## 七、环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `BASE_URL` | `http://localhost:5000` | 部署域名，用于生成标注链接和企微通知 |
| `FLASK_DEBUG` | `0` | 调试模式（生产环境务必为 0） |

---

## 八、数据库迁移

项目使用 Flask-Migrate (Alembic) 管理 Schema 变更：

```bash
# 生成迁移脚本
flask db migrate -m "描述变更内容"

# 执行迁移
flask db upgrade
```

已有的迁移：
- `8b730e8d5d54_add_use_sliding_window_to_case.py` — 为 Case 表添加 `use_sliding_window` 字段
