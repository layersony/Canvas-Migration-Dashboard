from config import *
from functions.utils import paginate, post

def export_users():
    url = f"{SOURCE_DOMAIN}/api/v1/accounts/1/users?per_page=100"
    return paginate(url, HEADERS_SRC)

def import_user(user):
    data = {
        "user[name]": user.get("name"),
        "user[short_name]": user.get("short_name", user.get("name")),
        "user[email]": user.get("login_id"),
        "pseudonym[unique_id]": user.get("login_id")
    }
    url = f"{TARGET_DOMAIN}/api/v1/accounts/1/users"
    return post(url, HEADERS_DST, data)
