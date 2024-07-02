`uvicorn app.app:app --reload`

`ngrok http http://127.0.0.1:8000`

`alembic upgrade head`

`celery -A celery_config.celery_app worker --loglevel=info`

`celery -A celery_config.celery_app beat --loglevel=info`
