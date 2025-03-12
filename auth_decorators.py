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


def get_months():
    return [
        {"value": 1, "name": "มกราคม"},
        {"value": 2, "name": "กุมภาพันธ์"},
        {"value": 3, "name": "มีนาคม"},
        {"value": 4, "name": "เมษายน"},
        {"value": 5, "name": "พฤษภาคม"},
        {"value": 6, "name": "มิถุนายน"},
        {"value": 7, "name": "กรกฎาคม"},
        {"value": 8, "name": "สิงหาคม"},
        {"value": 9, "name": "กันยายน"},
        {"value": 10, "name": "ตุลาคม"},
        {"value": 11, "name": "พฤศจิกายน"},
        {"value": 12, "name": "ธันวาคม"},
    ]
