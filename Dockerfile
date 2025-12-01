# 使用官方 Python 运行时作为基础镜像
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 预先复制依赖文件并安装依赖
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# 复制项目全部代码
COPY . .

# 让 Cloud Run 知道容器会监听哪个端口（一般写 8080）
ENV PORT=8080

# 启动 FastAPI 应用
# 关键：这里一定要用 8080，跟上面的 PORT 环境保持一致
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
