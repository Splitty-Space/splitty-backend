import datetime

from sqlalchemy import Column, ForeignKey, types, orm, sql, schema, Table
from sqlalchemy.orm import mapper

from app.orm import Base


user_group_table = Table(
    "user_groups",
    Base.metadata,
    Column("user_id", ForeignKey("users.id"), primary_key=True),
    Column("group_id", ForeignKey("groups.id"), primary_key=True),
)


friends_association_table = Table(
    "friends",
    Base.metadata,
    Column("user_id", types.Integer, ForeignKey("users.id")),
    Column("friend_id", types.Integer, ForeignKey("users.id")),
)

class User(Base):
    __tablename__ = "users"

    id: orm.Mapped[int] = orm.mapped_column(types.Integer, primary_key=True, unique=True)
    fullname: orm.Mapped[str] = orm.mapped_column(types.Text, nullable=False)
    username: orm.Mapped[str] = orm.mapped_column(types.Text, nullable=True)
    photo_url: orm.Mapped[str] = orm.mapped_column(types.Text, nullable=True)

    is_admin: orm.Mapped[bool] = orm.mapped_column(types.Boolean, default=sql.false())

    groups: orm.Mapped[list["Group"]] = orm.relationship(
        secondary=user_group_table, back_populates="users", order_by='Group.id.desc()'
    )
    expense_users: orm.Mapped[list["ExpenseUser"]] = orm.relationship(
        "ExpenseUser", back_populates="user"
    )
    feeds: orm.Mapped[list["Feed"]] = orm.relationship(
        "Feed", back_populates="user"
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
    name: orm.Mapped[str] = orm.mapped_column(types.Text, nullable=False)
    simplify_debts: orm.Mapped[bool] = orm.mapped_column(types.Boolean, nullable=False, default=False)

    users: orm.Mapped[list["User"]] = orm.relationship(
        secondary=user_group_table, back_populates="groups"
    )
    expenses: orm.Mapped[list["Expense"]] = orm.relationship(
        back_populates="group",
        cascade="all, delete-orphan"
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

    currency: orm.Mapped[str] = orm.mapped_column(types.String, nullable=False)
    amount: orm.Mapped[float] = orm.mapped_column(types.DECIMAL, nullable=False)

    expense: orm.Mapped["Expense"] = orm.relationship(back_populates="transactions")
    borrower: orm.Mapped["User"] = orm.relationship("User", foreign_keys=[borrower_id],
                                                    back_populates="transactions_as_borrower")

    debtor: orm.Mapped["User"] = orm.relationship("User", foreign_keys=[debtor_id],
                                                  back_populates="transactions_as_debtor")


class Expense(Base):
    __tablename__ = "expenses"

    id: orm.Mapped[int] = orm.mapped_column(types.Integer, primary_key=True)
    description: orm.Mapped[str] = orm.mapped_column(types.String)

    payment: orm.Mapped[bool] = orm.mapped_column(types.Boolean)
    group_id: orm.Mapped[int] = orm.mapped_column(
        types.Integer, schema.ForeignKey("groups.id"), nullable=True
    )
    amount: orm.Mapped[float] = orm.mapped_column(types.DECIMAL, nullable=False)

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


class Feed(Base):
    __tablename__ = "feeds"

    id: orm.Mapped[int] = orm.mapped_column(types.Integer, primary_key=True)
    user_id: orm.Mapped[int] = orm.mapped_column(
        types.Integer, schema.ForeignKey("users.id"), nullable=False
    )

    message: orm.Mapped[dict] = orm.mapped_column(types.JSON, nullable=False)
    type: orm.Mapped[str] = orm.mapped_column(types.String, nullable=False)

    user: orm.Mapped["User"] = orm.relationship(back_populates="feeds")
