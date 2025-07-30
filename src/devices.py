"""
Enumerations for device types and categories in the rental property system.
"""
from enum import Enum

class Devices(Enum):
    """
    Collection types of devices that can be managed at a property level.
    Used for filtering and grouping operations.
    """
    LOCKS = "Locks"           # Door locks for access control
    LIGHTS = "Lights"         # Lighting systems
    THERMOSTATS = "Thermostats"  # Climate control systems

class Device(Enum):
    """
    Individual device types for specific operation and logging.
    """
    LOCK = "Lock"
    LIGHT = "Light"
    THERMOSTAT = "Thermostat"
