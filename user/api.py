import datetime
import random
from typing import Annotated
import fastapi
from fastapi import Query, status, Depends
from sqlalchemy.orm import load_only, Session
from sqlalchemy import select, sql, func, case, or_
from sqlalchemy.sql.functions import coalesce

from app import orm
from app.services.feed_service import FeedService
from core.dtos import PaginationRequest
from user.dtos import (
    AddFriend,
    CreateUser,
    FriendShortInfo,
    SearchUserPaginationResponse,
    UserInfo,
    CreateExpense,
    FriendInfo,
    ExpenseShortInfo,
    ExpenseInfo, TransactionInfo, EditExpense, GroupShortInfo, AddGroup, GroupInfo, EditGroup, ExpenseUserInfo,
    FeedInfo,
)
from user.models import User, friends_association_table, Expense, Transaction, Group, user_group_table, \
    ExpenseUser
from utils.calculate_user_balance import calculate_user_balances
from utils.entities.UserBalance import UserBalance
from utils.make_payment_graph import make_payment_graph

router = fastapi.APIRouter()


@router.get("/friends")
def friends(user_id: int) -> list[FriendShortInfo]:
    with orm.Session.begin() as transaction:
        total_borrowed_query = (
            transaction.query(Transaction.debtor_id, func.sum(Transaction.amount).label("total"))
            .select_from(Transaction)
            .filter(Transaction.borrower_id == user_id, Transaction.settled == False)
            .group_by(Transaction.debtor_id)
            .subquery()
        )
        total_lent_query = (
            select(Transaction.borrower_id, func.sum(Transaction.amount).label("total"))
            .select_from(Transaction)
            .filter(Transaction.debtor_id == user_id, Transaction.settled == False)
            .group_by(Transaction.borrower_id)
            .subquery()
        )
        stmt = (
            select(
                User,
                coalesce(total_borrowed_query.c.total, 0) - coalesce(total_lent_query.c.total, 0)
            )
            .options(
                load_only(
                    User.id,
                    User.username,
                    User.fullname,
                    User.photo_url,
                )
            )
            .outerjoin(total_borrowed_query, total_borrowed_query.c.debtor_id == User.id)
            .outerjoin(total_lent_query, total_lent_query.c.borrower_id == User.id)
            .join(
                friends_association_table,
                friends_association_table.c.friend_id == User.id,
            )
            .group_by(User.id)
            .filter(friends_association_table.c.user_id == user_id)
            .order_by(User.id.desc())
        )

        friends = transaction.execute(stmt).fetchall()

        return [
            FriendShortInfo(
                id=friend[0].id,
                username=friend[0].username,
                name=friend[0].fullname,
                photo_url=friend[0].photo_url,
                amount=round(friend[1], 2)
            )
            for friend in friends
        ]


