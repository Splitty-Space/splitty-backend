import random
from typing import Annotated
import fastapi
from fastapi import Query, status, Depends
from sqlalchemy.orm import load_only, Session
from sqlalchemy import select, sql, func, case, or_
from sqlalchemy.sql.functions import coalesce

from app import orm
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
    ExpenseInfo, TransactionInfo, EditExpense, GroupShortInfo, AddGroup, GroupInfo, EditGroup,
)
from user.models import User, friends_association_table, Expense, Transaction, ExpensePayer, Group, user_group_table

router = fastapi.APIRouter()


@router.get("/friends")
def friends(user_id: int) -> list[FriendShortInfo]:
    with orm.Session.begin() as transaction:
        total_borrowed_query = (
            transaction.query(Transaction.debtor_id, func.sum(Transaction.amount).label("total"))
            .select_from(Transaction)
            .filter((Transaction.borrower_id == user_id))
            .group_by(Transaction.debtor_id)
            .subquery()
        )
        total_lent_query = (
            select(Transaction.borrower_id, func.sum(Transaction.amount).label("total"))
            .select_from(Transaction)
            .filter((Transaction.debtor_id == user_id))
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
            .filter((Transaction.borrower_id == user_id) & (Transaction.debtor_id == friend_id))
            .alias("borrowed_transactions")
        )
        total_lent_query = (
            select(func.sum(Transaction.amount).label('amount'))
            .filter((Transaction.debtor_id == user_id) & (Transaction.borrower_id == friend_id))
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
                coalesce(total_lent_expense_query.c.total, 0)
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
                fullname=user.fullname,
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
                fullname=user.fullname,
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
            fullname=create_user.name,
            photo_url=create_user.photo_url,
        )
        transaction.add(user)
        return True


@router.post("/expenses")
def add_expense(create_expense: CreateExpense):
    with orm.Session.begin() as transaction:
        expense = Expense(description=create_expense.description, data=create_expense.data, group_id=create_expense.group_id)
        transaction.add(expense)

        transactions = [
            Transaction(
                amount=round(transaction.amount, 2),
                debtor_id=transaction.debtor_id,
                borrower_id=transaction.borrower_id,
                expense=expense,
                currency="USD"
            ) for transaction in create_expense.transactions
        ]
        transaction.add_all(transactions)

        expense_payers = [
            ExpensePayer(
                amount=payer.amount,
                user_id=payer.user_id,
                expense=expense,
                currency="USD"
            ) for payer in create_expense.expense_payers
        ]
        transaction.add_all(expense_payers)
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

        expense.description = edit_expense.description
        expense.data = edit_expense.data

        transaction.query(Transaction).filter(Transaction.expense_id == expense.id).delete()
        transaction.query(ExpensePayer).filter(ExpensePayer.expense_id == expense.id).delete()

        transactions = [
            Transaction(
                amount=round(transaction.amount, 2),
                debtor_id=transaction.debtor_id,
                borrower_id=transaction.borrower_id,
                expense=expense,
                currency="USD"
            ) for transaction in edit_expense.transactions
        ]
        transaction.add_all(transactions)

        expense_payers = [
            ExpensePayer(
                amount=payer.amount,
                user_id=payer.user_id,
                expense=expense,
                currency="USD"
            ) for payer in edit_expense.expense_payers
        ]
        transaction.add_all(expense_payers)
        return True


