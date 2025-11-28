# Redis Cache Warm-Up Playbook for Express T2S Microservices

## Goals
- Avoid cold-start performance degradation after deployment or restart of core services.
- Pre-populate high-value keys for the Express T2S service and relevant Backstage plugins.

## Steps

1. **Confirm Deployment Stability**
- Wait until all application pods (especially those relying on Redis) are **Ready** and passing Liveness/Readiness probes.
- Verify that the Redis service itself is stable and accessible.

2. **Execute Warm-Up Job (Kubernetes)**
- Run the dedicated `redis-warmup-job.yaml` (or equivalent script) as a one-off Kubernetes Job.
- This script must target key API endpoints (e.g., core T2S functions, Backstage Catalog APIs) to force data loading into the cache.

3. **Monitor Cache Performance**
- Check Redis command rate (`INFO STATS`) to confirm data loading activity.
- Monitor **Cache Hit Ratio** and aim for the target threshold (e.g., >95%) before proceeding.
- Validate application latency using monitoring dashboards while the job is running.

4. **Clean Up**
- Once the cache hit ratio is acceptable, confirm the Warm-Up Job has completed successfully and delete the Kubernetes Job resource to avoid resource waste.

5. **Automate/Integrate**
- Integrate the warm-up job execution into the deployment pipeline as a **post-deployment hook** in your GitOps configuration (ArgoCD/Flux) to ensure it runs on every relevant deployment.
