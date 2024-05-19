from sqlalchemy import select, func, update
from sqlalchemy.sql.functions import coalesce

from user.models import Transaction, Expense, User, Group
from utils.entities.UserBalance import UserBalance
from utils.make_payment_graph import make_payment_graph


class SettleUpService:
    def __init__(self, transaction, group_id, transactions, simplify_debts):
        self.transaction = transaction
        self.group_id = group_id
        self.transactions = transactions
        self.simplify_debts = simplify_debts

    def call(self):
        for expense_transaction in self.transactions:
            if self.group_id:
                total_borrowed_query = (
                    select(func.sum(Transaction.amount).label('amount'))
                    .join(Expense)
                    .filter(Transaction.borrower_id == expense_transaction['borrower_id'],
                            Transaction.debtor_id == expense_transaction['debtor_id'], Transaction.settled.is_(False),
                            Expense.group_id == self.group_id)
                    .alias("borrowed_transactions")
                )
                total_lent_query = (
                    select(func.sum(Transaction.amount).label('amount'))
                    .join(Expense)
                    .filter(Transaction.debtor_id == expense_transaction['borrower_id'],
                            Transaction.borrower_id == expense_transaction['debtor_id'], Transaction.settled.is_(False),
                            Expense.group_id == self.group_id)
                    .alias("lent_transactions")
                )
                amount = self.transaction.query(
                    coalesce(total_borrowed_query.c.amount, 0) - coalesce(total_lent_query.c.amount, 0)).first()
                if float(amount[0]) == 0:
                    subq = select(Transaction.id).join(Expense).filter(
                        Transaction.settled.is_(False),
                        ((Transaction.borrower_id == expense_transaction['borrower_id']) & (
                                Transaction.debtor_id == expense_transaction['debtor_id'])) | (
                                (Transaction.debtor_id == expense_transaction['borrower_id']) & (
                                Transaction.borrower_id == expense_transaction['debtor_id'])),
                        Expense.group_id == self.group_id
                    ).alias()
                    stmt = (
                        update(Transaction)
                        .where(Transaction.id.in_(subq))
                        .values(settled=True)
                    )

                    self.transaction.execute(stmt)

                if self.simplify_debts:
                    total_borrowed_query = (
                        self.transaction.query(Transaction.debtor_id, func.sum(Transaction.amount).label("total"))
                        .select_from(Transaction)
                        .join(Expense)
                        .filter(Expense.group_id == self.group_id, Transaction.settled.is_(False))
                        .group_by(Transaction.debtor_id)
                        .subquery()
                    )
                    total_lent_query = (
                        select(Transaction.borrower_id, func.sum(Transaction.amount).label("total"))
                        .select_from(Transaction)
                        .join(Expense)
                        .filter(Expense.group_id == self.group_id, Transaction.settled.is_(False))
                        .group_by(Transaction.borrower_id)
                        .subquery()
                    )

                    users_stmt = (
                        select(
                            User,
                            coalesce(total_borrowed_query.c.total, 0) - coalesce(total_lent_query.c.total, 0)
                        )
                        .join(User.groups)
                        .outerjoin(total_borrowed_query, total_borrowed_query.c.debtor_id == User.id)
                        .outerjoin(total_lent_query, total_lent_query.c.borrower_id == User.id)
                        .group_by(User.id)
                        .filter(Group.id == self.group_id)
                    )

                    users = self.transaction.execute(users_stmt).fetchall()

                    payment_graph = make_payment_graph(
                        [UserBalance(user_id=user[0], final_balance=user[1]) for user in users])

                    if len(payment_graph) == 0:
                        subq = select(Transaction.id).join(Expense).filter(Transaction.settled.is_(False), Expense.group_id == self.group_id).alias()
                        stmt = (
                            update(Transaction)
                            .where(Transaction.id.in_(subq))
                            .values(settled=True)
                        )

                        self.transaction.execute(stmt)

            else:
                total_borrowed_query = (
                    select(func.sum(Transaction.amount).label('amount'))
                    .filter(Transaction.borrower_id == expense_transaction['borrower_id'],
                            Transaction.debtor_id == expense_transaction['debtor_id'], Transaction.settled.is_(False))
                    .alias("borrowed_transactions")
                )
                total_lent_query = (
                    select(func.sum(Transaction.amount).label('amount'))
                    .filter(Transaction.borrower_id == expense_transaction['debtor_id'],
                            Transaction.debtor_id == expense_transaction['borrower_id'], Transaction.settled.is_(False))
                    .alias("lent_transactions")
                )
                amount = self.transaction.query(
                    coalesce(total_borrowed_query.c.amount, 0) - coalesce(total_lent_query.c.amount, 0)).first()
                if float(amount[0]) == 0:
                    self.transaction.query(Transaction).filter(
                        Transaction.settled.is_(False),
                        ((Transaction.borrower_id == expense_transaction['borrower_id']) & (
                                Transaction.debtor_id == expense_transaction['debtor_id'])) | (
                                (Transaction.debtor_id == expense_transaction['borrower_id']) & (
                                Transaction.borrower_id == expense_transaction['debtor_id']))
                    ).update({Transaction.settled: True})
