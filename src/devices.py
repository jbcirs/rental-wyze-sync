from enum import Enum

class Devices(Enum):
    LOCKS = "Locks"
    LIGHTS = "Lights"
    THERMOSTATS  = "Thermostats"

class Device(Enum):
    LOCK = "Lock"
    LIGHT = "Light"
    THERMOSTAT  = "Thermostat"