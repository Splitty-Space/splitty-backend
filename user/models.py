import datetime
import enum
from typing import Optional

from sqlalchemy import Column, ForeignKey, types, orm, sql, schema, Table, LargeBinary

from app.orm import Base

user_group_table = Table(
    "user_groups",
    Base.metadata,
    Column("user_id", ForeignKey("users.id"), primary_key=True),
    Column("group_id", ForeignKey("groups.id"), primary_key=True),
    Column("created_at", types.DateTime, default=datetime.datetime.utcnow),
)

friends_association_table = Table(
    "friends",
    Base.metadata,
    Column("user_id", types.Integer, ForeignKey("users.id")),
    Column("friend_id", types.Integer, ForeignKey("users.id")),
    Column("created_at", types.DateTime, default=datetime.datetime.utcnow, nullable=False),
)


class User(Base):
    __tablename__ = "users"

    id: orm.Mapped[int] = orm.mapped_column(types.BigInteger, primary_key=True, unique=True)
    fullname: orm.Mapped[str] = orm.mapped_column(types.Text, nullable=False)
    username: orm.Mapped[str] = orm.mapped_column(types.Text, nullable=True)
    default_currency: orm.Mapped[str] = orm.mapped_column(types.String, nullable=False)
    language: orm.Mapped[str] = orm.mapped_column(types.String, nullable=False)
    photo_url: orm.Mapped[str] = orm.mapped_column(types.Text, nullable=True)
    photo = Column(LargeBinary, nullable=True)
    created_at: orm.Mapped[datetime.datetime] = orm.mapped_column(types.DateTime, default=datetime.datetime.utcnow)

    referred_by: orm.Mapped[Optional[int]] = orm.mapped_column(
        types.Integer, ForeignKey('users.id'), nullable=True
    )

    referrer: orm.Mapped[Optional["User"]] = orm.relationship(
        "User", remote_side=[id], back_populates="referrals"
    )
    referrals: orm.Mapped[list["User"]] = orm.relationship(
        "User", back_populates="referrer"
    )

    referral_code: orm.Mapped[str] = orm.mapped_column(
        types.String(length=36),
        unique=True,
        nullable=True,
    )

    is_admin: orm.Mapped[bool] = orm.mapped_column(types.Boolean, default=sql.false())

    groups: orm.Mapped[list["Group"]] = orm.relationship(
        secondary=user_group_table, back_populates="users", order_by='Group.id.desc()'
    )
    expense_users: orm.Mapped[list["ExpenseUser"]] = orm.relationship(
        "ExpenseUser", back_populates="user"
    )
    activity_user: orm.Mapped[list["ActivityUser"]] = orm.relationship(
        "ActivityUser", back_populates="user"
    )
    feeds: orm.Mapped[list["Feed"]] = orm.relationship(
        "Feed", back_populates="user"
    )
    created_groups: orm.Mapped[list["Group"]] = orm.relationship(
        "Group", back_populates="user"
    )

    friends: orm.Mapped[list["User"]] = orm.relationship(
        "User",
        secondary=friends_association_table,
        primaryjoin=(friends_association_table.c.user_id == id),
        secondaryjoin=(friends_association_table.c.friend_id == id),
        backref="friend_of",
    )
    transactions_as_borrower: orm.Mapped[list["Transaction"]] = orm.relationship(
        "Transaction",
        foreign_keys="[Transaction.borrower_id]",
        back_populates="borrower"
    )
    transactions_as_debtor: orm.Mapped[list["Transaction"]] = orm.relationship(
        "Transaction",
        foreign_keys="[Transaction.debtor_id]",
        back_populates="debtor"
    )


