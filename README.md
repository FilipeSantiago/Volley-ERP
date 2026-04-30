## Volley ERP Backend

FastAPI backend using Controller / Service / Repository architecture with Google Drive and Google Sheets integrations.

### Current Access Model

- Authentication identity is user-based (`user_id`).
- Authorization is organization/team scoped in Firestore.
- BYOS workspace provisioning is organization-scoped.
- Invited users do not get personal Drive workspaces.

### Run

```bash
uvicorn main:app --reload
# or
python main.py --reload
```

### Google Auth Setup (Local)

```bash
gcloud auth application-default login
```

Set `GOOGLE_AUTH_MODE=adc` in `.env` (default in `.env.example`).

### Test

```bash
.venv/bin/python -m unittest discover -s tests
```
