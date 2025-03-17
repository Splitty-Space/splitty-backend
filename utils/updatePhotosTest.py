def download_image(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.content
    except requests.RequestException as e:
        print(f"Ошибка при загрузке {url}: {e}")
        return None


users = transaction.query(User).all()
for user in users:
    if not user.photo and user.photo_url:
        image_data = download_image(user.photo_url)
        if image_data:
            user.photo = image_data
            print(f"Фото для пользователя {user.id} обновлено.")
        else:
            print(f"Не удалось загрузить фото для пользователя {user.id}.")
transaction.commit()
