# Automated Remediation Engine

This directory contains the logic for the **Execution Phase** of the AIOps control loop. It serves as the actuation layer that translates high-level decisions from the Planner Agent into specific, low-level infrastructure commands (e.g., Kubernetes API calls, Terraform applies, or script executions).

The design prioritizes safety and determinism, ensuring that automated actions do not cause cascading failures or "flapping" states.

## System Architecture

### 1. The Execution Core
* **File:** `remediation_engine.py`
* **Function:** The runtime execution driver.
* **Technical Detail:** This script acts as a safe wrapper around infrastructure APIs. It accepts a standard `Plan` object and matches it against the defined rules. It implements critical SRE safety patterns:
    * **Idempotency:** Ensures that applying the same action multiple times yields the same result (e.g., "Scale to 5 replicas" is safe to repeat; "Add 1 replica" is not).
    * **Dry-Run Capability:** Allows the system to simulate remediation actions in logs without mutating the production state.
    * **Error Handling:** Graceful fallbacks if the underlying cloud provider API is unresponsive.

### 2. Policy-as-Code Configuration
* **File:** `remediation_rules.yaml`
* **Function:** The declarative knowledge base for self-healing.
* **Technical Detail:** Decouples the remediation *logic* (Python) from the remediation *policy* (YAML). This allows SREs to add new self-healing capabilities (e.g., "Restart Pod on Memory Leak") without redeploying the engine code.

## Remediation Workflow

The engine follows a strict **Trigger-Action-Validation** flow:

1.  **Trigger:** The engine receives a `RemediationPlan` from the Planner Agent containing a `diagnosis_id` (e.g., `HIGH_LATENCY_FRONTEND`).
2.  **Lookup:** It scans `remediation_rules.yaml` to find the matching policy.
3.  **Constraints Check:** It verifies if the action is currently allowed (e.g., not during a blackout window, and not exceeding the rate limit).
4.  **Execution:** It invokes the specific handler (e.g., `scale_deployment(service, count)`).
5.  **Audit:** The action is logged with a correlation ID for post-incident review.

## Configuration Example

Rules are defined declaratively to support dynamic reloading:

```yaml
rules:
  - id: "cpu-saturation-recovery"
    description: "Horizontal scaling when CPU exceeds safety thresholds"
    trigger_condition: "cpu_usage > 85%"
    action:
      type: "kubernetes_scale"
      target_resource: "deployment/frontend"
      parameters:
        min_replicas: 3
        max_replicas: 10
        step_size: 2
    safety_rails:
      cooldown_period: "300s"
      max_daily_actions: 5
````

## Usage

The engine is typically invoked by the Orchestrator, but can be run manually for testing rules:

```bash
# Test a specific rule against a dry-run target
python remediation_engine.py --rule cpu-saturation-recovery --dry-run
```

### Interview Talking Point
> I architected the `remediation` module to separate **Mechanism** from **Policy**. The `remediation_engine.py` is the mechanism—it knows *how* to scale a pod or restart a service. The `remediation_rules.yaml` is the policy—it decides *when* that should happen. This separation is critical for a Senior SRE role because it allows me to safely enable automation incrementally. We can deploy the code today but keep the rules commented out, or run them in 'Dry Run' mode to build confidence before letting the AI touch production.
