import fastapi
from fastapi import status
from sqlalchemy import select, func, case, asc, text
from sqlalchemy.orm import aliased
from sqlalchemy.sql.functions import coalesce

from app import orm
from app.query.group_total_calculator import GroupTotalCalculator
from app.query.total_calculator import TotalCalculator
from app.services.build_transaction_info import BuildTransactionInfo
from user.dtos import (
    FriendShortInfo,
    UserInfo,
    ExpenseShortInfo,
    TransactionInfo, GroupShortInfo, AddGroup, GroupInfo, EditGroup, GroupUserInfo, DebtInfo, GroupResponse, )
from user.models import User, Expense, Transaction, Group, user_group_table
from utils.entities.UserBalance import UserBalance
from utils.make_payment_graph import make_payment_graph

router = fastapi.APIRouter()


@router.get("/groups")
def groups(user_id: int) -> GroupResponse:
    with orm.Session.begin() as transaction:
        user = transaction.query(User).get(user_id)

        if not user:
            raise fastapi.HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

        total_borrowed_query = (
            transaction.query(Expense.group_id, func.sum(Transaction.amount).label("total"))
            .join(Expense, Expense.id == Transaction.expense_id)
            .filter(Transaction.borrower_id == user_id, Transaction.settled.is_(False))
            .group_by(Expense.group_id)
            .subquery()
        )

        total_lent_query = (
            transaction.query(Expense.group_id, func.sum(Transaction.amount).label("total"))
            .join(Expense, Expense.id == Transaction.expense_id)
            .filter(Transaction.debtor_id == user_id, Transaction.settled.is_(False))
            .group_by(Expense.group_id)
            .subquery()
        )

        # Create the CTE (Common Table Expression) for the amounts
        amount_cte = (
            select(
                Group.id.label('group_id'),
                (func.coalesce(total_borrowed_query.c.total, 0) - func.coalesce(total_lent_query.c.total, 0)).label(
                    "amount")
            )
            .select_from(Group)
            .outerjoin(total_borrowed_query, total_borrowed_query.c.group_id == Group.id)
            .outerjoin(total_lent_query, total_lent_query.c.group_id == Group.id)
            .cte("amount_cte")
        )

        # Create the main statement with priority case and joins
        stmt = (
            select(
                Group,
                amount_cte.c.amount,
                case(
                    (amount_cte.c.amount < 0, 1),
                    (amount_cte.c.amount > 0, 2),
                    else_=3
                ).label("priority")
            )
            .select_from(Group)
            .join(amount_cte, amount_cte.c.group_id == Group.id)
            .join(user_group_table, user_group_table.c.group_id == Group.id)
            .join(User, User.id == user_group_table.c.user_id)
            .filter(User.id == user_id)
            .order_by(asc("priority"), asc(amount_cte.c.amount))
        )

        groups = transaction.execute(stmt).fetchall()

        return GroupResponse(data=[
            GroupShortInfo(
                id=group[0].id,
                name=group[0].name,
                kind=group[0].kind,
                owes=round(group[1], 2),
                owe=round(group[2], 2),
                total=[
                    DebtInfo(
                        currency=debt[0],
                        amount=debt[1]
                    )
                    for debt in GroupTotalCalculator(transaction, user_id, group[0].id).call() if debt[1] != 0
                ],
                users=[GroupUserInfo(
                    id=member.id,
                    username=member.username,
                    name=member.fullname,
                )
                    for member in group[0].users]
            )
            for group in groups
        ],
            meta={
                'total': TotalCalculator(transaction, user_id).call(),
                'default_currency': user.default_currency
            }
        )


@router.post("/groups")
def create_group(add_group: AddGroup):
    with orm.Session.begin() as transaction:
        user = transaction.query(User).filter_by(id=add_group.user_id).first()

        if not user:
            raise fastapi.HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

        group = Group(name=add_group.name, kind=add_group.kind)
        user.groups.append(group)

        return True


