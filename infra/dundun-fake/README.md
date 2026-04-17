# dundun-fake

Stateless HTTP fake for the Dundun message API. Dev and E2E only.

## Usage

```
docker compose -f docker-compose.dev.yml up dundun-fake
curl http://localhost:8081/health
curl -X POST http://localhost:8081/messages \
     -H 'Content-Type: application/json' \
     -d '{"thread_id":"t1","content":"hello","user_id":"u1"}'
```

## Environment variables

| Variable    | Values                          | Default         |
|-------------|---------------------------------|-----------------|
| `FAKE_MODE` | `deterministic` \| `stochastic` | `deterministic` |

## Error injection

Send `X-Fake-Force-Error: 500` or `X-Fake-Force-Error: 429` to trigger error responses.
