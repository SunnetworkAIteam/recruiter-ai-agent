import getpass
import re
import urllib.parse

project_ref = input("Supabase project ref (e.g. qdcedhjoyaouypjfncjb): ").strip()
pooler_host = input("Pooler host (e.g. aws-1-ap-northeast-1.pooler.supabase.com): ").strip()
password = getpass.getpass("Database password (won't be shown on screen): ")

username = f"postgres.{project_ref}"
encoded_password = urllib.parse.quote(password, safe="")
new_url = f"DATABASE_URL=postgresql://{username}:{encoded_password}@{pooler_host}:5432/postgres"

with open(".env", "r") as f:
    lines = f.readlines()

replaced = False
for i, line in enumerate(lines):
    if line.startswith("DATABASE_URL="):
        lines[i] = new_url + "\n"
        replaced = True
        break

if not replaced:
    lines.append(new_url + "\n")

with open(".env", "w") as f:
    f.writelines(lines)

print("\nDone. DATABASE_URL updated in .env (password hidden below):")
print(re.sub(r":[^:@]+@", ":****@", new_url))