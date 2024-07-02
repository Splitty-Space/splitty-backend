from celery import Celery
from celery.schedules import crontab

celery_app = Celery(
    "worker",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/0",
    include=["tasks"]
)

celery_app.conf.beat_schedule = {
    'add-every-minute': {
        'task': 'tasks.update_users_photos',
        'schedule': crontab(hour='*')
    },
}
celery_app.conf.timezone = 'UTC'

if __name__ == "__main__":
    celery_app.start()