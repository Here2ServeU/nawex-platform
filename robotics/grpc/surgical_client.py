import grpc
import time
import random
import surgical_telemetry_pb2 as pb2
import surgical_telemetry_pb2_grpc as pb2_grpc

def generate_telemetry_stream():
    """Simulates a continuous stream of robotic telemetry packets."""
    device_id = "SURG-ROBOT-01"
    while True:
        # Simulate normal operation with slight jitter
        rtt = 12.0 + random.uniform(-2, 2)
        vibration = 0.02 + random.uniform(-0.01, 0.01)
        
        # Inject an anomaly every 10 packets to test the interceptor
        if random.random() > 0.9:
            rtt = 35.0  # Above safety threshold
            vibration = 0.08

        packet = pb2.TelemetryPacket(
            device_id=device_id,
            timestamp=str(time.time()),
            kinematics=pb2.TelemetryPacket.Kinematics(
                joint_vibration_index=vibration,
                motor_temp_celsius=37.5,
                torque_nm=1.4
            ),
            network=pb2.TelemetryPacket.Network(
                cloud_rtt_ms=rtt,
                packet_loss_pct=0.01
            )
        )
        yield packet
        time.sleep(0.5) # 2Hz stream for simulation purposes

def run():
    """Connects to the Surgical Telemetry Server and processes safety commands."""
    with grpc.insecure_channel('localhost:50051') as channel:
        stub = pb2_grpc.SurgicalTelemetryStub(channel)
        print(">>> [ROBOT] Establishing low-latency gRPC stream to platform...")
        
        responses = stub.StreamTelemetry(generate_telemetry_stream())
        
        for command in responses:
            print(f"[RECV] Safety Command: {command.recommended_action} | Reason: {command.reason}")
            
            if command.recommended_action == pb2.SafetyCommand.EMERGENCY_STOP:
                print("!!! [HALT] Executing hardware-level Emergency Stop !!!")
                break
            elif command.recommended_action == pb2.SafetyCommand.REROUTE_TO_EDGE:
                print(">>> [ADAPT] Switching to Edge Compute for local continuity.")

if __name__ == "__main__":
    run()
