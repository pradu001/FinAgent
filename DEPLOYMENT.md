Here is the complete, updated `DEPLOYMENT.md` file in a single markdown block, ready for you to copy and paste directly into VS Code:

```markdown
# Deployment Guide — FinAgent

## Prerequisites

- Docker and Docker Compose
- Python 3.11+
- `uv` (Astral's fast Python package installer)
- API keys: OpenAI, Tavily, LangSmith
- AWS account (for production)

---

## Local Development

### 1. Clone and configure

```bash
git clone [https://github.com/pradyumna-001/FinAgent.git](https://github.com/pradyumna-001/FinAgent.git)
cd FinAgent/finagent
cp .env.example .env

```

Edit `.env` with your API keys:

```env
# LLM
OPENAI_API_KEY=sk-...
OPENAI_MODEL_FAST=gpt-4o-mini        # MacroAgent, CompanyAgent
OPENAI_MODEL_SMART=gpt-4o            # RiskAgent, EditorAgent

# Web search
TAVILY_API_KEY=tvly-...

# Observability
LANGCHAIN_API_KEY=ls-...
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=finagent

# Database
DATABASE_URL=postgresql+asyncpg://finagent:finagent@localhost:5432/finagent
REDIS_URL=redis://localhost:6379/0

# Security
SECRET_KEY=your-secret-key-here

```

### 2. Start services

```bash
docker compose up -d

```

This starts:

* PostgreSQL 16 with pgvector and Apache AGE extensions
* Redis with AOF persistence enabled
* Celery worker
* Celery Beat scheduler

### 3. Install Dependencies & Run migrations

To install dependencies locally on your host machine:

```bash
uv sync

```

To run your database migrations:

```bash
docker compose exec api alembic upgrade head

```

### 4. Verify setup

```bash
curl http://localhost:8000/health
# Expected: {"status": "ok", "db": "ok", "redis": "ok", "age": "ok"}

```

### 5. Run tests

You can execute tests locally on your host:

```bash
uv run pytest

```

Or inside the API container:

```bash
docker compose exec api pytest tests/ -v

```

---

## Running the Pipeline Manually

```bash
# Trigger pipeline for a specific manager and company list
docker compose exec api python -m app.workers.pipeline \
  --manager-id 1 \
  --empresas PETR4,VALE3,ITUB4

```

---

## Production — AWS

### Infrastructure

```
AWS ECS (Fargate)
├── FastAPI service
└── Celery worker service

AWS RDS PostgreSQL 16 (Multi-AZ)
├── pgvector extension
└── Apache AGE extension

AWS ElastiCache Redis
└── AOF persistence enabled

AWS CloudWatch
├── Log Groups: /finagent/api, /finagent/celery
├── Dashboard: finagent-production
└── Alarms → SNS → email

```

### Deploy steps

**1. Build and push Docker image**

```bash
aws ecr get-login-password | docker login --username AWS --password-stdin $ECR_URI
docker build -t finagent .
docker tag finagent:latest $ECR_URI/finagent:latest
docker push $ECR_URI/finagent:latest

```

**2. Run migrations on RDS**

```bash
aws ecs run-task \
  --cluster finagent \
  --task-definition finagent-migrate \
  --overrides '{"containerOverrides":[{"name":"api","command":["alembic","upgrade","head"]}]}'

```

**3. Update ECS services**

```bash
aws ecs update-service --cluster finagent --service finagent-api --force-new-deployment
aws ecs update-service --cluster finagent --service finagent-worker --force-new-deployment

```

### CloudWatch Alarms

| Alarm | Threshold | Action |
| --- | --- | --- |
| Pipeline failure | > 0 failures/day | SNS email |
| API error rate | > 5% in 5 min | SNS email |
| Celery queue depth | > 50 tasks | SNS email |
| Redis memory | > 80% | SNS email |
| Agent latency | > 120s | SNS email |
| Confidence score avg | < 0.70 | SNS email |

---

## Celery Beat Schedule

The pipeline runs automatically every day at 6AM Brazil time (UTC-3):

```python
CELERYBEAT_SCHEDULE = {
    'daily-pipeline': {
        'task': 'app.workers.pipeline.run_daily_pipeline',
        'schedule': crontab(hour=9, minute=0),  # 9 UTC = 6 AM BRT
    },
}

```

---

## Row Level Security

RLS is enforced at the database level. Every isolated table has `manager_id` and policies that reject queries without the correct filter.

To verify RLS is working:

```sql
-- This should return 0 rows for manager_id = 999 (non-existent)
SET app.current_manager_id = '999';
SELECT COUNT(*) FROM morning_notes;

```

---

## Adding a New Manager

```bash
# Via API
curl -X POST http://localhost:8000/managers \
  -H "Content-Type: application/json" \
  -d '{
    "name": "John Doe",
    "email": "john@btg.com",
    "empresas": ["PETR4", "VALE3", "ITUB4", "BBDC4", "WEGE3"]
  }'

```

---

## Monitoring

* **LangSmith:** langsmith.com — filter by tag `pipeline_run:{date}`
* **CloudWatch:** AWS Console → CloudWatch → Dashboards → finagent-production
* **App dashboard:** http://localhost:8000/dashboard (managers only)

---

## Troubleshooting

**Pipeline did not run at 6AM**

```bash
docker compose logs celery-beat | tail -50
docker compose logs celery | grep "pipeline" | tail -20

```

**Morning note missing sections**
Check LangSmith trace for the `morning_note_id` — look for agents with `confidence < 0.75` or `data_freshness` flags.

**RLS blocking legitimate queries**

```bash
# Check if manager_id is being set correctly in the session
docker compose exec api python -m app.db.check_rls --manager-id 1

```

**Apache AGE graph not updating**

```bash
# Verify AGE extension is loaded
docker compose exec postgres psql -U finagent -c "SELECT * FROM ag_graph;"

```

```

```