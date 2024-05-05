class UserBalance:
    def __init__(self, user_id, final_balance):
        self.user_id = user_id
        self.final_balance = final_balance

    def __lt__(self, other):
        return self.final_balance > other.final_balance