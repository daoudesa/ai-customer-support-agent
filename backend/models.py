from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Float, ForeignKey
from sqlalchemy.orm import relationship
from database import Base


class Customer(Base):

    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)

    first_name = Column(String)
    last_name = Column(String)

    email = Column(String, unique=True, index=True)
    phone = Column(String)

    street = Column(String)
    city = Column(String)
    state = Column(String)
    zip_code = Column(String)
    country = Column(String)

    account_created = Column(String)
    last_login = Column(String)

    account_status = Column(String)
    membership_level = Column(String)

    orders = relationship(
        "Order",
        back_populates="customer"
    )

    messages = relationship(
        "Message",
        back_populates="customer",
        order_by="Message.created_at",
        cascade="all, delete-orphan"
    )


class Order(Base):

    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)

    order_number = Column(String)
    product = Column(String)

    price = Column(Float)

    status = Column(String)
    tracking_number = Column(String)
    order_date = Column(String)

    customer_id = Column(
        Integer,
        ForeignKey("customers.id")
    )

    customer = relationship(
        "Customer",
        back_populates="orders"
    )


class Message(Base):
    """One turn of conversation, owned by a customer.

    Conversation history used to be a single module-level list shared by every
    request, so one customer's messages -- and the account details quoted in
    them -- were replayed into the next customer's prompt. Keying history to
    the customer row fixes the leak and survives a restart.
    """

    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)

    role = Column(String)          # "user" or "assistant"
    content = Column(String)

    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    customer_id = Column(
        Integer,
        ForeignKey("customers.id"),
        index=True
    )

    customer = relationship(
        "Customer",
        back_populates="messages"
    )