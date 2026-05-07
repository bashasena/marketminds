# Migrations run on each release. Web uses a single worker so APScheduler does not duplicate jobs.
release: cd backend && alembic upgrade head
web: cd backend && gunicorn -k uvicorn.workers.UvicornWorker app.main:app --bind 0.0.0.0:$PORT --workers 1 --timeout 300
