from enum import IntEnum


DEFAULT_SRC = 32
DEFAULT_DEST = 53

PLUG_MAX_WATTS_LIMIT = 2500

class WatthType(IntEnum):
    TOTAL = 1
    TO_PLUGS = 2 # ?
    TO_BATTERY = 3 # ?
    FROM_BATTERY = 4 # ?
    PV1 = 7 #?
    PV2 = 8 #?

class CmdFuncs(IntEnum):
    DEFAULT = 0
    POWERSTREAM = 20
    SMART_PLUG = 2
    REPORTS = 254

class SupplyPriority(IntEnum):
    POWER = 0
    BATTERY = 1

class FeedPriority(IntEnum):
    ALL_SUN_TO_POWER = 0
    ONLY_PERMANENT_WATT = 1       

class CmdIds(IntEnum):
    # powerstream
    HEARTBEAT = 1
    HEARTBEAT2 = 4
    SET_PERMANENT_WATTS = 129
    SET_SUPPLY_PRIORITY = 130
    SET_BAT_LOWER = 132
    SET_BAT_UPPER = 133
    SET_BRIGHTNESS = 135
    SET_UNKNOWN_136 = 136
    SET_UNKNOWN_138 = 138
    SET_FEED_PRIORITY = 143

    # smart plug
    PLUG_HEARTBEAT = 1
    TIME_TASK_CONFIG = 2
    SET_PLUG_SWITCH = 129
    SET_PLUG_BRIGHTNESS = 130
    PLUG_POWER_PACK = 133
    SET_UNKNOWN_135 = 135
    SET_MAX_WATTS = 137
    SET_MESH_ENABLE = 138
    INCLUDE_PLUG = 142

    # cmd_func 254
    ENERGY_TOTAL_REPORT = 32

    # delta max
    CAR_OUT_CFG = 81
    USB_OUT_CFG = 34
    AC_OUT_CFG = 66
