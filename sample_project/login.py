from auth import authenticate

def login(user_id):
    if authenticate(user_id):
        return "Login successful"
    return "Login failed"
