import json
import time

class SafetyInterceptor:
    def __init__(self, threshold_ms=25.0):
        self.threshold_ms = threshold_ms
        self.failover_active = False

    def analyze_telemetry(self, data):
        """
        Analyzes kinematic and network data to predict operational fragility.
        """
        metrics = data.get("telemetry", {})
        rtt = metrics.get("network", {}).get("cloud_rtt_ms", 0)
        vibration = metrics.get("kinematics", {}).get("joint_vibration_index", 0)
        
        # Logic: If RTT > threshold AND vibration is rising, trigger agentic failover
        if rtt > self.threshold_ms and vibration > 0.05:
            self.execute_failover(data)
        elif data.get("status") == "FRAGILE":
            self.execute_failover(data)
        else:
            print(f"[NOMINAL] Cloud Link Stable: {rtt}ms RTT | Vibration: {vibration}")

    def execute_failover(self, data):
        if not self.failover_active:
            print("\n!!! [CRITICAL] AGENTIC INTERVENTION TRIGGERED !!!")
            print(f">>> Reason: Latent Fragility Detected in {data['device_id']}")
            print(">>> Action: Rerouting control packets to LOCAL EDGE GATEWAY.")
            print(">>> Protocol: Executing Safe-State Transition via local_persistence_service.py")
            self.failover_active = True

# Simulation of the Interceptor in action
interceptor = SafetyInterceptor()

# Example: Processing a 'Fragile' packet from your simulator
fragile_packet = {
    "device_id": "SURG-ROBOT-01",
    "telemetry": {"network": {"cloud_rtt_ms": 45.2}, "kinematics": {"joint_vibration_index": 0.082}},
    "status": "FRAGILE"
}

interceptor.analyze_telemetry(fragile_packet)
