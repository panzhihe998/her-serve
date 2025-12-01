FROM python:3.10-slim

# 工作目录
WORKDIR /app

# 一些 python 小优化
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 先复制依赖并安装（利用缓存）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 再复制剩下代码
COPY . .

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
