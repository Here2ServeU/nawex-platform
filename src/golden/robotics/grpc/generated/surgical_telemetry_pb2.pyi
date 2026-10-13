from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class TelemetryPacket(_message.Message):
    __slots__ = ("device_id", "timestamp", "kinematics", "network")
    class Kinematics(_message.Message):
        __slots__ = ("joint_vibration_index", "motor_temp_celsius", "torque_nm")
        JOINT_VIBRATION_INDEX_FIELD_NUMBER: _ClassVar[int]
        MOTOR_TEMP_CELSIUS_FIELD_NUMBER: _ClassVar[int]
        TORQUE_NM_FIELD_NUMBER: _ClassVar[int]
        joint_vibration_index: float
        motor_temp_celsius: float
        torque_nm: float
        def __init__(self, joint_vibration_index: _Optional[float] = ..., motor_temp_celsius: _Optional[float] = ..., torque_nm: _Optional[float] = ...) -> None: ...
    class Network(_message.Message):
        __slots__ = ("cloud_rtt_ms", "packet_loss_pct")
        CLOUD_RTT_MS_FIELD_NUMBER: _ClassVar[int]
        PACKET_LOSS_PCT_FIELD_NUMBER: _ClassVar[int]
        cloud_rtt_ms: float
        packet_loss_pct: float
        def __init__(self, cloud_rtt_ms: _Optional[float] = ..., packet_loss_pct: _Optional[float] = ...) -> None: ...
    DEVICE_ID_FIELD_NUMBER: _ClassVar[int]
    TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    KINEMATICS_FIELD_NUMBER: _ClassVar[int]
    NETWORK_FIELD_NUMBER: _ClassVar[int]
    device_id: str
    timestamp: str
    kinematics: TelemetryPacket.Kinematics
    network: TelemetryPacket.Network
    def __init__(self, device_id: _Optional[str] = ..., timestamp: _Optional[str] = ..., kinematics: _Optional[_Union[TelemetryPacket.Kinematics, _Mapping]] = ..., network: _Optional[_Union[TelemetryPacket.Network, _Mapping]] = ...) -> None: ...

class SafetyCommand(_message.Message):
    __slots__ = ("recommended_action", "reason", "command_id")
    class Action(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        NOMINAL: _ClassVar[SafetyCommand.Action]
        REROUTE_TO_EDGE: _ClassVar[SafetyCommand.Action]
        SAFE_STATE_TRANSITION: _ClassVar[SafetyCommand.Action]
        EMERGENCY_STOP: _ClassVar[SafetyCommand.Action]
    NOMINAL: SafetyCommand.Action
    REROUTE_TO_EDGE: SafetyCommand.Action
    SAFE_STATE_TRANSITION: SafetyCommand.Action
    EMERGENCY_STOP: SafetyCommand.Action
    RECOMMENDED_ACTION_FIELD_NUMBER: _ClassVar[int]
    REASON_FIELD_NUMBER: _ClassVar[int]
    COMMAND_ID_FIELD_NUMBER: _ClassVar[int]
    recommended_action: SafetyCommand.Action
    reason: str
    command_id: str
    def __init__(self, recommended_action: _Optional[_Union[SafetyCommand.Action, str]] = ..., reason: _Optional[str] = ..., command_id: _Optional[str] = ...) -> None: ...
