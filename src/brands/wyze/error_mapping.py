# Mapping of Wyze API error codes to human-readable error messages
# These can be used to provide more meaningful information in logs and notifications
error_codes = {
    # Existing codes
    5030: "Name already in use. Please modify the name and try again.",
    5034: "The operation is too fast, please wait a moment.",
    5021: "Successfully deleted",
    3027: "The parameter is incorrect. Date time frame may not be valid.",
    
    # Additional common error codes
    1001: "Authentication failed. Please check your credentials.",
    1002: "Session expired. Please reauthenticate.",
    1003: "Permission denied. Your account doesn't have access to this device.",
    2000: "Device is offline. Please check device connectivity.",
    2001: "Device is already in use by another operation.",
    2002: "Device firmware needs to be updated.",
    3000: "Invalid request parameters.",
    4000: "Service unavailable. Wyze servers may be experiencing issues.",
    4001: "API rate limit exceeded. Please retry after a short delay.",
    5000: "Internal server error from Wyze API.",
    9000: "Network connectivity issue. Please check your internet connection."
}

def get_error_message(errno):
    """
    Get a human-readable error message for a Wyze API error code.
    
    Args:
        errno: Wyze API error code
        
    Returns:
        str: Human-readable error message or a generic message if code is unknown
    """
    return error_codes.get(errno, f"Unknown error occurred (code {errno}). Please check the Wyze app for device status.")