@router.get("/friends/{friend_id}")
def friends(user_id: int, friend_id: int) -> FriendInfo:
    with (orm.Session.begin() as transaction):
        stmt = select(friends_association_table).where(
            (
                    (friends_association_table.c.user_id == user_id)
                    & (friends_association_table.c.friend_id == friend_id)
            )
            | (
                    (friends_association_table.c.user_id == friend_id)
                    & (friends_association_table.c.friend_id == user_id)
            )
        )
        is_friends = transaction.execute(stmt).scalar()
        if is_friends is None:
            raise fastapi.HTTPException(status.HTTP_404_NOT_FOUND, "Not found friend")

        total_borrowed_query = (
            select(func.sum(Transaction.amount).label('amount'))
            .filter((Transaction.borrower_id == user_id) & (Transaction.debtor_id == friend_id) & (
                Transaction.settled.is_(False)))
            .alias("borrowed_transactions")
        )
        total_lent_query = (
            select(func.sum(Transaction.amount).label('amount'))
            .filter((Transaction.debtor_id == user_id) & (Transaction.borrower_id == friend_id) & (
                Transaction.settled.is_(False)))
            .alias("lent_transactions")
        )
        friend = transaction.query(User,
                                   coalesce(total_borrowed_query.c.amount, 0) - coalesce(total_lent_query.c.amount,
                                                                                         0)).filter_by(
            id=friend_id).first()

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
                coalesce(total_borrowed_expense_query.c.total, 0),
                coalesce(total_lent_expense_query.c.total, 0),
                ~Expense.transactions.any((Transaction.settled == False) & (
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
        expenses = transaction.execute(expenses_stmt).fetchall()

        return FriendInfo(
            id=friend[0].id,
            username=friend[0].username,
            name=friend[0].fullname,
            photo_url=friend[0].photo_url,
            amount=round(friend[1], 2),
            expenses=[
                ExpenseShortInfo(
                    id=expense[0].id,
                    description=expense[0].description,
                    payment=expense[0].payment,
                    settled=expense[3],
                    owes=round(expense[1], 2),
                    owe=round(expense[2], 2),
                )
                for expense in expenses
            ]
        )


@router.get("/searchUser")
def search_user(
        page: Annotated[int, Query()],
        per_page: Annotated[int, Query()],
        query: Annotated[str, Query(max_length=30)],
) -> SearchUserPaginationResponse:
    with orm.Session.begin() as transaction:
        query = query.strip()
        stmt = (
            transaction.query(User)
            .filter(
                sql.or_(
                    User.username.like(f"%{query}%"),
                    User.fullname.like(f"%{query}%"),
                )
            )
            .offset(
                (page - 1) * per_page,
            )
            .limit(
                per_page,
            )
        )
        users = stmt.all()
        total = stmt.count()

        data = [
            UserInfo(
                id=user.id,
                username=user.username,
                name=user.fullname,
                photo_url=user.photo_url,
            )
            for user in users
        ]

        response = SearchUserPaginationResponse(
            page=page,
            per_page=per_page,
            total=total,
            data=data,
        )

        return response


@router.get("/searchFriends")
def search_friend(
        user_id: Annotated[int, Query()],
        page: Annotated[int, Query()],
        per_page: Annotated[int, Query()],
        query: Annotated[str, Query(max_length=30)],
) -> SearchUserPaginationResponse:
    with orm.Session.begin() as transaction:
        query = query.strip()
        stmt = (
            transaction.query(User)
            .join(
                friends_association_table,
                friends_association_table.c.friend_id == User.id,
            )
            .filter(
                sql.and_(
                    friends_association_table.c.user_id == user_id,
                    sql.or_(
                        User.username.like(f"%{query}%"),
                        User.fullname.like(f"%{query}%"),
                    ),
                )
            )
            .offset(
                (page - 1) * per_page,
            )
            .limit(
                per_page,
            )
        )
        users = stmt.all()
        total = stmt.count()

        data = [
            UserInfo(
                id=user.id,
                username=user.username,
                name=user.fullname,
                photo_url=user.photo_url,
            )
            for user in users
        ]

        response = SearchUserPaginationResponse(
            page=page,
            per_page=per_page,
            total=total,
            data=data,
        )

        return response


@router.post("/addFriend")
def add_friend(add_friend: AddFriend):
    with orm.Session.begin() as transaction:
        first_user = transaction.query(User).filter_by(id=add_friend.user_id).first()
        second_user = transaction.query(User).filter_by(id=add_friend.friend_id).first()

        if not first_user or not second_user:
            raise fastapi.HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

        stmt = select(friends_association_table).where(
            (
                    (friends_association_table.c.user_id == add_friend.user_id)
                    & (friends_association_table.c.friend_id == add_friend.friend_id)
            )
            | (
                    (friends_association_table.c.user_id == add_friend.friend_id)
                    & (friends_association_table.c.friend_id == add_friend.user_id)
            )
        )
        is_friends = transaction.execute(stmt).scalar()
        if is_friends is not None:
            raise fastapi.HTTPException(
                status.HTTP_400_BAD_REQUEST, "Users are already friends"
            )

        first_user.friends.append(second_user)
        second_user.friends.append(first_user)

        return True


@router.post("/registerUser")
def register_user(create_user: CreateUser):
    with orm.Session.begin() as transaction:
        is_user_exist = (
                transaction.query(User).filter_by(id=create_user.user_id).count() == 1
        )
        if is_user_exist:
            return True

        user = User(
            id=create_user.user_id,
            username=create_user.username,
            fullname=create_user.fullname,
            photo_url=create_user.photo_url,
        )
        transaction.add(user)
        return True


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
            payment_node = next((node for node in payment_graph if node.from_user == user_id or node.to_user == user_id), None)
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

        transaction.commit()

    with orm.Session.begin() as transaction:
        for user_id in create_expense.users:
            total_borrowed_query = (
                select(func.sum(Transaction.amount).label('amount'))
                .filter(Transaction.borrower_id == user_id, Transaction.settled == False)
                .alias("borrowed_transactions")
            )
            total_lent_query = (
                select(func.sum(Transaction.amount).label('amount'))
                .filter(Transaction.debtor_id == user_id, Transaction.settled == False)
                .alias("lent_transactions")
            )
            user = transaction.query(User, coalesce(total_borrowed_query.c.amount, 0) - coalesce(
                total_lent_query.c.amount, 0)).filter_by(id=user_id).first()
            if float(user[1]) == 0:
                transaction.query(Transaction).filter(Transaction.settled == False,
                                                      (Transaction.borrower_id == user_id) | (
                                                              Transaction.debtor_id == user_id)).update(
                    {Transaction.settled: True})

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

        expense.description = edit_expense.description
        expense.amount = edit_expense.amount
        expense.group = group

        created_at = expense.transactions[0].created_at
        transaction.query(Transaction). \
            filter(
            Transaction.created_at >= created_at,
            Transaction.settled.is_(True),
            or_(
                Transaction.borrower_id.in_(edit_expense.users),
                Transaction.debtor_id.in_(edit_expense.users)
            )
        ). \
            update({Transaction.settled: False})

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
            ) for user_id in edit_expense.users
        ]
        transaction.add_all(expense_users)

        transaction.commit()

    with orm.Session.begin() as transaction:
        for user_id in edit_expense.users:
            total_borrowed_query = (
                select(func.sum(Transaction.amount).label('amount'))
                .filter(Transaction.borrower_id == user_id, Transaction.settled.is_(False))
                .alias("borrowed_transactions")
            )
            total_lent_query = (
                select(func.sum(Transaction.amount).label('amount'))
                .filter(Transaction.debtor_id == user_id, Transaction.settled.is_(False))
                .alias("lent_transactions")
            )
            user = transaction.query(User, coalesce(total_borrowed_query.c.amount, 0) - coalesce(
                total_lent_query.c.amount, 0)).filter_by(id=user_id).first()
            if float(user[1]) == 0:
                transaction.query(Transaction).filter(Transaction.settled == False,
                                                      (Transaction.borrower_id == user_id) | (
                                                              Transaction.debtor_id == user_id)).update(
                    {Transaction.settled: True})

        transaction.commit()
    return True


