from select import select

from sqlalchemy import func
from sqlalchemy.sql.functions import coalesce

from user.dtos import DebtInfo
from user.models import Transaction, Expense


class TotalCalculator:
    def __init__(self, transaction, user_id, group_id=None):
        self.transaction = transaction
        self.user_id = user_id
        self.group_id = group_id

    def call(self):
        if self.group_id:
            total_borrowed_query = (
                self.transaction.query(Expense.currency,
                                       func.sum(Transaction.amount).label("total"))
                .select_from(Transaction)
                .join(Expense)
                .filter(Transaction.borrower_id == self.user_id, Transaction.settled.is_(False), Expense.group_id == self.group_id)
                .group_by(Expense.currency)
                .subquery()
            )
            total_lent_query = (
                self.transaction.query(Expense.currency,
                                       func.sum(Transaction.amount).label("total"))
                .select_from(Transaction)
                .join(Expense)
                .filter(Transaction.debtor_id == self.user_id, Transaction.settled.is_(False), Expense.group_id == self.group_id)
                .group_by(Expense.currency)
                .subquery()
            )
        else:
            total_borrowed_query = (
                self.transaction.query(Expense.currency, func.sum(Transaction.amount).label("total"))
                .select_from(Transaction)
                .join(Expense)
                .filter(Transaction.borrower_id == self.user_id, Transaction.settled.is_(False))
                .group_by(Expense.currency)
                .subquery()
            )
            total_lent_query = (
                self.transaction.query(Expense.currency, func.sum(Transaction.amount).label("total"))
                .select_from(Transaction)
                .join(Expense)
                .filter(Transaction.debtor_id == self.user_id, Transaction.settled.is_(False))
                .group_by(Expense.currency)
                .subquery()
            )

        currencies_query = (
            self.transaction.query(total_borrowed_query.c.currency.label("currency"))
            .union(self.transaction.query(total_lent_query.c.currency.label("currency")))
            .subquery()
        )

        total = (
            self.transaction.query(
                currencies_query.c.currency,
                (coalesce(total_borrowed_query.c.total, 0) - coalesce(total_lent_query.c.total, 0)).label('balance')
            )
            .outerjoin(total_borrowed_query, total_borrowed_query.c.currency == currencies_query.c.currency)
            .outerjoin(total_lent_query, total_lent_query.c.currency == currencies_query.c.currency)
            .all()
        )

        result = {'owe': [], 'owes': []}

        for debt in total:
            if debt.balance > 0:
                result['owes'].append(DebtInfo(currency=debt.currency, amount=round(debt.balance, 2)))
            elif debt.balance < 0:
                result['owe'].append(DebtInfo(currency=debt.currency, amount=round(abs(debt.balance), 2)))

        return result
