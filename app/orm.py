import sqlalchemy
from sqlalchemy import orm
from config import DATABASE_URL


engine = sqlalchemy.create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False}
)

Session = orm.sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(orm.DeclarativeBase):
    def to_dict(self):
        return {field.name: getattr(self, field.name) for field in self.__table__.c}
