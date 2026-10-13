from user_service import get_user

def authenticate(user_id):
    user = get_user(user_id)
    return user is not None
