import datetime
from pprint import pprint

import fastapi
from fastapi import status
from sqlalchemy import select, func, or_, update
from sqlalchemy.sql.functions import coalesce

from app import orm
from app.services.feed_service import FeedService
from app.services.settle_up_service import SettleUpService
from user.dtos import (
    FriendShortInfo,
    UserInfo,
    CreateExpense,
    ExpenseInfo, TransactionInfo, EditExpense, GroupShortInfo, ExpenseUserInfo,
)
from user.models import User, Expense, Transaction, Group, ExpenseUser
from utils.calculate_user_balance import calculate_user_balances
from utils.make_payment_graph import make_payment_graph

router = fastapi.APIRouter()


@router.post("/expenses")
def add_expense(create_expense: CreateExpense):
    with orm.Session.begin() as transaction:
        user = transaction.query(User).get(create_expense.user_id)

        if not user:
            raise fastapi.HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

        expense = Expense(
            description=create_expense.description, group_id=create_expense.group_id,
            amount=round(create_expense.amount, 2),
            payment=create_expense.payment
        )
        transaction.add(expense)
        payers_hash = {}
        debtors_hash = {}
        for payer in create_expense.payers:
            payers_hash[payer.user_id] = payer.amount
        for debtor in create_expense.debtors:
            debtors_hash[debtor.user_id] = debtor.amount

        created_at = datetime.datetime.utcnow()

        payment_graph = make_payment_graph(
            calculate_user_balances(create_expense.users, payers_hash, debtors_hash))
        transactions = [
            Transaction(
                amount=round(abs(transaction.amount), 2),
                debtor_id=transaction.to_user,
                borrower_id=transaction.from_user,
                expense=expense,
                currency="USD",
                created_at=created_at
            ) for transaction in payment_graph
        ]
        transaction.add_all(transactions)

        expense_users = [
            ExpenseUser(
                lent_amount=payers_hash[user_id],
                debt_amount=debtors_hash[user_id],
                user_id=user_id,
                expense=expense,
            ) for user_id in create_expense.users
        ]
        transaction.add_all(expense_users)

        for user_id in create_expense.users:
            payment_node = next(
                (node for node in payment_graph if node.from_user == user_id or node.to_user == user_id), None)
            if payment_node:
                if payment_node.from_user == user_id:
                    transaction_type = "get_back"
                else:
                    transaction_type = "receive"
                amount = round(float(payment_node.amount), 2)
            else:
                transaction_type = "nullify"
                amount = 0
            FeedService(
                transaction, "expense_created",
                {"description": create_expense.description, "created_by": {"id": user.id, "name": user.fullname},
                 "amount": amount, "transaction_type": transaction_type},
                user_id
            ).call()
        transactions_dict = [{'debtor_id': expense_transaction.debtor_id, 'borrower_id': expense_transaction.borrower_id} for
                         expense_transaction in transactions]
        group_simplify_debts = expense.group.simplify_debts if expense.group else None

        transaction.commit()

    with orm.Session.begin() as transaction:
        SettleUpService(transaction, create_expense.group_id, transactions_dict, group_simplify_debts).call()

        transaction.commit()
    return True


@router.delete("/expenses/{expense_id}")
def delete_expense(expense_id: int):
    with orm.Session.begin() as transaction:
        expense = (
            transaction.query(Expense)
            .filter(Expense.id == expense_id)
            .first()
        )

        if not expense:
            raise fastapi.HTTPException(status_code=404, detail="Expense not found")

        for expense_transaction in expense.transactions:
            if expense_transaction.settled:
                transaction.query(Transaction).filter(Transaction.id == expense_transaction.id).update(
                    {
                        Transaction.settled: False,
                        Transaction.expense_id: None,
                        Transaction.debtor_id: Transaction.borrower_id,
                        Transaction.borrower_id: Transaction.debtor_id
                    }
                )
            else:
                transaction.delete(expense_transaction)
        transaction.commit()

    with orm.Session.begin() as transaction:
        transaction.delete(expense)

    return True


