from database import SessionLocal, engine, Base
from models import Customer, Order
from datetime import datetime


Base.metadata.create_all(bind=engine)

db = SessionLocal()


customers = [
    Customer(
        first_name="John",
        last_name="Smith",
        email="john.smith@example.com",
        phone="555-123-4567",
        street="123 Main Street",
        city="Ann Arbor",
        state="MI",
        zip_code="48104",
        country="United States",
        account_created="2025-01-15",
        last_login="2026-07-27 20:43",
        account_status="Active",
        membership_level="Premium"
    ),

    Customer(
        first_name="Sarah",
        last_name="Johnson",
        email="sarah.johnson@example.com",
        phone="555-234-5678",
        street="456 Oak Avenue",
        city="Chicago",
        state="IL",
        zip_code="60614",
        country="United States",
        account_created="2024-08-22",
        last_login="2026-07-25 14:20",
        account_status="Active",
        membership_level="Standard"
    ),

    Customer(
        first_name="Michael",
        last_name="Williams",
        email="michael.williams@example.com",
        phone="555-345-6789",
        street="789 Pine Road",
        city="Dallas",
        state="TX",
        zip_code="75201",
        country="United States",
        account_created="2025-03-10",
        last_login="2026-07-28 09:15",
        account_status="Active",
        membership_level="Premium"
    ),

    Customer(
        first_name="Emily",
        last_name="Davis",
        email="emily.davis@example.com",
        phone="555-456-7890",
        street="321 Maple Lane",
        city="Seattle",
        state="WA",
        zip_code="98101",
        country="United States",
        account_created="2024-11-05",
        last_login="2026-07-20 18:55",
        account_status="Suspended",
        membership_level="Standard"
    ),

    Customer(
        first_name="David",
        last_name="Brown",
        email="david.brown@example.com",
        phone="555-567-8901",
        street="654 Cedar Drive",
        city="Boston",
        state="MA",
        zip_code="02108",
        country="United States",
        account_created="2025-06-18",
        last_login="2026-07-26 11:30",
        account_status="Active",
        membership_level="Enterprise"
    )
]


for customer in customers:
    existing = db.query(Customer).filter(
        Customer.email == customer.email
    ).first()

    if not existing:
        db.add(customer)


db.commit()


print("5 fake customers added!")

db.close()