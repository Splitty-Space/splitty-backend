from dataclasses import dataclass
from typing import Optional

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
class FriendShortInfo:
    id: int
    username: str
    name: str
    photo_url: str
    amount: Optional[Decimal] = None
    type: Optional[str] = "user"


@dataclass
class ExpenseShortInfo:
    id: int
    owe: Decimal
    owes: Decimal
    settled: bool
    payment: bool
    description: Optional[str] = None


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
class GroupInfo:
    id: int
    name: str
    amount: Decimal
    simplify_debts: bool
    expenses: list[ExpenseShortInfo]
    members: list[FriendShortInfo]
    total: list[TransactionInfo]


@dataclass
class GroupShortInfo:
    id: int
    owe: Decimal
    owes: Decimal
    name: str
    users: list[FriendShortInfo]
    type: Optional[str] = "group"


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
class AddGroup:
    user_id: int
    name: str


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
    message: dict
