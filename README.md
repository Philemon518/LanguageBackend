# Canto — Cantonese Language Learning App

Mobile-first Cantonese learning with a 40-lesson Beginner road, fixed-screen listening-first exercises, four-skill progress, a local FastAPI backend, SQLite, and Qwen realtime speech.

## Structure

- `backend/` — FastAPI API, Qwen gateway, account and progress services
- `content/` — Versioned curriculum seeds and generation scripts
- Frontend: [Philemon518/LanguageFrontend](https://github.com/Philemon518/LanguageFrontend)

## Quick start

### Backend

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill Qwen key if you want audio/chat
uvicorn app.main:app --reload --port 8000
```

## Railway deployment

The backend repository is deployable from its root `Dockerfile`.

1. Create a Railway service from the backend GitHub repository.
2. Add Railway PostgreSQL and expose its `DATABASE_URL` to the service.
3. Set `JWT_SECRET` to a long random value and set `CORS_ORIGINS` to the
   deployed frontend URL.
4. Set `DASHSCOPE_API_KEY` to enable speaking and conversation features.
5. Deploy and copy the generated backend domain.

Deploy the frontend repository as a second Railway service. Set its
`API_BASE_URL` build variable to the backend's public HTTPS URL. The result is
a mobile-friendly Flutter web/PWA. Native iOS and Android distribution still
requires App Store and Play Store builds.

### Content import

```bash
cd backend
source .venv/bin/activate
python ../content/scripts/import_seed.py
python ../content/scripts/generate_audio.py \
  --model qwen3-tts-flash-realtime \
  --voice Kiki \
  --replace-all
```

Audio generation is content-addressed and resumable. Re-running the command
reuses every valid cached WAV; use `--retry-failed` to retry only failed clips.

## Environment

See `backend/.env.example`.
