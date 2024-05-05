from user.models import Feed


class FeedService:
    def __init__(self, transaction, type, message, user_id):
        self.transaction = transaction
        self.type = type
        self.message = message
        self.user_id = user_id

    def call(self):
        self.transaction.add(Feed(user_id=self.user_id, type=self.type, message=self.message))
