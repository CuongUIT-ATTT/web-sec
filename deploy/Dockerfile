FROM node:22-alpine AS frontend
WORKDIR /app/frontend
COPY frontend/package.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY backend/ ./backend/
RUN pip install --no-cache-dir .
COPY --from=frontend /app/frontend/dist ./frontend_dist
ENV PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["uvicorn", "backend.app.server:app", "--host", "0.0.0.0", "--port", "8000"]
