# Kafka Queue Drain Playbook

## When to Use
- Before deploying breaking changes to consumers.
- Before performing maintenance on Kafka brokers.

## Steps

1. **Pause Consumers**
   - Scale deployment replicas of consumers to 0, or
   - Use consumer group pause functionality if available.

2. **Drain Queue**
   - Option A: Temporary consumer that reads and discards messages.
   - Option B: Allow in-flight consumers to finish with no new messages.

3. **Deploy New Version**
   - Deploy updated consumer using GitOps (ArgoCD/Flux).

4. **Resume Consumption**
   - Scale consumers back up.
   - Monitor lag, error rates, and processing time.