@router.put("/expenses/{expense_id}")
def edit_expense(expense_id: int, edit_expense: EditExpense):
    with orm.Session.begin() as transaction:
        expense = (
            transaction.query(Expense)
            .join(Transaction,
                  (Transaction.expense_id == Expense.id) & ((Transaction.borrower_id == edit_expense.user_id) | (
                          Transaction.debtor_id == edit_expense.user_id))
                  )

            .filter(Expense.id == expense_id)
            .first()
        )

        if not expense:
            raise fastapi.HTTPException(status_code=404, detail="Expense not found")

        group = (
            transaction.query(Group)
            .join(User.groups)
            .filter(User.id == edit_expense.user_id, Group.id == edit_expense.group_id)
            .first()
        )

        if edit_expense.group_id and not group:
            raise fastapi.HTTPException(status_code=404, detail="Group not found")

        old_group_id = expense.group_id
        old_group_simplify_debts = expense.group.simplify_debts if expense.group else None
        old_transactions_dict = [{'debtor_id': expense_transaction.debtor_id, 'borrower_id': expense_transaction.borrower_id} for
                         expense_transaction in expense.transactions]

        expense.description = edit_expense.description
        expense.amount = edit_expense.amount
        expense.group = group

        # created_at = expense.transactions[0].created_at
        # transaction.query(Transaction). \
        #     filter(
        #     Transaction.created_at >= created_at,
        #     Transaction.settled.is_(True),
        #     or_(
        #         Transaction.borrower_id.in_(edit_expense.users),
        #         Transaction.debtor_id.in_(edit_expense.users)
        #     )
        # ). \
        #     update({Transaction.settled: False})

        for expense_transaction in expense.transactions:
            if expense_transaction.settled:
                transaction.query(Transaction).filter(Transaction.id == expense_transaction.id).update(
                    {
                        Transaction.settled: False,
                        Transaction.expense_id: None,
                        Transaction.debtor_id: Transaction.borrower_id,
                        Transaction.borrower_id: Transaction.debtor_id
                    }
                )
            else:
                transaction.delete(expense_transaction)

        transaction.query(ExpenseUser).filter(ExpenseUser.expense_id == expense.id).delete()

        payers_hash = {}
        debtors_hash = {}
        for payer in edit_expense.payers:
            payers_hash[payer.user_id] = payer.amount
        for debtor in edit_expense.debtors:
            debtors_hash[debtor.user_id] = debtor.amount
        payment_graph = make_payment_graph(calculate_user_balances(edit_expense.users, payers_hash, debtors_hash))
        transactions = [
            Transaction(
                amount=round(abs(transaction.amount), 2),
                debtor_id=transaction.to_user,
                borrower_id=transaction.from_user,
                expense=expense,
                currency="USD",
                #created_at=created_at
                created_at=datetime.datetime.utcnow()
            ) for transaction in payment_graph
        ]
        transaction.add_all(transactions)

        expense_users = [
            ExpenseUser(
                lent_amount=payers_hash[user_id],
                debt_amount=debtors_hash[user_id],
                user_id=user_id,
                expense=expense,
            ) for user_id in edit_expense.users
        ]

        transaction.add_all(expense_users)

        new_transactions_dict = [{'debtor_id': expense_transaction.debtor_id, 'borrower_id': expense_transaction.borrower_id} for
                         expense_transaction in expense.transactions]
        new_group_simplify_debts = expense.group.simplify_debts if expense.group else None

        transaction.commit()


    with orm.Session.begin() as transaction:
        if old_group_id == edit_expense.group_id:
            SettleUpService(transaction, old_group_id, new_transactions_dict + old_transactions_dict, old_group_simplify_debts).call()
        else:
            if old_group_id:
                SettleUpService(transaction, old_group_id, old_transactions_dict, old_group_simplify_debts).call()
            SettleUpService(transaction, edit_expense.group_id, new_transactions_dict, new_group_simplify_debts).call()

        transaction.commit()
    return True


@router.get("/expenses/{expense_id}")
def get_expense(user_id: int, expense_id: int) -> ExpenseInfo:
    with (orm.Session.begin() as transaction):
        total_borrowed_expense_query = (
            transaction.query(Transaction.expense_id, func.sum(Transaction.amount).label('total'))
            .select_from(Transaction)
            .filter(Transaction.borrower_id == user_id, Transaction.settled.is_(False))
            .group_by(Transaction.expense_id)
            .subquery()
        )
        total_lent_expense_query = (
            transaction.query(Transaction.expense_id, func.sum(Transaction.amount).label('total'))
            .select_from(Transaction)
            .group_by(Transaction.expense_id)
            .filter(Transaction.debtor_id == user_id, Transaction.settled.is_(False))
            .subquery()
        )
        expense_stmt = (
            select(
                Expense,
                coalesce(total_borrowed_expense_query.c.total, 0),
                coalesce(total_lent_expense_query.c.total, 0)
            )
            .select_from(Expense)
            .outerjoin(total_borrowed_expense_query, total_borrowed_expense_query.c.expense_id == Expense.id)
            .outerjoin(total_lent_expense_query, total_lent_expense_query.c.expense_id == Expense.id)
            .join(Transaction,
                  (Transaction.expense_id == Expense.id) & (
                          (Transaction.borrower_id == user_id) | (Transaction.debtor_id == user_id))
                  )
            .join(User, (User.id == Transaction.debtor_id) | (User.id == Transaction.borrower_id))
            .filter(Expense.id == expense_id)
            .group_by(Expense.id)
        )

        expense = transaction.execute(expense_stmt).fetchone()

        if not expense:
            raise fastapi.HTTPException(status_code=404, detail="Expense not found")

        group = expense[0].group

        expense_info = ExpenseInfo(
            id=expense[0].id,
            description=expense[0].description,
            amount=round(expense[0].amount, 2),
            payment=expense[0].payment,
            expense_users=[
                ExpenseUserInfo(
                    id=expense_user.id,
                    user=UserInfo(
                        id=expense_user.user.id,
                        username=expense_user.user.username,
                        name=expense_user.user.fullname,
                        photo_url=expense_user.user.photo_url
                    ),
                    lent_amount=expense_user.lent_amount,
                    debt_amount=expense_user.debt_amount,
                )
                for expense_user in expense[0].expense_users
            ],
            transactions=[
                TransactionInfo(
                    id=transaction.id,
                    debtor=UserInfo(id=transaction.debtor.id, username=transaction.debtor.username,
                                    name=transaction.debtor.fullname, photo_url=transaction.debtor.photo_url),
                    borrower=UserInfo(id=transaction.borrower.id, username=transaction.borrower.username,
                                      name=transaction.borrower.fullname, photo_url=transaction.borrower.photo_url),
                    amount=round(transaction.amount, 2),
                )
                for transaction in expense[0].transactions
            ],
            owes=round(expense[1], 2),
            owe=round(expense[2], 2),
            group=GroupShortInfo(
                id=group.id,
                name=group.name,
                users=[FriendShortInfo(
                    id=member.id,
                    username=member.username,
                    name=member.fullname,
                    photo_url=member.photo_url,
                    amount=None
                )
                    for member in group.users]
            ) if group else None
        )
        return expense_info