class Group(Base):
    __tablename__ = "groups"

    id: orm.Mapped[int] = orm.mapped_column(types.Integer, primary_key=True)
    name: orm.Mapped[str] = orm.mapped_column(types.VARCHAR, nullable=False)
    kind: orm.Mapped[str] = orm.mapped_column(types.String)
    user_id: orm.Mapped[int] = orm.mapped_column(
        types.Integer, schema.ForeignKey("users.id"), nullable=False
    )
    simplify_debts: orm.Mapped[bool] = orm.mapped_column(types.Boolean, nullable=False, default=False)
    created_at: orm.Mapped[datetime.datetime] = orm.mapped_column(types.DateTime, default=datetime.datetime.utcnow)
    user: orm.Mapped["User"] = orm.relationship(back_populates="created_groups")

    users: orm.Mapped[list["User"]] = orm.relationship(
        secondary=user_group_table, back_populates="groups"
    )
    expenses: orm.Mapped[list["Expense"]] = orm.relationship(
        back_populates="group",
    )


class ExpenseUser(Base):
    __tablename__ = "expense_users"

    id: orm.Mapped[int] = orm.mapped_column(types.Integer, primary_key=True)
    user_id: orm.Mapped[int] = orm.mapped_column(
        types.Integer, schema.ForeignKey("users.id"), nullable=False
    )
    expense_id: orm.Mapped[int] = orm.mapped_column(
        types.Integer, schema.ForeignKey("expenses.id"), nullable=False
    )

    lent_amount: orm.Mapped[float] = orm.mapped_column(types.DECIMAL, nullable=False)
    debt_amount: orm.Mapped[float] = orm.mapped_column(types.DECIMAL, nullable=False)

    expense: orm.Mapped["Expense"] = orm.relationship(back_populates="expense_users")
    user: orm.Mapped["User"] = orm.relationship(back_populates="expense_users")

    def to_dict(self):
        return {
            "user_id": self.user_id,
            "expense_id": self.expense_id,
            "lent_amount": float(self.lent_amount),  # Convert Decimal to float
            "debt_amount": float(self.debt_amount),  # Convert Decimal to float
        }


class Transaction(Base):
    __tablename__ = "transactions"

    id: orm.Mapped[int] = orm.mapped_column(types.Integer, primary_key=True)
    debtor_id: orm.Mapped[int] = orm.mapped_column(
        types.Integer, schema.ForeignKey("users.id"), nullable=False
    )
    borrower_id: orm.Mapped[int] = orm.mapped_column(
        types.Integer, schema.ForeignKey("users.id"), nullable=False
    )
    expense_id: orm.Mapped[int] = orm.mapped_column(
        types.Integer, schema.ForeignKey("expenses.id"), nullable=True
    )
    settled: orm.Mapped[bool] = orm.mapped_column(types.Boolean, default=False)
    created_at: orm.Mapped[datetime.datetime] = orm.mapped_column(types.DateTime, default=datetime.datetime.utcnow)

    amount: orm.Mapped[float] = orm.mapped_column(types.DECIMAL, nullable=False)

    expense: orm.Mapped["Expense"] = orm.relationship(back_populates="transactions")
    borrower: orm.Mapped["User"] = orm.relationship("User", foreign_keys=[borrower_id],
                                                    back_populates="transactions_as_borrower")

    debtor: orm.Mapped["User"] = orm.relationship("User", foreign_keys=[debtor_id],
                                                  back_populates="transactions_as_debtor")

    def to_dict(self):
        return {
            "debtor_id": self.debtor_id,
            "borrower_id": self.borrower_id,
            "expense_id": self.expense_id,
            "settled": self.settled,
            "amount": float(self.amount),  # Convert Decimal to float
        }


