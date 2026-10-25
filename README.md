# Traffic Management System (Simulation): UE24CS341A, Problem 16

Adaptive signal control, vehicle detection, simulation and admin tools for a simulated city intersection.
Python 3.11+, FastAPI, SQLAlchemy (SQLite), Jinja2 pages, pytest.

| Role | Owner | Modules |
|---|---|---|
| Product Owner | Manoj | `signal_control/` (F-001/002/003), operator console page |
| Tech Lead | Naveen | app shell, `simulation/` (F-009/010/011), UI shell |
| QA Lead | Likhita | `detection/` (F-006/007/008), integration suite, detection page |
| Scrum Master | Roshini | `admin/` (F-018/019), `infra/tls.py`, CI/CD, admin page |

## Run it
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python scripts/run_server.py            # http://127.0.0.1:8000  (docs at /docs)
python scripts/run_https.py             # https://127.0.0.1:8443 (TLS 1.2+ only, self-signed cert)
python data/detection_samples/generate_feed.py --minutes 5   # post synthetic sensor events
pytest                                   # whole suite
```
Demo sign-ins: `operator/operator123`, `analyst/analyst123`, `admin/admin12345`. Sensors send `X-API-Key: sensor-demo-key`.
Copy `.env.example` to `.env` to change settings.

## Layout
`src/tms/{common,admin,detection,signal_control,simulation,infra,ui}`, `tests/{unit,integration,security,performance}`,
`data/` (sample networks, detection samples), `docs/` (ADR, deviations, test cases, traceability).
`incident/` and `reporting/` are Sprint 2.

## Working rules
One branch per issue, one PR per assignee, owners review and merge, CI (GitHub Actions) must be green. PR template in `.github/`.
