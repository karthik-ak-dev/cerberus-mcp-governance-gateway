# Database Migrations Guide

Cerberus uses **Alembic** for database migrations with async SQLAlchemy.

## How Migrations Work

Migrations run **automatically on app startup** (`RUN_MIGRATIONS_ON_STARTUP=true` by default).

```
App Startup:
─────────────
1. Connect to database
2. Check for pending migrations
3. If migrations exist → run them
4. If already up-to-date → skip
5. Start serving requests
```

This works the same way for local development, staging, and production.

## Key Files

| File | Purpose |
|------|---------|
| `alembic.ini` | Alembic configuration |
| `alembic/env.py` | Migration environment (async-aware) |
| `alembic/versions/` | Migration scripts |
| `app/models/*.py` | SQLAlchemy models (source of truth) |
| `app/db/migrations.py` | Auto-migration runner |

---

# Part 1: Local Development

## Docker Compose (Recommended)

### First-Time Setup

```bash
cd cerberus/docker

# Start all services - migrations run automatically
docker-compose up -d

# (Optional) Seed test data
docker-compose exec cerberus python -m scripts.seed_db

# Verify
curl http://localhost:8000/health
```

That's it! Migrations run automatically when the app starts.

### Creating New Migrations

When you modify models in `app/models/`:

```bash
# 1. Make changes to your model
#    Example: Add a field to User model in app/models/user.py

# 2. Generate migration from model changes
docker-compose exec cerberus alembic revision --autogenerate -m "Add last_login_at to users"

# 3. Review the generated file in alembic/versions/
#    Check the upgrade() and downgrade() functions are correct

# 4. Restart the app - migration runs automatically
docker-compose restart cerberus

# Or run manually if you prefer
docker-compose exec cerberus alembic upgrade head
```

### Common Commands

```bash
# Check current migration status
docker-compose exec cerberus alembic current

# Show migration history
docker-compose exec cerberus alembic history --verbose

# Rollback last migration
docker-compose exec cerberus alembic downgrade -1

# Generate SQL without executing (for review)
docker-compose exec cerberus alembic upgrade head --sql

# Reset database completely (loses all data!)
docker-compose down -v           # Remove volumes
docker-compose up -d             # Restart (migrations run automatically)
docker-compose exec cerberus python -m scripts.seed_db
```

---

## Without Docker

### First-Time Setup

```bash
cd cerberus

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start PostgreSQL locally
# macOS: brew services start postgresql@15
# Ubuntu: sudo systemctl start postgresql

# Create database
createdb cerberus

# Copy environment file
cp env.example .env

# Start the server - migrations run automatically
uvicorn app.main:app --reload
```

### Creating New Migrations

```bash
# 1. Modify your model in app/models/

# 2. Generate migration
alembic revision --autogenerate -m "Add last_login_at to users"

# 3. Review the generated file in alembic/versions/

# 4. Restart the app - migration runs automatically
# Or run manually: alembic upgrade head
```

### Common Commands

```bash
alembic current              # Show current migration
alembic history --verbose    # Show full history
alembic upgrade head         # Apply all pending (manual)
alembic upgrade +1           # Apply next one only
alembic downgrade -1         # Rollback one
alembic downgrade base       # Rollback all (dangerous!)
alembic upgrade head --sql   # Preview SQL without running
```

---

## Handling Migration Conflicts

When multiple developers create migrations on different branches:

```bash
# 1. Pull latest changes
git pull origin main

# 2. Check for multiple heads
alembic heads

# 3. If multiple heads exist, merge them
alembic merge -m "Merge branch migrations" <rev1> <rev2>

# 4. Restart app or run manually
alembic upgrade head

# 5. Commit the merge migration
git add alembic/versions/
git commit -m "Merge migration heads"
```

---

# Part 2: Staging & Production (AWS App Runner + Aurora)

Same approach - migrations run automatically on app startup.

## Multi-Instance Safety

When App Runner scales to multiple instances, a **PostgreSQL advisory lock** prevents race conditions:

```
Container 1: Acquires lock → runs migrations → releases lock → serves traffic
Container 2: Waits for lock → lock released → already migrated → serves traffic
```

The lock is implemented in `app/db/migrations.py` using `pg_try_advisory_lock()`.

## Configuration

Already configured in Terraform (`infra/environments/stage/main.tf` and `prod/main.tf`):

