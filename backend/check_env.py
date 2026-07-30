import os
import urllib.parse
from dotenv import load_dotenv

load_dotenv()
url = os.environ["DATABASE_URL"]
parsed = urllib.parse.urlparse(url)

print("Scheme:", parsed.scheme)
print("Username:", parsed.username)
print("Password length:", len(parsed.password) if parsed.password else 0)
print("Password (masked, showing length):", "*" * len(parsed.password) if parsed.password else None)
print("Password repr (shows hidden/whitespace chars):", repr(parsed.password))
print("Host:", parsed.hostname)
print("Port:", parsed.port)
print("Database:", parsed.path)