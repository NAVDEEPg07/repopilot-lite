from user_service import find_user

def authenticate(username):
    return find_user(username)
