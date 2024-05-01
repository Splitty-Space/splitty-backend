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
        secondary=user_group_table, back_populates="users"
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

    users: orm.Mapped[list["User"]] = orm.relationship(
        secondary=user_group_table, back_populates="groups"
    )


class ExpensePayer(Base):
    __tablename__ = "expense_payers"

    id: orm.Mapped[int] = orm.mapped_column(types.Integer, primary_key=True)
    user_id: orm.Mapped[int] = orm.mapped_column(
        types.Integer, schema.ForeignKey("users.id"), nullable=False
    )
    expense_id: orm.Mapped[int] = orm.mapped_column(
        types.Integer, schema.ForeignKey("expenses.id"), nullable=False
    )

    amount: orm.Mapped[float] = orm.mapped_column(types.DECIMAL, nullable=False)

    expense: orm.Mapped["Expense"] = orm.relationship(back_populates="expense_payers")
    currency: orm.Mapped[str] = orm.mapped_column(types.String, nullable=False)

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
        types.Integer, schema.ForeignKey("expenses.id"), nullable=False
    )

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

    # isSettled: orm.Mapped[bool] = orm.mapped_column(
    #    types.Boolean,
    # )
    # user_id: orm.Mapped[int] = orm.mapped_column(types.Integer, schema.ForeignKey("users.id"), nullable=True)
    group_id: orm.Mapped[int] = orm.mapped_column(
        types.Integer, schema.ForeignKey("groups.id"), nullable=True
    )
    data: orm.Mapped[dict] = orm.mapped_column(types.JSON, nullable=False, default={})

    expense_payers: orm.Mapped[list["ExpensePayer"]] = orm.relationship(
        back_populates="expense",
        cascade="all, delete-orphan"
    )
    transactions: orm.Mapped[list["Transaction"]] = orm.relationship(
        back_populates="expense",
        cascade="all, delete-orphan"
    )
