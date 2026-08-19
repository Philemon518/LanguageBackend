.PHONY: install backend mobile test seed audio

install:
	cd backend && python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
	cd mobile && flutter pub get

backend:
	cd backend && . .venv/bin/activate && uvicorn app.main:app --reload --port 8000

mobile:
	cd mobile && flutter run --dart-define=API_BASE_URL=http://127.0.0.1:8000

test:
	cd backend && . .venv/bin/activate && pytest tests/ -v
	cd mobile && flutter test
	python3 content/scripts/validate_check.py

seed:
	cd backend && . .venv/bin/activate && python ../content/scripts/import_seed.py

audio:
	cd backend && . .venv/bin/activate && python ../content/scripts/generate_audio.py Kiki
