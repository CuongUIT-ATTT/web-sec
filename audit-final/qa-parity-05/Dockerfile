FROM node:22-alpine AS frontend
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build
RUN find src -type f -exec sha256sum {} + > /app/frontend-source.sha256
FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY backend/ ./backend/
RUN pip install --no-cache-dir .
COPY --from=frontend /app/frontend/dist ./frontend_dist
COPY --from=frontend /app/frontend-source.sha256 ./frontend-source.sha256
COPY audit-final/qa-parity-05/qa_app.py ./qa_app.py
USER 65534:65534
CMD ["uvicorn", "qa_app:application", "--factory", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
