from sqlalchemy import Column, Integer, String, Float, ForeignKey
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