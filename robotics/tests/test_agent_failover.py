# ===========================================================================
# NERP - Naweji Enterprise Reliability Platform
# Copyright (c) 2026 Rev. Dr. Emmanuel Naweji. All rights reserved.
# https://github.com/Here2ServeU/Naweji-Reliability-Platform
# ===========================================================================
import json
import os
import sys

# Import the core safety agents for testing
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from agents.safety_interceptor import SafetyInterceptor
from agents.emergency_stop_handler import EmergencyStopHandler

def run_failover_test():
    """
    Simulates a 'Latent Fragility' event to verify autonomous safety protocols.
    """
    print("--- INITIALIZING CLINICAL FAILOVER TEST ---")
    
    interceptor = SafetyInterceptor(policy_path="../agents/failover_policy.json")
    estop = EmergencyStopHandler()

    # Scenario: Critical Jitter + Mechanical Stress
    failure_data = {
        "device_id": "SURG-ROBOT-TEST",
        "telemetry": {
            "network": {"cloud_rtt_ms": 48.5}, # Above 25ms threshold
            "kinematics": {"joint_vibration_index": 0.095} # Above 0.05 threshold
        },
        "status": "FRAGILE"
    }

    print(f"\n[TEST] Injecting Failure Pattern: {json.dumps(failure_data['telemetry'])}")
    
    # 1. Verify Detection
    interceptor.analyze_telemetry(failure_data)
    
    if interceptor.failover_active:
        print(">>> SUCCESS: Safety Interceptor detected fragility and initiated failover.")
        
        # 2. Verify Hardware E-Stop (for Category 0 events)
        estop.trigger_estop(source="TEST_SUITE", reason="SIMULATED_KINEMATIC_DESYNC")
        
        # 3. Verify Forensic Logging
        log_files = [f for f in os.listdir('.') if f.startswith('clinical_incident_')]
        if log_files:
            print(f">>> SUCCESS: Forensic Audit Log generated: {log_files[0]}")
        else:
            print("!!! FAILURE: No forensic incident report found.")
    else:
        print("!!! FAILURE: Safety Interceptor failed to detect the critical anomaly.")

if __name__ == "__main__":
    run_failover_test()
