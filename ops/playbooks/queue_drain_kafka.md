# Kafka Queue Drain Playbook for Express T2S Microservices

## When to Use
- Before deploying breaking schema or code changes to consumers.
- Before performing maintenance or scaling down Kafka brokers/clusters.

## Steps

1. **Pause Consumers (Kubernetes/Helm)**
- Use Helm/GitOps tooling to **scale the deployment replicas of the target consumer to 0** (`replicaCount: 0`).
- **Verify** that the consumer group is no longer actively consuming messages.
- *Alternative:* If using internal application controls, use consumer group pause functionality if available in the client library.

2. **Verify Queue Drain State**
- **Crucial Check:** Confirm that the consumer group **lag is zero** or messages are not actively building up. Use a tool like `kafka-consumer-groups.sh` or a dedicated monitoring dashboard.
- Allow any in-flight messages (Option B) to finish processing before proceeding.
- If necessary, run a temporary consumer (Option A) that reads and discards remaining messages to hit zero lag.

3. **Deploy New Consumer Version (GitOps)**
- Update the image tag/chart values in Git.
- Allow ArgoCD/Flux to deploy the updated consumer version while replicas remain at 0.
- **Verify** the new Deployment/StatefulSet template is ready for scaling.

4. **Resume Consumption and Monitor**
- Use Helm/GitOps to **scale consumer replicas back up** to the desired count.
- **Monitor lag** immediately to ensure consumers are catching up quickly.
- Monitor error rates, processing time, and application logs for any issues introduced by the new version.
