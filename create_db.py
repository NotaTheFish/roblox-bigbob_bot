# create_db.py
from bot.db import Base, engine

print("⏳ Creating tables in PostgreSQL...")
Base.metadata.create_all(engine)
print("✅ Tables created successfully!")