@router.get("/expenses/{expense_id}")
def get_expense(user_id: int, expense_id: int) -> ExpenseInfo:
    with (orm.Session.begin() as transaction):
        total_borrowed_expense_query = (
            transaction.query(Transaction.expense_id, func.sum(Transaction.amount).label('total'))
            .select_from(Transaction)
            .filter(Transaction.borrower_id == user_id, Transaction.settled == False)
            .group_by(Transaction.expense_id)
            .subquery()
        )
        total_lent_expense_query = (
            transaction.query(Transaction.expense_id, func.sum(Transaction.amount).label('total'))
            .select_from(Transaction)
            .group_by(Transaction.expense_id)
            .filter(Transaction.debtor_id == user_id, Transaction.settled == False)
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
                owe=0,
                owes=0,
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


@router.get("/groups")
def groups(user_id: int) -> list[GroupShortInfo]:
    with orm.Session.begin() as transaction:
        user = transaction.query(User).get(user_id)

        if not user:
            raise fastapi.HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

        return [
            GroupShortInfo(
                id=group.id,
                name=group.name,
                owe=0,
                owes=0,
                users=[FriendShortInfo(
                    id=member.id,
                    username=member.username,
                    name=member.fullname,
                    photo_url=member.photo_url,
                    amount=None
                )
                    for member in group.users]
            )
            for group in user.groups
        ]


@router.post("/groups")
def create_group(add_group: AddGroup):
    with orm.Session.begin() as transaction:
        user = transaction.query(User).filter_by(id=add_group.user_id).first()

        if not user:
            raise fastapi.HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

        group = Group(name=add_group.name)
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
                ~Expense.transactions.any((Transaction.settled == False) & (
                        (Transaction.debtor_id == user_id) | (Transaction.borrower_id == user_id)))
            )
            .select_from(Expense)
            .outerjoin(total_borrowed_expense_query, total_borrowed_expense_query.c.expense_id == Expense.id)
            .outerjoin(total_lent_expense_query, total_lent_expense_query.c.expense_id == Expense.id)
            .join(Transaction,
                  (Transaction.expense_id == Expense.id) & (
                          (Transaction.debtor_id == user_id) |
                          (Transaction.borrower_id == user_id)))
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
                .filter(Expense.group_id == group_id, Transaction.settled == False)
                .group_by(Transaction.debtor_id)
                .subquery()
            )
            total_lent_query = (
                select(Transaction.borrower_id, func.sum(Transaction.amount).label("total"))
                .select_from(Transaction)
                .join(Expense)
                .filter(Expense.group_id == group_id, Transaction.settled == False)
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
                    debtor=UserInfo(id=transaction.to_user.id, username=transaction.to_user.username,
                                    name=transaction.to_user.fullname, photo_url=transaction.to_user.photo_url),
                    borrower=UserInfo(id=transaction.from_user.id, username=transaction.from_user.username,
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
                .filter(Expense.group_id == group_id, Transaction.settled == False,
                        (Transaction.debtor_id == user_id) | (Transaction.borrower_id == user_id))
                .group_by(Transaction.borrower_id, Transaction.debtor_id)
            )

            transactions = transaction.execute(transactions_smtp).fetchall()

            total = [
                TransactionInfo(
                    id=0,
                    debtor=UserInfo(id=transaction[0].debtor.id, username=transaction[0].debtor.username,
                                    name=transaction[0].debtor.fullname, photo_url=transaction[0].debtor.photo_url),
                    borrower=UserInfo(id=transaction[0].borrower.id, username=transaction[0].borrower.username,
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
                user_group_table.c.group_id == Group.id,  # Assuming Group.id is the primary key of the Group table
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


@router.get("/me")
def get_me(user_id: int) -> FriendShortInfo:
    with orm.Session.begin() as transaction:
        user = transaction.query(User).get(user_id)

        if not user:
            raise fastapi.HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

        return FriendShortInfo(
            id=user.id,
            username=user.username,
            name=user.fullname,
            photo_url=user.photo_url
        )


@router.get("/feeds")
def feeds(user_id: int) -> list[FeedInfo]:
    with orm.Session.begin() as transaction:
        user = transaction.query(User).get(user_id)

        if not user:
            raise fastapi.HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

        return [
            FeedInfo(
                id=feed.id,
                type=feed.type,
                message=feed.message,
            )
            for feed in user.feeds
        ]

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
