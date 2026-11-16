# AI Content Detector

- Run: `run.bat` (Windows) / `./run.sh` → `launcher.py` → http://localhost:5000
- Tests: `python test_detector.py --files --thesis --security` (needs `reportlab`, test-only);
  with the server running: `python test_detector.py --server`. Lint: `ruff check --select F,E9 .`
- Release history: `docs/CHANGELOG.md`; bump `APP_VERSION` in `ai_detector_server.py`.
- Never commit `search_config.json`, `corpus/*`, `*.sqlite3`, `calibration_profile.json` (keys / private theses).
- No auth on any endpoint: keep `host="127.0.0.1"` and the host allowlist + cross-site
  (CSRF) checks in `_block_foreign_requests`. Don't loosen them.
- Scores must be reproducible: no background auto-updating of phrase lists. New AI phrases
  must not fire on ordinary CS/networking vocabulary; run the tests to catch score regressions.
- Plagiarism check does not cover Turnitin's private database; say so in UI/docs.
- `main` is protected (PR + required CI checks): after a tested, working change, push a branch and open a PR without asking.
