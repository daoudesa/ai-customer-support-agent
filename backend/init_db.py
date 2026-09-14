from database import engine, Base
import models


print("Creating database...")

Base.metadata.create_all(bind=engine)

print("Database created!")