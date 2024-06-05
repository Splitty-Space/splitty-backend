from dataclasses import dataclass
from typing import Optional, List, Union

from core.dtos import PaginationResponse
from decimal import Decimal


@dataclass
class CreateUser:
    user_id: int
    username: str
    fullname: str
    photo_url: str


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
    default_currency: Optional[str] = None
    language: Optional[str] = None


@dataclass
class GroupUserInfo:
    id: int
    username: str
    name: str
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
class ExpenseShortInfo:
    id: int
    owe: Decimal
    owes: Decimal
    settled: bool
    payment: bool
    first_transaction: Optional[TransactionInfo] = None
    description: Optional[str] = None


@dataclass
class ExpenseUserInfo:
    id: int
    user: UserInfo
    lent_amount: Decimal
    debt_amount: Decimal


@dataclass
class GroupInfo:
    id: int
    name: str
    amount: Decimal
    simplify_debts: bool
    expenses: list[ExpenseShortInfo]
    expenses: list[ExpenseShortInfo]
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
    transactions: list[TransactionInfo]
    expense_users: list[ExpenseUserInfo]
    description: Optional[str] = None
    group: Optional[GroupShortInfo] = None


@dataclass
class FriendInfo:
    id: int
    username: str
    name: str
    photo_url: str
    amount: Decimal
    expenses: list[ExpenseShortInfo]


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
class UpdateSettings:
    user_id: int
    default_currency: Optional[str] = None
    language: Optional[str] = None


@dataclass
class AddGroup:
    user_id: int
    name: str
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
