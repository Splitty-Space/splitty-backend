import fastapi
from fastapi import status

from app import orm
from user.dtos import (ActivityResponse, ActivityDTO, UserInfo, ExpenseActivityInfo, ExpenseUserInfo)
from user.models import User, Activity, ActivityUser, Expense

router = fastapi.APIRouter()


@router.get("/activities")
def get_activities(user_id: int, page: int, page_size: int):
    with orm.Session.begin() as transaction:
        user = transaction.query(User).get(user_id)

        if not user:
            raise fastapi.HTTPException(status.HTTP_400_BAD_REQUEST, "User not found")

        query = transaction.query(Activity).filter(
            Activity.activity_user.any(ActivityUser.user_id == user_id)).order_by(Activity.created_at.desc())

        activities = query.offset((page - 1) * page_size).limit(page_size).all()

        total_records = query.count()
        has_more = total_records > page * page_size

        data = []

        user_ids = [activity.performed_by_user_id for activity in activities]
        users = transaction.query(User).where(User.id.in_(user_ids)).all()

        expense_ids = [activity.expenses_id for activity in activities]
        expenses = transaction.query(Expense).where(Expense.id.in_(expense_ids)).all()

        for activity in activities:
            user = next((user for user in users if user.id == activity.performed_by_user_id), None)
            expense = next((expense for expense in expenses if expense.id == activity.expenses_id), None)

            data.append(ActivityDTO(
                id=activity.id,
                activity_type=activity.activity_type,
                created_at=activity.created_at,
                data=activity.data,
                user=UserInfo(
                    id=user.id,
                    username=user.username,
                    name=user.fullname,
                    photo_url=user.photo_url,
                ),
                expense=ExpenseActivityInfo(
                    id=expense.id,
                    description=expense.description,
                    isDeleted=expense.isDeleted,
                    amount=expense.amount,
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
                        for expense_user in expense.expense_users
                    ],
                )
            ))

        return ActivityResponse(
            data=data,
            meta={
                'has_more': has_more,
                'total_records': total_records
            }
        )

@router.get("/activity")
def get_activity(user_id: int, expanse_id: int):
    with orm.Session.begin() as transaction:
        user = transaction.query(User).get(user_id)

        if not user:
            raise fastapi.HTTPException(status.HTTP_400_BAD_REQUEST, "User not found")

        query = transaction.query(Activity).filter(
            Activity.activity_user.any(ActivityUser.user_id == user_id),
            Activity.expenses_id == expanse_id
        ).order_by(Activity.created_at.desc())

        activities = query.all()

        data = []

        user_ids = [activity.performed_by_user_id for activity in activities]
        users = transaction.query(User).where(User.id.in_(user_ids)).all()

        expense_ids = [activity.expenses_id for activity in activities]
        expenses = transaction.query(Expense).where(Expense.id.in_(expense_ids)).all()

        for activity in activities:
            user = next((user for user in users if user.id == activity.performed_by_user_id), None)
            expense = next((expense for expense in expenses if expense.id == activity.expenses_id), None)

            data.append(ActivityDTO(
                id=activity.id,
                activity_type=activity.activity_type,
                created_at=activity.created_at,
                data=activity.data,
                user=UserInfo(
                    id=user.id,
                    username=user.username,
                    name=user.fullname,
                    photo_url=user.photo_url,
                ),
                expense=ExpenseActivityInfo(
                    id=expense.id,
                    description=expense.description,
                    isDeleted=expense.isDeleted,
                    amount=expense.amount,
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
                        for expense_user in expense.expense_users
                    ],
                )
            ))

        return ActivityResponse(
            data=data,
            meta={}
        )