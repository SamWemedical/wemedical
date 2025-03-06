from flask import session
from functools import wraps

def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def wrapper(*args,**kwargs):
            if 'role' not in session:
                return "ไม่มีสิทธิ์ (ยังไม่ได้ล็อกอิน)"
            if session['role'] not in roles:
                return "ไม่มีสิทธิ์ (role นี้ไม่อนุญาต)"
            return f(*args,**kwargs)
        return wrapper
    return decorator
