from dataclasses import dataclass
from typing import Optional

from core.dtos import PaginationResponse
from decimal import Decimal

@dataclass
class CreateUser:
    user_id: int
    username: str
    name: str
    photo_url: str

@dataclass
class CreateExpensePayer:
    user_id: int
    amount: Decimal

@dataclass
class CreateTransaction:
    debtor_id: int
    borrower_id: int
    amount: Decimal

@dataclass
class CreateExpense:
    expense_payers: list[CreateExpensePayer]
    transactions: list[CreateTransaction]
    data: dict
    description: Optional[str] = None
    group_id: Optional[int] = None

@dataclass
class EditExpense:
    user_id: int
    expense_payers: list[CreateExpensePayer]
    transactions: list[CreateTransaction]
    data: dict
    description: Optional[str] = None

@dataclass
class UserInfo:
    id: int
    fullname: str
    photo_url: str
    username: str


@dataclass
class FriendShortInfo:
    id: int
    username: str
    name: str
    photo_url: str
    amount: Decimal
    type: Optional[str] = "user"

@dataclass
class ExpenseShortInfo:
    id: int
    owe: Decimal
    owes: Decimal
    description: Optional[str] = None


@dataclass
class TransactionInfo:
    id: int
    borrower: UserInfo
    debtor: UserInfo
    amount: Decimal


@dataclass
class ExpenseInfo:
    id: int
    owe: Decimal
    owes: Decimal
    data: dict
    transactions: list[TransactionInfo]
    description: Optional[str] = None


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
class GroupShortInfo:
    id: int
    owe: Decimal
    owes: Decimal
    name: str
    users: list[FriendShortInfo]
    type: Optional[str] = "group"

@dataclass
class GroupInfo:
    id: int
    name: str
    amount: Decimal
    members: list[FriendShortInfo]

@dataclass
class AddGroup:
    user_id: int
    name: str

@dataclass
class EditGroup:
    user_id: int
    members: list[int]
    name: str
