# Deploying

**Host in the Netherlands or West Europe.** The Sentinel archives are served from Amsterdam, and almost all of a cold run's time is downloading from them. Use a machine with at least 4 GB of RAM and a permanent disk, because sealed evidence lives on disk and every QR verify link depends on it. Keep it to one process: rate limits, the run queue and the scheduler are in memory.

## Option A: a VM (recommended)

Azure for Students, an Ubuntu VM in West Europe, size B2s or larger, ports 22, 80 and 443 open. Then:

```bash
git clone -b build/fasalsaakshi https://github.com/AnirudhSinghRajora/Forge
cd Forge
sudo GEMINI_API_KEY=your-key ./deploy/run-on-vm.sh
```

It prints the live URL. Without a domain it uses `<ip>.sslip.io`, with HTTPS from Let's Encrypt.

## After every deploy or engine change

Run this from any machine. It creates the demo cases with real runs and performs each full check once, so a QR scan shows a stored result immediately:

```bash
cd backend
uv run python scripts/warm_demo.py --base-url https://your-url --verify
```

Check that `GET /api/health` shows `"gemini": true` if a key was set. On the server, test Gemini with:

```bash
docker exec -it fasalsaakshi .venv/bin/python -m app.agent.llm --selftest
```

## Limits to set

| Variable | Default | Change it when |
|---|---|---|
| `RATE_INVESTIGATIONS_PER_HOUR` | 12 per IP | Judges share one network and many will run new pins |
| `RATE_VERIFY_PER_HOUR` | 3 per IP | The same |

Pass them with `-e` in `run-on-vm.sh`. Do not add `--workers`.

## Backups

Everything that matters is in the `fasalsaakshi-data` Docker volume. Removing that volume breaks every QR link.
