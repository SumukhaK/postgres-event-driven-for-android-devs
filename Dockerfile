FROM node:22-alpine AS playground-build
WORKDIR /app
COPY package.json package-lock.json vite.config.js ./
COPY learning_app/static ./learning_app/static
COPY site/assets ./site/assets
RUN npm ci && npm run build

FROM python:3.12-slim AS course-build
WORKDIR /app
RUN pip install --no-cache-dir markdown
COPY src ./src
COPY tools/build.py ./tools/build.py
COPY site/assets ./site/assets
RUN python tools/build.py

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 LEARNING_DB_PATH=/data/learning.sqlite3
WORKDIR /app
COPY project/requirements.txt ./project/requirements.txt
RUN pip install --no-cache-dir -r project/requirements.txt \
    && useradd --system --uid 10001 app \
    && mkdir /data \
    && chown app:app /data
COPY --chown=app:app learning_app ./learning_app
COPY --chown=app:app --from=course-build /app/src ./src
COPY --chown=app:app --from=course-build /app/site ./site
COPY --chown=app:app --from=playground-build /app/learning_app/dist ./learning_app/dist
VOLUME ["/data"]
USER app
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "learning_app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
