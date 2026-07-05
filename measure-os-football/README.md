# MEASURE OS Football

MEASURE OS Football is a separate project from the enterprise edition.

## Repository / Deploy

- **GitHub**: same repo as enterprise — `pmwj3333-ns/measureos-site` (`measure-os-football/` subdirectory)
- **Production branch**: `milestone/package-a-phase1` (same as enterprise)
- **Production URL** (after deploy): `/football` or `/measure-os-football/match-setup/v0.1/index.html`
- **Deploy**: push to `milestone/package-a-phase1` → GitHub Actions runs `deploy-measureos` on VPS (requires Actions Secrets), or SSH manually: `deploy-measureos`

## Screens

- Match Setup v0.1: `match-setup/v0.1/index.html`（エントリーポイント）
- Plan v0.1: `plan/v0.1/index.html`
- Operation: `observer/index.html`
- State Engine v0.1: `state-engine/v0.1/`

Future Operation development should update `observer/index.html` and files directly under
`observer/`. Versioned Observer folders are kept as archives.

## Archive

- Observer v0.1: `observer/v0.1/index.html`
- Observer v0.2: `observer/v0.2/index.html`
- Observer v0.3: `observer/v0.3/index.html`
- Observer v0.4: `observer/v0.4/index.html`
- Observer v0.5: `observer/v0.5/index.html`