@router.get("/groups/{group_id}")
def get_group(user_id: int, group_id: int) -> GroupInfo:
    with (orm.Session.begin() as transaction):
        group = (
            transaction.query(Group)
            .join(User.groups)
            .filter(User.id == user_id, Group.id == group_id)
            .first()
        )

        if not group:
            raise fastapi.HTTPException(status_code=404, detail="Group not found")

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
                coalesce(total_borrowed_expense_query.c.total, 0),
                coalesce(total_lent_expense_query.c.total, 0),
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
        expenses = transaction.execute(expenses_stmt).fetchall()

        stmt = (
            select(
                User,
            )
            .join(
                user_group_table,
                (user_group_table.c.user_id == User.id) & (user_group_table.c.group_id == group_id),
            )
            .group_by(User.id)
        )

        members = transaction.execute(stmt).fetchall()

        if group.simplify_debts:
            total_borrowed_query = (
                transaction.query(Transaction.debtor_id, func.sum(Transaction.amount).label("total"))
                .select_from(Transaction)
                .join(Expense)
                .filter(Expense.group_id == group_id, Transaction.settled.is_(False))
                .group_by(Transaction.debtor_id)
                .subquery()
            )
            total_lent_query = (
                select(Transaction.borrower_id, func.sum(Transaction.amount).label("total"))
                .select_from(Transaction)
                .join(Expense)
                .filter(Expense.group_id == group_id, Transaction.settled.is_(False))
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
                .filter(Group.id == group_id)
            )

            users = transaction.execute(users_stmt).fetchall()

            payment_graph = make_payment_graph([UserBalance(user_id=user[0], final_balance=user[1]) for user in users])

            total = [
                TransactionInfo(
                    id=0,
                    borrower=UserInfo(id=transaction.to_user.id, username=transaction.to_user.username,
                                      name=transaction.to_user.fullname, photo_url=transaction.to_user.photo_url),
                    debtor=UserInfo(id=transaction.from_user.id, username=transaction.from_user.username,
                                    name=transaction.from_user.fullname,
                                    photo_url=transaction.from_user.photo_url),
                    amount=round(transaction.amount, 2),
                )
                for transaction in payment_graph
            ]
        else:
            transactions_smtp = (
                select(Transaction, Transaction.borrower_id, Transaction.debtor_id, func.sum(Transaction.amount))
                .select_from(Transaction)
                .join(Expense)
                .filter(Expense.group_id == group_id, Transaction.settled.is_(False),
                        (Transaction.debtor_id == user_id) | (Transaction.borrower_id == user_id))
                .group_by(Transaction.borrower_id, Transaction.debtor_id)
            )

            transactions = transaction.execute(transactions_smtp).fetchall()

            total = [
                TransactionInfo(
                    id=0,
                    borrower=UserInfo(id=transaction[0].debtor.id, username=transaction[0].debtor.username,
                                      name=transaction[0].debtor.fullname, photo_url=transaction[0].debtor.photo_url),
                    debtor=UserInfo(id=transaction[0].borrower.id, username=transaction[0].borrower.username,
                                    name=transaction[0].borrower.fullname,
                                    photo_url=transaction[0].borrower.photo_url),
                    amount=round(transaction[3], 2),
                )
                for transaction in transactions
            ]
        return GroupInfo(
            id=group.id,
            name=group.name,
            amount=0,
            simplify_debts=group.simplify_debts,
            expenses=[
                ExpenseShortInfo(
                    id=expense[0].id,
                    description=expense[0].description,
                    payment=expense[0].payment,
                    settled=expense[3],
                    owes=round(expense[1], 2),
                    owe=round(expense[2], 2),
                    first_transaction=BuildTransactionInfo(expense[0].transactions[0]).call() if expense[
                        0].payment else None
                )
                for expense in expenses
            ],
            members=[
                FriendShortInfo(
                    id=member[0].id,
                    username=member[0].username,
                    name=member[0].fullname,
                    photo_url=member[0].photo_url,
                )
                for member in members
            ],
            total=total
        )


@router.put("/groups/{group_id}")
def edit_group(group_id: int, edit_group: EditGroup):
    with orm.Session.begin() as transaction:
        group = (
            transaction.query(Group)
            .join(
                user_group_table,
                user_group_table.c.group_id == Group.id,
            )
            .filter(
                user_group_table.c.group_id == group_id,
                user_group_table.c.user_id == edit_group.user_id
            )
            .first()
        )

        if not group:
            raise fastapi.HTTPException(status_code=404, detail="Group not found")

        group.name = edit_group.name
        group.simplify_debts = edit_group.simplify_debts

        params_members = edit_group.members if edit_group.members is not None else []
        params_members.append(edit_group.user_id)

        members = transaction.query(User).filter(User.id.in_(params_members)).all()
        existing_member_ids = [member.id for member in group.users]

        for member in members:
            if member.id not in existing_member_ids:
                member.groups.append(group)

        transaction.query(user_group_table).filter(~user_group_table.c.user_id.in_(params_members),
                                                   user_group_table.c.group_id == group_id).delete()

        transaction.add(group)
        transaction.add_all(members)
        transaction.commit()
        return True


@router.delete("/groups/{group_id}")
def delete_group(group_id: int):
    with orm.Session.begin() as transaction:
        group = (
            transaction.query(Group)
            .filter(Group.id == group_id)
            .first()
        )

        if not group:
            raise fastapi.HTTPException(status_code=404, detail="Group not found")

        transaction.delete(group)
        return True