@router.get("/expenses/{expense_id}")
def friends(user_id: int, expense_id: int) -> ExpenseInfo:
    with (orm.Session.begin() as transaction):
        total_borrowed_expense_query = (
            transaction.query(Transaction.expense_id, func.sum(Transaction.amount).label('total'))
            .select_from(Transaction)
            .filter((Transaction.borrower_id == user_id))
            .group_by(Transaction.expense_id)
            .subquery()
        )
        total_lent_expense_query = (
            transaction.query(Transaction.expense_id, func.sum(Transaction.amount).label('total'))
            .select_from(Transaction)
            .group_by(Transaction.expense_id)
            .filter((Transaction.debtor_id == user_id))
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

        expense_info = ExpenseInfo(
            id=expense[0].id,
            description=expense[0].description,
            data=expense[0].data,
            transactions=[
                TransactionInfo(
                    id=transaction.id,
                    debtor=UserInfo(id=transaction.debtor.id, username=transaction.debtor.username,
                                    fullname=transaction.debtor.fullname, photo_url=transaction.debtor.photo_url),
                    borrower=UserInfo(id=transaction.borrower.id, username=transaction.borrower.username,
                                      fullname=transaction.borrower.fullname, photo_url=transaction.borrower.photo_url),
                    amount=round(transaction.amount, 2),
                )
                for transaction in expense[0].transactions
            ],
            owes=round(expense[1], 2),
            owe=round(expense[2], 2),
        )
        return expense_info


@router.get("/groups")
def friends(user_id: int) -> list[GroupShortInfo]:
    with orm.Session.begin() as transaction:
        stmt = (
            select(
                Group,
            )
            .select_from(Group)
            .join(
                user_group_table,
                user_group_table.c.user_id == user_id,
            ).group_by(Group.id)
        )

        groups = transaction.execute(stmt).fetchall()

        return [
            GroupShortInfo(
                id=group[0].id,
                name=group[0].name,
                owe=0,
                owes=0,
                users=[FriendShortInfo(
                    id=member.id,
                    username=member.username,
                    name=member.fullname,
                    photo_url=member.photo_url,
                    amount=None
                )
                    for member in group[0].users]
            )
            for group in groups
        ]


@router.post("/groups")
def friends(add_group: AddGroup):
    with orm.Session.begin() as transaction:
        user = transaction.query(User).filter_by(id=add_group.user_id).first()

        if not user:
            raise fastapi.HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

        group = Group(name=add_group.name)
        user.groups.append(group)

        return True


@router.get("/groups/{group_id}")
def friends(user_id: int, group_id: int) -> GroupInfo:
    with (orm.Session.begin() as transaction):
        stmt = (
            select(
                Group,
            )
            .select_from(Group)
            .join(
                user_group_table,
                user_group_table.c.group_id == group_id,
            )
            .filter(user_group_table.c.user_id == user_id)
        )

        group = transaction.execute(stmt).fetchone()

        if not group:
            raise fastapi.HTTPException(status_code=404, detail="Group not found")

        total_borrowed_query = (
            transaction.query(Transaction.debtor_id, func.sum(Transaction.amount).label("total"))
            .select_from(Transaction)
            .filter((Transaction.borrower_id == user_id))
            .group_by(Transaction.debtor_id)
            .subquery()
        )
        total_lent_query = (
            select(Transaction.borrower_id, func.sum(Transaction.amount).label("total"))
            .select_from(Transaction)
            .filter((Transaction.debtor_id == user_id))
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
                user_group_table,
                (user_group_table.c.user_id == User.id) & (user_group_table.c.group_id == group_id),
            )
            .group_by(User.id)
            .filter(friends_association_table.c.user_id == user_id)
            .order_by(User.id.desc())
        )

        members = transaction.execute(stmt).fetchall()

        return GroupInfo(
            id=group[0].id,
            name=group[0].name,
            amount=0,
            members=[
                FriendShortInfo(
                    id=member[0].id,
                    username=member[0].username,
                    name=member[0].fullname,
                    photo_url=member[0].photo_url,
                    amount=round(member[1], 2)
                )
                for member in members
            ]
        )


@router.put("/groups/{group_id}")
def friends(group_id: int, edit_group: EditGroup):
    with (orm.Session.begin() as transaction):
        group = (
            transaction.query(Group)
            .join(
                user_group_table,
                user_group_table.c.group_id == group_id,
            )
            .filter(user_group_table.c.user_id == edit_group.user_id)
            .first()
        )

        if not group:
            raise fastapi.HTTPException(status_code=404, detail="Group not found")

        group.name = edit_group.name

        params_members = edit_group.members if edit_group.members is not None else []
        params_members.append(edit_group.user_id)

        members = transaction.query(User).filter(User.id.in_(params_members)).all()
        existing_member_ids = [member.id for member in group.users]

        for member in members:
            if member.id not in existing_member_ids:
                member.groups.append(group)

        transaction.query(user_group_table).filter(~user_group_table.c.user_id.in_(params_members),
                                                   user_group_table.c.group_id == group_id).delete()

        return True
