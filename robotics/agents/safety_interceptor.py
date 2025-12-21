import json
import os

class SafetyInterceptor:
    def __init__(self, policy_path="failover_policy.json"):
        self.policy = self._load_policy(policy_path)
        self.failover_active = False

    def _load_policy(self, path):
        """Loads the deterministic governance policy."""
        if os.path.exists(path):
            with open(path, 'r') as f:
                return json.load(f)
        return {}

    def analyze_telemetry(self, data):
        """Analyzes telemetry against the Clinical-Kinematic-Safety-Protocol."""
        thresholds = self.policy.get("thresholds", {})
        metrics = data.get("telemetry", {})
        
        # Extract thresholds from the JSON policy
        critical_rtt = thresholds.get("network_latency", {}).get("critical_ms", 25.0)
        max_vibration = thresholds.get("kinematics_stability", {}).get("max_vibration_index", 0.05)
        
        # Extract live telemetry
        current_rtt = metrics.get("network", {}).get("cloud_rtt_ms", 0)
        current_vibration = metrics.get("kinematics", {}).get("joint_vibration_index", 0)

        # Execute actions based on the deterministic policy
        if current_rtt > critical_rtt:
            self.execute_action(thresholds["network_latency"]["action"], f"RTT: {current_rtt}ms")
        
        if current_vibration > max_vibration:
            self.execute_action(thresholds["kinematic_stability"]["action"], f"Vibration: {current_vibration}")

    def execute_action(self, action_type, reason):
        if not self.failover_active:
            print(f"\n[POLICY ENFORCED] Action: {action_type}")
            print(f"Reason: {reason}")
            print(f"Compliance: {self.policy['governance']['compliance_standard']}")
            self.failover_active = True

# --- Practical Test with Clinical Policy ---
interceptor = SafetyInterceptor()
test_data = {
    "device_id": "SURG-ROBOT-01",
    "telemetry": {
        "network": {"cloud_rtt_ms": 32.5}, 
        "kinematics": {"joint_vibration_index": 0.07}
    }
}
interceptor.analyze_telemetry(test_data)