```hcl
environment_variables = {
  RUN_MIGRATIONS_ON_STARTUP = "true"
}
```

---

## Deployment Workflow

```bash
# 1. Create migration locally
alembic revision --autogenerate -m "Add new_field to users"

# 2. Review generated SQL
alembic upgrade head --sql

# 3. Restart local app to test
docker-compose restart cerberus

# 4. Commit and push
git add .
git commit -m "Add new_field to users table"
git push origin main

# 5. Deploy to staging (migrations run automatically)
cd infra/scripts && ./deploy-stage.sh

# 6. Verify staging
curl https://cerberus-stage.xxx.awsapprunner.com/health

# 7. Deploy to production
./deploy-prod.sh
```

### Pre-Deployment Checklist

**Before Staging:**
- [ ] Migration tested locally
- [ ] Migration SQL reviewed (`alembic upgrade head --sql`)

**Before Production:**
- [ ] Migration successful in staging
- [ ] Aurora snapshot created (backup)
- [ ] Team notified

---

## Creating Aurora Snapshots (Backup)

**Always create a snapshot before deploying schema changes to production:**

```bash
# Create snapshot
aws rds create-db-cluster-snapshot \
  --db-cluster-identifier cerberus-prod-aurora-cluster \
  --db-cluster-snapshot-identifier cerberus-pre-deploy-$(date +%Y%m%d-%H%M%S)

# Wait for completion
aws rds wait db-cluster-snapshot-available \
  --db-cluster-snapshot-identifier cerberus-pre-deploy-xxx
```

---

## Checking Migration Status

### View Logs

```bash
# Local (Docker)
docker-compose logs cerberus | grep -i migration

# App Runner
aws logs tail /aws/apprunner/cerberus-stage-service/service --follow

# Expected output:
# INFO: Attempting to run database migrations...
# INFO: Migration lock acquired, running migrations...
# INFO: Database migrations completed successfully
```

### Check Database State

```bash
# Local
docker-compose exec cerberus alembic current

# Staging/Prod via bastion
ssh -L 5432:aurora-endpoint:5432 ec2-user@bastion
DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/cerberus" alembic current
```

---

## Rollback Procedures

### Rollback Last Migration

```bash
# Local
docker-compose exec cerberus alembic downgrade -1

# Staging/Prod via bastion
ssh -L 5432:aurora-endpoint:5432 ec2-user@bastion
DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/cerberus" alembic downgrade -1
```

### Full Database Restore (Production)

```bash
# 1. Pause App Runner
aws apprunner pause-service --service-arn <arn>

# 2. Restore from snapshot
aws rds restore-db-cluster-from-snapshot \
  --db-cluster-identifier cerberus-prod-restored \
  --snapshot-identifier cerberus-pre-deploy-xxx \
  --engine aurora-postgresql

# 3. Update DATABASE_URL in Terraform, redeploy

# 4. Resume App Runner
aws apprunner resume-service --service-arn <arn>
```

---

## Troubleshooting

### "Multiple heads" Error

```bash
alembic heads                                    # List heads
alembic merge -m "Merge migrations" <rev1> <rev2>  # Merge
alembic upgrade head                              # Apply
```

### "Target database is not up to date"

```bash
alembic current       # Check state
alembic stamp head    # Force mark as current (if DB is correct)
```

### Migration Lock Timeout

If logs show "Could not acquire migration lock after max attempts":

```sql
-- Check for stuck locks
SELECT * FROM pg_locks WHERE locktype = 'advisory';

-- Force release (use with caution)
SELECT pg_advisory_unlock(123456789);
```

---

## Safe Migration Patterns

### Adding Columns

```python
# Safe: Add nullable column (no table lock)
op.add_column('users', sa.Column('new_field', sa.String(255), nullable=True))
```

### Removing Columns

Do in two stages:
1. Deploy code that stops using the column
2. Deploy migration that drops the column

### Adding Indexes on Large Tables

```python
# Use CONCURRENTLY to avoid locking
op.execute("CREATE INDEX CONCURRENTLY idx_users_email ON users(email)")
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `RUN_MIGRATIONS_ON_STARTUP` | `true` | Run alembic upgrade on app start |
| `DATABASE_URL` | (required) | PostgreSQL connection string |

---

## Related Documentation

- [Getting Started](./getting-started.md) - Local development setup
- [Deployment](./deployment.md) - AWS infrastructure and deployment
