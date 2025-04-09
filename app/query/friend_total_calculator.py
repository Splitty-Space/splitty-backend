from select import select

from sqlalchemy import func
from sqlalchemy.sql.functions import coalesce

from user.models import Transaction, Expense


class FriendTotalCalculator:
    def __init__(self, transaction, user_id, friend_id):
        self.transaction = transaction
        self.user_id = user_id
        self.friend_id = friend_id

    def call(self):
        total_borrowed_query = (
            self.transaction.query(Expense.currency, Transaction.debtor_id, func.sum(Transaction.amount).label("total"))
            .select_from(Transaction)
            .join(Expense)
            .filter(Transaction.borrower_id == self.user_id, Transaction.debtor_id == self.friend_id,
                    Transaction.settled.is_(False))
            .group_by(Transaction.debtor_id, Expense.currency)
            .subquery()
        )
        total_lent_query = (
            self.transaction.query(Expense.currency, Transaction.borrower_id,
                                   func.sum(Transaction.amount).label("total"))
            .select_from(Transaction)
            .join(Expense)
            .filter(Transaction.debtor_id == self.user_id, Transaction.borrower_id == self.friend_id,
                    Transaction.settled.is_(False))
            .group_by(Transaction.borrower_id, Expense.currency)
            .subquery()
        )

        expense_currencies = (
            self.transaction.query(Expense.currency)
            .select_from(Transaction)
            .join(Expense)
            .filter(
                Transaction.settled.is_(False),
                ((Transaction.borrower_id == self.user_id) & (
                        Transaction.debtor_id == self.friend_id)) | (
                        (Transaction.debtor_id == self.user_id) & (
                        Transaction.borrower_id == self.friend_id))
            )
            .group_by(Expense.currency).subquery()
        )

        total = (
            self.transaction.query(expense_currencies.c.currency,
                                   coalesce(total_borrowed_query.c.total, 0) - coalesce(total_lent_query.c.total,
                                                                                        0).label("net"))
            .select_from(expense_currencies)
            .outerjoin(total_borrowed_query, total_borrowed_query.c.currency == expense_currencies.c.currency)
            .outerjoin(total_lent_query, total_lent_query.c.currency == expense_currencies.c.currency)
            .all()
        )

        return total
