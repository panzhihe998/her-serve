FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Cloud Run 默认使用端口 8080
ENV PORT=8080

# 这里用 app.main:app，匹配 app/main.py 里的 app = FastAPI(...)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
