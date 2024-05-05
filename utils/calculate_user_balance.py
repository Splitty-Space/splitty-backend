from utils.entities.UserBalance import UserBalance


def calculate_user_balances(users, payers_hash, debtors_hash):
    return [
        UserBalance(user_id=user, final_balance=round(debtors_hash[user] - payers_hash[user], 2)) for user in users
    ]