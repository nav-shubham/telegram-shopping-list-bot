from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, BigInteger, UniqueConstraint, Float
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    telegram_id = Column(BigInteger, primary_key=True, autoincrement=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    lists = relationship("ShoppingList", back_populates="user", cascade="all, delete-orphan")
    histories = relationship("ShoppingHistory", back_populates="user", cascade="all, delete-orphan")

class ListType(Base):
    __tablename__ = "list_types"

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    emoji = Column(String, nullable=False)

    # Relationships
    lists = relationship("ShoppingList", back_populates="list_type")

class ShoppingList(Base):
    __tablename__ = "lists"

    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, ForeignKey("users.telegram_id", ondelete="CASCADE"), nullable=False)
    type_id = Column(Integer, ForeignKey("list_types.id", ondelete="RESTRICT"), nullable=False)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uix_user_list_name"),
    )

    # Relationships
    user = relationship("User", back_populates="lists")
    list_type = relationship("ListType", back_populates="lists")
    items = relationship("Item", back_populates="shopping_list", cascade="all, delete-orphan")

class Item(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True)
    list_id = Column(Integer, ForeignKey("lists.id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=False)
    quantity = Column(Float, default=1.0)
    unit = Column(String, nullable=True)
    is_completed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    shopping_list = relationship("ShoppingList", back_populates="items")

class ShoppingHistory(Base):
    __tablename__ = "shopping_histories"

    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, ForeignKey("users.telegram_id", ondelete="CASCADE"), nullable=False)
    list_name = Column(String, nullable=False)
    list_type = Column(String, nullable=False)
    list_type_emoji = Column(String, nullable=False)
    completion_date = Column(DateTime, default=datetime.utcnow)
    total_items = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="histories")
    items = relationship("ShoppingHistoryItem", back_populates="history", cascade="all, delete-orphan")

class ShoppingHistoryItem(Base):
    __tablename__ = "shopping_history_items"

    id = Column(Integer, primary_key=True)
    history_id = Column(Integer, ForeignKey("shopping_histories.id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=False)
    quantity = Column(Float, default=1.0)
    unit = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    history = relationship("ShoppingHistory", back_populates="items")
