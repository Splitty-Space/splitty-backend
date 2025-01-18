from user.models import Activity, ActivityType


def process_expense_creation(transaction, expenses_id, created_at, activity_user, performed_by_user_id, data):
    transaction.add(Activity(
        activity_type=ActivityType.EXPENSE_CREATED,
        expenses_id=expenses_id,
        created_at=created_at,
        activity_user=activity_user,
        performed_by_user_id=performed_by_user_id,
        data=data,
    ))

def process_expense_deletion(transaction):
    transaction.add(Activity(activity_type=ActivityType.EXPENSE_DELETED))


def process_expense_edition(transaction):
    transaction.add(Activity(activity_type=ActivityType.EXPENSE_EDITED))


def process_payment_creation(transaction):
    transaction.add(Activity(activity_type=ActivityType.PAYMENT_CREATED))


def process_payment_deletion(transaction):
    transaction.add(Activity(activity_type=ActivityType.PAYMENT_DELETED))


def process_payment_edition(transaction):
    transaction.add(Activity(activity_type=ActivityType.PAYMENT_EDITED))


class ActivityService:
    pass
