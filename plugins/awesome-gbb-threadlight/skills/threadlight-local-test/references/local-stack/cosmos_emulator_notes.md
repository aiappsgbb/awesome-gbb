# Cosmos DB Emulator — local-test gotchas

The `mcr.microsoft.com/cosmosdb/linux/azure-cosmos-emulator:vnext-preview`
image ("vnext") is the right one to use as of 2026 — it's the
reactive/Linux-native emulator that boots in ~30s and supports the
data + management APIs at `https://localhost:8081`.

## SSL — the #1 blocker

The emulator ships a self-signed cert. Python clients will fail with
`SSLError: self-signed certificate` unless one of:

1. **Disable verify on the client** (recommended for local-test only):

   ```python
   from azure.cosmos import CosmosClient
   client = CosmosClient(endpoint, credential=key, connection_verify=False)
   ```

   Set `COSMOS_VERIFY_SSL=false` in `.env.local` and read it in the
   PoC's Cosmos factory:

   ```python
   verify = os.environ.get("COSMOS_VERIFY_SSL", "true").lower() != "false"
   client = CosmosClient(endpoint, credential=key, connection_verify=verify)
   ```

2. **Trust the emulator cert system-wide** (more invasive, but works
   with code that doesn't expose `connection_verify`):

   ```powershell
   # Pull the cert out of the running container
   docker exec tl-cosmos-emulator cat /tmp/cosmos/appdata/.system/profiles/Client/AppData/Local/CosmosDBEmulator/CosmosDBEmulator.crt > emulator.crt

   # Windows: install into Trusted Root Certification Authorities
   Import-Certificate -FilePath emulator.crt -CertStoreLocation Cert:\LocalMachine\Root
   ```

   Don't forget to remove it when you're done: `Remove-Item Cert:\LocalMachine\Root\<thumbprint>`.

## ARM (M-series Mac, Windows on ARM)

The `vnext-preview` image **is** multi-arch as of late 2025 and works
on ARM. The legacy `windowsservercore-1809` image does NOT. If you
get `exec format error` on `docker compose up`, you accidentally
pulled the legacy image — pin to `vnext-preview` explicitly.

## Ports

Exposed in compose:

| Port | What | Why |
|------|------|-----|
| 8081 | Data + management API + explorer | Primary client traffic |
| 10250-10256 | Legacy gateway range | Some older SDK versions probe these on connection negotiation |

If you see `connection refused on port 10251`, your Cosmos SDK is
trying to use the gateway protocol and these ports aren't exposed.
The compose file ships them all.

## Performance

The vnext emulator is much faster than the legacy Windows image but
still ~10x slower than real Cosmos. Bulk-seed scripts that work in
prod (parallel upserts via `asyncio.gather`) can saturate the local
emulator and trigger `429 TooManyRequests`. For the seed script,
serialize + add a 50ms sleep between batches.

## Persistence

`AZURE_COSMOS_EMULATOR_ENABLE_DATA_PERSISTENCE=true` + the
`cosmos-data` named volume in compose persist data across
`down`/`up`. Run `docker compose down -v` to wipe (the `-v` removes
volumes).

## Authentication

The emulator only accepts the well-known emulator key (it's the same
across every install — this is intentional, not a leaked secret):

```
C2y6yDjf5/R+ob0N8A7Cgv30VRDJIWEHLM+4QDU5DE2nQ9nDuVTqobD4b8mGGyPMbIZnqyMsEcaGQy67XIw/Jw==
```

`DefaultAzureCredential` does NOT work against the emulator —
always pass the key explicitly. This means your PoC's Cosmos factory
needs a small branch:

```python
def cosmos_client():
    endpoint = os.environ["COSMOS_ENDPOINT"]
    if "localhost" in endpoint or "127.0.0.1" in endpoint:
        return CosmosClient(endpoint, credential=os.environ["COSMOS_KEY"], connection_verify=False)
    return CosmosClient(endpoint, credential=DefaultAzureCredential())
```

This branch is what makes the same code path work both locally and
in production.

## Health check delay

The emulator's `start_period: 60s` health check is conservative —
the vnext image typically reaches healthy in 25-40s. If your
seed/smoke script races the readiness, sleep an extra ~10s after
`docker compose up -d` before invoking, or poll the explorer URL.
