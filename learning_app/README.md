# Postgres Lab app

This is the full-stack learning app, separate from the ChaiPoint order API in `project/app/`.

From the repository root, install dependencies, build the course pages and frontend bundle, and start the app:

```powershell
python -m pip install -r project/requirements.txt
npm ci
npm run build
python tools/build.py
python -m uvicorn learning_app.main:app --reload
```

Open `http://127.0.0.1:8000/`. The lesson catalog is available at `/api/course` and the health check at `/api/health`. Built lessons are also served under `/course/`.

Account storage, interactive exercises, and AI provider connections are tracked in [`../tasks/todo.md`](../tasks/todo.md).
