#!/bin/sh
set -e

# 1) 优先尝试通过 Alembic 应用官方迁移（非必须，失败不阻断启动）
flask db upgrade 2>/dev/null || true

# 2) 幂等兜底：确保 cases 表具备 detail 列，
#    兼容仅依赖 db.create_all() 的存量数据库（create_all 不会给旧表加列）
python - <<'PY'
import os
import sqlite3

db = os.environ.get("DATABASE", "/app/data/annotation.db")
if not os.path.exists(db):
    print("DB 不存在，将由应用启动时通过 create_all 创建（已含 detail 列）")
else:
    conn = sqlite3.connect(db)
    try:
        cols = [r[1] for r in conn.execute("PRAGMA table_info(cases)").fetchall()]
        if "detail" not in cols:
            conn.execute("ALTER TABLE cases ADD COLUMN detail TEXT")
            conn.commit()
            print("已为存量库添加 detail 列")
        else:
            print("detail 列已存在，无需变更")
    finally:
        conn.close()
PY

# 3) 启动 Web 服务
exec gunicorn --bind 0.0.0.0:5000 --workers 4 --timeout 120 --worker-class gthread --threads 2 run:app
