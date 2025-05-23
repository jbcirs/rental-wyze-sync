"""
Enumeration of time periods for device settings.
Used to determine which settings to apply based on reservation status.
"""
from enum import Enum

class When(Enum):
    """
    Defines when specific device settings should be applied
    """
    RESERVATIONS_ONLY = "reservations_only"  # Apply only during active reservations
    NON_RESERVATIONS = "non_reservations"    # Apply when there are no active reservations
