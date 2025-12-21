import grpc
from concurrent import futures
import time
import surgical_telemetry_pb2 as pb2
import surgical_telemetry_pb2_grpc as pb2_grpc

class SurgicalTelemetryServicer(pb2_grpc.SurgicalTelemetryServicer):
    def StreamTelemetry(self, request_iterator, context):
        """Processes bi-directional telemetry streams from surgical robots."""
        for packet in request_iterator:
            print(f"[RECV] Telemetry from {packet.device_id} | Jitter: {packet.network.cloud_rtt_ms}ms")
            
            # Logic: If Jitter > 25ms, issue an immediate REROUTE_TO_EDGE command
            action = pb2.SafetyCommand.NOMINAL
            reason = "Operational Baseline Maintained"
            
            if packet.network.cloud_rtt_ms > 25.0:
                action = pb2.SafetyCommand.REROUTE_TO_EDGE
                reason = "Cloud Latency Threshold Exceeded"
            
            yield pb2.SafetyCommand(
                recommended_action=action,
                reason=reason,
                command_id=f"CMD-{int(time.time())}"
            )

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    pb2_grpc.add_SurgicalTelemetryServicer_to_server(SurgicalTelemetryServicer(), server)
    server.add_insecure_port('[::]:50051')
    print(">>> [GRPC] Clinical Telemetry Server active on port 50051...")
    server.start()
    server.wait_for_termination()

if __name__ == "__main__":
    serve()
