from select import select

from sqlalchemy import func
from sqlalchemy.sql.functions import coalesce

from user.models import Transaction, Expense


class GroupTotalCalculator:
    def __init__(self, transaction, user_id, group_id):
        self.transaction = transaction
        self.user_id = user_id
        self.group_id = group_id

    def call(self):
        total_borrowed_query = (
            self.transaction.query(Expense.currency, Transaction.debtor_id, func.sum(Transaction.amount).label("total"))
            .select_from(Transaction)
            .join(Expense)
            .filter(Transaction.borrower_id == self.user_id, Expense.group_id == self.group_id, Transaction.settled.is_(False))
            .group_by(Transaction.debtor_id, Expense.currency)
            .subquery()
        )
        total_lent_query = (
            self.transaction.query(Expense.currency, Transaction.borrower_id, func.sum(Transaction.amount).label("total"))
            .select_from(Transaction)
            .join(Expense)
            .filter(Transaction.debtor_id == self.user_id, Expense.group_id == self.group_id, Transaction.settled.is_(False))
            .group_by(Transaction.borrower_id, Expense.currency)
            .subquery()
        )

        total = (
            self.transaction.query(Expense.currency, coalesce(total_borrowed_query.c.total, 0) - coalesce(total_lent_query.c.total, 0))
            .select_from(Transaction)
            .join(Expense)
            .outerjoin(total_borrowed_query, total_borrowed_query.c.currency == Expense.currency)
            .outerjoin(total_lent_query, total_lent_query.c.currency == Expense.currency)
            .group_by(Expense.currency).all()
        )

        return total
