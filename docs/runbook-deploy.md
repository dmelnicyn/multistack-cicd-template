# Deployment Runbook

## Overview

- **Staging**: Auto-deploys on push to `main` after CI passes (Railway watches GitHub)
- **Production**: Manual promotion via Railway dashboard ("sync from staging")

## How Staging Deploy Works

1. Push to `main` triggers CI workflow
2. CI runs lint + tests (must pass)
3. Railway detects push, waits for CI, deploys to staging
4. Staging Smoke Check workflow verifies /health

## Pre-Promotion Checklist

- [ ] CI workflow passed (green check on commit)
- [ ] Staging Smoke Check passed
- [ ] Manual sanity test on staging (visit STAGING_URL, test key flows)
- [ ] No open critical issues for this release

## Promote Staging to Production

1. Open Railway dashboard
2. Navigate to project → Production service
3. Click "Deployments" tab
4. Click "Deploy" → "From Staging" (or "Sync changes from staging")
5. Confirm deployment
6. Wait for deployment to complete (~1-2 min)

## Post-Promotion Verification

```bash
curl -sf "$PROD_URL/health"
# Expected: {"status":"ok"}
```

Test critical user flows manually.

## Rollback Options

### Option A: Revert commit + re-promote

1. `git revert <bad-commit>` on main
2. Push to main (triggers staging redeploy)
3. Verify staging is healthy
4. Promote staging to prod again

### Option B: Railway rollback

1. Open Railway dashboard → Production → Deployments
2. Find previous healthy deployment
3. Click "Redeploy" on that version

## Troubleshooting

| Symptom | Check |
|---------|-------|
| Staging smoke check fails | Check Railway logs, verify deployment completed |
| Health returns non-200 | Check app logs, DB connectivity, env vars |
| Deployment stuck | Check Railway dashboard for build errors |
| Prod unhealthy after promotion | Rollback immediately, investigate in staging |
