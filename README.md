## Volley ERP Backend

FastAPI backend using Controller / Service / Repository architecture with Google Drive and Google Sheets integrations.

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
python -m unittest discover -s tests
```
