import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.database import get_db
from app.models.interview import Interview
from app.services import interview_service

gen = get_db()
db = next(gen)
rows = db.query(Interview).filter(Interview.vapi_call_id.isnot(None)).all()
for iv in rows:
    if iv.recording_storage_path and not iv.recording_storage_path.startswith("http"):
        continue  # already archived
    p = interview_service.archive_vapi_recordings(iv.id, iv.vapi_call_id, attempts=1)
    if p.get("audio"):
        iv.recording_storage_path = p["audio"]
        db.commit()
    print(iv.id, p)
gen.close()
