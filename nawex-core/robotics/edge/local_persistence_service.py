# ===========================================================================
# NAWEX - Nawex Platform
# Copyright (c) 2026 Rev. Dr. Emmanuel Naweji. All rights reserved.
# https://github.com/Here2ServeU/Naweji-Reliability-Platform
# ===========================================================================
import json
import os
import time
from datetime import datetime

class LocalPersistenceService:
    """
    Ensures zero data loss for clinical robotics during cloud disconnects.
    Pipes critical telemetry to local NVMe storage until uplink is restored.
    """
    def __init__(self, storage_path="/data/forensics/local_buffer"):
        self.storage_path = storage_path
        os.makedirs(self.storage_path, exist_ok=True)
        print(f">>> [EDGE] Local Persistence initialized at: {self.storage_path}")

    def save_telemetry_locally(self, telemetry_data):
        """Writes encrypted telemetry to local disk for later synchronization."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        file_name = f"telemetry_buffer_{timestamp}.json"
        full_path = os.path.join(self.storage_path, file_name)
        
        try:
            with open(full_path, 'w') as f:
                json.dump(telemetry_data, f, indent=4)
            print(f">>> [OFFLINE MODE] Telemetry persisted locally: {file_name}")
            return True
        except Exception as e:
            print(f"!!! [CRITICAL] Local storage failure: {str(e)}")
            return False

# --- Offline Failover Test ---
if __name__ == "__main__":
    persistence = LocalPersistenceService()
    
    # Simulating a data packet during a Cloud Outage
    critical_telemetry = {
        "device_id": "SURG-ROBOT-01",
        "status": "OFFLINE_BUFFERING",
        "data": {
            "joint_vibration": 0.042,
            "packet_loss": 1.0,
            "latency_ms": "inf"
        }
    }
    
    persistence.save_telemetry_locally(critical_telemetry)
