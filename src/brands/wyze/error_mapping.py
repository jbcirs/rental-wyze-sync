
error_codes = {
    5030: "Name already in use. Please modify the name and try again.",
    5034: "The operation is too fast, please wait a moment.",
    5021: "Successfully deleted",
    3027: "The parameter is incorrect. Date time frame may not be valid."
}

def get_error_message(errno):
    return error_codes.get(errno, "An unknown error occurred.")
