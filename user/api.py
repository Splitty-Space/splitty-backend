from typing import Annotated, Optional
import logging
import datetime
from decimal import Decimal
import jwt
import os
import fastapi
import requests
import hashlib
from fastapi import Query, status, HTTPException
from sqlalchemy import select, sql, func, asc, case
from sqlalchemy.orm import load_only
from sqlalchemy.sql.functions import coalesce
from init_data_py import InitData
from utils.send_message import send_message
from app import orm
from app.query.friend_total_calculator import FriendTotalCalculator
from app.query.total_calculator import TotalCalculator
from user.dtos import (
    AddFriend,
    DeleteFriend,
    CreateUser,
    FriendShortInfo,
    SearchUserPaginationResponse,
    UserInfo,
    FriendInfo,
    FeedInfo,
    FriendsResponse,
    DebtInfo,
    FeedResponse,
    MessageRequest,
    CreateExpense,
    CreateExpenseUser,
)
from user.models import User, friends_association_table, Transaction, Feed, UserMessage
from user.routers.expenses import add_expense
from utils.generate_referral_code import generate_referral_code
from user.dependencies import verify_token

router = fastapi.APIRouter(dependencies=[fastapi.Depends(verify_token)])


@router.get("/friends")
def friends(user_id: int, search_name: Optional[str] = None) -> FriendsResponse:
    with orm.Session.begin() as transaction:
        user = transaction.query(User).get(user_id)

        if not user:
            raise fastapi.HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

        total_borrowed_query = (
            transaction.query(Transaction.debtor_id, func.sum(Transaction.amount).label("total"))
            .select_from(Transaction)
            .filter(Transaction.borrower_id == user_id, Transaction.settled.is_(False))
            .group_by(Transaction.debtor_id)
            .subquery()
        )
        total_lent_query = (
            select(Transaction.borrower_id, func.sum(Transaction.amount).label("total"))
            .select_from(Transaction)
            .filter(Transaction.debtor_id == user_id, Transaction.settled.is_(False))
            .group_by(Transaction.borrower_id)
            .subquery()
        )

        amount_cte = (
            select(
                User.id.label('user_id'),
                (coalesce(total_borrowed_query.c.total, 0) - coalesce(total_lent_query.c.total, 0)).label("amount")
            )
            .outerjoin(total_borrowed_query, total_borrowed_query.c.debtor_id == User.id)
            .outerjoin(total_lent_query, total_lent_query.c.borrower_id == User.id)
            .cte("amount_cte")
        )

        stmt = (
            select(
                User,
                amount_cte.c.amount,
                case(
                    (amount_cte.c.amount < 0, 1),
                    (amount_cte.c.amount > 0, 2),
                    else_=3
                ).label("priority")
            )
            .join(amount_cte, amount_cte.c.user_id == User.id)
            .options(
                load_only(
                    User.id,
                    User.username,
                    User.fullname,
                    User.photo_url,
                )
            )
            .join(
                friends_association_table,
                friends_association_table.c.friend_id == User.id,
            )
            .group_by(User.id, amount_cte.c.amount)
            .filter(
                sql.and_(
                    friends_association_table.c.user_id == user_id,
                    sql.or_(
                        User.username.like(f"%{search_name}%"),
                        User.fullname.like(f"%{search_name}%"),
                    ) if search_name is not None and len(search_name) != 0 else True
                )
            )
            .order_by(asc("priority"), asc(amount_cte.c.amount))
        )

        friends = transaction.execute(stmt).fetchall()

        return FriendsResponse(
            data=[FriendShortInfo(
                id=friend[0].id,
                username=friend[0].username,
                name=friend[0].fullname,
                photo_url=friend[0].photo_url,
                amount=round(friend[1], 2),
                total=[
                    DebtInfo(
                        currency=debt[0],
                        amount=round(debt[1], 2)
                    )
                    for debt in FriendTotalCalculator(transaction, user_id, friend[0].id).call() if debt[1] != 0
                ]
            )
                for friend in friends],
            meta={'total': TotalCalculator(transaction, user_id).call(), 'default_currency': user.default_currency}
        )


@router.get("/friends/{friend_id}")
def get_friend_info(user_id: int, friend_id: int) -> FriendInfo:
    with (orm.Session.begin() as transaction):
        user = transaction.query(User).get(user_id)

        if not user:
            raise fastapi.HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

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

        return FriendInfo(
            id=friend[0].id,
            username=friend[0].username,
            name=friend[0].fullname,
            photo_url=friend[0].photo_url,
            amount=round(friend[1], 2),
            total=[
                DebtInfo(
                    currency=debt[0],
                    amount=round(debt[1], 2)
                )
                for debt in FriendTotalCalculator(transaction, user_id, friend_id).call() if debt[1] != 0
            ],
            default_currency=user.default_currency
        )


@router.get("/searchUser")
def search_user(
        page: Annotated[int, Query()],
        per_page: Annotated[int, Query()],
        query: Annotated[str, Query(max_length=30)],
) -> SearchUserPaginationResponse:
    with orm.Session.begin() as transaction:
        query = query.strip().replace("@", "")
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
                status.HTTP_409_CONFLICT, "Users are already friends"
            )

        first_user.friends.append(second_user)
        second_user.friends.append(first_user)

        fullname = first_user.fullname
        language = second_user.language

        create_tutorial_expenses_for_test_user(add_friend, language)

        transaction.commit()

        send_friend_invitation_message(fullname, language)

        return True


