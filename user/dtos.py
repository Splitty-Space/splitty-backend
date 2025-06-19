from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List, Union

from core.dtos import PaginationResponse
from decimal import Decimal


@dataclass
class CreateUser:
    user_id: int
    username: str
    fullname: str
    photo_url: str
    referred_by_code: Optional[str] = None


@dataclass
class CreateExpenseUser:
    user_id: int
    amount: Decimal


@dataclass
class Balance:
    user_id: int
    amount: Decimal


@dataclass
class CreateExpense:
    payers: list[CreateExpenseUser]
    debtors: list[CreateExpenseUser]
    users: list[int]
    user_id: int
    amount: Decimal
    payment: bool
    currency: str
    date: datetime
    description: Optional[str] = None
    group_id: Optional[int] = None


@dataclass
class EditExpense:
    user_id: int
    payers: list[CreateExpenseUser]
    debtors: list[CreateExpenseUser]
    users: list[int]
    amount: Decimal
    description: Optional[str] = None
    group_id: Optional[int] = None


@dataclass
class UserInfo:
    id: int
    name: str
    photo_url: str
    username: str
    type: Optional[str] = "user"


@dataclass
class DebtInfo:
    currency: str
    amount: Decimal


@dataclass
class FriendShortInfo:
    id: int
    username: str
    name: str
    photo_url: str
    amount: Optional[Decimal] = None
    type: Optional[str] = "user"
    total: Optional[List[DebtInfo]] = tuple()


@dataclass
class UserInfo:
    id: int
    username: str
    name: str
    photo_url: str
    referral_code: Optional[str] = None
    default_currency: Optional[str] = None
    language: Optional[str] = None


@dataclass
class GroupUserInfo:
    id: int
    username: str
    name: str
    photo_url: str
    type: Optional[str] = "user"


@dataclass
class FriendsResponse:
    data: List[FriendShortInfo]
    meta: dict


@dataclass
class TransactionInfo:
    id: int
    borrower: UserInfo
    debtor: UserInfo
    amount: Decimal


@dataclass
class ExpenseUserInfo:
    id: int
    user: UserInfo
    lent_amount: Decimal
    debt_amount: Decimal


@dataclass
class ExpenseShortInfo:
    id: int
    owe: Decimal
    owes: Decimal
    amount: Decimal
    currency: str
    settled: bool
    payment: bool
    created_at: str
    date: str
    expense_users: list[ExpenseUserInfo]
    transactions: list[TransactionInfo] = None
    description: Optional[str] = None


@dataclass
class GroupInfo:
    id: int
    user_id: int
    name: str
    kind: str
    amount: Decimal
    simplify_debts: bool
    members: list[FriendShortInfo]
    total: list[TransactionInfo]


@dataclass
class GroupShortInfo:
    id: int
    name: str
    users: List[Union['FriendShortInfo', 'GroupUserInfo']]
    type: Optional[str] = "group"
    owe: Optional[Decimal] = None
    owes: Optional[Decimal] = None
    total: Optional[List[DebtInfo]] = tuple()
    kind: Optional[str] = None


@dataclass
class GroupResponse:
    data: List[GroupShortInfo]
    meta: dict


@dataclass
class ExpenseInfo:
    id: int
    owe: Decimal
    owes: Decimal
    amount: Decimal
    payment: bool
    date: str
    currency: str
    transactions: list[TransactionInfo]
    expense_users: list[ExpenseUserInfo]
    description: Optional[str] = None
    group: Optional[GroupShortInfo] = None


@dataclass
class ExpensesResponse:
    data: List[ExpenseShortInfo]
    meta: dict


@dataclass
class FriendInfo:
    id: int
    username: str
    name: str
    photo_url: str
    amount: Decimal
    default_currency: str
    total: List[DebtInfo]


@dataclass
class FriendsPaginationResponse(PaginationResponse):
    data: list[FriendShortInfo]


@dataclass
class SearchUserPaginationResponse(PaginationResponse):
    data: list[UserInfo]


@dataclass
class AddFriend:
    user_id: int
    friend_id: int

@dataclass
class DeleteFriend:
    user_id: int
    friend_id: int

@dataclass
class UpdateSettings:
    user_id: int
    default_currency: Optional[str] = None
    language: Optional[str] = None


@dataclass
class AddGroup:
    user_id: int
    name: str
    members: Optional[list[int]] = tuple()
    kind: Optional[str] = None


@dataclass
class EditGroup:
    user_id: int
    members: list[int]
    name: str
    simplify_debts: bool


@dataclass
class FeedInfo:
    id: int
    type: str
    created_at: str
    message: dict


@dataclass
class FeedResponse:
    data: List[FeedInfo]
    meta: dict


@dataclass
class Index:
    user_id: int
    page: int
    limit: int


@dataclass
class ActivityUser:
    user_id: int
    activity_id: int

@dataclass
class ExpenseActivityInfo:
    id: int
    isDeleted: bool
    amount: Decimal
    expense_users: list[ExpenseUserInfo]
    description: Optional[str] = None

@dataclass
class ActivityDTO:
    id: int
    activity_type: str
    created_at: str
    data: dict
    user: UserInfo
    expense: ExpenseActivityInfo

@dataclass
class ActivityResponse:
    data: object
    meta: dict

@dataclass
class AuthData:
    init_data_raw: str

@dataclass
class MessageRequest:
    user_id: int
    message: str
    date: int