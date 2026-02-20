# Anci Ops Suite

## How to run locally

Use Docker Compose from the repository root:

```bash
docker compose -f infra/docker-compose.yml up --build
```

The API will be available at `http://localhost:8000`.

Health check:

```bash
curl http://localhost:8000/api/v1/health
```

Hot food forecast (stub):

```bash
curl "http://localhost:8000/api/v1/hot-food/forecast?store_id=store-001&horizon_days=7"
```