def create_tutorial_expenses_for_test_user(add_friend, language):
    TUTORIAL_USER_ID = 7013457029
    if add_friend.friend_id != TUTORIAL_USER_ID:
        return

    if language == "en":
        description = "Dinner at the restaurant"
        description2 = "Picnic in the park"
    elif language == "ru":
        description = "Ужин в ресторане"
        description2 = "Пикник в парке"
    elif language == "ua":
        description = "Вечеря у ресторані"
        description2 = "Пікнік у парку"
    else:
        description = "Dinner at the restaurant"
        description2 = "Picnic in the park"

    temp_expense = CreateExpense(
        payers=[CreateExpenseUser(user_id=add_friend.user_id, amount=100),
                CreateExpenseUser(user_id=add_friend.friend_id, amount=0)],
        debtors=[CreateExpenseUser(user_id=add_friend.user_id, amount=50),
                 CreateExpenseUser(user_id=add_friend.friend_id, amount=50)],
        users=[add_friend.user_id, add_friend.friend_id],
        user_id=add_friend.user_id,
        amount=Decimal(100),
        payment=False,
        currency="USD",
        date=datetime.datetime.utcnow(),
        description=description,
        group_id=None
    )
    add_expense(temp_expense)

    temp_expense2 = CreateExpense(
        payers=[CreateExpenseUser(user_id=add_friend.user_id, amount=322),
                CreateExpenseUser(user_id=add_friend.friend_id, amount=0)],
        debtors=[CreateExpenseUser(user_id=add_friend.user_id, amount=161),
                 CreateExpenseUser(user_id=add_friend.friend_id, amount=161)],
        users=[add_friend.user_id, add_friend.friend_id],
        user_id=add_friend.user_id,
        amount=Decimal(100),
        payment=False,
        currency="EUR",
        date=datetime.datetime.utcnow(),
        description=description2,
        group_id=None
    )
    add_expense(temp_expense2)


def send_friend_invitation_message(fullname, language):
    if language == "en":
        message = "accepted your friend invitation."
    elif language == "ru":
        message = "принял ваше приглашение дружбы."
    elif language == "ua":
        message = "прийняв ваше запрошення дружби."

    send_message(add_friend.friend_id, f"{fullname} {message}")


@router.post("/deleteFriend")
def delete_friend(delete_friend: DeleteFriend):
    with orm.Session.begin() as transaction:
        user = transaction.query(User).get(delete_friend.user_id)
        friend = transaction.query(User).get(delete_friend.friend_id)

        if friend in user.friends:
            user.friends.remove(friend)

        if user in friend.friends:
            friend.friends.remove(user)

        transaction.commit()

        return True


# TODO not used remove?
@router.post("/registerUser")
def register_user(create_user: CreateUser):
    with orm.Session.begin() as transaction:
        user = transaction.query(User).filter_by(id=create_user.user_id).first()

        if create_user.photo_url != "":
            try:
                response = requests.get(create_user.photo_url)
                response.raise_for_status()
                photo_data = response.content
            except Exception as e:
                logging.error(f"Error loading image from URL: {e}")
                photo_data = None
        else:
            try:
                with open("icons/default_avatar.png", "rb") as f:
                    photo_data = f.read()
            except Exception as e:
                logging.error(f"Error loading default avatar: {e}")
                photo_data = None

        refer_id = None
        if create_user.referred_by_code:
            refer = transaction.query(User).filter_by(referral_code=create_user.referred_by_code).first()
            if (not user) or (refer and refer.id != user.id):
                refer_id = refer.id if refer else None
        else:
            refer = None

        if user:
            user.username = create_user.username
            user.fullname = create_user.fullname
            user.photo_url = create_user.photo_url
            user.photo = photo_data
        else:
            user = User(
                id=create_user.user_id,
                username=create_user.username,
                fullname=create_user.fullname,
                photo_url=create_user.photo_url,
                photo=photo_data,
                default_currency="USD",
                language="en",
                referral_code=generate_referral_code(create_user.user_id),
                referred_by=refer.id if refer else None
            )
            transaction.add(user)
        transaction.commit()

        if refer_id:
            add_friend(AddFriend(create_user.user_id, friend_id=refer_id))

        return True


# TODO not used remove?
@router.get("/feeds")
def feeds(user_id: int, page: int, limit: int) -> FeedResponse:
    with orm.Session.begin() as transaction:
        feeds = transaction.query(Feed).order_by(Feed.id.asc()).filter(Feed.user_id == user_id).offset(
            (page - 1) * limit).limit(limit + 1).all()
        has_more = len(feeds) == limit + 1
        feeds = feeds[:-1] if has_more else feeds

        feed_infos = []
        unique_years = set()
        for feed in feeds:
            feed_infos.append(FeedInfo(
                id=feed.id,
                type=feed.type,
                message=feed.message,
                created_at=feed.created_at,
            ))
            unique_years.add(feed.created_at.year)
        return FeedResponse(data=feed_infos, meta={'has_more': has_more, 'years': unique_years})


@router.post("/sendMessage")
def post_message(request: MessageRequest):
    with orm.Session.begin() as session:
        print("user_id:", request.user_id)
        print("message:", request.message)
        print("date:", request.date)

        dt = datetime.datetime.fromtimestamp(request.date)
        user_message = UserMessage(user_id=request.user_id, text=request.message, created_at=dt)
        session.add(user_message)
        session.commit()
        session.refresh(user_message)
        return {"status": "success", "message_id": user_message.id}
