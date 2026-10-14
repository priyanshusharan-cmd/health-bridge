"""Remove only the uniquely named database created by the frontend integration test."""
import re
import sys
from pathlib import Path
from dotenv import load_dotenv
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
load_dotenv(Path(__file__).resolve().parents[1] / '.env')
from app.store import mongo_client
name = sys.argv[1]
if not re.fullmatch(r'healthbridge_e2e_\d{13}', name):
    raise SystemExit('Refusing non-test database name')
try:
    mongo_client().drop_database(name)
except Exception:
    raise SystemExit('Test database cleanup failed; credentials omitted') from None
