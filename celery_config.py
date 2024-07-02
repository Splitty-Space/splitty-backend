from celery import Celery
from celery.schedules import crontab

celery_app = Celery(
    "worker",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/0",
    include=["tasks"]
)

celery_app.conf.beat_schedule = {
    'run-every-hour': {
        'task': 'tasks.update_users_photos',
        'schedule': crontab(minute=0),
    },
}
celery_app.conf.timezone = 'UTC'

if __name__ == "__main__":
    celery_app.start()