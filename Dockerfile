FROM python:3.13-slim

WORKDIR /app

# 系统依赖（如需编译某些Python包时保留）
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 依赖层（利用缓存）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 应用代码
COPY app/ app/
COPY migrations/ migrations/
COPY run.py .

# 创建非root用户运行，提升安全性
RUN groupadd -r appgroup && useradd -r -g appgroup appuser

# 数据目录，赋予非root用户读写权限
RUN mkdir -p /app/data && chown -R appuser:appgroup /app/data

ENV FLASK_APP=run.py
ENV BASE_URL=http://localhost:5000
ENV FLASK_DEBUG=0

EXPOSE 5000

# 健康检查
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/healthz')" || exit 1

# 切换到非root用户
USER appuser

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "120", "run:app"]
