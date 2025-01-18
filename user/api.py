from typing import Annotated, Optional

import fastapi
from fastapi import Query, status
from sqlalchemy import select, sql, func, asc, case
from sqlalchemy.orm import load_only
from sqlalchemy.sql.functions import coalesce

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
)
from user.models import User, friends_association_table, Transaction, Feed

router = fastapi.APIRouter()


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
            .group_by(User.id)
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
def friends(user_id: int, friend_id: int) -> FriendInfo:
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
                status.HTTP_400_BAD_REQUEST, "Users are already friends"
            )

        first_user.friends.append(second_user)
        second_user.friends.append(first_user)

        return True


@router.post("/deleteFriend")
def delete_friend(delete_friend: DeleteFriend):
    with orm.Session.begin() as transaction:
        user = transaction.query(User).get(delete_friend.user_id)
        friend = transaction.query(User).get(delete_friend.friend_id)

        if friend in user.friends:
            user.friends.remove(friend)
            transaction.commit()

        return True


@router.post("/registerUser")
def register_user(create_user: CreateUser):
    with orm.Session.begin() as transaction:
        user = transaction.query(User).filter_by(id=create_user.user_id).first()

        if user:
            user.username = create_user.username
            user.fullname = create_user.fullname
            user.photo_url = create_user.photo_url
        else:
            user = User(
                id=create_user.user_id,
                username=create_user.username,
                fullname=create_user.fullname,
                photo_url=create_user.photo_url,
                default_currency="USD",
                language="en",
            )
            transaction.add(user)
        transaction.commit()
        return True


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
