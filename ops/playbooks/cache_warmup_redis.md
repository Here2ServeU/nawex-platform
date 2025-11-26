# Redis Cache Warm-Up Playbook

## Goals
- Avoid cold-start performance degradation after deployment or restart.
- Pre-populate high-value keys.

## Steps

1. **Identify Hot Keys**
   - From Redis MONITOR / keyspace stats / application logs.

2. **Warm-Up Job**
   - Run a one-off Kubernetes Job or script that:
     - Calls key API endpoints.
     - Preloads commonly accessed data into cache.

3. **Monitor**
   - Check Redis command rate, hit ratio.
   - Validate application latency before cutting over traffic.

4. **Automate**
   - Integrate warm-up into deployment pipeline or a post-deploy hook.
