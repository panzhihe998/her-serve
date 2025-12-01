FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Cloud Run 默认使用端口 8080
ENV PORT=8080

# 一定要用 0.0.0.0 + 8080，否则 Cloud Run 连接不上
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
