# ===========================================================================
# NAWEX - Nawex Platform
# Copyright (c) 2026 Rev. Dr. Emmanuel Naweji. All rights reserved.
# https://github.com/Here2ServeU/Naweji-Reliability-Platform
# ===========================================================================
import time
import json

class EmergencyStopHandler:
    """
    Implements a Category 0 Emergency Stop (E-Stop) for surgical robotics.
    Ensures immediate halting of all hazardous movements.
    """
    def __init__(self):
        self.estop_active = False

    def trigger_estop(self, source="UNKNOWN", reason="CRITICAL_SAFETY_FAULT"):
        """
        Instantly halts robot operations. In a real system, this would 
        interface directly with hardware safety relays.
        """
        if not self.estop_active:
            print("\n" + "!"*50)
            print(f"!!! EMERGENCY STOP ACTIVATED BY: {source} !!!")
            print(f"!!! REASON: {reason} !!!")
            print("!"*50)
            
            # Action: Shuts down power to all robot servos instantly
            self._cut_actuator_power()
            
            # Action: Notify the surgical team via the Console
            self._notify_surgical_console()
            
            self.estop_active = True
            
            # Action: Lock system against automatic restart
            print(">>> System LOCKED. Manual reset required via Supervisor Key.")

    def _cut_actuator_power(self):
        """Simulates cutting power to the robot's physical drives."""
        print(">>> [HARDWARE] Actuator Power: DISCONNECTED (Category 0)")

    def _notify_surgical_console(self):
        """Sends a high-priority alert message to the HMI/Console."""
        alert = {
            "priority": "ALARM_CRITICAL",
            "message": "EMERGENCY STOP ENGAGED - CLEAR SURGICAL FIELD",
            "timestamp": time.time()
        }
        print(f">>> [CONSOLE ALERT]: {alert['message']}")

# --- Simulation of a Critical Fault Trigger ---
if __name__ == "__main__":
    handler = EmergencyStopHandler()
    
    # Simulate a critical failure detected by the Safety Interceptor
    critical_fault_event = {
        "source": "JOINT_04_DESYNC",
        "reason": "Kinematic desynchronization exceeding 50ms safety window."
    }
    
    handler.trigger_estop(
        source=critical_fault_event["source"], 
        reason=critical_fault_event["reason"]
    )
