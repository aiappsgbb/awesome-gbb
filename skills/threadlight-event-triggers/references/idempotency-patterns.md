# Idempotency patterns

Every threadlight trigger receiver MUST be idempotent. This file captures
the three canonical backing stores for the dedup table — pick one based on
your throughput and cost profile.

## Decision table

| Backing store | Throughput | Cost | Best for |
|---------------|------------|------|----------|
| **Cosmos DB** | High (10K RU/s+) | $$ | Default — agent already uses Cosmos |
| **Storage Table** | Medium | $ | Lowest cost; slower than Cosmos |
| **Redis (Azure Cache)** | Very high | $$$ | Sub-ms dedup for 10K+ events/sec |

For most threadlight processes: **Cosmos DB** is the right default. The
agent already provisions Cosmos (case state, audit trail, agent memory),
so the dedup table piggybacks on that with a dedicated `trigger_idempotency`
container.

## Cosmos pattern (default)

### Container shape

| Property | Value |
|----------|-------|
| Container name | `trigger_idempotency` |
| Partition key | `/id` |
| TTL | `null` per-item (set per insertion based on dedup window) |
| Throughput | 400 RU/s (dedicated) — enough for ~100 receivers/min |
| Indexing | id (default) — no other fields needed for lookup |

### Code shape

```python
from datetime import datetime, timedelta, timezone
from azure.cosmos.aio import CosmosClient
from azure.cosmos import exceptions

class IdempotencyStore:
    def __init__(self, container, dedup_window: timedelta):
        self.container = container
        self.window = dedup_window

    async def is_already_processed(self, key: str) -> bool:
        try:
            entry = await self.container.read_item(item=key, partition_key=key)
            seen_at = datetime.fromisoformat(entry["seen_at"])
            return (datetime.now(timezone.utc) - seen_at) < self.window
        except exceptions.CosmosResourceNotFoundError:
            return False

    async def mark_processed(self, key: str):
        await self.container.upsert_item({
            "id": key,
            "seen_at": datetime.now(timezone.utc).isoformat(),
            "ttl": int(self.window.total_seconds() * 2),  # auto-cleanup
        })
```

Use `ttl` per-item so the table self-cleans — old entries fall off after 2x
the dedup window without operator intervention.

## Storage Table pattern

For very low-throughput receivers where every $ counts. Same logical
shape; replace Cosmos client with `azure.data.tables.TableClient`.

## Redis pattern

For sub-ms dedup. Use `SETNX` with PX (millisecond expiry):

```python
async def is_already_processed(self, key: str) -> bool:
    # SETNX returns True if key didn't exist (i.e. first time we've seen it)
    was_new = await self.redis.set(key, "1", nx=True, px=int(self.window.total_seconds() * 1000))
    return not was_new
```

## Idempotency key derivation (decision tree)

```
Does the source provide a unique message ID?
├── Service Bus → use MessageId
├── Event Grid → use event.id
├── HTTP webhook → use sender's X-Request-Id header (require it)
└── Cron job → use ISO date string (so re-running today is a no-op)

If none → derive from payload hash (canonical-JSON + SHA-256)
          dedup_window = source's natural retry window
```

## Replay scenarios

When the customer replays events (post-incident), you need to either:

- **Bypass dedup**: provide a `--bypass-dedup` flag on receiver entry points
- **Time-shift dedup window**: temporarily shrink the window so old entries
  fall off and re-process

Document both in the receiver's README.
