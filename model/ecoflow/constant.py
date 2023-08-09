from enum import IntEnum


DEFAULT_SRC = 32
DEFAULT_DEST = 53

PLUG_MAX_WATTS_LIMIT = 2500

class CmdFuncs(IntEnum):
    POWERSTREAM = 20
    SMART_PLUG = 2

class SupplyPriority(IntEnum):
    POWER = 0
    BATTERY = 1

class CmdIds(IntEnum):
    # powerstream
    HEARTBEAT = 1
    SET_PERMANENT_WATTS = 129
    SET_SUPPLY_PRIORITY = 130
    SET_BAT_LOWER = 132
    SET_BAT_UPPER = 133
    SET_BRIGHTNESS = 135

    # smart plug
    PLUG_HEARTBEAT = 1
    TIME_TASK_CONFIG = 2
    SET_PLUG_SWITCH = 129
    SET_PLUG_BRIGHTNESS = 130
    SET_MAX_WATTS = 137
    SET_MESH_ENABLE = 138

    # cmd_func 254
    ENERGY_TOTAL_REPORT = 32