from celery import shared_task
import telebot

from app.orm import Session
from user.models import User

bot = telebot.TeleBot("7088707160:AAFL1MNhBlxHF-ltlb4BrOWOA6v5uO8PVSA", threaded=False)

@shared_task
def update_users_photos():
    session = Session()
    users = session.query(User).all()
    for user in users:
        try:
            user_photos = bot.get_user_profile_photos(user.id, limit=1)

            if user_photos.photos:
                file_id = user_photos.photos[0][0].file_id
                file_url = bot.get_file_url(file_id)
            else:
                file_url = ''
        except:
            file_url = ''
        user.photo_url = file_url
        session.commit()

    session.close()
    return True
