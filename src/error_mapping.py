
error_codes = {
    5030: "Name already in use. Please modify the name and try again.",
    # Add other error codes and their messages here as needed
}

def get_error_message(errno):
    return error_codes.get(errno, "An unknown error occurred.")