class Expense(Base):
    __tablename__ = "expenses"

    id: orm.Mapped[int] = orm.mapped_column(types.Integer, primary_key=True)
    description: orm.Mapped[str] = orm.mapped_column(types.String, nullable=True)

    payment: orm.Mapped[bool] = orm.mapped_column(types.Boolean)
    isDeleted: orm.Mapped[bool] = orm.mapped_column(types.Boolean, default=False)
    group_id: orm.Mapped[int] = orm.mapped_column(
        types.Integer, schema.ForeignKey("groups.id", ondelete="SET NULL"), nullable=True
    )
    amount: orm.Mapped[float] = orm.mapped_column(types.DECIMAL, nullable=False)
    currency: orm.Mapped[str] = orm.mapped_column(types.String, nullable=False)
    created_at: orm.Mapped[datetime.datetime] = orm.mapped_column(types.DateTime, default=datetime.datetime.utcnow)
    date: orm.Mapped[datetime.datetime] = orm.mapped_column(types.DateTime, default=datetime.datetime.utcnow)

    expense_users: orm.Mapped[list["ExpenseUser"]] = orm.relationship(
        back_populates="expense",
        cascade="all, delete-orphan"
    )
    transactions: orm.Mapped[list["Transaction"]] = orm.relationship(
        back_populates="expense",
        cascade="all, delete-orphan",
        lazy='subquery'
    )
    group: orm.Mapped["Group"] = orm.relationship(back_populates="expenses")

    # Convert object to a dictionary
    def to_dict(self):
        return {
            "id": self.id,
            "description": self.description,
            "payment": self.payment,
            "group_id": self.group_id,
            "amount": float(self.amount),  # Convert to float if it's a Decimal
            "currency": self.currency,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "date": self.date.isoformat() if self.date else None,
            "expense_users": [expense_user.to_dict() for expense_user in self.expense_users],
            "transactions": [transaction.to_dict() for transaction in self.transactions],
            "group": self.group.to_dict() if self.group else None,  # Handle group as an object
        }


class Feed(Base):
    __tablename__ = "feeds"

    id: orm.Mapped[int] = orm.mapped_column(types.Integer, primary_key=True)
    user_id: orm.Mapped[int] = orm.mapped_column(
        types.Integer, schema.ForeignKey("users.id"), nullable=False
    )
    created_at: orm.Mapped[datetime.datetime] = orm.mapped_column(types.DateTime, default=datetime.datetime.utcnow)

    message: orm.Mapped[dict] = orm.mapped_column(types.JSON, nullable=False)
    type: orm.Mapped[str] = orm.mapped_column(types.String, nullable=False)

    user: orm.Mapped["User"] = orm.relationship(back_populates="feeds")

class ActivityType(enum.Enum):
    EXPENSE_CREATED = "EXPENSE_CREATED"
    EXPENSE_EDITED = "EXPENSE_EDITED"
    EXPENSE_DELETED = "EXPENSE_DELETED"
    PAYMENT_CREATED = "PAYMENT_CREATED"
    PAYMENT_EDITED = "PAYMENT_EDITED"
    PAYMENT_DELETED = "PAYMENT_DELETED"

class Activity(Base):
    __tablename__ = "activity"

    id: orm.Mapped[int] = orm.mapped_column(types.Integer, primary_key=True)
    # activity_type: orm.Mapped[str] = orm.mapped_column(types.Enum(ActivityType), nullable=False)
    activity_type: orm.Mapped[str] = orm.mapped_column(types.String, nullable=False)
    performed_by_user_id: orm.Mapped[int] = orm.mapped_column(
        types.Integer, schema.ForeignKey("users.id"), nullable=False
    )
    expenses_id: orm.Mapped[int] = orm.mapped_column(
        types.Integer, schema.ForeignKey("expenses.id"), nullable=False
    )
    created_at: orm.Mapped[datetime.datetime] = orm.mapped_column(types.DateTime, default=datetime.datetime.utcnow)
    data: orm.Mapped[dict] = orm.mapped_column(types.JSON, nullable=False)
    activity_user: orm.Mapped[list["ActivityUser"]] = orm.relationship(
        back_populates="activity",
        cascade="all, delete-orphan"
    )


class ActivityUser(Base):
    __tablename__ = "activity_user"

    id: orm.Mapped[int] = orm.mapped_column(types.Integer, primary_key=True)
    user_id: orm.Mapped[int] = orm.mapped_column(
        types.Integer, schema.ForeignKey("users.id"), nullable=False
    )
    activity_id: orm.Mapped[int] = orm.mapped_column(
        types.Integer, schema.ForeignKey("activity.id"), nullable=False
    )
    activity: orm.Mapped["Activity"] = orm.relationship(back_populates="activity_user")
    user: orm.Mapped["User"] = orm.relationship(back_populates="activity_user")
