FROM python:3.11-slim

WORKDIR /app

# 系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖并安装
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 安装可选扩展
COPY requirements-ext.txt .
RUN pip install --no-cache-dir -r requirements-ext.txt 2>/dev/null || true

# 拷贝项目
COPY . .

# 持久化目录
RUN mkdir -p logs data cache

# 环境
ENV PYTHONUNBUFFERED=1
ENV TZ=Asia/Shanghai
ENV STREAMLIT_SERVER_PORT=8501
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0

EXPOSE 8000 8501

# 默认启动 FastAPI 服务
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
