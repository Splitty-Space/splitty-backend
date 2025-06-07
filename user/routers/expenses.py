import datetime
from typing import Optional

import fastapi
from fastapi import status
from sqlalchemy import select, func
from sqlalchemy.sql.functions import coalesce

from app import orm
from app.services.build_transaction_info import BuildTransactionInfo
from app.services.feed_service import FeedService
from app.services.settle_up_service import SettleUpService
from user.dtos import (
    FriendShortInfo,
    UserInfo,
    CreateExpense,
    ExpenseInfo, TransactionInfo, EditExpense, GroupShortInfo, ExpenseUserInfo, ExpensesResponse, ExpenseShortInfo,
)
from user.models import User, Expense, Transaction, Group, ExpenseUser, Activity, ActivityType, ActivityUser
from utils.calculate_user_balance import calculate_user_balances
from utils.deep_dict_diff import deep_dict_diff
from utils.make_payment_graph import make_payment_graph
from utils.send_message import send_message

router = fastapi.APIRouter()


@router.post("/expenses")
def add_expense(create_expense: CreateExpense):
    with orm.Session.begin() as transaction:
        user = transaction.query(User).get(create_expense.user_id)

        if not user:
            raise fastapi.HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

        if create_expense.group_id:
            group = (
                transaction.query(Group)
                .join(User.groups)
                .filter(User.id == create_expense.user_id, Group.id == create_expense.group_id)
                .first()
            )

            if not group:
                raise fastapi.HTTPException(status_code=404, detail="Group not found")
        else:
            group = None

        expense = Expense(
            description=create_expense.description, group_id=create_expense.group_id,
            amount=round(create_expense.amount, 2),
            payment=create_expense.payment,
            currency=create_expense.currency,
            date=create_expense.date,
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
            FeedService(
                transaction, "expense_created",
                {"description": create_expense.description,
                 "created_by": {"id": user.id, "name": user.fullname, "photo_url": user.photo_url}
                 },
                user_id
            ).call()
        transactions_dict = [
            {'debtor_id': expense_transaction.debtor_id, 'borrower_id': expense_transaction.borrower_id} for
            expense_transaction in transactions]
        group_simplify_debts = group.simplify_debts if group else None
        transaction.flush()

        new_activity = Activity(
            activity_type=ActivityType.PAYMENT_CREATED.value if expense.payment else ActivityType.EXPENSE_CREATED.value,
            expenses_id=expense.id,
            created_at=expense.created_at,
            performed_by_user_id=user.id,
            data={},
        )
        transaction.add(new_activity)
        transaction.flush()

        activity_users = [
            ActivityUser(user_id=user_id, activity_id=new_activity.id)
            for user_id in create_expense.users
        ]
        transaction.add_all(activity_users)

        expense_id = expense.id

        transaction.commit()

    with orm.Session.begin() as transaction:
        SettleUpService(transaction, create_expense.group_id, transactions_dict, group_simplify_debts).call()

        transaction.commit()

    return get_expense(create_expense.user_id, expense_id)


@router.delete("/expenses/{expense_id}")
def delete_expense(expense_id: int, user_id: int):
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

        user = transaction.query(User).get(user_id)

        if not user:
            raise fastapi.HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

        new_activity = Activity(
            activity_type=ActivityType.PAYMENT_DELETED.value if expense.payment else ActivityType.EXPENSE_DELETED.value,
            expenses_id=expense.id,
            performed_by_user_id=user.id,
            data={},
        )
        transaction.add(new_activity)
        transaction.flush()

        activity_users = [
            ActivityUser(user_id=user.user_id, activity_id=new_activity.id)
            for user in expense.expense_users
        ]
        transaction.add_all(activity_users)

        transaction.commit()

    with orm.Session.begin() as transaction:
        expense.isDeleted = True
        transaction.add(expense)
        transaction.commit()

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

        old_expense = expense.to_dict()

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
        old_transactions_dict = [
            {'debtor_id': expense_transaction.debtor_id, 'borrower_id': expense_transaction.borrower_id} for
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
                # created_at=created_at
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

        new_transactions_dict = [
            {'debtor_id': expense_transaction.debtor_id, 'borrower_id': expense_transaction.borrower_id} for
            expense_transaction in expense.transactions]
        new_group_simplify_debts = expense.group.simplify_debts if expense.group else None

        transaction.commit()

    with orm.Session.begin() as transaction:
        user = transaction.query(User).get(edit_expense.user_id)

        expense = (
            transaction.query(Expense)
            .join(Transaction,
                  (Transaction.expense_id == Expense.id) & ((Transaction.borrower_id == edit_expense.user_id) | (
                          Transaction.debtor_id == edit_expense.user_id))
                  )

            .filter(Expense.id == expense_id)
            .first()
        )

        diff = deep_dict_diff(old_expense, expense.to_dict())

        new_activity = Activity(
            activity_type=ActivityType.PAYMENT_EDITED.value if expense.payment else ActivityType.EXPENSE_EDITED.value,
            expenses_id=expense.id,
            performed_by_user_id=user.id,
            data=diff,
        )
        transaction.add(new_activity)
        transaction.flush()

        activity_users = [
            ActivityUser(user_id=user_id, activity_id=new_activity.id)
            for user_id in edit_expense.users
        ]
        transaction.add_all(activity_users)

        transaction.commit()

    with orm.Session.begin() as transaction:
        if old_group_id == edit_expense.group_id:
            SettleUpService(transaction, old_group_id, new_transactions_dict + old_transactions_dict,
                            old_group_simplify_debts).call()
        else:
            if old_group_id:
                SettleUpService(transaction, old_group_id, old_transactions_dict, old_group_simplify_debts).call()
            SettleUpService(transaction, edit_expense.group_id, new_transactions_dict, new_group_simplify_debts).call()

        transaction.commit()

        print("edit_expense.users = ", edit_expense.users)
        print("edit_expense.user_id = ", edit_expense.user_id)

        for user_id in edit_expense.users:
            if user_id != edit_expense.user_id:
                print("user_id = ", user_id)
                send_message(user_id, "You got new expense. Check it out in app!")

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
                func.sum(coalesce(total_borrowed_expense_query.c.total, 0)),
                func.sum(coalesce(total_lent_expense_query.c.total, 0))
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
            date=expense[0].created_at,
            description=expense[0].description,
            amount=round(expense[0].amount, 2),
            payment=expense[0].payment,
            currency=expense[0].currency,
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


@router.get("/expenses")
def get_expenses(user_id: int, page: int, limit: int, friend_id: Optional[int] = None,
                 group_id: Optional[int] = None) -> ExpensesResponse:
    if friend_id is None and group_id is None:
        raise fastapi.HTTPException(
            status_code=422,
            detail="Either friend_id or group_id must be provided."
        )

    with (orm.Session.begin() as transaction):
        user = transaction.query(User).get(user_id)

        if not user:
            raise fastapi.HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

        if friend_id:
            total_borrowed_expense_query = (
                transaction.query(Transaction.expense_id, func.sum(Transaction.amount).label('total'))
                .select_from(Transaction)
                .filter((Transaction.borrower_id == user_id) & (Transaction.debtor_id == friend_id))
                .group_by(Transaction.expense_id)
                .subquery()
            )
            total_lent_expense_query = (
                transaction.query(Transaction.expense_id, func.sum(Transaction.amount).label('total'))
                .select_from(Transaction)
                .group_by(Transaction.expense_id)
                .filter((Transaction.debtor_id == user_id) & (Transaction.borrower_id == friend_id))
                .subquery()
            )

            expenses_stmt = (
                select(
                    Expense,
                    func.sum(coalesce(total_borrowed_expense_query.c.total, 0)),
                    func.sum(coalesce(total_lent_expense_query.c.total, 0)),
                    ~Expense.transactions.any((Transaction.settled.is_(False)) & (
                            (Transaction.debtor_id == user_id) | (Transaction.borrower_id == user_id)))
                )
                .select_from(Expense)
                .outerjoin(total_borrowed_expense_query, total_borrowed_expense_query.c.expense_id == Expense.id)
                .outerjoin(total_lent_expense_query, total_lent_expense_query.c.expense_id == Expense.id)
                .join(Transaction,
                      (Transaction.expense_id == Expense.id) & (
                              ((Transaction.debtor_id == user_id) & (Transaction.borrower_id == friend_id)) |
                              ((Transaction.debtor_id == friend_id) & (Transaction.borrower_id == user_id))))
                .group_by(Expense.id)
                .order_by(Expense.id.desc())
            )

        if group_id:
            total_borrowed_expense_query = (
                transaction.query(Transaction.expense_id, func.sum(Transaction.amount).label('total'))
                .select_from(Transaction)
                .filter(Transaction.borrower_id == user_id)
                .group_by(Transaction.expense_id)
                .subquery()
            )
            total_lent_expense_query = (
                transaction.query(Transaction.expense_id, func.sum(Transaction.amount).label('total'))
                .select_from(Transaction)
                .group_by(Transaction.expense_id)
                .filter(Transaction.debtor_id == user_id)
                .subquery()
            )

            expenses_stmt = (
                select(
                    Expense,
                    func.sum(coalesce(total_borrowed_expense_query.c.total, 0)),
                    func.sum(coalesce(total_lent_expense_query.c.total, 0)),
                    ~Expense.transactions.any((Transaction.settled.is_(False)) & (
                            (Transaction.debtor_id == user_id) | (Transaction.borrower_id == user_id)))
                )
                .select_from(Expense)
                .outerjoin(total_borrowed_expense_query, total_borrowed_expense_query.c.expense_id == Expense.id)
                .outerjoin(total_lent_expense_query, total_lent_expense_query.c.expense_id == Expense.id)
                .join(Transaction, (Transaction.expense_id == Expense.id))
                .group_by(Expense.id)
                .order_by(Expense.id.desc())
                .filter(Expense.group_id == group_id)
            )

        expenses = transaction.execute(expenses_stmt.offset((page - 1) * limit).limit(limit + 1)).fetchall()
        has_more = len(expenses) == limit + 1
        expenses = expenses[:-1] if has_more else expenses
        expense_infos = []
        unique_years = set()
        for expense in expenses:
            expense_model = expense[0]

            transactions = []

            for trans in expense_model.transactions:
                transactions.append(BuildTransactionInfo(trans).call())

            expense_infos.append(ExpenseShortInfo(
                id=expense_model.id,
                description=expense_model.description,
                payment=expense_model.payment,
                settled=expense[3],
                owes=round(expense[1], 2),
                owe=round(expense[2], 2),
                amount=expense_model.amount,
                currency=expense_model.currency,
                transactions=transactions,
                created_at=expense_model.created_at,
                date=expense_model.date,
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
                    for expense_user in expense_model.expense_users
                ],
            ))
            unique_years.add(expense_model.date.year)

        return ExpensesResponse(
            data=expense_infos,
            meta={'has_more': has_more, 'years': unique_years}
        )
