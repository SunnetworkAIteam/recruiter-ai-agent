import os
from dotenv import load_dotenv
import psycopg2

load_dotenv()
conn = psycopg2.connect(os.environ["DATABASE_URL"])
conn.autocommit = True
cur = conn.cursor()
cur.execute("DROP TABLE IF EXISTS jobs CASCADE")
cur.execute("DROP TABLE IF EXISTS candidates CASCADE")
cur.execute("DROP TABLE IF EXISTS alembic_version CASCADE")
print("Dropped. Database is now empty.")