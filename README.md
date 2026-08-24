# SlickBack — Prototype v0.1

This is the first vertical slice of the SIH26143 concept.

## Current pipeline

1. Synthetic SAR/oil detection result
2. Slick geometry
3. Synthetic backward particle drift
4. Probable source region + release window
5. Historical/synthetic AIS candidates
6. Candidate scoring
7. AIS gap + kinematic anomaly flags
8. React + Leaflet investigation dashboard

## Run backend

```bash
cd backend
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

API: http://localhost:8000/docs

## Run frontend

```bash
cd frontend
npm install
npm run dev
```

Open the Vite URL, normally http://localhost:5173.

## Important

The environmental fields, vessel records, and detection confidence are synthetic prototype data. They are deliberately isolated so we can replace them with Sentinel-1, real environmental data, and AIS without rewriting the dashboard.
