from flask import Flask, render_template, request, redirect, url_for, session, make_response, flash, jsonify, Blueprint
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime, date, timedelta
from calendar import monthrange, weekday
from io import StringIO
from functools import wraps
from collections import OrderedDict, defaultdict
import sqlite3
import math
import pytz
import csv
import locale
import json
import calendar

from db import get_db_connection
from auth_decorators import role_required

locale.setlocale(locale.LC_TIME, "th_TH.UTF-8")

app = Flask(__name__)
app.secret_key = "secret_key"


from doctor import doctor_bp
app.register_blueprint(doctor_bp)
doctor_bp = Blueprint('doctor_bp', __name__)

from admin import admin_bp
app.register_blueprint(admin_bp)
admin_bp = Blueprint('admin_bp', __name__)





# Initialize
def init_db():
    conn = get_db_connection()

    # users
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL,
            role_id INTEGER NOT NULL,
            sub_category_id INTEGER,
            gender TEXT,
            nickname TEXT,
            first_name TEXT,
            last_name TEXT,
            pr_code TEXT,
            phone TEXT,
            address TEXT,
            dob TEXT,
            start_date TEXT,
            education_level TEXT,
            ethnicity TEXT,
            nationality TEXT,
            emergency_name TEXT,
            emergency_phone TEXT,
            emergency_relation TEXT,
            special_ability TEXT,
            prev_company TEXT,
            prev_position TEXT,
            education_institution TEXT,
            probation BOOLEAN DEFAULT 1,  -- 1 ยังไม่ผ่านโปร, 0 ผ่านโปรแล้ว
            festival_option INTEGER DEFAULT 1,
            doctor_id INTEGER,
            incentive_sx_rate REAL DEFAULT 0, -- ส่วนคิดค่าคอมฯ
            incentive_aes_rate REAL DEFAULT 0,
            incentive_afc_rate REAL DEFAULT 0,
            credit REAL DEFAULT 0,
            translate REAL DEFAULT 0,
            or_aes REAL DEFAULT 0,
            extra_travel REAL DEFAULT 0,
            extra_phone REAL DEFAULT 0,
            online_page REAL DEFAULT 0,
            nurse REAL DEFAULT 0,
            pharmacy REAL DEFAULT 0,
            bonus REAL DEFAULT 0,
            manager REAL DEFAULT 0,
            FOREIGN KEY (role_id) REFERENCES roles(role_id),
            FOREIGN KEY (sub_category_id) REFERENCES sub_categories(sub_category_id)
        );
    """)


    # customers
    conn.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hn TEXT NOT NULL,
            prefix TEXT,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            first_service_date TEXT,
            service_type TEXT,
            nickname TEXT,
            gender TEXT,
            phone TEXT,
            birthday TEXT,
            age INTEGER,
            nationality TEXT,
            address TEXT,
            occupation TEXT,
            id_card_or_passport TEXT,
            emergency_contact TEXT,
            emergency_relationship TEXT,
            emergency_phone TEXT,
            drug_allergy_history TEXT,
            drug_allergy_symptoms TEXT,
            chronic_disease TEXT,
            current_medications TEXT,
            previous_surgeries TEXT,
            referral_channel TEXT,
            reason_to_choose_clinic TEXT,
            created_at TEXT
        );
    """)
    
    # doctors
    conn.execute("""
        CREATE TABLE IF NOT EXISTS doctors (
            doctor_id INTEGER PRIMARY KEY AUTOINCREMENT,
            thai_full_name TEXT NOT NULL,
            eng_full_name TEXT NOT NULL,
            short_name TEXT NOT NULL,
            license_number TEXT NOT NULL,
            start_date DATE NOT NULL,
            df_surgery REAL NOT NULL,
            df_aesthetic REAL NOT NULL,
            created_at DATETIME NOT NULL
        );
    """)

    # procedures
    conn.execute("""
        CREATE TABLE IF NOT EXISTS procedures (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_name TEXT NOT NULL,
            procedure_name TEXT NOT NULL,
            short_code TEXT NOT NULL,
            price REAL NOT NULL,
            aes_commission_rate REAL DEFAULT 0,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # daily_income_header สำหรับ Header ของรายรับประจำวัน
    conn.execute("""
        CREATE TABLE IF NOT EXISTS daily_income_header (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            record_date DATE NOT NULL,           -- วันที่บันทึก (YYYY-MM-DD)
            customer_id INTEGER NOT NULL,        -- อ้างอิงจากตาราง customers (เช่น customers.id)
            total_price INTEGER NOT NULL,        -- ผลรวมราคาจากรายการ detail (เช่น procedure_price รวมกัน)
            deposit INTEGER NOT NULL,            -- จำนวนเงินมัดจำ (integer)
            deposit_date DATE NOT NULL,          -- วันที่มัดจำ (YYYY-MM-DD)
            cash INTEGER NOT NULL,               -- จำนวนเงินสด
            transfer INTEGER NOT NULL,           -- จำนวนเงินโอน
            credit_card INTEGER NOT NULL,        -- จำนวนเงินชำระด้วยบัตรเครดิต
            credit_card_fee INTEGER NOT NULL,    -- ค่าธรรมเนียมบัตรเครดิต (จะไม่รวมใน total_price)
            is_final INTEGER DEFAULT 0,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # daily_income_detail เก็บรายละเอียดแต่ละ procedure (Detail)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS daily_income_detail (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            header_id INTEGER NOT NULL,          -- FK อ้างอิง daily_income_header.id
            procedure_doctor TEXT NOT NULL,      -- แพทย์ที่ทำ procedure นั้น ๆ
            procedure_category TEXT NOT NULL,    -- หมวดหมู่ (surgery, aesthetic, aftercare, medicine, others)
            procedure_name TEXT NOT NULL,        -- ชื่อ procedure (ต้องไม่ว่าง)
            procedure_short_code TEXT NOT NULL,  -- รหัสย่อของ procedure
            procedure_price INTEGER NOT NULL,    -- ราคาของ procedure (ในหน่วย integer)
            pr_code1 TEXT NOT NULL,              -- รหัส PR คนที่ 1
            pr_price1 INTEGER NOT NULL,          -- ราคาของ PR คนที่ 1
            pr_code2 TEXT,                      -- รหัส PR คนที่ 2 (อาจว่างได้)
            pr_price2 INTEGER,                  -- ราคาของ PR คนที่ 2
            pr_code3 TEXT,                      -- รหัส PR คนที่ 3 (อาจว่างได้)
            pr_price3 INTEGER,                  -- ราคาของ PR คนที่ 3
            aes_assigned_user_id INTEGER DEFAULT NULL,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (header_id) REFERENCES daily_income_header(id)
        );
    """)

    # user_commissions
    conn.execute("""
        CREATE TABLE IF NOT EXISTS user_commissions (
            user_pr_code TEXT,
            procedure_name TEXT,
            commission_type TEXT CHECK(commission_type IN ('PERCENT','FIX')),
            commission_value REAL,
            PRIMARY KEY (user_pr_code, procedure_name)
        );
    """)

    # credit_commission
    conn.execute("""
        CREATE TABLE IF NOT EXISTS credit_commission (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            year INT NOT NULL,
            month INT NOT NULL,
            credit_value REAL NOT NULL DEFAULT 0.0,
            created_at TEXT,
            updated_at TEXT,
            UNIQUE(user_id, year, month)
        );
    """)

    # translate_commission
    conn.execute("""
        CREATE TABLE IF NOT EXISTS translate_commission (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            record_date TEXT NOT NULL,
            word_count INTEGER DEFAULT 0,
            article_link TEXT,
            created_at TEXT,
            updated_at TEXT
        );
    """)

    # payday_config
    conn.execute("""
        CREATE TABLE IF NOT EXISTS payday_config (
            user_id INTEGER NOT NULL,   -- 0 หมายถึง default 
            year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            salary_pay_day INTEGER DEFAULT 28,
            welfare_pay_day INTEGER DEFAULT 10,
            updated_at TEXT,
            PRIMARY KEY (user_id, year, month),
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        );
    """)

    # สร้าง admin ถ้าไม่มี
    admin_exists = conn.execute("SELECT * FROM users WHERE role='ADMIN'").fetchone()
    if not admin_exists:
        from werkzeug.security import generate_password_hash

        # แฮชรหัสผ่าน
        pw_hash = generate_password_hash("wemedical0666")

        # ดึง role_id และ sub_category_id ของ ADMIN
        role_row = conn.execute("SELECT role_id FROM roles WHERE role_name = 'ADMIN'").fetchone()
        sub_category_row = conn.execute("""
            SELECT sub_category_id 
            FROM sub_categories 
            WHERE role_id = (SELECT role_id FROM roles WHERE role_name = 'ADMIN') 
            AND sub_category_name = 'ADMIN (System)'
            LIMIT 1
        """).fetchone()

        # ตรวจสอบว่า role_id และ sub_category_id มีอยู่ในระบบ
        if role_row and sub_category_row:
            role_id = role_row['role_id']
            sub_category_id = sub_category_row['sub_category_id']

            # เพิ่ม Admin ผู้ใช้ใหม่
            conn.execute("""
                INSERT INTO users (first_name, last_name, username, password_hash, role_id, sub_category_id)
                VALUES (?, ?, ?, ?, ?, ?)
            """, ("Super", "Admin", "admin", pw_hash, role_id, sub_category_id))
            conn.commit()
        else:
            print("Error: ไม่พบ role_id หรือ sub_category_id สำหรับ ADMIN")

    # system_config
    conn.execute("""
        CREATE TABLE IF NOT EXISTS system_config (
            config_key TEXT PRIMARY KEY,
            config_value TEXT
        );
    """)
    row = conn.execute("SELECT * FROM system_config WHERE config_key='employee_join_code'").fetchone()
    if not row:
        conn.execute("""
            INSERT INTO system_config (config_key, config_value)
            VALUES ('employee_join_code','CHANGE_ME')
        """)
    
    # workflow_config
    conn.execute("""
        CREATE TABLE IF NOT EXISTS workflow_config (
            config_id INTEGER PRIMARY KEY AUTOINCREMENT,
            function_key TEXT NOT NULL,
            require_subcategory INTEGER DEFAULT 0,
            allowed_subcategory_ids TEXT,
            description TEXT
        );
    """)

    # roles
    conn.execute("""
        CREATE TABLE IF NOT EXISTS roles (
            role_id INTEGER PRIMARY KEY AUTOINCREMENT,
            role_name TEXT NOT NULL UNIQUE
        );
    """)
    
    # sub_categories
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sub_categories (
            sub_category_id INTEGER PRIMARY KEY AUTOINCREMENT,
            role_id INTEGER NOT NULL,
            sub_category_name TEXT NOT NULL,
            FOREIGN KEY (role_id) REFERENCES roles(role_id),
            UNIQUE(role_id, sub_category_name)
        );
    """)

    # subcat_access
    conn.execute("""
        CREATE TABLE IF NOT EXISTS subcat_access (
            parent_subcat_id INTEGER NOT NULL,
            child_subcat_id INTEGER NOT NULL,
            PRIMARY KEY (parent_subcat_id, child_subcat_id),
            FOREIGN KEY (parent_subcat_id) REFERENCES sub_categories(sub_category_id),
            FOREIGN KEY (child_subcat_id) REFERENCES sub_categories(sub_category_id)
        );
    """)

    # ตาราง attendance
    conn.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            attendance_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            checkin_time DATETIME,
            checkout_time DATETIME,
            work_date DATE NOT NULL,
            late_minutes INTEGER DEFAULT 0,
            late_reason TEXT,
            ot_before_midnight INTEGER DEFAULT 0,
            ot_after_midnight INTEGER DEFAULT 0,
            ot_status TEXT DEFAULT 'pending',
            ot_reason TEXT,
            ot_approve_comment TEXT,
            approved_by INTEGER,
            first_approver_id INTEGER,
            final_approver_id INTEGER,
            FOREIGN KEY (user_id) REFERENCES users(user_id),
            FOREIGN KEY (approved_by) REFERENCES users(user_id)
        );
    """)

    # work_schedules
    conn.execute("""
        CREATE TABLE IF NOT EXISTS work_schedules (
            schedule_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            work_date TEXT NOT NULL,
            planned_start_time TEXT,
            planned_end_time TEXT,
            UNIQUE(user_id, work_date),
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        );
    """)

    # leave_quota
    conn.execute("""
        CREATE TABLE IF NOT EXISTS leave_quota (
            quota_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            leave_type TEXT NOT NULL,
            carry_forward INTEGER DEFAULT 0,
            total_days INTEGER DEFAULT 0,
            used_days INTEGER DEFAULT 0,
            year INTEGER NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        );
    """)

    # leave_requests
    conn.execute("""
        CREATE TABLE IF NOT EXISTS leave_requests (
            leave_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            leave_type TEXT,
            start_date TEXT,
            end_date TEXT,
            reason TEXT,
            status TEXT DEFAULT 'pending',
            hr_comment TEXT,
            days_requested INTEGER DEFAULT 0,
            updated_by INTEGER,
            created_at DATETIME,
            updated_at DATETIME,
            updated_by INTEGER,
            medical_certificate BOOLEAN DEFAULT 0,
            medical_certificate_submitted BOOLEAN DEFAULT 0,
            first_approver_id INTEGER,
            final_approver_id INTEGER,
            FOREIGN KEY(user_id) REFERENCES users(user_id),
            FOREIGN KEY(updated_by) REFERENCES users(user_id)
        );
    """)

    # festival_option_requests ลาเทศกาล
    conn.execute("""
        CREATE TABLE IF NOT EXISTS festival_option_requests (
            request_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            original_option INTEGER,
            chosen_option INTEGER NOT NULL,  -- 1=13,2=4,3=1
            reason TEXT,                     -- ถ้ามี
            status TEXT DEFAULT 'pending',   -- pending, approved, rejected
            created_at TEXT,
            approved_at TEXT,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        );
    """)

    # loan_deduction_records หัก กยศ
    conn.execute("""
        CREATE TABLE IF NOT EXISTS loan_deduction_records (
            record_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            loan_deduction REAL DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id),
            UNIQUE(user_id, year, month) -- ป้องกันการบันทึกซ้ำ
        );
    """)

    # tax_deduction_records หัก ภาษี ณ ที่จ่าย
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tax_deduction_records (
            record_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            tax_deduction REAL DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id),
            UNIQUE(user_id, year, month)  -- ป้องกันการบันทึกข้อมูลซ้ำ
        );
    """)

    # other_deductions
    conn.execute("""
        CREATE TABLE IF NOT EXISTS other_deductions (
            deduction_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            deduction_type TEXT NOT NULL,  -- เช่น "ค่าหักอื่นๆ", "เบี้ยเลี้ยง", ฯลฯ
            deduction_amount REAL NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        );
    """)

    # notifications
    conn.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            notif_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            message TEXT NOT NULL,
            is_read INTEGER DEFAULT 0,
            created_at DATETIME,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        );
    """)

    # salary_records ฐานเงินเดือน
    conn.execute("""
    CREATE TABLE IF NOT EXISTS salary_records (
        salary_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        base_salary DECIMAL(10,2),
        daily_wage DECIMAL(10,2),
        hourly_wage DECIMAL(10,2),
        effective_date TEXT,
        created_at DATETIME,
        updated_at DATETIME,
        FOREIGN KEY(user_id) REFERENCES users(user_id)
    );
    """)  

    # salary_history ประวัติปรับฐานเงินเดือน
    conn.execute("""
    CREATE TABLE IF NOT EXISTS salary_history (
        history_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        new_salary DECIMAL(10,2),
        reason TEXT,
        effective_date TEXT,
        created_at DATETIME,
        FOREIGN KEY(user_id) REFERENCES users(user_id)
    );
    """)  

    # insurance_fund แสดงเงินประกันสะสม
    conn.execute("""
    CREATE TABLE IF NOT EXISTS insurance_fund (
        fund_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        month INTEGER,
        year INTEGER,
        deducted_amount DECIMAL(10,2) DEFAULT 0,       -- หักจากเงินเดือน
        company_contribute DECIMAL(10,2) DEFAULT 0,    -- บริษัทสมทบ
        withdraw_amount DECIMAL(10,2) DEFAULT 0,       -- เบิกออก
        repay_amount DECIMAL(10,2) DEFAULT 0,          -- คืนสะสม
        comment TEXT,
        created_at DATETIME,
        FOREIGN KEY(user_id) REFERENCES users(user_id)
    );
    """)

    # insurance_fund_config เก็บค่าว่าหักเงินประกันสะสมเดือนละเท่าไหร่
    conn.execute("""
    CREATE TABLE IF NOT EXISTS insurance_fund_config (
        config_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        monthly_deduction DECIMAL(10,2) DEFAULT 1000, 
        active_deduction INTEGER DEFAULT 1,      -- 1=ยังหัก, 0=หยุดหัก
        effective_date TEXT,                     -- YYYY-MM-DD (อาจตั้งเป็นวันที่เริ่มใช้ config นี้)
        created_at TEXT,
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    );
    """)

    # insurance_stop_request ขอหยุดหักเงินประกันสะสม
    conn.execute("""
    CREATE TABLE IF NOT EXISTS insurance_stop_request (
        stop_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        request_date TEXT,           -- วันที่ user ยื่นคำขอ (YYYY-MM-DD หรือ DATETIME)
        request_type TEXT DEFAULT 'STOP', -- 'STOP' or 'REACTIVATE'
        reason TEXT,                 -- เหตุผล
        status TEXT DEFAULT 'pending', -- 'pending','approved','rejected'
        updated_at TEXT,
        FOREIGN KEY(user_id) REFERENCES users(user_id)
    );
    """)

    # insurance_withdraw_request ขอเบิกเงินสะสม
    conn.execute("""
    CREATE TABLE IF NOT EXISTS insurance_withdraw_request (
        request_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        request_date TEXT,          -- วันที่ user ขอ
        withdraw_amount DECIMAL(10,2) NOT NULL,  -- ยอดที่จะเบิก 
        repay_months INTEGER,                   -- จำนวนเดือนที่จะผ่อนคืน (<=12)
        monthly_repay DECIMAL(10,2),            -- จำนวนเงินที่ต้องคืนต่อเดือน (อย่างน้อย 1,000)
        status TEXT DEFAULT 'pending',          -- 'pending','approved','rejected'
        updated_at TEXT, 
        FOREIGN KEY(user_id) REFERENCES users(user_id)
    );
    """)

    # insurance_repay_plan แจ้งคืนเงินสะสมกลับ
    conn.execute("""
    CREATE TABLE IF NOT EXISTS insurance_repay_plan (
        plan_id INTEGER PRIMARY KEY AUTOINCREMENT,
        request_id INTEGER NOT NULL,   -- อ้างอิงมาจากตาราง withdraw_request
        user_id INTEGER NOT NULL,
        repay_month INTEGER,           -- เดือนที่จะเริ่มหัก, หรือเดือนลำดับที่
        repay_amount DECIMAL(10,2),    -- ยอดที่จะหักคืนในเดือนนั้น
        status TEXT DEFAULT 'unpaid',  -- 'unpaid','paid'
        updated_at TEXT,
        FOREIGN KEY(request_id) REFERENCES insurance_withdraw_request(request_id),
        FOREIGN KEY(user_id) REFERENCES users(user_id)
    );
    """)

    # insurance_repay-stop_request ขอคืนเงินเบิกสะสมเต็มจำนวน
    conn.execute("""
    CREATE TABLE IF NOT EXISTS insurance_repay_stop_request (
        stop_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        request_id INTEGER NOT NULL,   -- ชี้ไปที่ insurance_withdraw_request
        request_date TEXT,
        lumpsum_amount DECIMAL(10,2),
        reason TEXT,
        status TEXT DEFAULT 'pending',
        updated_at TEXT,
        FOREIGN KEY(user_id) REFERENCES users(user_id),
        FOREIGN KEY(request_id) REFERENCES insurance_withdraw_request(request_id)
    );
    """)

    conn.commit()
    conn.close()

    initialize_roles()
    initialize_sub_categories()
    initialize_default_workflow_configurations()



# ------------------------------------------- #
# ------------------------------------------- #
# ------------------------------------------- #
#                    'HR'                     #
# ------------------------------------------- #
# ------------------------------------------- #
# ------------------------------------------- #



# ดึง configuration ของฟังก์ชันที่ต้องการ
def get_workflow_config(function_key):
    conn = get_db_connection()
    row = conn.execute("""
        SELECT * FROM workflow_config WHERE function_key = ?
    """, (function_key,)).fetchone()
    conn.close()
    if row:
        # แปลง allowed_subcategory_ids เป็นลิสต์ของตัวเลข หากมีข้อมูล
        allowed = []
        if row["allowed_subcategory_ids"]:
            allowed = [int(x.strip()) for x in row["allowed_subcategory_ids"].split(",")]
        return {
            "require_subcategory": bool(row["require_subcategory"]),
            "allowed_subcategory_ids": allowed,
            "description": row["description"]
        }
    return {}


# Flexible Decorator สำหรับตรวจสอบ Subcategory
def subcategory_required(function_key):
    """
    Decorator สำหรับตรวจสอบสิทธิ์ subcategory ตาม configuration ของฟังก์ชัน
    function_key: ชื่อฟังก์ชันหรือ request type ที่ใช้ดึง configuration
    """
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            # ตรวจสอบว่ามี sub_category_id ใน session หรือไม่
            if 'sub_category_id' not in session:
                return "ไม่มีสิทธิ์ (ไม่พบ sub_category_id ใน session)"
            user_subcat = session['sub_category_id']
            # ดึง configuration ของฟังก์ชันจากตาราง workflow_config
            config = get_workflow_config(function_key)
            # หาก configuration ระบุให้ require subcategory
            if config.get('require_subcategory', False):
                allowed = config.get('allowed_subcategory_ids', [])
                if user_subcat not in allowed:
                    return "ไม่มีสิทธิ์; คุณไม่ได้รับอนุญาตให้เข้าถึงฟังก์ชันนี้"
            return f(*args, **kwargs)
        return wrapper
    return decorator


# dictionary ที่เก็บ default configuration สำหรับแต่ละฟังก์ชัน
def initialize_default_workflow_configurations():
    # สร้าง dictionary ที่เก็บ default configuration สำหรับแต่ละฟังก์ชัน
    default_configs = {
        "ot_approval_list": {"require_subcategory": 1, "allowed_subcategory_ids": "2,3,4,5,6,7", "description": "เฉพาะ HR, GM"},
        "ot_approve": {"require_subcategory": 1, "allowed_subcategory_ids": "2,3,4,5,6,7", "description": "เฉพาะ HR, GM"},
        "tax_deduction": {"require_subcategory": 1, "allowed_subcategory_ids": "16", "description": "เฉพาะ SECRETARY"},
        "tax_deduction_history": {"require_subcategory": 1, "allowed_subcategory_ids": "16", "description": "เฉพาะ SECRETARY"},
        "daily_income": {"require_subcategory": 1, "allowed_subcategory_ids": "14", "description": "เฉพาะ ฝ่ายบัญชี"},
        "get_daily_income_detail": {"require_subcategory": 1, "allowed_subcategory_ids": "14", "description": "เฉพาะ ฝ่ายบัญชี"},
        "edit_daily_income": {"require_subcategory": 1, "allowed_subcategory_ids": "14", "description": "เฉพาะ ฝ่ายบัญชี"},
        "delete_daily_income": {"require_subcategory": 1, "allowed_subcategory_ids": "14", "description": "เฉพาะ ฝ่ายบัญชี"},
        "search_customer_for_daily_income": {"require_subcategory": 1, "allowed_subcategory_ids": "14", "description": "เฉพาะ ฝ่ายบัญชี"},
        "aes_commission_rate": {"require_subcategory": 1, "allowed_subcategory_ids": "1,5", "description": "เฉพาะ หัวหน้า OR"},
        "aes_commission_assignment": {"require_subcategory": 1, "allowed_subcategory_ids": "5,10", "description": "เฉพาะ แผนก OR"},
        "pr_income_summary": {"require_subcategory": 1, "allowed_subcategory_ids": "4,5,9,16", "description": "เฉพาะ PR"},
        "translate_commission": {"require_subcategory": 1, "allowed_subcategory_ids": "1,2,9", "description": "เฉพาะ PA INDO"},



        # เพิ่มฟังก์ชันอื่นๆ ที่ต้องการ default configuration ที่นี่
    }
    
    conn = get_db_connection()
    for function_key, config in default_configs.items():
        cur = conn.execute("SELECT COUNT(*) AS count FROM workflow_config WHERE function_key = ?", (function_key,))
        row = cur.fetchone()
        if row["count"] == 0:
            conn.execute("""
                INSERT INTO workflow_config (function_key, require_subcategory, allowed_subcategory_ids, description)
                VALUES (?, ?, ?, ?)
            """, (function_key, config["require_subcategory"], config["allowed_subcategory_ids"], config["description"]))
    conn.commit()
    conn.close()


# ข้อมูลเริ่มต้นใน roles
def initialize_roles():
    conn = get_db_connection()
    existing_roles = conn.execute("SELECT COUNT(*) AS count FROM roles").fetchone()['count']
    if existing_roles == 0:
        conn.executemany("""
            INSERT INTO roles (role_name) VALUES (?)
        """, [
            ('ADMIN',),
            ('HR',),
            ('MANAGER',),
            ('EMPLOYEE',),
            ('OPD',),
            ('SECRETARY',),
            ('DOCTOR',),
            ('PATIENT',)
        ])
        conn.commit()
    conn.close()


# ข้อมูลเริ่มต้นใน sub_categories
def initialize_sub_categories():
    conn = get_db_connection()
    roles = conn.execute("SELECT role_id, role_name FROM roles").fetchall()
    role_map = {row['role_name']: row['role_id'] for row in roles}

    existing_sub_categories = conn.execute("SELECT COUNT(*) AS count FROM sub_categories").fetchone()['count']

    if existing_sub_categories == 0:
        sub_categories_data = [
            (role_map['ADMIN'], 'ADMIN (System)'),
            (role_map['HR'], 'HR (GENERAL)'),
            (role_map['MANAGER'], 'MANAGER (GENERAL)'),
            (role_map['MANAGER'], 'MANAGER (PA)'),
            (role_map['MANAGER'], 'MANAGER (OR)'),
            (role_map['MANAGER'], 'MANAGER (ADMIN_ONLINE)'),
            (role_map['MANAGER'], 'MANAGER (MARKETING)'),
            (role_map['HR'], 'HR (PAYROLL)'),
            (role_map['EMPLOYEE'], 'EMPLOYEE (PA)'),
            (role_map['EMPLOYEE'], 'EMPLOYEE (OR)'),
            (role_map['EMPLOYEE'], 'EMPLOYEE (ADMIN_ONLINE)'),
            (role_map['EMPLOYEE'], 'EMPLOYEE (MARKETING)'),
            (role_map['OPD'], 'OPD (CS)'),
            (role_map['OPD'], 'OPD (FINANCE)'),
            (role_map['OPD'], 'OPD (PATIENT)'),
            (role_map['SECRETARY'], 'SECRETARY'),
            (role_map['SECRETARY'], 'SECRETARY ASSISTANCE'),
            (role_map['DOCTOR'], 'DOCTOR'),
            (role_map['PATIENT'], 'PATIENT'),
        ]

        conn.executemany("""
            INSERT INTO sub_categories (role_id, sub_category_name)
            VALUES (?, ?)
        """, sub_categories_data)
        conn.commit()
    conn.close()


# default role ใน sub_category
def add_default_subcategory(role_id, role_name):
    conn = get_db_connection()

    # ตรวจสอบว่ามี Subcategory อยู่หรือไม่
    existing = conn.execute("""
        SELECT COUNT(*) AS count
        FROM sub_categories
        WHERE role_id = ?
    """, (role_id,)).fetchone()['count']

    if existing == 0:  # ถ้ายังไม่มี Subcategory
        conn.execute("""
            INSERT INTO sub_categories (role_id, sub_category_name)
            VALUES (?, ?)
        """, (role_id, "General"))  # ตั้งค่า Default Subcategory เป็น General
        conn.commit()

    conn.close()


# ดึง Role ทั้งหมดพร้อม Subcategories
def get_roles_with_subcategories():
    conn = get_db_connection()

    # Query Role และ Subcategory โดยกำจัดข้อมูลซ้ำ
    rows = conn.execute("""
        SELECT DISTINCT
            r.role_id, 
            r.role_name, 
            sc.sub_category_id, 
            sc.sub_category_name
        FROM roles r
        LEFT JOIN sub_categories sc ON r.role_id = sc.role_id
        ORDER BY sc.sub_category_id ASC
    """).fetchall()

    # จัดกลุ่ม Role และ Subcategories
    roles = {}
    for row in rows:
        role_id = row['role_id']
        role_name = row['role_name']
        sub_category_id = row['sub_category_id']
        sub_category_name = row['sub_category_name']

        # ถ้า Role ยังไม่มีในผลลัพธ์ ให้เพิ่ม Role พร้อม Subcategories ว่าง
        if role_id not in roles:
            roles[role_id] = {
                "role_id": role_id,
                "role_name": role_name,
                "sub_categories": []
            }

        # ถ้ามี Subcategory ให้เพิ่มใน Role
        if sub_category_id:
            roles[role_id]["sub_categories"].append({
                "sub_category_id": sub_category_id,
                "sub_category_name": sub_category_name
            })

    conn.close()
    return list(roles.values())


# Check out ส่งข้อมูลจาก Employee > Manager แผนก
def get_manager_for_employee(employee_subcat_id):
    """
    ดึง user_id ของ Manager (child manager) สำหรับพนักงานที่มี employee_subcat_id
    ตัวอย่าง: ถ้า employee_subcat_id = 9 (EMPLOYEE (PA)) แล้วในตาราง subcat_access มี row (4,9)
             จะได้ manager_subcat_id = 4 ซึ่งในตาราง users ควรมี MANAGER (PA) ที่มี sub_category_id = 4
    """
    conn = get_db_connection()
    row = conn.execute("""
        SELECT parent_subcat_id
        FROM subcat_access
        WHERE child_subcat_id = ?
    """, (employee_subcat_id,)).fetchone()
    if row:
        manager_subcat_id = row['parent_subcat_id']
        user_row = conn.execute("""
            SELECT user_id
            FROM users
            WHERE sub_category_id = ? AND role LIKE 'MANAGER%'
            ORDER BY user_id LIMIT 1
        """, (manager_subcat_id,)).fetchone()
        conn.close()
        if user_row:
            return user_row['user_id']
    conn.close()
    return None


# Check out ส่งข้อมูลจาก Manager แผนก > Manager General
def get_parent_manager_for_employee(manager_subcat_id):
    """
    ดึง user_id ของ Parent Manager สำหรับ Manager ที่มี manager_subcat_id
    ตัวอย่าง: ถ้า manager_subcat_id = 4 (MANAGER (PA)) แล้วในตาราง subcat_access มี row (3,4)
             จะได้ parent_manager_subcat_id = 3 ซึ่งในตาราง users ควรมี MANAGER (GENERAL) ที่มี sub_category_id = 3
    """
    conn = get_db_connection()
    row = conn.execute("""
        SELECT parent_subcat_id
        FROM subcat_access
        WHERE child_subcat_id = ?
    """, (manager_subcat_id,)).fetchone()
    if row:
        parent_manager_subcat_id = row['parent_subcat_id']
        user_row = conn.execute("""
            SELECT user_id
            FROM users
            WHERE sub_category_id = ? AND role LIKE 'MANAGER%'
            ORDER BY user_id LIMIT 1
        """, (parent_manager_subcat_id,)).fetchone()
        conn.close()
        if user_row:
            return user_row['user_id']
    conn.close()
    return None


# Get Allowed ดึง employee subcategory IDs
def get_allowed_employee_subcategories(manager_subcat_id):
    """
    ดึงรายชื่อ employee subcategory IDs ที่ Manager (child) สามารถดูได้
    จากตาราง subcat_access โดยใช้ parent_subcat_id เป็น manager_subcat_id
    """
    conn = get_db_connection()
    rows = conn.execute("""
        SELECT child_subcat_id
        FROM subcat_access
        WHERE parent_subcat_id = ?
    """, (manager_subcat_id,)).fetchall()
    conn.close()
    # คืนค่าเป็น list ของตัวเลขหรือ string (ขึ้นอยู่กับการเก็บใน DB)
    return [row['child_subcat_id'] for row in rows]


# คำนวณ อายุงาน
def calc_service_age(start_date_str):
    if not start_date_str: return ""
    y,m,d = start_date_str.split('-')
    start_d = date(int(y),int(m),int(d))
    today = date.today()
    days = (today - start_d).days
    if days<0: return "ยังไม่ถึงวันเริ่มงาน"
    years = days//365
    remain = days%365
    months = remain//30
    day_left = remain%30
    return f"{years} ปี {months} เดือน {day_left} วัน"


# คำนวณ อายุพนักงาน
def calc_age(dob_str):
    """คำนวณอายุจากวันเกิด dob_str (รูปแบบ YYYY-MM-DD) แล้วคืนเป็น string เช่น '25 ปี 3 เดือน 12 วัน' """
    if not dob_str:
        return ""  # กรณีไม่มีข้อมูลวันเกิด
    try:
        y, m, d = dob_str.split('-')
        birth_date = date(int(y), int(m), int(d))
        today = date.today()
        days = (today - birth_date).days

        if days < 0:
            return "ยังไม่เกิด"  # เผื่อกรณีข้อมูลผิด หรืออนาคต

        years = days // 365
        remain = days % 365
        months = remain // 30
        return f"{years} ปี {months} เดือน"

    except:
        return ""


# คำนวณเวลา (ชั่วโมง-นาที)
def format_hh_mm(minutes):
    h = minutes//60
    m = minutes%60
    return f"{h} ชม. {m} นาที"


# Calculate Late Minutes คำนวณ มาสาย (นาที)
def calculate_late_minutes(planned_start, checkin_time):
    try:
        checkin_dt = datetime.strptime(checkin_time, "%Y-%m-%d %H:%M:%S")
    except Exception as e:
        print("Error parsing checkin_time:", e)
        return 0

    # สร้างเวลาที่วางแผน (planned_start_dt) โดยใช้วันที่เดียวกับ checkin_dt
    try:
        start_hour, start_minute = map(int, planned_start.split(":"))
    except Exception as e:
        print("Error parsing planned_start:", e)
        return 0

    planned_start_dt = checkin_dt.replace(hour=start_hour, minute=start_minute, second=0, microsecond=0)
    if checkin_dt <= planned_start_dt:
        return 0
    delta = checkin_dt - planned_start_dt
    return int(delta.total_seconds() // 60)


# Calculate OT Split คำนวณ OT ก่อน-หลังเที่ยงคืน (ชั่วโมง-นาที)
def calculate_ot_split(planned_end, checkout_time):
    try:
        checkout_dt = datetime.strptime(checkout_time, "%Y-%m-%d %H:%M:%S")
    except Exception as e:
        print("Error parsing checkout_time:", e)
        return 0, 0

    try:
        end_hour, end_minute = map(int, planned_end.split(":"))
    except Exception as e:
        print("Error parsing planned_end:", e)
        return 0, 0

    planned_end_dt = checkout_dt.replace(hour=end_hour, minute=end_minute, second=0, microsecond=0)
    if checkout_dt <= planned_end_dt:
        return 0, 0

    overtime = checkout_dt - planned_end_dt
    # กำหนดเที่ยงคืนของวันเดียวกัน (สำหรับ OT ก่อนเที่ยงคืน)
    midnight = checkout_dt.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    
    if checkout_dt <= midnight:
        ot_before_midnight = overtime
        ot_after_midnight = timedelta(0)
    else:
        ot_before_midnight = midnight - planned_end_dt
        ot_after_midnight = checkout_dt - midnight

    return int(ot_before_midnight.total_seconds() // 60), int(ot_after_midnight.total_seconds() // 60)


# Save Attendance บันทึกเวลาเข้า-ออกงาน
def save_attendance(user_id, checkin_time, checkout_time, work_date, planned_start=None, planned_end=None):
    conn = get_db_connection()

    # เติม Default Work Schedule หากยังไม่มี
    ensure_work_schedule(user_id, work_date)

    # ดึงข้อมูล Work Schedule
    schedule = conn.execute("""
        SELECT planned_start_time, planned_end_time
        FROM work_schedules
        WHERE user_id = ? AND work_date = ?
    """, (user_id, work_date)).fetchone()

    planned_start = planned_start or schedule['planned_start_time']
    planned_end = planned_end or schedule['planned_end_time']

    # ตรวจสอบข้อมูล Attendance ซ้ำ
    existing = conn.execute("""
        SELECT * FROM attendance
        WHERE user_id = ? AND work_date = ?
    """, (user_id, work_date)).fetchone()

    if existing:
        print("Attendance already exists for this date")
        conn.close()
        return

    # คำนวณค่ามาสายและ OT
    late_minutes = calculate_late_minutes(planned_start, checkin_time)
    ot_before_midnight, ot_after_midnight = calculate_ot_split(planned_end, checkout_time)

    # บันทึก Attendance
    conn.execute("""
        INSERT INTO attendance (user_id, checkin_time, checkout_time, work_date, late_minutes, ot_before_midnight, ot_after_midnight)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (user_id, checkin_time, checkout_time, work_date, late_minutes, ot_before_midnight, ot_after_midnight))

    conn.commit()
    conn.close()


# Calculate Payroll เพื่อใช้ใน Payroll Summary
def calculate_payroll(user_id, month, year, is_final=False):
    conn = get_db_connection()

    debug_var = {}  # เอาไว้เก็บ debug ชั่วคราว

    # =============== 1) ดึงข้อมูลฐานเงินเดือน ===============
    row_salary = conn.execute("""
        SELECT base_salary
        FROM salary_records
        WHERE user_id = ?
        ORDER BY effective_date DESC
        LIMIT 1
    """, (user_id,)).fetchone()

    if not row_salary:
        conn.close()
        return {
            "error": "ไม่พบข้อมูลฐานเงินเดือนในระบบ",
            "debug_var": {"no_salary_row_for_user": user_id}
        }

    base_salary = float(row_salary['base_salary'])
    daily_wage = base_salary / 30.0
    hourly_wage = daily_wage / 8.0

    # เก็บลง debug
    debug_var["base_salary"] = base_salary
    debug_var["daily_wage"] = daily_wage
    debug_var["hourly_wage"] = hourly_wage

    # =============== 2) festival_option => festival_comp ===============
    row_opt = conn.execute("""
        SELECT festival_option, pr_code,
               incentive_sx_rate, incentive_aes_rate, incentive_afc_rate,
               credit, translate, or_aes,
               extra_travel, extra_phone, online_page,
               nurse, pharmacy, bonus, manager
        FROM users
        WHERE user_id = ?
    """, (user_id,)).fetchone()

    if not row_opt:
        conn.close()
        return {
            "error": "ไม่พบ user นี้ในตาราง users",
            "debug_var": {"no_user_in_users": user_id}
        }

    festival_opt = row_opt['festival_option'] or 1
    user_pr_code = row_opt['pr_code']

    # float() ป้องกัน error
    incentive_sx_rate  = float(row_opt['incentive_sx_rate']  or 0)
    incentive_aes_rate = float(row_opt['incentive_aes_rate'] or 0)
    incentive_afc_rate = float(row_opt['incentive_afc_rate'] or 0)
    user_credit        = float(row_opt['credit']    or 0)
    user_translate     = float(row_opt['translate'] or 0)
    user_or_aes        = float(row_opt['or_aes']    or 0)
    extra_travel       = float(row_opt['extra_travel'] or 0)
    extra_phone        = float(row_opt['extra_phone']  or 0)
    online_page        = float(row_opt['online_page']  or 0)
    nurse_value        = float(row_opt['nurse']        or 0)
    pharmacy_value     = float(row_opt['pharmacy']     or 0)
    bonus_value        = float(row_opt['bonus']        or 0)
    manager_value      = float(row_opt['manager']      or 0)

    festival_comp = 0.0
    festival_bonus_rate = daily_wage
    if festival_opt == 2:
        # สมมติห้ามในเดือน 1,4,12
        if month not in [1, 4, 12]:
            festival_comp = festival_bonus_rate
    elif festival_opt == 3:
        festival_comp = festival_bonus_rate

    debug_var["festival_opt"] = festival_opt
    debug_var["festival_comp"] = festival_comp

    # =============== 3) Attendance => OT, late ===============
    attendance_rows = conn.execute("""
        SELECT late_minutes, ot_before_midnight, ot_after_midnight
        FROM attendance
        WHERE user_id = ?
          AND strftime('%Y', work_date) = ?
          AND strftime('%m', work_date) = ?
    """, (user_id, str(year), f"{month:02d}")).fetchall()

    total_ot_before = sum(r['ot_before_midnight'] for r in attendance_rows)
    total_ot_after = sum(r['ot_after_midnight'] for r in attendance_rows)
    ot_income_before = (total_ot_before / 60) * hourly_wage * 1.5
    ot_income_after  = (total_ot_after  / 60) * hourly_wage * 2.0

    ot_before_h = int(total_ot_before // 60)
    ot_before_m = int(total_ot_before % 60)
    ot_after_h  = int(total_ot_after  // 60)
    ot_after_m  = int(total_ot_after  % 60)

    debug_var["attendance_rows_count"] = len(attendance_rows)
    debug_var["total_ot_before"] = total_ot_before
    debug_var["total_ot_after"]  = total_ot_after

    incomes = []

    # OT ก่อนเที่ยงคืน
    if ot_income_before > 0:
        incomes.append({
            "description": "OT ก่อนเที่ยงคืน",
            "quantity": f"{ot_before_h} ชม. {ot_before_m} นาที",
            "rate": f"1.5 × {hourly_wage:,.2f}",
            "amount": round(ot_income_before, 2)
        })
    # OT หลังเที่ยงคืน
    if ot_income_after > 0:
        incomes.append({
            "description": "OT หลังเที่ยงคืน",
            "quantity": f"{ot_after_h} ชม. {ot_after_m} นาที",
            "rate": f"2 × {hourly_wage:,.2f}",
            "amount": round(ot_income_after, 2)
        })
    # ชดเชยวันนักขัตฤกษ์
    if festival_comp > 0:
        incomes.append({
            "description": "ชดเชยทำงานวันนักขัตฤกษ์",
            "quantity": "1 วัน",
            "rate": f"{festival_bonus_rate:,.2f}",
            "amount": round(festival_comp, 2)
        })

    # =============== 4) ค่าปรับสาย => net_salary ===============
    total_late = sum(r['late_minutes'] for r in attendance_rows)
    late_excess = max(0, total_late - 60)
    late_deduction = late_excess * 5.0

    debug_var["total_late"] = total_late
    debug_var["late_excess"] = late_excess
    debug_var["late_deduction"] = late_deduction

    # =============== 5) ตรวจใบลา => หักเงิน ===============
    leave_rows = conn.execute("""
        SELECT leave_type, days_requested
        FROM leave_requests
        WHERE user_id = ?
          AND status = 'approved'
          AND strftime('%Y', start_date) = ?
          AND strftime('%m', start_date) = ?
    """, (user_id, str(year), f"{month:02d}")).fetchall()

    leave_deductions = []
    total_leave_deduction = 0.0
    for lv in leave_rows:
        ltype = lv['leave_type']
        days_req = lv['days_requested']
        if ltype == "ลาเทศกาล":
            continue
        if ltype == "ลาฉุกเฉิน":
            rate = 2.0 * daily_wage
        else:
            rate = daily_wage
        amt = days_req * rate
        leave_deductions.append({
            "description": f"{ltype}",
            "quantity": f"{days_req} วัน",
            "rate": f"{rate:,.2f}",
            "amount": round(amt, 2)
        })
        total_leave_deduction += amt

    debug_var["leave_count"] = len(leave_rows)
    debug_var["total_leave_deduction"] = total_leave_deduction

    # =============== 6) Other Deductions ===============
    other_deductions = []
    total_other = 0.0

    # (6.1) กยศ.
    row_loan = conn.execute("""
        SELECT loan_deduction
        FROM loan_deduction_records
        WHERE user_id = ? AND year = ? AND month = ?
    """, (user_id, year, month)).fetchone()
    loan_deduct = float(row_loan['loan_deduction']) if row_loan else 0.0
    if loan_deduct > 0:
        other_deductions.append({
            "description": "ชำระค่า กยศ.",
            "quantity": "-",
            "rate": "ตามจริง",
            "amount": loan_deduct
        })
    total_other += loan_deduct

    # (6.2) ภาษี
    row_tax = conn.execute("""
        SELECT tax_deduction
        FROM tax_deduction_records
        WHERE user_id = ? AND year = ? AND month = ?
    """, (user_id, year, month)).fetchone()
    tax_deduct = float(row_tax['tax_deduction']) if row_tax else 0.0
    if tax_deduct > 0:
        other_deductions.append({
            "description": "หัก ภาษี ณ ที่จ่าย",
            "quantity": "-",
            "rate": "ตามจริง",
            "amount": tax_deduct
        })
    total_other += tax_deduct

    # (6.3) เงินประกันสะสม
    row_cfg = conn.execute("""
        SELECT monthly_deduction, active_deduction
        FROM insurance_fund_config
        WHERE user_id = ?
    """, (user_id,)).fetchone()
    insurance_fund = 0.0
    if row_cfg and row_cfg['active_deduction'] == 1:
        insurance_fund = float(row_cfg['monthly_deduction'] or 0.0)
    if insurance_fund > 0:
        other_deductions.append({
            "description": "เงินประกันสะสม",
            "quantity": "-",
            "rate": "สะสมอยู่",
            "amount": insurance_fund
        })
    total_other += insurance_fund

    # (6.4) หักอื่น ๆ
    row_others = conn.execute("""
        SELECT deduction_type, deduction_amount
        FROM other_deductions
        WHERE user_id = ? AND year = ? AND month = ?
    """, (user_id, year, month)).fetchall()
    for od in row_others:
        desc = od['deduction_type']
        amt = float(od['deduction_amount'] or 0.0)
        if amt > 0:
            other_deductions.append({
                "description": f"หัก {desc}",
                "quantity": "-",
                "rate": "-",
                "amount": amt
            })
        total_other += amt

    # (6.5) ผ่อนคืน
    repay_row = conn.execute("""
        SELECT repay_amount
        FROM insurance_repay_plan
        WHERE user_id = ?
          AND repay_month = ?
          AND status = 'unpaid'
    """, (user_id, year*100+month)).fetchone()
    if repay_row:
        repay_amt = float(repay_row['repay_amount'] or 0.0)
        if repay_amt > 0:
            other_deductions.append({
                "description": "ผ่อนคืนเงินสะสม (repay)",
                "quantity": "-",
                "rate": "-",
                "amount": repay_amt
            })
            total_other += repay_amt

    # =============== 7) คำนวณเบี้ยขยัน ===============
    row_user = conn.execute("""
        SELECT start_date
        FROM users
        WHERE user_id = ?
    """, (user_id,)).fetchone()
    if row_user and row_user['start_date']:
        sdt = datetime.strptime(row_user['start_date'], "%Y-%m-%d")
        lday = monthrange(year, month)[1]
        payroll_end_dt = date(year, month, lday)
        months_diff = (payroll_end_dt.year - sdt.year)*12 + (payroll_end_dt.month - sdt.month)
    else:
        months_diff = 0

    total_late_ok = (total_late <= 60)
    no_leave_this_month = (len(leave_rows) == 0)

    diligence_bonus = 0.0
    if total_late_ok and no_leave_this_month:
        if months_diff < 6:
            diligence_bonus = 1000.0
        else:
            diligence_bonus = 2000.0

    if diligence_bonus > 0:
        incomes.append({
            "description": "เบี้ยขยัน",
            "quantity": "ได้",
            "rate": "-",
            "amount": diligence_bonus
        })

    # =============== 8) Commission Calculation (เดิม) ===============
    cat_list = ["SX","AES","AFC","ค่ายาและบริการ","อื่นๆ"]
    total_commission = 0.0
    if user_pr_code:
        comm_rows = conn.execute("""
            SELECT procedure_name, commission_type, commission_value
            FROM user_commissions
            WHERE user_pr_code=?
        """,(user_pr_code,)).fetchall()
        commission_rate_map={}
        for c in comm_rows:
            pname=c['procedure_name']
            ctype=c['commission_type']
            cval=float(c['commission_value'] or 0)
            commission_rate_map[pname]={"type":ctype,"value":cval}

        sales_rows=conn.execute("""
            SELECT did.procedure_name AS pname,
                   did.procedure_category AS cat,
                   SUM(
                     CASE WHEN did.pr_code1=? THEN did.pr_price1
                          WHEN did.pr_code2=? THEN did.pr_price2
                          WHEN did.pr_code3=? THEN did.pr_price3
                          ELSE 0 END
                   ) as total_sales,
                   COUNT(
                     CASE WHEN (did.pr_code1=? AND did.pr_price1>0)
                           OR (did.pr_code2=? AND did.pr_price2>0)
                           OR (did.pr_code3=? AND did.pr_price3>0)
                           THEN 1 END
                   ) as total_cases
            FROM daily_income_detail did
            JOIN daily_income_header dih ON did.header_id=dih.id
            WHERE strftime('%Y',dih.record_date)=?
              AND strftime('%m',dih.record_date)=?
            GROUP BY did.procedure_name,did.procedure_category
        """,(user_pr_code, user_pr_code, user_pr_code,
             user_pr_code, user_pr_code, user_pr_code,
             str(year),f"{month:02d}")).fetchall()

        from collections import defaultdict
        cat_comm_sum=defaultdict(float)

        for rowX in sales_rows:
            pname=rowX['pname']
            cat=rowX['cat'] or "อื่นๆ"
            sales_amt=float(rowX['total_sales'] or 0)
            case_count=int(rowX['total_cases'] or 0)
            ctype="-"
            cval=0.0
            commission_amt=0.0
            if pname in commission_rate_map:
                ctype=commission_rate_map[pname]["type"]
                cval=commission_rate_map[pname]["value"]
                if ctype=="PERCENT":
                    commission_amt=(cval/100.0)*sales_amt
                elif ctype=="FIX":
                    commission_amt=cval*case_count
            cat_comm_sum[cat]+=commission_amt
            total_commission+=commission_amt

        for cat_item in cat_list:
            c_amt= cat_comm_sum[cat_item] if cat_item in cat_comm_sum else 0.0
            if c_amt>0:
                incomes.append({
                    "description": f"ค่าแนะนำ ({cat_item})",
                    "quantity":"", "rate":"", "amount":round(c_amt,2)
                })

    # =============== 8.1) คำนวณ incentive SX, AES, AFC ===============
    if user_pr_code:
        cat_incent_rows= conn.execute("""
            SELECT did.procedure_category AS cat,
                   SUM(
                     CASE WHEN did.pr_code1=? THEN did.pr_price1
                          WHEN did.pr_code2=? THEN did.pr_price2
                          WHEN did.pr_code3=? THEN did.pr_price3
                          ELSE 0 END
                   ) as total_amt
            FROM daily_income_detail did
            JOIN daily_income_header dih ON did.header_id=dih.id
            WHERE strftime('%Y',dih.record_date)=?
              AND strftime('%m',dih.record_date)=?
              AND did.procedure_category IN ('SX','AES','AFC')
            GROUP BY did.procedure_category
        """,(user_pr_code,user_pr_code,user_pr_code,
             str(year),f"{month:02d}")).fetchall()

        cat_incent_map={}
        for r2 in cat_incent_rows:
            cat2=r2['cat']
            cat_incent_map[cat2]=float(r2['total_amt'] or 0)

        sx_sum= cat_incent_map['SX'] if 'SX' in cat_incent_map else 0
        inc_sx= sx_sum*(incentive_sx_rate/10000.0)
        if inc_sx>0:
            incomes.append({
                "description":"Incentive SX",
                "quantity":"",
                "rate":f"× {incentive_sx_rate}",
                "amount":round(inc_sx,2)
            })

        aes_sum= cat_incent_map['AES'] if 'AES' in cat_incent_map else 0
        inc_aes= aes_sum*(incentive_aes_rate/100.0)
        if inc_aes>0:
            incomes.append({
                "description":"Incentive AES",
                "quantity":"",
                "rate":f"× {incentive_aes_rate}",
                "amount":round(inc_aes,2)
            })

        afc_sum= cat_incent_map['AFC'] if 'AFC' in cat_incent_map else 0
        inc_afc= afc_sum*(incentive_afc_rate/100.0)
        if inc_afc>0:
            incomes.append({
                "description":"Incentive AFC",
                "quantity":"",
                "rate":f"× {incentive_afc_rate}",
                "amount":round(inc_afc,2)
            })

    # =============== 8.2) credit commission ===============
    row_cc= conn.execute("""
        SELECT credit_value
        FROM credit_commission
        WHERE user_id=? AND year=? AND month=?
    """,(user_id,year,month)).fetchone()
    if row_cc:
        c_val= float(row_cc['credit_value'] or 0.0)
        c_amt= (c_val-25)* user_credit
        if c_amt<0: c_amt=0
        if c_amt>0:
            incomes.append({
                "description":"Credit Commission",
                "quantity":f"{c_val:.2f} -25",
                "rate":f"× {user_credit}",
                "amount":round(c_amt,2)
            })

    # =============== 8.3) translate ===============
    row_tc= conn.execute("""
        SELECT SUM(word_count) AS total_words
        FROM translate_commission
        WHERE user_id=?
          AND strftime('%Y', created_at)=?
          AND strftime('%m', created_at)=?
    """,(user_id,str(year),f"{month:02d}")).fetchone()
    total_words= float(row_tc['total_words'] or 0.0)
    if total_words>0:
        tran_amt= (total_words/6000.0)* user_translate
        if tran_amt>0:
            incomes.append({
                "description":"Translate Commission",
                "quantity":f"{int(total_words)} words",
                "rate":f"/6000 × {user_translate}",
                "amount":round(tran_amt,2)
            })

    # =============== 8.4) ค่ามือ AES ===============
    row_aes= conn.execute("""
        SELECT did.procedure_short_code AS short_code,
               COUNT(*) as case_count
        FROM daily_income_detail did
        JOIN daily_income_header dih ON did.header_id=dih.id
        WHERE did.procedure_category='AES'
          AND did.aes_assigned_user_id=?
          AND strftime('%Y',dih.record_date)=?
          AND strftime('%m',dih.record_date)=?
        GROUP BY did.procedure_short_code
    """,(user_id,str(year),f"{month:02d}")).fetchall()

    total_aes_hand= 0.0
    for rA in row_aes:
        sc= rA['short_code']
        cc= rA['case_count'] or 0
        prow= conn.execute("""
            SELECT aes_commission_rate
            FROM procedures
            WHERE short_code=?
        """,(sc,)).fetchone()
        if prow and prow['aes_commission_rate']:
            rateA= float(prow['aes_commission_rate'])
            total_aes_hand += (rateA* cc)

    aes_hand_amt= total_aes_hand* user_or_aes
    if aes_hand_amt>0:
        incomes.append({
            "description":"ค่ามือ AES",
            "quantity":f"cases={int(total_aes_hand)}",
            "rate":f"× {user_or_aes}",
            "amount":round(aes_hand_amt,2)
        })

    # =============== 8.5) extras from users ===============
    # Travel
    if extra_travel>0:
        incomes.append({
            "description":"ค่าเดินทาง",
            "quantity":"",
            "rate":"",
            "amount":round(extra_travel,2)
        })
    # Phone
    if extra_phone>0:
        incomes.append({
            "description":"ค่าโทรศัพท์",
            "quantity":"",
            "rate":"",
            "amount":round(extra_phone,2)
        })
    # Online Page
    if online_page>0:
        incomes.append({
            "description":"ค่าดูแลเพจ",
            "quantity":"",
            "rate":"",
            "amount":round(online_page,2)
        })
    # Nurse
    if nurse_value>0:
        incomes.append({
            "description":"วิชาชีพพยาบาล",
            "quantity":"",
            "rate":"",
            "amount":round(nurse_value,2)
        })
    # Pharmacy
    if pharmacy_value>0:
        incomes.append({
            "description":"วิชาชีพเภสัชกร",
            "quantity":"",
            "rate":"",
            "amount":round(pharmacy_value,2)
        })
    # Bonus
    if bonus_value>0:
        incomes.append({
            "description":"โบนัส",
            "quantity":"",
            "rate":"",
            "amount":round(bonus_value,2)
        })
    # Manager
    if manager_value>0:
        incomes.append({
            "description":"ค่าดูแลทีม",
            "quantity":"",
            "rate":"",
            "amount":round(manager_value,2)
        })

    # ปิด connect
    conn.close()

    # =============== 9) Deductions ===============
    deductions = []
    if late_deduction>0:
        deductions.append({
            "description":"เวลาทำงาน (>60)",
            "quantity":f"{late_excess} นาที",
            "rate":"5",
            "amount":round(late_deduction,2)
        })
    deductions += leave_deductions
    total_deductions= sum(item["amount"] for item in deductions)
    total_deductions= round(total_deductions,2)

    # =============== 10) total_income ===============
    total_income= sum(item["amount"] for item in incomes)
    total_income= round(total_income,2)

    net_salary= total_income- total_deductions
    # total_other => จากขั้นตอน 6)
    transfer_amount= net_salary- float(total_other)

    # เรียงลำดับ incomes/deductions
    # ตัวอย่าง: sort ตาม description, หรืออยาก grouping
    # จะ grouping 2 กลุ่ม (incomes, commissions/incentives) ก็ได้
    # ตัวอย่างนี้ขอ sort ตาม description ตัวอักษร
    incomes_sorted = sorted(incomes, key=lambda x: x["description"])
    deductions_sorted = sorted(deductions, key=lambda x: x["description"])

    # สร้าง debug ที่เหลือ
    debug_var["incomes_raw_count"] = len(incomes)
    debug_var["deductions_raw_count"] = len(deductions)
    debug_var["incomes_sorted"] = [x["description"] for x in incomes_sorted]
    debug_var["deductions_sorted"] = [x["description"] for x in deductions_sorted]

    payroll_start= date(year,month,1)
    today_date= date.today()
    if (year==today_date.year and month==today_date.month and not is_final):
        payroll_end= today_date
    else:
        lday= monthrange(year,month)[1]
        payroll_end= date(year,month,lday)

    months_list= get_months()
    if 1<=month<=12:
        month_name= months_list[month-1]["name"]
    else:
        month_name= str(month)

    payroll_period= f"{payroll_start.day} {month_name} {year} - {payroll_end.day} {month_name} {year}"

    return {
        "base_salary": base_salary,
        "daily_wage": daily_wage,
        "hourly_wage": hourly_wage,

        # ส่ง incomes/deductions ที่ sort แล้ว
        "incomes": incomes_sorted,
        "deductions": deductions_sorted,

        "other_deductions": other_deductions,
        "total_income": total_income,
        "total_deductions": total_deductions,
        "net_salary": round(net_salary,2),
        "total_other_deductions": round(total_other,2),
        "transfer_amount": round(transfer_amount,2),
        "payroll_period": payroll_period,

        "late_deduction": round(late_deduction,2),
        "late_excess": late_excess,

        # debug_var เก็บไว้ดู
        "debug_var": debug_var
    }


# Save Work Schedule และ Recalculate Attendance ใหม่
def save_work_schedule(user_id, work_date, planned_start_time, planned_end_time):
    conn = get_db_connection()

    # ตรวจสอบว่ามี Work Schedule สำหรับวันที่นี้หรือยัง
    existing_schedule = conn.execute("""
        SELECT * FROM work_schedules
        WHERE user_id = ? AND work_date = ?
    """, (user_id, work_date)).fetchone()

    if existing_schedule:
        # อัปเดต Work Schedule
        conn.execute("""
            UPDATE work_schedules
            SET planned_start_time = ?, planned_end_time = ?
            WHERE user_id = ? AND work_date = ?
        """, (planned_start_time, planned_end_time, user_id, work_date))
        print(f"อัปเดต Work Schedule สำหรับ user_id={user_id} และวันที่ {work_date}")
    else:
        # เพิ่ม Work Schedule ใหม่
        conn.execute("""
            INSERT INTO work_schedules (user_id, work_date, planned_start_time, planned_end_time)
            VALUES (?, ?, ?, ?)
        """, (user_id, work_date, planned_start_time, planned_end_time))
        print(f"เพิ่ม Work Schedule ใหม่สำหรับ user_id={user_id} และวันที่ {work_date}")

    conn.commit()

    # คำนวณ Attendance ใหม่
    recalculate_attendance(user_id, work_date)

    conn.close()


# Recalculate Attendance ใหม่เมื่อ HR เปลี่ยนตารางเวลาทำงาน
def recalculate_attendance(user_id, work_date):
    conn = get_db_connection()

    # ดึงตารางเวลาทำงานจาก work_schedules
    schedule = conn.execute("""
        SELECT planned_start_time, planned_end_time
        FROM work_schedules
        WHERE user_id=? AND work_date=?
    """, (user_id, work_date)).fetchone()

    if not schedule:
        print(f"ไม่พบตารางเวลาทำงานสำหรับ user_id={user_id} วันที่ {work_date}")
        conn.close()
        return

    planned_start = schedule['planned_start_time']  # คาดว่าเป็น "HH:MM"
    planned_end = schedule['planned_end_time']      # คาดว่าเป็น "HH:MM"

    # ดึงข้อมูล Attendance
    attendance = conn.execute("""
        SELECT attendance_id, checkin_time, checkout_time
        FROM attendance
        WHERE user_id=? AND work_date=?
    """, (user_id, work_date)).fetchone()

    if not attendance:
        print(f"ไม่พบข้อมูล Attendance สำหรับ user_id={user_id} วันที่ {work_date}")
        conn.close()
        return

    checkin_time = attendance['checkin_time']       # คาดว่าเป็น "YYYY-MM-DD HH:MM:SS"
    checkout_time = attendance['checkout_time']     # คาดว่าเป็น "YYYY-MM-DD HH:MM:SS"

    # คำนวณค่ามาสายและ OT
    late_minutes = calculate_late_minutes(planned_start, checkin_time)
    ot_before_midnight, ot_after_midnight = calculate_ot_split(planned_end, checkout_time)

    # อัปเดตค่าในตาราง attendance
    conn.execute("""
        UPDATE attendance
        SET late_minutes = ?, ot_before_midnight = ?, ot_after_midnight = ?
        WHERE attendance_id = ?
    """, (late_minutes, ot_before_midnight, ot_after_midnight, attendance['attendance_id']))
    conn.commit()
    conn.close()
    print(f"คำนวณ Attendance ใหม่สำหรับ user_id={user_id} วันที่ {work_date} สำเร็จ")


# เติม Default Work Schedule ให้พนักงานทุกคนล่วงหน้า
def populate_default_work_schedules(days_ahead=90):
    """
    เติม Default Work Schedule ให้พนักงานทุกคนล่วงหน้าหลายวัน
    :param days_ahead: จำนวนวันที่ต้องการสร้างล่วงหน้า (ค่าเริ่มต้น: 90 วัน)
    """
    conn = get_db_connection()

    # ดึงรายการพนักงานทั้งหมด
    users = conn.execute("""
        SELECT user_id FROM users WHERE role in ('HR', 'EMPLOYEE', 'MANAGER', 'SECRETARY')
    """).fetchall()

    today = datetime.now().date()
    default_start_time = "10:30"
    default_end_time = "19:30"

    for user in users:
        user_id = user['user_id']

        # เติม Default Schedule ในแต่ละวันล่วงหน้า
        for i in range(days_ahead):
            work_date = today + timedelta(days=i)

            # ตรวจสอบว่ามี Work Schedule สำหรับวันนั้นแล้วหรือยัง
            existing = conn.execute("""
                SELECT * FROM work_schedules
                WHERE user_id = ? AND work_date = ?
            """, (user_id, work_date)).fetchone()

            if not existing:
                # เพิ่ม Default Schedule
                conn.execute("""
                    INSERT INTO work_schedules (user_id, work_date, planned_start_time, planned_end_time)
                    VALUES (?, ?, ?, ?)
                """, (user_id, work_date, default_start_time, default_end_time))

    conn.commit()
    conn.close()
    print(f"Default Work Schedules ถูกเติมล่วงหน้า {days_ahead} วันสำเร็จ")


# ตรวจสอบและเติม Default Work Schedule หากยังไม่มี
def ensure_work_schedule(user_id, work_date):
    conn = get_db_connection()

    # ตรวจสอบว่ามี Work Schedule สำหรับวันนั้นแล้วหรือยัง
    existing = conn.execute("""
        SELECT * FROM work_schedules
        WHERE user_id = ? AND work_date = ?
    """, (user_id, work_date)).fetchone()

    if not existing:
        default_start_time = "10:30"
        default_end_time = "19:30"

        # เพิ่ม Default Schedule
        conn.execute("""
            INSERT INTO work_schedules (user_id, work_date, planned_start_time, planned_end_time)
            VALUES (?, ?, ?, ?)
        """, (user_id, work_date, default_start_time, default_end_time))

        conn.commit()

    conn.close()


# ตรวจสอบว่าช่วงวันลาทับซ้อนกับคำขอลาเดิมหรือไม่
def check_leave_overlap(user_id, start_date, end_date):
    conn = get_db_connection()
    overlap = conn.execute("""
        SELECT * FROM leave_requests
        WHERE user_id = ?
          AND status IN ('pending', 'approved')
          AND (
            (start_date BETWEEN ? AND ?) OR
            (end_date BETWEEN ? AND ?) OR
            (? BETWEEN start_date AND end_date)
          )
    """, (user_id, start_date, end_date, start_date, end_date, start_date)).fetchone()
    conn.close()
    return overlap is not None


# สิทธิ์ ลาพักร้อน ตามอายุงาน
def calculate_vacation_annual(start_date_str, target_year):
    """
    คำนวณสิทธิ์ลาพักร้อน (Vacation) แบบ Partial Mid-Year:
      - ถ้า ณ วันที่ 1 ม.ค. (target_year) อายุงาน >=1 ปี => 7 วัน
      - ถ้า <1 ปี ณ ต้นปี => เริ่มต้น 0
        แต่ถ้ากลางปีถึงวันครบรอบ 1 ปี => ได้สิทธิ์บางส่วน (7..1)
        โดยดูเดือนที่ครบปี (start_date +1ปี) => ถ้าเป็นม.ค =>7, ก.พ/มี.ค=>6, เม.ย/พ.ค=>5, ฯลฯ
    หมายเหตุ:
      * จำเป็นต้องเรียก/Update โควต้ากลางปี (เช่นผ่าน cron หรือ event) เมื่อถึงวันจริง
    :param start_date_str: "YYYY-MM-DD" วันที่เริ่มงาน
    :param target_year: ปีที่เรากำลังพิจารณา (int) เช่น 2025
    :return: จำนวนวันพักร้อนที่พนักงานควรได้ (ณ ช่วงเวลาที่ตรวจ)
    """
    from datetime import datetime
    if not start_date_str:
        return 0  # ถ้าไม่รู้วันเริ่มงาน ให้เป็น 0

    start_dt = datetime.strptime(start_date_str, '%Y-%m-%d')
    jan1 = datetime(target_year, 1, 1)

    # 1) ถ้า start_dt > jan1 => แปลว่า ยังไม่ถึง 1 ม.ค. => พนักงานยังไม่เริ่มงานก่อนปีนี้ => 0
    if start_dt > jan1:
        # ยังไม่เริ่มงานเลย => 0
        return 0

    # 2) นับอายุงานในวันที่ 1 ม.ค. (target_year)
    # ถ้า start_date <= 1 ม.ค.(target_year -1) => แปลว่าอายุงาน >=1 ปีแล้ว => ได้ 7 วันทันที
    years_of_service = target_year - start_dt.year
    # ex: start=2023-03-10, target_year=2024 => years_of_service=1 (แต่ยังไม่ถึง 1 ปีเต็มใน 1 ม.ค. 2024)

    # วันครบ 1 ปี
    one_year_anniversary = start_dt.replace(year=start_dt.year + 1)  # 1 ปีหลัง start_dt

    if one_year_anniversary < jan1:
        # แปลว่าในวันที่ 1 ม.ค. ของ target_year อายุงาน >=1 ปีแล้ว
        # => 7 วัน
        return 7
    elif one_year_anniversary.year > target_year:
        # แปลว่า แม้ภายในปีนี้ก็ยังไม่ครบ 1 ปี => 0
        return 0
    else:
        # กรณี one_year_anniversary อยู่ในปี target_year
        # => partial
        # logic: 
        #   ม.ค =>7 
        #   ก.พ/มี.ค =>6 
        #   เม.ย/พ.ค =>5 
        #   มิ.ย/ก.ค =>4 
        #   ส.ค/ก.ย =>3 
        #   ต.ค/พ.ย =>2 
        #   ธ.ค =>1
        anniv_month = one_year_anniversary.month
        if anniv_month == 1:
            return 7
        elif anniv_month in [2, 3]:
            return 6
        elif anniv_month in [4, 5]:
            return 5
        elif anniv_month in [6, 7]:
            return 4
        elif anniv_month in [8, 9]:
            return 3
        elif anniv_month in [10, 11]:
            return 2
        else:  # dec
            return 1


# สิทธิ์ ลาพักร้อน partial midyear
def calculate_vacation_annual_partial_midyear(start_date_str, target_year):
    """
    ฟังก์ชันคำนวณลาพักร้อน (Partial Mid-Year) 
    - ถ้าอายุงาน >=1 ปีตั้งแต่ก่อน 1 ม.ค. => 7
    - ถ้าอายุงานยังไม่ถึง 1 ปีใน 1 ม.ค. => 0 แต่ถ้า 'ครบ1ปี' ในกลางปี => ได้ 7..1
    (เหมือนที่เคยเขียนไว้)

    * ส่วนนี้ copy หรือปรับปรุงตามฟังก์ชันที่คุณออกแบบ
    """
    if not start_date_str:
        return 0
    start_dt = datetime.strptime(start_date_str, '%Y-%m-%d')
    jan1 = datetime(target_year, 1, 1)
    if start_dt > jan1:
        return 0
    one_year_anniv = start_dt.replace(year=start_dt.year+1)
    if one_year_anniv < jan1:
        return 7
    elif one_year_anniv.year > target_year:
        return 0
    else:
        m = one_year_anniv.month
        if m==1: return 7
        elif m in [2,3]: return 6
        elif m in [4,5]: return 5
        elif m in [6,7]: return 4
        elif m in [8,9]: return 3
        elif m in [10,11]: return 2
        else: return 1


# สิทธิ์ ลาพักร้อน ที่ได้ระหว่างปี CRON
def cron_check_vacation_partial(conn, target_year=None):
    """
    ตรวจพนักงานทุกคน:
     - ถ้าวันนี้ >= (start_date + 1ปี) และเคยตั้ง quota=0 สำหรับปีนี้ => อัปเดต partial (7..1)
     - ใช้เมื่อระบบ run กลางปี (เช่น daily/weekly) -> กันลืม

    :param conn: sqlite3 connection (already opened)
    :param target_year: ปีที่ต้องการเช็ค (ถ้าไม่กำหนด จะใช้ปีปัจจุบัน)
    :return: (count_update, list_of_user) => จำนวนคนที่อัปเดต
    """
    if target_year is None:
        target_year = date.today().year

    # 1) load user
    users = conn.execute("""
        SELECT user_id, start_date
        FROM users
        WHERE role in ('HR', 'EMPLOYEE', 'MANAGER', 'SECRETARY')
          AND start_date IS NOT NULL
    """).fetchall()

    count_updated = 0
    updated_users = []

    for u in users:
        uid = u['user_id']
        sdate = u['start_date']
        # วันครบรอบ 1 ปี
        start_dt = datetime.strptime(sdate, '%Y-%m-%d')
        one_year_anniv = start_dt.replace(year=start_dt.year+1)

        today_dt = datetime.today()
        # ถ้าวันนี้ < วันครบรอบ => ยังไม่ถึงเวลากลางปี => continue
        if today_dt < one_year_anniv:
            continue

        # ถ้าเคยผ่าน 1ปี => partial = calculate
        partial = calculate_vacation_annual_partial_midyear(sdate, target_year)
        if partial <= 0:
            continue

        # 2) check leave_quota ว่าปีนี้ 'ลาพักร้อน' เป็นเท่าไร
        row = conn.execute("""
            SELECT quota_id, total_days
            FROM leave_quota
            WHERE user_id=? AND leave_type='ลาพักร้อน' AND year=?
        """, (uid, target_year)).fetchone()

        if row:
            qid = row['quota_id']
            old_total = row['total_days']
            # ถ้า old_total=0 => อัปเดต partial
            if old_total == 0:
                conn.execute("""
                    UPDATE leave_quota
                    SET total_days=?
                    WHERE quota_id=?
                """, (partial, qid))
                count_updated += 1
                updated_users.append(uid)
        else:
            # ไม่มี record => insert
            conn.execute("""
                INSERT INTO leave_quota (user_id, leave_type, carry_forward, total_days, year)
                VALUES (?, 'ลาพักร้อน', 0, ?, ?)
            """, (uid, partial, target_year))
            count_updated += 1
            updated_users.append(uid)

    conn.commit()
    return (count_updated, updated_users)


# สิทธิ์ ลากิจ เมื่อผ่านโปร
def calculate_personal_annual(start_date_str, probation, target_year):
    """
    ถ้าผ่านโปร probation=0 => 3 วัน
    ถ้ายัง probation=1 => 0
    *เมื่อขึ้นปีใหม่ => carry=0 => total=3 (ถ้าผ่านโปร), else=0
    """
    if probation == 0:
        return 3
    else:
        return 0


# สิทธิ์ ลาเทศกาล (นักขัติ) มี 3 option
def calculate_festival_days(option):
    """
    option1 => 13
    option2 => 4
    option3 => 1
    """
    if option==2:
        return 4
    elif option==3:
        return 1
    return 13  # default = option1


# on-the-fly leftover ยกยอดสิทธิ์วันลาของปีก่อนๆ
def load_leftover_of_previous_year(conn, prev_year):
    """
    คำนวณ leftover ของปี prev_year แบบ on-the-fly
    leftover = (carry_forward + total_days) - used_days
    โดย used_days อาจเป็นตัวเลขที่เราบันทึกใน leave_quota
    หรือจะไป query จาก leave_requests (status='approved') ก็ได้
    """
    leftover_data = {}
    rows = conn.execute("""
        SELECT user_id, leave_type, carry_forward, total_days, used_days
        FROM leave_quota
        WHERE year = ?
    """, (prev_year,)).fetchall()

    for r in rows:
        uid = r['user_id']
        lt = r['leave_type']
        c_fwd = r['carry_forward']
        t_days = r['total_days']
        u_days = r['used_days']  # หรือจะ on-the-fly จาก leave_requests

        leftover = (c_fwd + t_days) - u_days
        leftover_data[(uid, lt)] = leftover if leftover>0 else 0

    return leftover_data


# on-the-fly ลากิจ ลาป่วย ลางานศพ(ไม่หักเงิน) ลาเทศกาล
def get_other_leaves_leftover_on_the_fly(user_id, year):
    """
    คำนวณ leftover (สิทธิ์ - used) ของ:
      - ลากิจ (Personal)
      - ลาป่วย (Sick)
      - ลางานศพ(ไม่หักเงิน) (Funeral)
      - ลาเทศกาล (Festival)
    ทั้งหมดแบบ "on-the-fly":
      1) Query user -> ดู probation, festival_option
      2) กำหนดโควต้าปีนี้ (total_days) ตามเงื่อนไข
      3) Query ใบลา (leave_requests) => sum used (status='approved') year=... 
      4) leftover = total_days - used
    * ไม่ต้องเก็บลง leave_quota

    Return: dict เช่น:
    {
      'ลากิจ': leftover_personal,
      'ลาป่วย': leftover_sick,
      'ลางานศพ (ไม่หักเงิน)': leftover_funeral,
      'ลาเทศกาล': leftover_festival
    }
    """

    from datetime import datetime, date
    conn = get_db_connection()

    # 1) Load user data: probation, festival_option
    user_row = conn.execute("""
        SELECT probation, festival_option
        FROM users
        WHERE user_id=?
    """, (user_id,)).fetchone()

    if not user_row:
        conn.close()
        # กรณีไม่เจอ user -> return 0
        return {
          'ลากิจ': 0,
          'ลาป่วย': 0,
          'ลางานศพ (ไม่หักเงิน)': 0,
          'ลาเทศกาล': 0
        }

    prob = user_row['probation']  # 0=ผ่านโปร,1=ยังไม่ผ่าน
    fest_opt = user_row['festival_option'] or 1

    # 2) กำหนดโควต้าตาม logic
    # ลากิจ: 3 วันถ้าผ่านโปร probation=0, else=0
    personal_total = 3 if prob==0 else 0

    # ลาป่วย: fix 30
    sick_total = 30

    # ลางานศพ(ไม่หักเงิน): fix 3
    funeral_total = 3

    # ลาเทศกาล: fest_opt=1 =>13,2=>4,3=>1
    if fest_opt == 2:
        festival_total = 4
    elif fest_opt == 3:
        festival_total = 1
    else:
        festival_total = 13

    # 3) Query used day from leave_requests (status='approved') for each type in this year
    # ใช้ strftime('%Y', start_date)= year
    year_str = str(year)

    # A helper dict to store leftover result
    leftover_dict = {
      'ลากิจ': 0,
      'ลาป่วย': 0,
      'ลางานศพ (ไม่หักเงิน)': 0,
      'ลาเทศกาล': 0
    }
    # A helper dict for total mapping
    total_map = {
      'ลากิจ': personal_total,
      'ลาป่วย': sick_total,
      'ลางานศพ (ไม่หักเงิน)': funeral_total,
      'ลาเทศกาล': festival_total
    }

    # build a list of leaves
    LEAVE_TYPES_OTHER = ['ลากิจ','ลาป่วย','ลางานศพ (ไม่หักเงิน)','ลาเทศกาล']

    for lt in LEAVE_TYPES_OTHER:
        row = conn.execute("""
            SELECT COALESCE(SUM(days_requested),0) AS used_sum
            FROM leave_requests
            WHERE user_id=?
              AND leave_type=?
              AND status='approved'
              AND strftime('%Y', start_date)=?
        """, (user_id, lt, year_str)).fetchone()
        used_sum = row['used_sum'] if row else 0
        leftover = total_map[lt] - used_sum
        leftover_dict[lt] = leftover if leftover>0 else 0

    conn.close()
    return leftover_dict


# on-the-fly คำนวณสิทธิ์ลา ยอดยกมาจากปีที่แล้ว
def get_on_the_fly_leftover(user_id, leave_type, target_year):
    """
    คำนวณ leftover = quota - used_past
    - ถ้า 'ลาพักร้อน' => carry_forward (DB) + partial mid-year - used
    - ลากิจ => 3 ถ้าผ่านโปร
    - ลาป่วย => 30
    - ลางานศพ (ไม่หักเงิน) => 3
    - ลาเทศกาล => 13/4/1
    - extra => 0
    """
    today = date.today()
    conn = get_db_connection()

    # 1) load user => start_date, probation, festival_option
    user_row = conn.execute("""
        SELECT start_date, probation, festival_option
        FROM users
        WHERE user_id=?
    """, (user_id,)).fetchone()

    if not user_row:
        conn.close()
        return 0
    start_date_str = user_row['start_date'] or ''
    prob = user_row['probation'] or 1
    fest_opt = user_row['festival_option'] or 1

    # 2) ถ้าเป็นลาพักร้อน => load carry_forward
    carry_fwd = 0
    if leave_type=='ลาพักร้อน':
        crow = conn.execute("""
            SELECT carry_forward
            FROM leave_quota
            WHERE user_id=? AND leave_type='ลาพักร้อน' AND year=?
        """, (user_id, target_year)).fetchone()
        carry_fwd = crow['carry_forward'] if crow else 0

    # 3) used_past => sum of days_requested (status='approved') in year, start_date <= today
    row_used = conn.execute(f"""
        SELECT COALESCE(SUM(days_requested),0) as used_sum
        FROM leave_requests
        WHERE user_id=?
          AND leave_type=?
          AND status='approved'
          AND strftime('%Y', start_date)=?
          AND start_date <= ?
    """, (user_id, leave_type, str(target_year), today.strftime('%Y-%m-%d'))).fetchone()

    used_past = row_used['used_sum'] if row_used else 0

    conn.close()

    # 4) คำนวณ quota on-the-fly
    partial = 0
    if leave_type=='ลาพักร้อน':
        partial = calc_vacation_partial_midyear(start_date_str, target_year)
        quota = carry_fwd + partial
    elif leave_type=='ลากิจ':
        quota = 3 if prob==0 else 0
    elif leave_type=='ลาป่วย':
        quota = 30
    elif leave_type=='ลางานศพ (ไม่หักเงิน)':
        quota = 3
    elif leave_type=='ลาเทศกาล':
        if fest_opt==2: quota=4
        elif fest_opt==3: quota=1
        else: quota=13
    else:
        quota=0  # extra =>0

    leftover_present = quota - used_past
    if leftover_present<0: leftover_present=0

    return leftover_present


# on-the-fly คำนวณสิทธิ์ลา ใบลายัง pending
def get_on_the_fly_leftover_exclude(user_id, leave_type, year, exclude_leave_id=None):
    """
    เหมือน get_on_the_fly_leftover แต่ exclude ใบลาที่กำลัง approve (ถ้ามันอยู่ใน DB)
    leftover = quota - sum(usedPast)
    usedPast => ใบลา status='approved' AND leave_type=... AND year=...
        แต่อย่ารวม leave_id=exclude_leave_id
    """
    conn = get_db_connection()
    # 1) load user => start_date, probation, festival_option
    user_row = conn.execute("""
        SELECT start_date, probation, festival_option
        FROM users
        WHERE user_id=?
    """,(user_id,)).fetchone()
    if not user_row:
        conn.close()
        return 0

    start_date_str = user_row['start_date'] or ''
    prob = user_row['probation'] or 1
    fest_opt = user_row['festival_option'] or 1

    # 2) ถ้าเป็นลาพักร้อน => carry_fwd + partial
    carry_fwd = 0
    if leave_type=='ลาพักร้อน':
        crow = conn.execute("""
            SELECT carry_forward
            FROM leave_quota
            WHERE user_id=? AND leave_type='ลาพักร้อน' AND year=?
        """, (user_id, year)).fetchone()
        if crow:
            carry_fwd = crow['carry_forward']

    # 3) คำนวณ usedPast
    #    exclude leave_id=?
    if exclude_leave_id:
        used_sql = f"""
            SELECT COALESCE(SUM(days_requested),0) as used_sum
            FROM leave_requests
            WHERE user_id=?
              AND leave_type=?
              AND status='approved'
              AND strftime('%Y', start_date)=?
              AND leave_id != ?
        """
        used_row = conn.execute(used_sql, (user_id, leave_type, str(year), exclude_leave_id)).fetchone()
    else:
        used_sql = f"""
            SELECT COALESCE(SUM(days_requested),0) as used_sum
            FROM leave_requests
            WHERE user_id=?
              AND leave_type=?
              AND status='approved'
              AND strftime('%Y', start_date)=?
        """
        used_row = conn.execute(used_sql, (user_id, leave_type, str(year))).fetchone()

    used_past = used_row['used_sum'] if used_row else 0
    conn.close()

    # 4) คำนวณ quota
    def calc_vacation_partial_midyear(start_date_str, year):
        # partial
        import datetime
        if not start_date_str:
            return 0
        sdt = datetime.datetime.strptime(start_date_str,'%Y-%m-%d')
        jan1 = datetime.datetime(year,1,1)
        if sdt>jan1:
            return 0
        one_year = sdt.replace(year=sdt.year+1)
        if one_year<jan1:
            return 7
        elif one_year.year>year:
            return 0
        else:
            m=one_year.month
            if m==1:return 7
            elif m in [2,3]:return 6
            elif m in [4,5]:return 5
            elif m in [6,7]:return 4
            elif m in [8,9]:return 3
            elif m in [10,11]:return 2
            else:return 1

    if leave_type=='ลาพักร้อน':
        partial = calc_vacation_partial_midyear(start_date_str, year)
        quota = carry_fwd + partial
    elif leave_type=='ลากิจ':
        quota = 3 if prob==0 else 0
    elif leave_type=='ลาป่วย':
        quota = 30
    elif leave_type=='ลางานศพ (ไม่หักเงิน)':
        quota = 3
    elif leave_type=='ลาเทศกาล':
        # festival_opt => 1=>13,2=>4,3=>1 (สมมติ leftover=13/4/1)
        if fest_opt==2:
            quota=4
        elif fest_opt==3:
            quota=1
        else:
            quota=13
    else:
        quota=0

    leftover = quota - used_past
    if leftover<0:
        leftover=0
    return leftover


# on-the-fly คำนวณสิทธิ์ลา คงเหลือทั้งหมด
def get_on_the_fly_leftover_detail(user_id, leave_type, target_year):
    """
    คำนวณ leftover ของ leave_type ในปี target_year แบบ on-the-fly
    คืนค่าเป็น dict { 
      'quota': ...,
      'used_past': ...,
      'used_future': ...,
      'leftover_present': ...,
      'leftover_total': ...
    }
    โดย leftover_total = leftover_present - used_future
    leftover_present = quota - used_past
    used_past/future => ใบลา approved ในปีนั้น + split ตาม start_date <=/ > Today
    """
    conn = get_db_connection()
    # โหลด user => start_date, probation, festival_option
    row = conn.execute("""
        SELECT start_date, probation, festival_option
        FROM users
        WHERE user_id=?
    """,(user_id,)).fetchone()
    if not row:
        conn.close()
        return {
            "quota":0,"used_past":0,"used_future":0,
            "leftover_present":0,"leftover_total":0
        }

    start_date_str = row['start_date'] or ''
    prob = row['probation'] or 1
    fest_opt = row['festival_option'] or 1

    # ถ้าเป็นลาพักร้อน => carry_fwd + partial
    carry_fwd = 0
    if leave_type=='ลาพักร้อน':
        crow = conn.execute("""
            SELECT carry_forward
            FROM leave_quota
            WHERE user_id=? AND leave_type='ลาพักร้อน' AND year=?
        """,(user_id, target_year)).fetchone()
        if crow:
            carry_fwd = crow['carry_forward']

    # ดึงใบลา approved ในปี target_year
    # split used_past (start_date <= Today) / used_future (start_date > Today)
    from datetime import date, datetime
    today_dt = date.today()

    sql = """
    SELECT days_requested, start_date
    FROM leave_requests
    WHERE user_id=? 
      AND leave_type=?
      AND status='approved'
      AND strftime('%Y', start_date)=?
    """
    rows = conn.execute(sql,(user_id, leave_type, str(target_year))).fetchall()
    conn.close()

    used_past = 0
    used_future = 0
    for r in rows:
        sdt = datetime.strptime(r['start_date'],'%Y-%m-%d').date()
        if sdt<=today_dt:
            used_past += r['days_requested']
        else:
            used_future += r['days_requested']

    # คำนวณ quota
    def calc_vacation_partial(start_date_str, yr):
        # ตัวอย่าง partial mid-year logic
        if not start_date_str:
            return 0
        import datetime
        sdt = datetime.datetime.strptime(start_date_str,'%Y-%m-%d')
        jan1 = datetime.datetime(yr,1,1)
        if sdt>jan1:
            return 0
        one_year = sdt.replace(year=sdt.year+1)
        if one_year<jan1:
            return 7
        elif one_year.year>yr:
            return 0
        else:
            m=one_year.month
            if m==1:return 7
            elif m in [2,3]:return 6
            elif m in [4,5]:return 5
            elif m in [6,7]:return 4
            elif m in [8,9]:return 3
            elif m in [10,11]:return 2
            else:return 1

    if leave_type=='ลาพักร้อน':
        partial = calc_vacation_partial(start_date_str, target_year)
        quota = carry_fwd + partial
    elif leave_type=='ลากิจ':
        quota = 3 if prob==0 else 0
    elif leave_type=='ลาป่วย':
        quota = 30
    elif leave_type=='ลางานศพ (ไม่หักเงิน)':
        quota=3
    elif leave_type=='ลาเทศกาล':
        # festival_opt=1 =>13,2=>4,3=>1
        if fest_opt==2:
            quota=4
        elif fest_opt==3:
            quota=1
        else:
            quota=13
    else:
        quota=0

    leftover_present = quota - used_past
    if leftover_present<0:
        leftover_present=0
    leftover_total = leftover_present - used_future
    if leftover_total<0:
        leftover_total=0

    return {
        "quota": quota,
        "used_past": used_past,
        "used_future": used_future,
        "leftover_present": leftover_present,
        "leftover_total": leftover_total
    }


# on-the-fly คำนวณสิทธิ์ลา partial พนักงานอายุงานพึ่งครบ 1 ปี
def calc_vacation_partial_midyear(start_date_str, target_year):
    # เหมือนที่ใช้ใน on-the-fly
    from datetime import datetime
    if not start_date_str:
        return 0
    sdt = datetime.strptime(start_date_str,'%Y-%m-%d')
    jan1 = datetime(target_year,1,1)
    if sdt>jan1:
        return 0
    one_year = sdt.replace(year=sdt.year+1)
    if one_year<jan1:
        return 7
    elif one_year.year>target_year:
        return 0
    else:
        m=one_year.month
        if m==1:return 7
        elif m in [2,3]:return 6
        elif m in [4,5]:return 5
        elif m in [6,7]:return 4
        elif m in [8,9]:return 3
        elif m in [10,11]:return 2
        else:return 1


# carry_forward ยอดลาพักร้อนยกมาจากปีก่อน
def get_vacation_quota_with_carry(user_id, start_date_str, target_year):
    """
    ผสม carry_forward (DB) + partial mid-year
    leftover = carry_forward + partialVacation - used
    """
    # 1) partialVacation
    partial = calc_vacation_partial_midyear(start_date_str, target_year)

    # 2) load carry_forward from leave_quota
    conn = get_db_connection()
    row = conn.execute("""
        SELECT carry_forward
        FROM leave_quota
        WHERE user_id=? AND leave_type='ลาพักร้อน' AND year=?
    """, (user_id, target_year)).fetchone()
    conn.close()
    cf = row['carry_forward'] if row else 0

    # return sum
    return cf + partial


# สำหรับ HR กรอกยอดวันลายกมา
def upsert_quota(conn, user_id, leave_type, carry_forward, total_days, year):
    """
    ถ้ามี record แล้ว => update 
    ถ้าไม่มี => insert
    """
    row = conn.execute("""
        SELECT quota_id FROM leave_quota
        WHERE user_id=? AND leave_type=? AND year=?
    """, (user_id, leave_type, year)).fetchone()
    if row:
        conn.execute("""
            UPDATE leave_quota
            SET carry_forward=?, total_days=?
            WHERE quota_id=?
        """, (carry_forward, total_days, row['quota_id']))
    else:
        conn.execute("""
            INSERT INTO leave_quota (user_id, leave_type, carry_forward, total_days, year)
            VALUES (?,?,?,?,?)
        """, (user_id, leave_type, carry_forward, total_days, year))


# leave type
def map_leave_type_to_quota(leave_type):
    """
    สมมติ: แปลงชื่อการลาในระบบ -> ชื่อที่ตรงกับ leave_quota.leave_type
    ปรับให้ตรงกับ DB จริง เช่น:
      - ลาพักร้อน => Vacation
      - ลากิจ => Personal
      - ลาป่วย => Sick
    """
    if leave_type == 'ลาพักร้อน':
        return 'Vacation'
    elif leave_type == 'ลากิจ':
        return 'Personal'
    elif leave_type == 'ลาป่วย':
        return 'Sick'
    return leave_type  # default


# Notification
def add_notification_for_roles(roles, message):
    """
    roles = list/tuple ของบทบาท (เช่น ['ADMIN','HR','MANAGER'] หรือ single ['HR'])
    หรือถ้าเผลอส่งเป็น string => จะถูกใส่ list ให้
    """
    # 1) ตรวจสอบ/แปลง roles เป็น list
    if isinstance(roles, (str, int)):
        roles = [roles]
    elif not isinstance(roles, (list, tuple)):
        # ถ้าเป็นแบบอื่น เช่น None, dict → error
        raise TypeError("roles must be list or tuple or string or int")

    conn = get_db_connection()
    
    # 2) สร้าง placeholders "?, ?, ?" ตามจำนวน roles
    placeholders = ','.join('?' * len(roles))
    query = f"SELECT user_id FROM users WHERE role IN ({placeholders})"

    rows = conn.execute(query, roles).fetchall()

    for row in rows:
        add_notification(row['user_id'], message)

    conn.close()


def add_notification(user_id, message):
    import datetime
    now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    conn = get_db_connection()
    conn.execute("""
        INSERT INTO notifications (user_id, message, created_at, is_read)
        VALUES (?, ?, ?, 0)
    """, (user_id, message, now_str))
    conn.commit()
    conn.close()


def add_notification_with_connection(conn, user_id, message):
    """
    บันทึก Notification โดยใช้การเชื่อมต่อฐานข้อมูลที่มีอยู่
    """
    import datetime
    now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    conn.execute("""
        INSERT INTO notifications (user_id, message, created_at, is_read)
        VALUES (?, ?, ?, 0)
    """, (user_id, message, now_str))

# Get User Detail
def get_user_detail(uid):
    conn = get_db_connection()
    row = conn.execute("""
        SELECT user_id, username, role, gender, nickname,
               first_name, last_name, phone, address, dob, start_date,
               education_level, education_institution, ethnicity, nationality,
               emergency_name, emergency_phone, emergency_relation,
               special_ability, prev_company, prev_position
        FROM users
        WHERE user_id=?
    """, (uid,)).fetchone()
    conn.close()
    return row


# รายชื่อเดือนภาษาไทย
@app.context_processor
def utility_processor():
    months = [
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

    current_year = datetime.now().year
    current_month = datetime.now().month

    return dict(
        months=get_months(),
        current_year=current_year,
        current_month=current_month,
        format_hh_mm=format_hh_mm
    )


# ดึงปีเริ่มต้นงานของพนักงาน
def get_start_year(user_id):
    conn = get_db_connection()
    result = conn.execute("""
        SELECT MIN(strftime('%Y', start_date)) AS start_year
        FROM users
        WHERE user_id = ?
    """, (user_id,)).fetchone()
    conn.close()
    return int(result['start_year']) if result and result['start_year'] else datetime.now().year


# ดึงข้อมูล Payroll Summary ย้อนหลังสำหรับแสดงผลในตาราง
def get_previous_payrolls(user_id, months_to_fetch=3):
    conn = get_db_connection()
    previous_payrolls = []

    for i in range(months_to_fetch):
        target_date = datetime.now() - timedelta(days=i * 30)  # คำนวณเดือนย้อนหลัง
        year, month = target_date.year, target_date.month

        payroll = calculate_payroll(user_id, month, year)
        previous_payrolls.append({
            "month": month,
            "year": year,
            "total_income": payroll.get("total_income", 0),
            "total_deductions": payroll.get("total_deductions", 0),
            "net_salary": payroll.get("net_salary", 0),
        })

    conn.close()
    return previous_payrolls


# ดึงข้อมูลเดือน
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



### -------------------------------
### Log in & Log out
### -------------------------------
@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db_connection()
        user = conn.execute("SELECT * FROM users WHERE username=?",(username,)).fetchone()
        conn.close()

        if user:
            if check_password_hash(user['password_hash'], password):
                session['user_id'] = user['user_id']
                session['role'] = user['role']
                session['username'] = user['username']
                session['sub_category_id'] = user['sub_category_id']

                if user['role']=='ADMIN':
                    return redirect(url_for('admin_dashboard'))
                elif user['role']=='HR':
                    return redirect(url_for('hr_dashboard'))
                elif user['role']=='MANAGER':
                    return redirect(url_for('manager_dashboard'))
                elif user['role']=='EMPLOYEE':
                    return redirect(url_for('employee_dashboard'))
                elif user['role']=='OPD':
                    return redirect(url_for('opd_dashboard'))
                elif user['role']=='SECRETARY':
                    return redirect(url_for('secretary_dashboard'))
                elif user['role']=='DOCTOR':
                    return redirect(url_for('doctor_dashboard'))
                else:
                    return redirect(url_for('patient_dashboard'))
            else:
                return "ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง"
        else:
            return "ไม่พบบัญชีผู้ใช้"
    else:
        # เมื่อเป็น 'GET' -> เรียก templates/login.html
        return render_template("login.html")

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


### -------------------------------
### Dashboard
### -------------------------------
@app.route('/admin')
@role_required('ADMIN')
def admin_dashboard():
    user_id = session['user_id']

    conn = get_db_connection()
    unread_notifications = conn.execute("""
        SELECT COUNT(*) AS unread_count
        FROM notifications
        WHERE user_id = ? AND is_read = 0
    """, (user_id,)).fetchone()['unread_count']
    conn.close()

    return render_template("dashboard/admin.html", unread_notifications=unread_notifications)

@app.route('/hr')
@role_required('HR')
def hr_dashboard():
    user_id = session['user_id']
    conn = get_db_connection()

    # 1) นับจำนวนแจ้งเตือนที่ยังไม่อ่าน
    unread_notifications = conn.execute("""
        SELECT COUNT(*) AS unread_count
        FROM notifications
        WHERE user_id = ? AND is_read = 0
    """, (user_id,)).fetchone()['unread_count']

    # 2) ดึงเวลาล่าสุดที่อัปเดตลาพักร้อน (Partial Mid-Year)
    row = conn.execute("""
        SELECT config_value
        FROM system_config
        WHERE config_key='cron_check_vacation_partial_update'
    """).fetchone()

    if row:
        last_update = row['config_value']  # เช่น "2025-06-15 14:30:00"
    else:
        last_update = "ยังไม่เคยอัปเดต"

    conn.close()

    return render_template(
        "dashboard/hr.html",
        unread_notifications=unread_notifications,
        last_update=last_update
    )

@app.route('/manager')
@role_required('MANAGER')
def manager_dashboard():
    user_id = session['user_id']

    conn = get_db_connection()
    unread_notifications = conn.execute("""
        SELECT COUNT(*) AS unread_count
        FROM notifications
        WHERE user_id = ? AND is_read = 0
    """, (user_id,)).fetchone()['unread_count']
    conn.close()

    return render_template("dashboard/manager.html", unread_notifications=unread_notifications)

@app.route('/employee')
@role_required('EMPLOYEE')
def employee_dashboard():
    user_id = session['user_id']
    conn = get_db_connection()
    unread_notifications = conn.execute("""
        SELECT COUNT(*) AS unread_count
        FROM notifications
        WHERE user_id = ? AND is_read = 0
    """, (user_id,)).fetchone()['unread_count']
    conn.close()

    return render_template("dashboard/employee.html", unread_notifications=unread_notifications)

@app.route('/opd')
@role_required('OPD')
def opd_dashboard():
    user_id = session['user_id']
    conn = get_db_connection()
    unread_notifications = conn.execute("""
        SELECT COUNT(*) AS unread_count
        FROM notifications
        WHERE user_id = ? AND is_read = 0
    """, (user_id,)).fetchone()['unread_count']
    conn.close()

    return render_template("dashboard/opd.html", unread_notifications=unread_notifications)

@app.route('/secretary')
@role_required('SECRETARY')
def secretary_dashboard():
    user_id = session['user_id']
    conn = get_db_connection()
    unread_notifications = conn.execute("""
        SELECT COUNT(*) AS unread_count
        FROM notifications
        WHERE user_id = ? AND is_read = 0
    """, (user_id,)).fetchone()['unread_count']
    conn.close()

    return render_template("dashboard/secretary.html", unread_notifications=unread_notifications)

@app.route('/doctor')
@role_required('DOCTOR')
def doctor_dashboard():
    user_id = session['user_id']
    conn = get_db_connection()
    unread_notifications = conn.execute("""
        SELECT COUNT(*) AS unread_count
        FROM notifications
        WHERE user_id = ? AND is_read = 0
    """, (user_id,)).fetchone()['unread_count']
    conn.close()

    return render_template("dashboard/doctor.html", unread_notifications=unread_notifications)

@app.route('/patient')
@role_required('PATIENT')
def patient_dashboard():
    user_id = session['user_id']
    conn = get_db_connection()
    unread_notifications = conn.execute("""
        SELECT COUNT(*) AS unread_count
        FROM notifications
        WHERE user_id = ? AND is_read = 0
    """, (user_id,)).fetchone()['unread_count']
    conn.close()

    return render_template("dashboard/patient.html", unread_notifications=unread_notifications)

@app.route('/dashboard')
def dashboard():
    # ถ้า user ยังไม่ล็อกอิน ก็ redirect ไป login
    if 'role' not in session:
        return redirect(url_for('login'))
    
    r = session['role']
    if r == 'ADMIN':
        return redirect(url_for('admin_dashboard'))
    elif r == 'HR':
        return redirect(url_for('hr_dashboard'))
    elif r == 'MANAGER':
        return redirect(url_for('manager_dashboard'))
    elif r == 'EMPLOYEE':
        return redirect(url_for('employee_dashboard'))
    elif r == 'OPD':
        return redirect(url_for('opd_dashboard'))
    elif r == 'SECRETARY':
        return redirect(url_for('secretary_dashboard'))
    elif r == 'DOCTOR':
        return redirect(url_for('doctor_dashboard'))
    elif r == 'PATIENT':
        return redirect(url_for('patient_dashboard'))
    else:
        return "บทบาทของคุณไม่มีสิทธิ์เข้าถึงแดชบอร์ด กรุณาติดต่อผู้ดูแลระบบ"



### -------------------------------
### User Management
### -------------------------------
# Registration
@app.route('/user/register_employee', methods=['GET', 'POST'])
def register_employee():
    if request.method == 'POST':
        # 1) รับข้อมูลจากฟอร์ม
        fn = request.form['first_name']
        ln = request.form['last_name']
        un = request.form['username']
        pw = request.form['password']

        join_code = request.form['join_code']

        nickname = request.form.get('nickname', '')
        education_level = request.form.get('education_level', '')
        university_name = request.form.get('university_name', '')

        # NEW: รับค่าจากช่อง pr_code (ถ้ามี)
        pr_code = request.form.get('pr_code', '').strip()

        # เชื้อชาติ
        eth_val = request.form.get('ethnicity','')
        eth_other = request.form.get('other_ethnicity','')
        if eth_val == 'อื่นๆ':
            ethnicity = eth_other.strip()
        else:
            ethnicity = eth_val

        # สัญชาติ
        nat_val = request.form.get('nationality','')
        nat_other = request.form.get('other_nationality','')
        if nat_val == 'อื่นๆ':
            nationality = nat_other.strip()
        else:
            nationality = nat_val

        phone = request.form.get('phone', '')
        address = request.form.get('address', '')
        dob = request.form.get('dob', '')
        st = request.form.get('start_date', '')

        # คนติดต่อฉุกเฉิน
        emergency_name = request.form.get('emergency_name', '')
        emergency_phone = request.form.get('emergency_phone', '')
        emergency_relation = request.form.get('emergency_relation', '')

        # ความสามารถพิเศษ
        special_ability = request.form.get('special_ability', '')

        # สถานที่ทำงาน และตำแหน่งล่าสุด
        last_workplace = request.form.get('last_workplace', '')
        last_position = request.form.get('last_position', '')

        # 2) ตรวจสอบโค้ดเข้าร่วม (join_code)
        conn = get_db_connection()
        row = conn.execute("SELECT config_value FROM system_config WHERE config_key='employee_join_code'").fetchone()
        real_code = row['config_value'] if row else ''
        if join_code != real_code:
            conn.close()
            return "โค้ด join ไม่ถูกต้อง"

        # 3) แฮชรหัสผ่าน
        pw_hash = generate_password_hash(pw)

        # 4) หา role_id ของ EMPLOYEE จากตาราง roles
        employee_role_row = conn.execute("SELECT role_id FROM roles WHERE role_name = 'EMPLOYEE'").fetchone()
        if employee_role_row:
            employee_role_id = employee_role_row['role_id']
        else:
            # ถ้าไม่เจอ row นี้ อาจกำหนด fallback เช่น 2 หรือแจ้ง error
            # สำหรับตัวอย่าง สมมติให้ fallback = 2
            employee_role_id = 2

        # 5) Insert ลงตาราง users
        try:
            conn.execute("""
                INSERT INTO users (
                    username, password_hash,
                    role, role_id,
                    first_name, last_name,
                    pr_code,
                    phone, address, dob, start_date,
                    nickname, education_level, education_institution,
                    ethnicity, nationality,
                    emergency_name, emergency_phone, emergency_relation,
                    special_ability, prev_company, prev_position
                ) 
                VALUES (?, ?, 
                        'EMPLOYEE', ?, 
                        ?, ?, 
                        ?, 
                        ?, ?, ?, ?, 
                        ?, ?, ?,
                        ?, ?,
                        ?, ?, ?,
                        ?, ?, ?)
            """, (
                un, pw_hash,
                employee_role_id,
                fn, ln,
                pr_code,    # pr_code
                phone, address, dob, st,
                nickname, education_level, university_name,
                ethnicity, nationality,
                emergency_name, emergency_phone, emergency_relation,
                special_ability, last_workplace, last_position
            ))
            conn.commit()
        except sqlite3.IntegrityError as e:
            conn.close()
            return f"ชื่อผู้ใช้นี้มีอยู่แล้ว หรือเกิดข้อผิดพลาด: {e}"

        conn.close()
        return "ลงทะเบียนสำเร็จ <p><a href='/login'>กลับหน้า Login</a></p>"

    else:
        return render_template("user/register_employee.html")

# Edit Profile
@app.route('/user/edit_profile', methods=['GET','POST'])
@role_required('EMPLOYEE','HR','MANAGER', 'OPD', 'SECRETARY')
def edit_profile():
    user_id = session['user_id']
    role = session['role']

    conn = get_db_connection()

    if request.method == 'POST':
        # เดิม: (ยกเว้น dob) => เปลี่ยนให้อนุญาตแก้ได้
        dob = request.form.get('dob', '')  # <-- เพิ่มส่วนนี้
        gender = request.form.get('gender', '')
        nickname = request.form.get('nickname', '')
        first_name = request.form.get('first_name', '')
        last_name = request.form.get('last_name', '')
        phone = request.form.get('phone', '')
        address = request.form.get('address', '')
        education_level = request.form.get('education_level', '')
        education_institution = request.form.get('education_institution', '')
        ethnicity = request.form.get('ethnicity', '')
        nationality = request.form.get('nationality', '')
        emergency_name = request.form.get('emergency_name', '')
        emergency_phone = request.form.get('emergency_phone', '')
        emergency_relation = request.form.get('emergency_relation', '')
        special_ability = request.form.get('special_ability', '')
        prev_company = request.form.get('prev_company', '')
        prev_position = request.form.get('prev_position', '')

        eth_sel = request.form.get('ethnicity_select','')
        eth_other = request.form.get('other_ethnicity','')
        if eth_sel == 'อื่นๆ':
            ethnicity = eth_other.strip()
        else:
            ethnicity = eth_sel

        nat_sel = request.form.get('nationality_select','')
        nat_other = request.form.get('other_nationality','')
        if nat_sel == 'อื่นๆ':
            nationality = nat_other.strip()
        else:
            nationality = nat_sel

        try:
            conn.execute("""
                UPDATE users
                SET
                    dob = ?,                  -- เพิ่ม dob
                    gender = ?,
                    nickname = ?,
                    first_name = ?,
                    last_name = ?,
                    phone = ?,
                    address = ?,
                    education_level = ?,
                    education_institution = ?,
                    ethnicity = ?,
                    nationality = ?,
                    emergency_name = ?,
                    emergency_phone = ?,
                    emergency_relation = ?,
                    special_ability = ?,
                    prev_company = ?,
                    prev_position = ?
                WHERE user_id = ?
            """, (
                dob,
                gender,
                nickname, first_name, last_name, phone, address,
                education_level, education_institution, ethnicity, nationality,
                emergency_name, emergency_phone, emergency_relation,
                special_ability, prev_company, prev_position,
                user_id
            ))
            conn.commit()
            flash("บันทึกสำเร็จ", "success")
        except Exception as e:
            flash(f"บันทึกไม่สำเร็จ: {str(e)}", "danger")
        finally:
            conn.close()

        return redirect(url_for('edit_profile'))

    else:
        # GET => load user
        row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        conn.close()

        if not row:
            return "ไม่พบข้อมูลผู้ใช้ในระบบ"

        return render_template("user/edit_profile.html", user=row, user_role=role)

# HR กำหนดวันเริ่มงาน
@app.route('/hr/employee_start_date', methods=['GET', 'POST'])
@role_required('HR')
def set_employee_start_date():
    """
    HR สามารถกำหนด/แก้ไขวันเริ่มงาน (start_date) ของพนักงานในหน้าเดียว
    """
    conn = get_db_connection()

    if request.method == 'POST':
        # อ่านค่าจากฟอร์มซึ่งอาจเป็น list/array ของ user_id / start_date
        user_ids = request.form.getlist('user_id')          # ['1','2','3']
        start_dates = request.form.getlist('start_date')    # ['2025-01-01','2025-02-15','...']

        updated_count = 0
        for uid, sdate in zip(user_ids, start_dates):
            # อัปเดตลง DB ถ้าไม่ว่าง
            if sdate.strip():
                conn.execute("""
                    UPDATE users
                    SET start_date=?
                    WHERE user_id=?
                      AND role in ('HR', 'EMPLOYEE', 'MANAGER', 'SECRETARY')
                """, (sdate.strip(), uid))
                updated_count += conn.total_changes  # นับว่ามี row ถูก update

        conn.commit()
        conn.close()

        flash(f"บันทึกวันเริ่มงานเรียบร้อย (อัปเดต {updated_count} รายการ)", "success")
        return redirect(url_for('set_employee_start_date'))

    else:
        # GET => ดึงพนักงานทั้งหมด (ยกเว้น Admin) มาแสดง
        users = conn.execute("""
            SELECT user_id, first_name, last_name, nickname, role, start_date
            FROM users
            WHERE role in ('HR', 'EMPLOYEE', 'MANAGER', 'SECRETARY')
            ORDER BY start_date
        """).fetchall()
        conn.close()

        return render_template('hr/employee_start_date.html', users=users)

# HR อนุมัติผ่านโปร
@app.route('/hr/approve_probation', methods=['GET','POST'])
@role_required('HR')
def approve_probation():
    conn = get_db_connection()
    if request.method == 'POST':
        user_id = request.form.get('user_id')
        conn.execute("""
            UPDATE users
            SET probation = 0
            WHERE user_id = ?
        """, (user_id,))
        conn.commit()
        conn.close()
        flash("อนุมัติผ่านโปรสำเร็จ", "success")
        return redirect(url_for('approve_probation'))
    else:
        # Query pending employees (those still in probation)
        pending_users = conn.execute("""
            SELECT user_id, first_name, last_name, nickname, role
            FROM users
            WHERE role in ('HR', 'EMPLOYEE', 'MANAGER', 'SECRETARY') AND probation = 1
        """).fetchall()

        # Query all employees (excluding admin) for grouping
        all_users = conn.execute("""
            SELECT first_name, last_name, role, probation, nickname, start_date
            FROM users
            WHERE role in ('HR', 'EMPLOYEE', 'MANAGER', 'SECRETARY')
            ORDER BY start_date
        """).fetchall()
        conn.close()

        # Group all_users: trial_users (probation = 1) and permanent_users (probation = 0)
        trial_users = [u for u in all_users if u['probation'] == 1]
        permanent_users = [u for u in all_users if u['probation'] == 0]

        return render_template('hr/approve_probation.html', 
                               pending_users=pending_users, 
                               trial_users=trial_users, 
                               permanent_users=permanent_users)

@app.route('/hr/generate_quota_form', methods=['GET','POST'])
@role_required('HR')
def generate_quota_form():
    if request.method=='POST':
        year = int(request.form.get('year'))
        return redirect(url_for('auto_generate_quota', year=year))
    else:
        # แสดงฟอร์มเลือกปี
        return '''
        <h3>Auto Generate Quota</h3>
        <form method="POST">
          <p>Year: <input type="number" name="year" value="2025"/></p>
          <button type="submit">Generate</button>
        </form>
        '''

# User List
@app.route('/user/user_list')
def user_list():
    # ดึง role, sub_category_id จาก session หรือที่ไหนก็ตาม
    current_role = session.get('role', 'EMPLOYEE')
    current_subcat_id = session.get('sub_category_id', 0)
    user_id = session.get('user_id', 0)

    conn = get_db_connection()
    
    if current_role == 'ADMIN':
        # Admin เห็นทุกคน
        rows = conn.execute("""
            SELECT u.*, sc.sub_category_name
            FROM users u
            LEFT JOIN sub_categories sc ON u.sub_category_id = sc.sub_category_id
            ORDER BY u.start_date
        """).fetchall()
    
    elif current_role == 'HR':
        # HR เห็นทั้งหมด ยกเว้น Admin
        rows = conn.execute("""
            SELECT u.*, sc.sub_category_name
            FROM users u
            LEFT JOIN sub_categories sc ON u.sub_category_id = sc.sub_category_id
            WHERE u.role in ('HR', 'EMPLOYEE', 'MANAGER', 'SECRETARY')
            ORDER BY u.start_date
        """).fetchall()

    elif current_role == 'MANAGER':
        # Manager → หา child_subcat ที่ตัวเองมองเห็นได้
        child_rows = conn.execute("""
            SELECT child_subcat_id
            FROM subcat_access
            WHERE parent_subcat_id = ?
        """, (current_subcat_id,)).fetchall()
        child_ids = [r['child_subcat_id'] for r in child_rows]

        # ถ้าอยากเห็นตัวเองด้วย
        if current_subcat_id not in child_ids:
            child_ids.append(current_subcat_id)

        if child_ids:
            placeholders = ','.join('?' * len(child_ids))  # "?,?"...
            sql = f"""
                SELECT u.*, sc.sub_category_name
                FROM users u
                LEFT JOIN sub_categories sc ON u.sub_category_id = sc.sub_category_id
                WHERE u.sub_category_id IN ({placeholders})
                  AND u.role in ('EMPLOYEE', 'MANAGER')  -- สมมติ MANAGER ไม่เห็น ADMIN
                ORDER BY u.start_date
            """
            rows = conn.execute(sql, child_ids).fetchall()
        else:
            # ถ้าไม่มี child_ids เลย แปลว่าดูใครไม่ได้
            rows = []

    else:
        # EMPLOYEE -> เห็นเฉพาะตัวเอง
        rows = conn.execute("""
            SELECT u.*, sc.sub_category_name
            FROM users u
            LEFT JOIN sub_categories sc ON u.sub_category_id = sc.sub_category_id
            WHERE u.user_id = ?
        """, (user_id,)).fetchall()

    conn.close()
    # 1) แปลง rows เป็น list ของ dict เพื่อแก้ไข/เพิ่ม key ได้
    user_data = []
    for r in rows:
        user_dict = dict(r)
        # 2) คำนวณอายุงาน ใส่ key "service_age"
        user_dict['service_age'] = calc_service_age(user_dict.get('start_date', ''))
        user_dict['age'] = calc_age(user_dict.get('dob', ''))
        user_data.append(user_dict)
    return render_template('user/user_list.html', user_list=user_data, role=current_role)

# Change Password
@app.route('/user/change_password', methods=['GET', 'POST'])
@role_required('ADMIN', 'HR', 'MANAGER', 'EMPLOYEE', 'OPD', 'SECRETARY')
def change_password():
    user_id = session.get('user_id')
    conn = get_db_connection()

    if request.method == 'POST':
        old_password = request.form.get('old_password', '')
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')

        # 1) ดึง password_hash จาก DB
        row = conn.execute("SELECT password_hash FROM users WHERE user_id = ?", (user_id,)).fetchone()
        if not row:
            conn.close()
            flash("ไม่พบผู้ใช้ในระบบ", "danger")
            return redirect(url_for('change_password'))

        current_hash = row['password_hash']

        # 2) ตรวจสอบ old_password
        if not check_password_hash(current_hash, old_password):
            conn.close()
            flash("รหัสผ่านเดิมไม่ถูกต้อง", "danger")
            return redirect(url_for('change_password'))

        # 3) ตรวจสอบ new_password == confirm_password
        if new_password != confirm_password:
            conn.close()
            flash("รหัสผ่านใหม่ไม่ตรงกัน", "warning")
            return redirect(url_for('change_password'))

        # 4) hash new_password + update
        new_hash = generate_password_hash(new_password)
        conn.execute("UPDATE users SET password_hash=? WHERE user_id=?", (new_hash, user_id))
        conn.commit()
        conn.close()

        flash("เปลี่ยนรหัสผ่านสำเร็จ", "success")
        return redirect(url_for('dashboard'))

    else:
        # GET => แสดงฟอร์ม
        conn.close()
        return render_template('user/change_password.html')

# Manage PR code
@app.route('/hr/manage_pr_codes', methods=['GET', 'POST'])
@role_required('HR', 'ADMIN')
def manage_pr_codes():
    conn = get_db_connection()

    if request.method == 'POST':
        # อ่านค่าจากฟอร์ม (user_id, pr_code ใหม่)
        user_id = request.form.get('user_id')
        new_pr_code = request.form.get('pr_code', '').strip()

        # ตรวจสอบว่าผู้ใช้มีอยู่จริง
        user = conn.execute("""
            SELECT user_id, first_name, last_name, nickname, pr_code
            FROM users
            WHERE user_id = ?
        """, (user_id,)).fetchone()

        if not user:
            conn.close()
            flash("ไม่พบผู้ใช้ในระบบ", "warning")
            return redirect(url_for('manage_pr_codes'))

        # อัปเดต pr_code
        try:
            conn.execute("""
                UPDATE users
                SET pr_code = ?
                WHERE user_id = ?
            """, (new_pr_code, user_id))
            conn.commit()
            flash(
                f"อัปเดต PR Code ของ {user['first_name']} {user['last_name']} เป็น {new_pr_code or '(เว้นว่าง)'} สำเร็จ",
                "success"
            )
        except Exception as e:
            conn.rollback()
            flash(f"เกิดข้อผิดพลาด: {e}", "danger")

    # GET หรือหลัง POST เสร็จ: ดึงรายการพนักงานทั้งหมด
    employees = conn.execute("""
        SELECT user_id, first_name, last_name, nickname, pr_code, start_date
        FROM users
        WHERE role IN ('EMPLOYEE','MANAGER', 'OPD')
        ORDER BY start_date
    """).fetchall()

    conn.close()

    return render_template('hr/manage_pr_codes.html', employees=employees)



### -------------------------------
### Admin Tasks
### -------------------------------
# 1. Add User
@app.route('/admin/create_user', methods=['GET', 'POST'])
@role_required('ADMIN')
def create_user():
    if request.method == 'POST':
        # รับข้อมูลจากฟอร์ม
        username = request.form.get('username')
        password = request.form.get('password')
        role_id = request.form.get('role_id')
        sub_category_id = request.form.get('sub_category_id')
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')

        # แฮช password
        password_hash = generate_password_hash(password)

        # ตรวจสอบว่าผู้ใช้ได้เลือก Role และ Subcategory
        if not role_id:
            flash("กรุณาเลือก Role ก่อน", "danger")
            return redirect(url_for('manage_users'))

        if not sub_category_id:
            flash("กรุณาเลือก Subcategory ก่อน", "danger")
            return redirect(url_for('manage_users'))

        # เริ่มเชื่อมต่อ DB
        conn = get_db_connection()
        try:
            # 1) ดึง role_name จากตาราง roles โดยใช้ role_id
            role_row = conn.execute(
                "SELECT role_name FROM roles WHERE role_id = ?",
                (role_id,)
            ).fetchone()

            if not role_row:
                # ถ้าไม่พบ row หมายความว่า role_id ไม่มีในตาราง roles
                flash("ไม่พบข้อมูล role ที่เลือกในระบบ", "danger")
                conn.close()
                return redirect(url_for('manage_users'))

            role_name = role_row['role_name']  # ได้ชื่อ Role เป็น text

            # 2) สร้างผู้ใช้ใหม่ใน DB (ระบุคอลัมน์ role ด้วย)
            conn.execute('''
                INSERT INTO users (
                    username, 
                    password_hash, 
                    role,         -- ใส่ค่า role text ตรงนี้
                    role_id, 
                    sub_category_id, 
                    first_name, 
                    last_name
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                username,
                password_hash,
                role_name,       # ค่า role TEXT ที่ได้จากตาราง roles
                role_id,
                sub_category_id,
                first_name,
                last_name
            ))
            conn.commit()

            flash("สร้างผู้ใช้เรียบร้อย", "success")

        except sqlite3.IntegrityError:
            flash("เกิดข้อผิดพลาด: username ซ้ำ หรือข้อมูลไม่ถูกต้อง", "danger")
        except Exception as e:
            flash(f"เกิดข้อผิดพลาด: {e}", "danger")
        finally:
            conn.close()

        # เสร็จแล้ว redirect ไปหน้า manage_users
        return redirect(url_for('manage_users'))

    else:
        # GET Method → ดึงข้อมูล roles ทั้งหมดมาแสดงใน dropdown
        conn = get_db_connection()
        roles_data = conn.execute('SELECT * FROM roles').fetchall()
        conn.close()

        return render_template('admin/create_user.html', roles=roles_data)

# 2. Delete User
@app.route('/admin/delete_user/<int:user_id>', methods=['POST'])
@role_required('ADMIN')
def delete_user(user_id):
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()

    if not user:
        conn.close()
        flash("ไม่พบผู้ใช้ในระบบ", "warning")
        return redirect(url_for('manage_users'))

    # ตรวจสอบว่าพยายามลบตัวเองหรือไม่
    if user_id == session['user_id']:
        conn.close()
        flash("ไม่สามารถลบตัวเองได้", "danger")
        return redirect(url_for('manage_users'))

    # ตรวจสอบว่าเป็น Admin หรือไม่
    if user['role'] == 'ADMIN':
        conn.close()
        flash("ไม่สามารถลบผู้ใช้ที่มีบทบาทเป็น Admin ได้", "danger")
        return redirect(url_for('manage_users'))

    try:
        # ลบผู้ใช้
        conn.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
        conn.commit()
        flash("ลบผู้ใช้สำเร็จ", "success")
    except Exception as e:
        flash(f"เกิดข้อผิดพลาด: {str(e)}", "danger")
    finally:
        conn.close()

    return redirect(url_for('manage_users'))

# 3. Manage user (Add/Edit Role/Reset Password)
@app.route('/admin/manage_users', methods=['GET','POST'])
@role_required('ADMIN')
def manage_users():
    conn = get_db_connection()

    if request.method == 'POST':
        action_type = request.form.get('action_type')
        user_id = request.form.get('user_id')

        # ตรวจสอบว่าผู้ใช้มีอยู่จริง
        user = conn.execute("""
            SELECT user_id, role_id, role, first_name, last_name
            FROM users
            WHERE user_id = ?
        """, (user_id,)).fetchone()

        if not user:
            conn.close()
            flash("ไม่พบผู้ใช้ในระบบ", "warning")
            return redirect(url_for('manage_users'))

        try:
            if action_type == 'update_role':
                new_role_id_str = request.form.get('role_id','0')
                new_role_id = int(new_role_id_str) if new_role_id_str.isdigit() else 0

                # ดึง role_name จากตาราง roles
                row_role = conn.execute("""
                    SELECT role_name
                    FROM roles
                    WHERE role_id = ?
                """, (new_role_id,)).fetchone()

                new_role_name = row_role['role_name'] if row_role else "UNKNOWN"

                # อัปเดต users: role_id, role
                conn.execute("""
                    UPDATE users
                    SET role_id = ?,
                        role = ?
                    WHERE user_id = ?
                """, (new_role_id, new_role_name, user_id))
                conn.commit()

                flash(f"อัปเดต Role ของ {user['first_name']} {user['last_name']} "
                      f"เป็น {new_role_name} (role_id={new_role_id}) สำเร็จ!", "success")

            elif action_type == 'update_subcategory':
                new_sub_category_id = request.form.get('sub_category_id','')

                # ตรวจสอบชื่อ sub_category (ถ้ามี)
                new_sub_category_name = "General"
                if new_sub_category_id:
                    row_sub = conn.execute("""
                        SELECT sub_category_name
                        FROM sub_categories
                        WHERE sub_category_id = ?
                    """, (new_sub_category_id,)).fetchone()
                    if row_sub:
                        new_sub_category_name = row_sub['sub_category_name']

                conn.execute("""
                    UPDATE users
                    SET sub_category_id = ?
                    WHERE user_id = ?
                """, (new_sub_category_id, user_id))
                conn.commit()

                flash(f"อัปเดตแผนกของ {user['first_name']} {user['last_name']} "
                      f"เป็น {new_sub_category_name} สำเร็จ!", "success")

        except Exception as e:
            conn.rollback()
            flash(f"เกิดข้อผิดพลาด: {e}", "danger")

    # --- หลัง POST หรือเป็น GET ---
    # ดึง users + left join sub_categories
    users = conn.execute("""
        SELECT 
          u.user_id, u.username, u.first_name, u.last_name,
          u.role_id, u.role,
          sc.sub_category_id, sc.sub_category_name
        FROM users u
        LEFT JOIN sub_categories sc ON u.sub_category_id = sc.sub_category_id
        ORDER BY u.user_id
    """).fetchall()

    # ดึง roles ทั้งหมด
    roles = conn.execute("""
        SELECT role_id, role_name
        FROM roles
        ORDER BY role_id
    """).fetchall()

    # ดึง sub_categories ทั้งหมด (เพื่อนำไป grouping)
    subcat_rows = conn.execute("""
        SELECT sub_category_id, role_id, sub_category_name
        FROM sub_categories
        ORDER BY role_id, sub_category_id
    """).fetchall()
    conn.close()

    # สร้าง dict grouping subcats ตาม role_id
    # grouped_subcats[role_id] = [ {id, name}, ... ]
    grouped_subcats = {}
    for row in subcat_rows:
        rid = row['role_id']
        if rid not in grouped_subcats:
            grouped_subcats[rid] = []
        grouped_subcats[rid].append({
            "id": row['sub_category_id'],
            "name": row['sub_category_name']
        })

    return render_template("admin/manage_users.html",
                           user_list=users,
                           roles=roles,
                           grouped_subcats=grouped_subcats
                           )

# ดึง Subcategory ตาม Role_id
@app.route('/admin/get_subcategories/<int:role_id>')
@role_required('ADMIN')
def get_subcategories(role_id):
    conn = get_db_connection()
    subcats = conn.execute('''
        SELECT sub_category_id, sub_category_name
        FROM sub_categories
        WHERE role_id = ?
    ''', (role_id,)).fetchall()
    conn.close()

    # แปลงข้อมูลเป็น list ของ dict เพื่อ jsonify
    results = []
    for s in subcats:
        results.append({
            'id': s['sub_category_id'],
            'name': s['sub_category_name']
        })
    return jsonify(results)

# Admin Reset Password
@app.route('/admin/reset_password/<int:user_id>', methods=['GET','POST'])
@role_required('ADMIN')
def reset_password(user_id):
    # user_id ของ user ที่จะ reset
    conn = get_db_connection()

    row = conn.execute("""
        SELECT user_id, username, first_name, last_name
        FROM users
        WHERE user_id = ?
    """, (user_id,)).fetchone()

    if not row:
        conn.close()
        flash("ไม่พบผู้ใช้ในระบบ", "warning")
        return redirect(url_for('admin_dashboard'))

    if request.method == 'POST':
        new_password = request.form.get('new_password','').strip()
        if not new_password:
            conn.close()
            flash("กรุณากรอกรหัสผ่านใหม่", "danger")
            return redirect(url_for('reset_password', user_id=user_id))

        # hash แล้วอัพเดต
        new_hash = generate_password_hash(new_password)
        conn.execute("UPDATE users SET password_hash=? WHERE user_id=?", (new_hash, user_id))
        conn.commit()
        conn.close()

        flash(f"รีเซตรหัสผ่านของ {row['first_name']} {row['last_name']} สำเร็จ!", "success")
        return redirect(url_for('admin_dashboard'))
    else:
        conn.close()
        # GET -> แสดงฟอร์ม
        return render_template('admin/reset_password.html', user=row)

# สร้าง code สมัคร log in
@app.route('/admin/change_code', methods=['GET','POST'])
@role_required('ADMIN')
def change_employee_code():
    conn = get_db_connection()
    # ดึงโค้ดปัจจุบัน
    row = conn.execute("""
        SELECT config_value 
        FROM system_config 
        WHERE config_key='employee_join_code'
    """).fetchone()
    current_code = row['config_value'] if row else ''

    if request.method=='POST':
        new_code = request.form.get('new_code','').strip()
        if not new_code:
            flash("กรุณากรอกโค้ดใหม่", "danger")
            conn.close()
            return redirect(url_for('change_employee_code'))
        
        conn.execute("""
            UPDATE system_config
            SET config_value=?
            WHERE config_key='employee_join_code'
        """, (new_code,))
        conn.commit()
        conn.close()

        flash(f"เปลี่ยนโค้ดจาก '{current_code}' เป็น '{new_code}' เรียบร้อย!", "success")
        return redirect(url_for('change_employee_code'))

    else:
        conn.close()
        # แสดงหน้า GET พร้อม current_code
        return render_template('admin/change_employee_code.html', 
                               current_code=current_code)

# 1. Add Subcategory
@app.route('/admin/add_subcategory', methods=['GET', 'POST'])
@role_required('ADMIN')
def add_subcategory():
    conn = get_db_connection()

    if request.method == 'POST':
        role_id = request.form.get('role_id')
        sub_category_name = request.form.get('sub_category_name')

        # ตรวจสอบการซ้ำกัน
        existing = conn.execute("""
            SELECT 1
            FROM sub_categories
            WHERE role_id = ? AND sub_category_name = ?
        """, (role_id, sub_category_name)).fetchone()

        if existing:
            conn.close()
            return "Subcategory นี้มีอยู่แล้วใน Role นี้"

        # เพิ่ม Subcategory ใหม่
        conn.execute("""
            INSERT INTO sub_categories (role_id, sub_category_name)
            VALUES (?, ?)
        """, (role_id, sub_category_name))
        conn.commit()

    # GET Method หรือ Refresh หลัง POST สำเร็จ
    roles = get_roles_with_subcategories()  # ดึงข้อมูล Role + Subcategories ใหม่
    conn.close()

    return render_template('admin/add_subcategory.html', roles=roles)

# 2. Delete Subcategory
@app.route('/admin/delete_subcategory/<int:subcat_id>', methods=['POST'])
@role_required('ADMIN')
def delete_subcategory(subcat_id):
    protected_ids = [1, 2, 3, 4, 5 ,6 ,7 ,8 ,9 ,10 ,11, 12, 13, 14, 15, 16, 17, 18, 19]  # ตัวอย่าง: subcategory ที่ไม่อนุญาตให้ลบ
    if subcat_id in protected_ids:
        flash("ไม่สามารถลบ Subcategory นี้ได้ เนื่องจากเป็นข้อมูลสำคัญ", "danger")
        return redirect(url_for('add_subcategory'))
    conn = get_db_connection()
    conn.execute("DELETE FROM sub_categories WHERE sub_category_id = ?", (subcat_id,))
    conn.commit()
    conn.close()
    flash("ลบ Subcategory สำเร็จ", "success")
    return redirect(url_for('add_subcategory'))

# 3. Edit Subcategory
@app.route('/admin/edit_subcategory/<int:sub_category_id>', methods=['POST'])
@role_required('ADMIN')
def edit_subcategory(sub_category_id):
    new_name = request.form.get('new_sub_category_name')

    if not new_name:
        return "ชื่อ Subcategory ไม่สามารถว่างได้", 400

    conn = get_db_connection()

    # อัปเดตชื่อ Subcategory
    conn.execute("""
        UPDATE sub_categories
        SET sub_category_name = ?
        WHERE sub_category_id = ?
    """, (new_name, sub_category_id))

    conn.commit()
    conn.close()

    # Redirect กลับไปยังหน้าหลักหลังแก้ไขสำเร็จ
    return redirect('/admin/add_subcategory')

# 4. Manage Subcategory Access
@app.route('/admin/manage_subcat_access', methods=['GET', 'POST'])
@role_required('ADMIN')
def manage_subcat_access():
    conn = get_db_connection()

    if request.method == 'POST':
        # ตรวจว่าเป็น action add หรือ delete
        action = request.form.get('action')
        
        if action == 'add':
            parent_id = request.form.get('parent_subcat_id')
            child_id = request.form.get('child_subcat_id')

            if not parent_id or not child_id:
                flash("กรุณาเลือก Parent Subcategory และ Child Subcategory ให้ครบ", "danger")
                conn.close()
                return redirect(url_for('manage_subcat_access'))
            
            try:
                conn.execute("""
                    INSERT INTO subcat_access (parent_subcat_id, child_subcat_id)
                    VALUES (?, ?)
                """, (parent_id, child_id))
                conn.commit()
                flash("เพิ่มการเข้าถึงระหว่าง Subcategory สำเร็จ", "success")
            except sqlite3.IntegrityError:
                flash("มีการกำหนดคู่นี้ไว้แล้ว หรือข้อมูลซ้ำ", "warning")
        
        elif action == 'delete':
            parent_id = request.form.get('parent_id')
            child_id = request.form.get('child_id')
            try:
                conn.execute("""
                    DELETE FROM subcat_access
                    WHERE parent_subcat_id = ? AND child_subcat_id = ?
                """, (parent_id, child_id))
                conn.commit()
                flash("ลบการเข้าถึงสำเร็จ", "success")
            except Exception as e:
                flash(f"เกิดข้อผิดพลาด: {e}", "danger")

        conn.close()
        return redirect(url_for('manage_subcat_access'))

    else:
        # GET method
        # 1) ดึง sub_categories ทั้งหมดมาแสดงใน dropdown
        subcats = conn.execute("""
            SELECT sub_category_id, sub_category_name
            FROM sub_categories
            ORDER BY sub_category_name
        """).fetchall()

        # 2) ดึงรายการ parent-child ที่มีอยู่ใน subcat_access
        access_list = conn.execute("""
            SELECT sa.parent_subcat_id, sa.child_subcat_id,
                   sc1.sub_category_name AS parent_name,
                   sc2.sub_category_name AS child_name
            FROM subcat_access sa
            JOIN sub_categories sc1 ON sa.parent_subcat_id = sc1.sub_category_id
            JOIN sub_categories sc2 ON sa.child_subcat_id = sc2.sub_category_id
            ORDER BY parent_name, child_name
        """).fetchall()
        
        conn.close()

        return render_template(
            'admin/manage_subcat_access.html',
            subcats=subcats,
            access_list=access_list
        )

# Admin Salary Overview
@app.route('/admin/salary_overview')
@role_required('ADMIN')
def salary_overview():
    """
    แสดงฐานเงินเดือนปัจจุบัน (base_salary, daily_wage, hourly_wage, effective_date) 
    ของผู้ใช้ทุกคน (ยกเว้น admin) โดยให้เฉพาะ admin มีสิทธิ์เข้าถึง
    """

    conn = get_db_connection()

    # SELECT รายชื่อ user (role in ('HR', 'EMPLOYEE', 'MANAGER', 'SECRETARY')) + record ล่าสุดจาก salary_records
    rows = conn.execute("""
    SELECT 
       u.user_id, 
       u.first_name, 
       u.last_name,
       u.nickname,
       u.start_date,
       COALESCE(sr.base_salary, 0) AS base_salary,
       COALESCE(sr.daily_wage, 0)  AS daily_wage,
       COALESCE(sr.hourly_wage, 0) AS hourly_wage,
       sr.effective_date
    FROM users u
    LEFT JOIN (
       SELECT s1.* 
       FROM salary_records s1
       JOIN (
         SELECT user_id, MAX(salary_id) AS max_id
         FROM salary_records
         GROUP BY user_id
       ) s2 ON s1.user_id = s2.user_id AND s1.salary_id = s2.max_id
    ) sr ON sr.user_id = u.user_id
    WHERE u.role in ('HR', 'EMPLOYEE', 'MANAGER', 'SECRETARY')
    ORDER BY u.start_date
    """).fetchall()

    conn.close()

    return render_template(
        'admin/salary_overview.html',
        rows=rows
    )

# 1. Add & View Doctors (Combined)
@app.route('/doctor_database', methods=['GET', 'POST'])
@role_required("ADMIN")
def doctor_database():
    if request.method == 'POST':
        # รับข้อมูลจากแบบฟอร์มสำหรับเพิ่มแพทย์
        thai_full_name = request.form.get('thai_full_name')
        eng_full_name  = request.form.get('eng_full_name')
        short_name     = request.form.get('short_name')
        license_number = request.form.get('license_number')
        start_date     = request.form.get('start_date')  # ควรอยู่ในรูปแบบ "YYYY-MM-DD"
        df_surgery     = request.form.get('df_surgery')
        df_aesthetic   = request.form.get('df_aesthetic')
        
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        conn = get_db_connection()
        try:
            conn.execute("""
                INSERT INTO doctors 
                (thai_full_name, eng_full_name, short_name, license_number, start_date, df_surgery, df_aesthetic, created_at)
                VALUES (?,?,?,?,?,?,?,?)
            """, (thai_full_name, eng_full_name, short_name, license_number, start_date, df_surgery, df_aesthetic, now_str))
            conn.commit()
            flash("เพิ่มรายชื่อแพทย์สำเร็จ", "success")
        except Exception as e:
            conn.rollback()
            flash(f"เกิดข้อผิดพลาด: {e}", "danger")
        finally:
            conn.close()
        return redirect(url_for('doctor_database'))
    else:
        # GET: ดึงรายชื่อแพทย์ทั้งหมดเพื่อแสดงในหน้าเดียวกัน
        conn = get_db_connection()
        doctors = conn.execute("SELECT * FROM doctors ORDER BY created_at DESC").fetchall()
        conn.close()
        return render_template('admin/doctor_database.html', doctor_list=doctors)

# 2. Edit Doctor
@app.route('/edit_doctor/<int:doctor_id>', methods=['GET', 'POST'])
@role_required("ADMIN")
def edit_doctor(doctor_id):
    conn = get_db_connection()
    if request.method == 'POST':
        thai_full_name = request.form.get('thai_full_name')
        eng_full_name  = request.form.get('eng_full_name')
        short_name     = request.form.get('short_name')
        license_number = request.form.get('license_number')
        start_date     = request.form.get('start_date')
        df_surgery     = request.form.get('df_surgery')
        df_aesthetic   = request.form.get('df_aesthetic')
        
        try:
            conn.execute("""
                UPDATE doctors
                SET thai_full_name = ?,
                    eng_full_name = ?,
                    short_name = ?,
                    license_number = ?,
                    start_date = ?,
                    df_surgery = ?,
                    df_aesthetic = ?
                WHERE doctor_id = ?
            """, (thai_full_name, eng_full_name, short_name, license_number, start_date, df_surgery, df_aesthetic, doctor_id))
            conn.commit()
            flash("แก้ไขข้อมูลแพทย์สำเร็จ", "success")
        except Exception as e:
            conn.rollback()
            flash(f"เกิดข้อผิดพลาด: {e}", "danger")
        finally:
            conn.close()
        return redirect(url_for('doctor_database'))
    else:
        doctor = conn.execute("SELECT * FROM doctors WHERE doctor_id = ?", (doctor_id,)).fetchone()
        conn.close()
        if doctor is None:
            flash("ไม่พบข้อมูลแพทย์", "danger")
            return redirect(url_for('doctor_database'))
        return render_template('admin/edit_doctor.html', doctor=doctor)

# 3. Delete Doctor
@app.route('/delete_doctor/<int:doctor_id>', methods=['POST'])
@role_required("ADMIN")
def delete_doctor(doctor_id):
    conn = get_db_connection()
    try:
        conn.execute("DELETE FROM doctors WHERE doctor_id = ?", (doctor_id,))
        conn.commit()
        flash("ลบข้อมูลแพทย์สำเร็จ", "success")
    except Exception as e:
        conn.rollback()
        flash(f"เกิดข้อผิดพลาด: {e}", "danger")
    finally:
        conn.close()
    return redirect(url_for('doctor_database'))



### -------------------------------------------
### Check In & Out
### -------------------------------------------
def calculate_distance(lat1, lon1, lat2, lon2):
    """
    คำนวณระยะทางระหว่างสองจุดบนพื้นโลกโดยใช้สูตร Haversine
    คืนค่าเป็นเมตร
    """
    R = 6371000  # รัศมีโลก (เมตร)
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    d = R * c
    return d

# Check In & Out (WE clinic GPS)
@app.route('/check_in_out', methods=['GET', 'POST'])
@role_required('EMPLOYEE', 'HR', 'MANAGER', 'SECRETARY')
def check_in_out():
    user_id = session['user_id']
    nickname = session.get('nickname')
    first_name = session.get('first_name')
    conn = get_db_connection()

    if request.method == 'POST':
        # ตรวจสอบตำแหน่งที่ส่งมาจากฟรอนต์เอนด์ (latitude, longitude)
        try:
            device_lat = float(request.form.get('latitude'))
            device_lng = float(request.form.get('longitude'))
        except (TypeError, ValueError):
            conn.close()
            return "ไม่สามารถตรวจสอบตำแหน่งที่ตั้งได้ กรุณาลองใหม่อีกครั้ง"

        # กำหนดตำแหน่งของคลินิก # WE Clinic
        CLINIC_LAT = 13.787791782463486  
        CLINIC_LNG = 100.54715289024793

        distance = calculate_distance(device_lat, device_lng, CLINIC_LAT, CLINIC_LNG)
        if distance > 100:
            conn.close()
            return f"ตำแหน่งของคุณอยู่ห่างจากคลินิก {distance:.1f} เมตร ซึ่งเกินขีดจำกัด 100 เมตร กรุณาอยู่ใกล้คลินิกเพื่อบันทึกเวลาเข้าออกงาน"

        action = request.form.get('action')
        row = conn.execute("""
            SELECT *
            FROM attendance
            WHERE user_id=?
            ORDER BY attendance_id DESC
            LIMIT 1
        """, (user_id,)).fetchone()

        if action == 'checkin':
            tz = pytz.timezone('Asia/Bangkok')
            now_dt = datetime.now(tz)
            today_str = now_dt.strftime('%Y-%m-%d')
            
            if row and row['work_date'] == today_str and row['checkout_time'] is None:
                conn.close()
                return "คุณยังไม่ได้บันทึกเวลาเลิกงานครั้งที่แล้ว"

            now_str = now_dt.strftime('%Y-%m-%d %H:%M:%S')
            wdate = today_str

            conn.execute("""
                INSERT INTO attendance (user_id, checkin_time, work_date, ot_status)
                VALUES (?, ?, ?, 'normal')
            """, (user_id, now_str, wdate))
            conn.commit()
            conn.close()

            return render_template('check_in_out/after_action.html',
                                   message="บันทึกเวลาเข้างานเรียบร้อย",
                                   return_url=url_for('check_in_out'))

        elif action == 'checkout':
            if row and row['checkout_time'] is None:
                tz = pytz.timezone('Asia/Bangkok')
                now_dt = datetime.now(tz)
                now_str = now_dt.strftime('%Y-%m-%d %H:%M:%S')

                ot_reason = request.form.get('ot_reason', '').strip()
                user_role = session.get('role')
                current_subcat = session.get('sub_category_id')
                
                if ot_reason:
                    if user_role == 'HR' or (user_role.startswith("MANAGER") and str(current_subcat) != "3"):
                        ot_status = 'pending_final'
                    else:
                        ot_status = 'pending'
                else:
                    ot_status = 'normal'
                
                work_date = row['work_date']
                schedule_row = conn.execute("""
                    SELECT planned_start_time, planned_end_time 
                    FROM work_schedules 
                    WHERE user_id = ? AND work_date = ?
                """, (user_id, work_date)).fetchone()
                
                if schedule_row:
                    planned_start = schedule_row['planned_start_time']
                    planned_end = schedule_row['planned_end_time']
                else:
                    planned_start = "10:30"
                    planned_end = "19:30"
                
                late_minutes = calculate_late_minutes(planned_start, row['checkin_time'])
                ot_before_midnight, ot_after_midnight = calculate_ot_split(planned_end, now_str)
                
                conn.execute("""
                    UPDATE attendance
                    SET checkout_time = ?,
                        ot_reason = ?,
                        ot_status = ?,
                        late_minutes = ?,
                        ot_before_midnight = ?,
                        ot_after_midnight = ?
                    WHERE attendance_id = ?
                """, (now_str, ot_reason, ot_status, late_minutes, ot_before_midnight, ot_after_midnight, row['attendance_id']))
                conn.commit()
                
                if ot_reason:
                    if user_role.startswith("MANAGER") and str(current_subcat) != "3":
                        approver_id = get_parent_manager_for_employee(current_subcat)
                    else:
                        approver_id = get_manager_for_employee(current_subcat)
                    
                    if approver_id is None:
                        flash("ไม่พบหัวหน้าแผนกสำหรับคำขอ OT", "warning")
                    else:
                        add_notification(approver_id, f"{nickname} -- {first_name} ขออนุมัติ OT, กรุณาตรวจสอบ")
                conn.close()
                
                return render_template('check_in_out/after_action.html',
                                       message="บันทึกเวลาเลิกงานเรียบร้อย" + (" (OT pending)" if ot_reason else ""),
                                       return_url=url_for('check_in_out'))
            else:
                conn.close()
                return "ไม่พบรายการที่ยังไม่บันทึกเวลาเลิกงาน"
        else:
            conn.close()
            return "ไม่พบการกระทำที่รองรับ"
    else:
        row = conn.execute("""
            SELECT *
            FROM attendance
            WHERE user_id=?
            ORDER BY attendance_id DESC
            LIMIT 1
        """, (user_id,)).fetchone()
        conn.close()

        tz = pytz.timezone('Asia/Bangkok')
        now_dt = datetime.now(tz)
        today_str = now_dt.strftime('%Y-%m-%d')

        def within_grace_period(check_time_str):
            try:
                check_dt = datetime.strptime(check_time_str, '%Y-%m-%d %H:%M:%S')
                hour = check_dt.hour
                return 0 <= hour < 6
            except Exception:
                return False

        if not row or row['work_date'] != today_str or (row['checkout_time'] is not None and not within_grace_period(row['checkout_time'])):
            status = 'ready_to_checkin'
            checkin_time = None
        else:
            status = 'ready_to_checkout'
            checkin_time = row['checkin_time']

        return render_template('check_in_out/check_in_out.html', status=status, checkin_time=checkin_time)

# My OT Summary
@app.route('/ot_summary', methods=['GET', 'POST'])
@role_required('EMPLOYEE', 'HR', 'MANAGER', 'SECRETARY')
def ot_summary():
    """
    สรุปเวลาทำงานของตัวเอง พร้อมตัวเลือกเดือนปัจจุบันและเดือนที่แล้ว
    """
    from datetime import datetime
    from calendar import monthrange

    # ดึงค่าเดือนและปีจาก POST หรือใช้ค่าเริ่มต้น (เดือนปัจจุบัน)
    if request.method == 'POST':
        year = int(request.form.get('year'))
        month = int(request.form.get('month'))
    else:
        today = datetime.today()
        year = today.year
        month = today.month

    # ดึง user_id จาก session
    user_id = session['user_id']
    conn = get_db_connection()
    num_days = monthrange(year, month)[1]

    summary_data = []
    total_late = 0
    total_ot_before = 0
    total_ot_after = 0

    for day in range(1, num_days + 1):
        date_str = f"{year:04d}-{month:02d}-{day:02d}"

        # ดึง Work Schedule
        row_sch = conn.execute("""
            SELECT planned_start_time, planned_end_time
            FROM work_schedules
            WHERE user_id = ? AND work_date = ?
        """, (user_id, date_str)).fetchone()

        planned_start = row_sch['planned_start_time'] if row_sch else None
        planned_end = row_sch['planned_end_time'] if row_sch else None

        # ดึง Attendance พร้อมค่า late_minutes, ot_before_midnight, ot_after_midnight
        row_att = conn.execute("""
            SELECT checkin_time, checkout_time, ot_status, late_minutes, ot_before_midnight, ot_after_midnight
            FROM attendance
            WHERE user_id = ? AND work_date = ?
        """, (user_id, date_str)).fetchone()

        if row_att:
            checkin_time = row_att['checkin_time']
            checkout_time = row_att['checkout_time']
            ot_status = row_att['ot_status']
            # ดึงค่าจากฐานข้อมูลโดยตรง
            late_min = row_att['late_minutes'] if row_att['late_minutes'] is not None else 0
            ot_before = row_att['ot_before_midnight'] if row_att['ot_before_midnight'] is not None else 0
            ot_after = row_att['ot_after_midnight'] if row_att['ot_after_midnight'] is not None else 0

            total_late += late_min
            total_ot_before += ot_before
            total_ot_after += ot_after
        else:
            checkin_time = None
            checkout_time = None
            ot_status = None
            late_min = 0
            ot_before = 0
            ot_after = 0

        summary_data.append({
            "day": day,
            "checkin": checkin_time or '-',
            "checkout": checkout_time or '-',
            "ot_status": ot_status or '-',
            "late_min": late_min,
            "ot_before": format_hh_mm(ot_before),
            "ot_after": format_hh_mm(ot_after),
        })

    conn.close()

    return render_template(
        'check_in_out/ot_summary.html',
        year=year,
        month=month,
        summary_data=summary_data,
        total_late=total_late,
        total_ot_before=format_hh_mm(total_ot_before),
        total_ot_after=format_hh_mm(total_ot_after)
    )



### -------------------------------------------
### OT Approval
### -------------------------------------------
@app.route('/ot_approval_list')
@role_required('HR', 'MANAGER')
@subcategory_required("ot_approval_list")
def ot_approval_list():
    current_role = session.get('role')
    current_subcat = session.get('sub_category_id')
    conn = get_db_connection()
    
    # สำหรับ HR: ให้แสดงรายการ OT ทั้งหมด
    if current_role == 'HR':
        query = """
            SELECT a.attendance_id, a.user_id, a.checkin_time, a.checkout_time, a.work_date,
                   a.ot_status, a.ot_reason, a.ot_approve_comment,
                   u.first_name, u.last_name, u.nickname
            FROM attendance a
            JOIN users u ON a.user_id = u.user_id
            WHERE a.ot_status IN ('pending', 'pending_final', 'approved', 'rejected')
            ORDER BY a.attendance_id DESC
        """
        params = []
    elif current_role.startswith("MANAGER"):
        # สำหรับ Manager: แยกตาม Manager (child) และ Manager (General)
        if str(current_subcat) == "3":
            # Manager (General): แสดงเฉพาะรายการที่ status เป็น pending_final
            query = """
                SELECT a.attendance_id, a.user_id, a.checkin_time, a.checkout_time, a.work_date,
                       a.ot_status, a.ot_reason, a.ot_approve_comment,
                       u.first_name, u.last_name, u.nickname
                FROM attendance a
                JOIN users u ON a.user_id = u.user_id
                WHERE a.ot_status = 'pending_final'
                ORDER BY a.attendance_id DESC
            """
            params = []
        else:
            # Manager (child): ดึงเฉพาะรายการที่เกี่ยวข้องกับ employee ที่อยู่ใน subcategories ที่ Manager (child) มีสิทธิ์ดู
            allowed_employee_subcats = get_allowed_employee_subcategories(current_subcat)
            if not allowed_employee_subcats:
                conn.close()
                return render_template("ot_approval/ot_approval_list.html", ot_rows=[])
            placeholders = ",".join("?" for _ in allowed_employee_subcats)
            query = f"""
                SELECT a.attendance_id, a.user_id, a.checkin_time, a.checkout_time, a.work_date,
                       a.ot_status, a.ot_reason, a.ot_approve_comment,
                       u.first_name, u.last_name, u.nickname
                FROM attendance a
                JOIN users u ON a.user_id = u.user_id
                WHERE a.ot_status = 'pending' 
                  AND u.sub_category_id IN ({placeholders})
                ORDER BY a.attendance_id DESC
            """
            params = tuple(allowed_employee_subcats)
    else:
        # สำหรับผู้ใช้งานอื่น ๆ (ถ้ามี)
        query = """
            SELECT a.attendance_id, a.user_id, a.checkin_time, a.checkout_time, a.work_date,
                   a.ot_status, a.ot_reason, a.ot_approve_comment,
                   u.first_name, u.last_name, u.nickname
            FROM attendance a
            JOIN users u ON a.user_id = u.user_id
            WHERE a.ot_status = 'pending'
            ORDER BY a.attendance_id DESC
        """
        params = []
    
    rows = conn.execute(query, params).fetchall()
    conn.close()
    
    return render_template("ot_approval/ot_approval_list.html", ot_rows=rows, current_role=current_role)

@app.route('/ot_approve', methods=['POST'])
@role_required('HR', 'MANAGER')
@subcategory_required("ot_approve")
def ot_approve():
    att_id = request.form.get('attendance_id')
    action = request.form.get('action') 
    comment = request.form.get('comment', '')
    
    current_role = session.get('role')
    current_subcat = session.get('sub_category_id')
    current_manager_id = session.get('user_id')
    
    conn = get_db_connection()
    try:
        # ดึงข้อมูล OT request พร้อมข้อมูลพนักงาน
        row = conn.execute("""
            SELECT a.attendance_id, a.user_id, a.ot_status, u.sub_category_id
            FROM attendance a
            JOIN users u ON a.user_id = u.user_id
            WHERE a.attendance_id = ?
        """, (att_id,)).fetchone()
        if not row:
            conn.close()
            flash("ไม่พบ OT request", "warning")
            return redirect(url_for('ot_approval_list'))
        
        employee_subcat = row['sub_category_id']
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # สำหรับ HR ไม่อนุมัติ OT โดยตรง
        if current_role == 'HR':
            conn.close()
            flash("HR ไม่สามารถอนุมัติ OT ได้", "warning")
            return redirect(url_for('ot_approval_list'))
        
        if current_role.startswith("MANAGER"):
            # สำหรับ Manager (child): current_subcat != "3"
            if current_subcat is not None and str(current_subcat) != "3":
                if action == 'approve':
                    # ดึง final approver (Manager General) จาก employee_subcat
                    final_manager_id = get_parent_manager_for_employee(employee_subcat)
                    if final_manager_id is None:
                        conn.close()
                        flash("ไม่พบ Manager (General) สำหรับ OT นี้", "warning")
                        return redirect(url_for('ot_approval_list'))
                    new_status = 'pending_final'
                    conn.execute("""
                        UPDATE attendance
                        SET ot_status = ?,
                            ot_approve_comment = ?,
                            first_approver_id = ?,
                            final_approver_id = ?,
                            updated_at = ?
                        WHERE attendance_id = ?
                    """, (new_status, comment, current_manager_id, final_manager_id, now_str, att_id))
                elif action == 'reject':
                    new_status = 'rejected'
                    conn.execute("""
                        UPDATE attendance
                        SET ot_status = ?,
                            ot_approve_comment = ?,
                            ot_before_midnight = 0,
                            ot_after_midnight = 0,
                            updated_at = ?
                        WHERE attendance_id = ?
                    """, (new_status, comment, now_str, att_id))
                else:
                    flash("ไม่รู้จัก action สำหรับ Manager (child)", "danger")
                    conn.close()
                    return redirect(url_for('ot_approval_list'))
            else:
                # สำหรับ Manager (General): current_subcat == "3"
                if (old_status := row['ot_status']) != 'pending_final':
                    flash("ใบ OT นี้ยังไม่ถึงขั้นตอนตัดสินใจขั้นสุดท้าย", "warning")
                    conn.close()
                    return redirect(url_for('ot_approval_list'))
                if action in ['approve']:
                    new_status = 'approved'
                    conn.execute("""
                        UPDATE attendance
                        SET ot_status = ?,
                            ot_approve_comment = ?,
                            updated_at = ?
                        WHERE attendance_id = ?
                    """, (new_status, comment, now_str, att_id))
                elif action == 'reject':
                    new_status = 'rejected'
                    conn.execute("""
                        UPDATE attendance
                        SET ot_status = ?,
                            ot_approve_comment = ?,
                            ot_before_midnight = 0,
                            ot_after_midnight = 0,
                            updated_at = ?
                        WHERE attendance_id = ?
                    """, (new_status, comment, now_str, att_id))
                else:
                    flash("ไม่รู้จัก action สำหรับ Manager (General)", "danger")
                    conn.close()
                    return redirect(url_for('ot_approval_list'))
        else:
            conn.close()
            flash("ไม่อนุญาตให้ดำเนินการ", "warning")
            return redirect(url_for('ot_approval_list'))
        
        conn.commit()
        flash("ดำเนินการ OT request เรียบร้อย", "success")
    except Exception as e:
        conn.rollback()
        flash(f"เกิดข้อผิดพลาด: {e}", "danger")
    finally:
        conn.close()
    return redirect(url_for('ot_approval_list'))



### -------------------------------------------
### Daily Schedule Editor (HR)
### -------------------------------------------
# Step 1
@app.route('/hr/schedule_editor_step1', methods=['GET', 'POST'])
@role_required('HR', 'MANAGER', 'ADMIN')
def schedule_editor_step1():
    """
    หน้าฟอร์มให้ HR/Manager เลือกพนักงานหลายคน + ใส่ปี/เดือน
    แล้ว POST -> schedule_editor_step2
    """
    if request.method == 'POST':
        # รับ user_ids (list)
        user_ids = request.form.getlist('user_ids')
        year = request.form.get('year')
        month = request.form.get('month')
        # รวมเป็นสตริง
        user_str = ",".join(user_ids)
        return redirect(url_for('schedule_editor_step2', user_str=user_str, year=year, month=month))
    else:
        conn = get_db_connection()

        # กำหนด mapping ของกลุ่ม subcategory
        subcat_groups = {
            'PA': (4, 9),
            'OR': (5, 10),
            'ADMIN_ONLINE': (6, 11),
            'MARKETING': (7, 12),
            'HR': (2,),
            'SECRETARY': (16, 17)
        }
        
        # สำหรับ HR ให้เห็นทุกแผนก: กำหนดพิเศษในกรณี 'ALL'
        special_group = (2, 4, 5, 6, 7, 9, 10, 11, 12, 16, 17)

        # รับค่า sub_category จาก query parameter (ค่าจะเป็น key ใน mapping หรือ 'ALL')
        selected_subcat = request.args.get('sub_category')
        if selected_subcat:
            if selected_subcat.upper() == 'ALL':
                group_tuple = special_group
            else:
                # ตรวจสอบว่าค่า selected_subcat อยู่ใน mapping หรือไม่
                if selected_subcat in subcat_groups:
                    group_tuple = subcat_groups[selected_subcat]
                else:
                    # หากไม่ตรงกับ mapping ให้ลองแปลงเป็น int แล้วใช้เป็นค่าเดียว
                    try:
                        group_tuple = (int(selected_subcat),)
                    except ValueError:
                        group_tuple = ()
            if group_tuple:
                placeholders = ','.join(['?'] * len(group_tuple))
                query = f"""
                    SELECT user_id, first_name, last_name, role, nickname, start_date
                    FROM users
                    WHERE role in ('HR', 'EMPLOYEE', 'MANAGER', 'SECRETARY')
                      AND sub_category_id IN ({placeholders})
                    ORDER BY start_date
                """
                user_list = conn.execute(query, group_tuple).fetchall()
            else:
                user_list = []
        else:
            user_list = []
        conn.close()

        current_year = datetime.now().year
        years = list(range(current_year - 3, current_year + 1))
        months = [{'value': i, 'name': f"เดือน {i}"} for i in range(1, 13)]

        # สร้างรายการสำหรับ dropdown ของ subcategories โดยใช้ mapping ที่กำหนดไว้
        sub_categories = [
            {'id': 'ALL', 'label': 'ทุกคน'},
            {'id': 'PA', 'label': 'PA'},
            {'id': 'OR', 'label': 'OR'},
            {'id': 'ADMIN_ONLINE', 'label': 'ADMIN_ONLINE'},
            {'id': 'MARKETING', 'label': 'MARKETING'},
            {'id': 'HR', 'label': 'HR'},
            {'id': 'SECRETARY', 'label': 'SECRETARY'}
        ]

        return render_template(
            "hr/schedule_editor_step1.html",
            user_list=user_list,
            years=years,
            current_year=current_year,
            months=months,
            sub_categories=sub_categories,
            selected_subcat=selected_subcat
        )

# Step 2
@app.route('/hr/schedule_editor_step2')
@role_required('HR', 'MANAGER', 'ADMIN')
def schedule_editor_step2():
    year = int(request.args.get('year', '2025'))
    month = int(request.args.get('month', '1'))
    user_str = request.args.get('user_str', '')
    user_ids = [u for u in user_str.split(',') if u]

    num_days = monthrange(year, month)[1]
    thai_days = ["อาทิตย์","จันทร์","อังคาร","พุธ","พฤหัส","ศุกร์","เสาร์"]

    # สร้าง days = [
    #   { "day_num":1, "date":"2025-02-01", "name":"พฤหัส1", "schedules": {} },
    #   ...
    # ]
    days = []
    for d in range(1, num_days+1):
        wday = weekday(year, month, d) # 0=จันทร์,...6=อาทิตย์
        name = thai_days[(wday+1)%7] + str(d)
        date_str = f"{year:04d}-{month:02d}-{d:02d}"
        days.append({
            "day_num": d,
            "date": date_str,
            "name": name,
            "schedules": {}  # เก็บค่า plan_start, plan_end ต่อ user
        })

    conn = get_db_connection()

    # ดึง user ที่เลือก
    user_rows=[]
    if user_ids:
        placeholder = ",".join("?" for _ in user_ids)
        user_rows = conn.execute(f"""
            SELECT user_id, first_name, last_name, nickname, start_date
            FROM users
            WHERE user_id IN ({placeholder})
            ORDER BY start_date
        """, tuple(user_ids)).fetchall()

    default_start_time="10:30"
    default_end_time="19:30"

    # สร้าง/อัปเดต work_schedules + เก็บลง days[..]["schedules"][uid]
    for d in days:
        for u in user_rows:
            # เช็คใน DB
            row = conn.execute("""
                SELECT planned_start_time, planned_end_time
                FROM work_schedules
                WHERE user_id=? AND work_date=?
            """,(u['user_id'], d['date'])).fetchone()
            if not row:
                # ถ้าไม่มี => insert default
                conn.execute("""
                    INSERT INTO work_schedules(user_id, work_date,
                                               planned_start_time, planned_end_time)
                    VALUES (?,?,?,?)
                """,(u['user_id'], d['date'],default_start_time, default_end_time))
                # ใช้ default
                d["schedules"][u['user_id']] = {
                    "start": default_start_time,
                    "end":   default_end_time
                }
            else:
                # มี => ใช้ค่านั้น
                d["schedules"][u['user_id']] = {
                    "start": row['planned_start_time'],
                    "end":   row['planned_end_time']
                }

    conn.commit()
    conn.close()

    return render_template("hr/schedule_editor_step2.html",
                           user_rows=user_rows,
                           year=year,
                           month=month,
                           days=days,
                           user_str=user_str)

# Step 3: save แล้วจะไม่ลบ Work Schedule เดิม แต่จะอัปเดตเฉพาะวันที่ HR ระบุ
@app.route('/hr/schedule_editor_save', methods=['POST'])
@role_required('HR', 'MANAGER', 'ADMIN')
def schedule_editor_save():
    year_str = request.form.get('year')
    month_str = request.form.get('month')
    user_str = request.form.get('user_str', '')

    year_int  = int(year_str)
    month_int = int(month_str)
    num_days  = monthrange(year_int, month_int)[1]

    user_ids  = [u for u in user_str.split(',') if u]

    conn = get_db_connection()

    # อัปเดตตาราง work_schedules ตามข้อมูลที่กรอกในฟอร์ม
    for uid in user_ids:
        for day in range(1, num_days+1):
            start_key = f"start_{uid}_{day}"
            end_key   = f"end_{uid}_{day}"
            start_val = request.form.get(start_key)
            end_val   = request.form.get(end_key)

            date_str = f"{year_int:04d}-{month_int:02d}-{day:02d}"

            if start_val or end_val:
                conn.execute("""
                    UPDATE work_schedules
                    SET planned_start_time = ?, planned_end_time = ?
                    WHERE user_id = ? AND work_date = ?
                """, (start_val, end_val, uid, date_str))
    conn.commit()
    conn.close()

    # หลังจากอัปเดต work_schedules แล้ว
    # เรียก recalculate_attendance สำหรับแต่ละ user ในแต่ละวันของเดือนที่แก้ไข
    for uid in user_ids:
        for day in range(1, num_days+1):
            date_str = f"{year_int:04d}-{month_int:02d}-{day:02d}"
            recalculate_attendance(uid, date_str)

    flash(f"บันทึกตารางเดือน {month_int}/{year_int} เรียบร้อย", "success")
    # หลังบันทึกเสร็จ redirect กลับไปที่ schedule_editor_step2
    return redirect(url_for('schedule_editor_step2', year=year_int, month=month_int, user_str=user_str))

# Step 4: คำนวณ Attendance ใหม่
@app.route('/recalculate_attendance/<int:user_id>/<work_date>', methods=['POST'])
@role_required('HR', 'MANAGER', 'ADMIN')
def recalculate_attendance_route(user_id, work_date):
    recalculate_attendance(user_id, work_date)
    return redirect(url_for('attendance_summary', year=work_date[:4], month=work_date[5:7]))



### -------------------------------------------
### OT Summary (All Employee)
### -------------------------------------------
@app.route('/hr/ot_summary_step1', methods=['GET', 'POST'])
@role_required('HR', 'MANAGER', 'ADMIN')
def ot_summary_step1():
    """
    หน้าฟอร์มให้ HR/Manager เลือกพนักงานหลายคน + ใส่ปี/เดือน
    แล้ว POST -> ot_summary_step2
    """
    if request.method == 'POST':
        # รับ user_ids (list)
        user_ids = request.form.getlist('user_ids')
        year = request.form.get('year')
        month = request.form.get('month')
        user_str = ",".join(user_ids)
        return redirect(url_for('ot_summary_step2', user_str=user_str, year=year, month=month))
    else:
        conn = get_db_connection()
        
        # กำหนด mapping ของกลุ่ม subcategory
        subcat_groups = {
            'PA': (4, 9),
            'OR': (5, 10),
            'ADMIN_ONLINE': (6, 11),
            'MARKETING': (7, 12),
            'HR': (2,),
            'SECRETARY': (16, 17)
        }
        # สำหรับ HR ให้เห็นทุกแผนก
        special_group = (2, 4, 5, 6, 7, 9, 10, 11, 12, 16, 17)

        # กำหนดรายการ dropdown ของ subcategories ตาม role
        role = session.get('role')
        allowed_sub_categories = []
        if role in ('HR', 'ADMIN'):
            allowed_sub_categories = [
                {'id': 'ALL', 'label': 'ทุกคน'},
                {'id': 'PA', 'label': 'PA'},
                {'id': 'OR', 'label': 'OR'},
                {'id': 'ADMIN_ONLINE', 'label': 'ADMIN_ONLINE'},
                {'id': 'MARKETING', 'label': 'MARKETING'},
                {'id': 'HR', 'label': 'HR'},
                {'id': 'SECRETARY', 'label': 'SECRETARY'}
            ]
        elif role.startswith("MANAGER"):
            # สำหรับ MANAGER ให้แสดงเฉพาะแผนกที่เกี่ยวข้องกับตัวเอง
            manager_subcat = session.get('sub_category_id')
            if manager_subcat in (4, 9):
                allowed_sub_categories = [{'id': 'PA', 'label': 'PA'}]
            elif manager_subcat in (5, 10):
                allowed_sub_categories = [{'id': 'OR', 'label': 'OR'}]
            elif manager_subcat in (6, 11):
                allowed_sub_categories = [{'id': 'ADMIN_ONLINE', 'label': 'ADMIN_ONLINE'}]
            elif manager_subcat in (7, 12):
                allowed_sub_categories = [{'id': 'MARKETING', 'label': 'MARKETING'}]
            elif manager_subcat in (16, 17):
                allowed_sub_categories = [{'id': 'SECRETARY', 'label': 'SECRETARY'}]
            else:
                allowed_sub_categories = []  # หรืออาจแสดงเป็นว่าง
        else:
            allowed_sub_categories = []

        # รับค่า sub_category จาก query parameter (ค่าที่เลือกจาก dropdown)
        selected_subcat = request.args.get('sub_category')
        if selected_subcat:
            if role in ('HR', 'ADMIN'):
                if selected_subcat.upper() == 'ALL':
                    group_tuple = special_group
                elif selected_subcat in subcat_groups:
                    group_tuple = subcat_groups[selected_subcat]
                else:
                    try:
                        group_tuple = (int(selected_subcat),)
                    except ValueError:
                        group_tuple = ()
            elif role.startswith("MANAGER"):
                # MANAGER สามารถเลือกเฉพาะตัวเลือกใน allowed_sub_categories
                if selected_subcat in subcat_groups:
                    group_tuple = subcat_groups[selected_subcat]
                else:
                    group_tuple = ()
            else:
                group_tuple = ()
                
            if group_tuple:
                placeholders = ','.join(['?'] * len(group_tuple))
                query = f"""
                    SELECT user_id, first_name, last_name, role, nickname, start_date
                    FROM users
                    WHERE role in ('HR', 'EMPLOYEE', 'MANAGER', 'SECRETARY')
                      AND sub_category_id IN ({placeholders})
                    ORDER BY start_date
                """
                user_list = conn.execute(query, group_tuple).fetchall()
            else:
                user_list = []
        else:
            user_list = []
        conn.close()

        current_year = datetime.now().year
        years = list(range(current_year - 3, current_year + 1))
        months = [{'value': i, 'name': f"เดือน {i}"} for i in range(1, 13)]

        return render_template(
            "hr/ot_summary_step1.html",
            user_list=user_list,
            years=years,
            current_year=current_year,
            months=months,
            sub_categories=allowed_sub_categories,
            selected_subcat=selected_subcat
        )

@app.route('/hr/ot_summary_step2')
@role_required('HR', 'MANAGER', 'ADMIN')
def ot_summary_step2():
    """
    แสดงผลสรุปเวลาทำงาน (Attendance/OT) ของ user(s) หลายคน ในเดือน/ปี ที่กำหนด
    """
    from calendar import monthrange
    user_str = request.args.get('user_str', '')
    year = int(request.args.get('year', '2025'))
    month = int(request.args.get('month', '1'))

    user_ids = [uid for uid in user_str.split(',') if uid]
    if not user_ids:
        return "ไม่พบ user_ids ที่เลือก"

    num_days = monthrange(year, month)[1]
    conn = get_db_connection()

    users_data = []
    for uid in user_ids:
        user_row = conn.execute("""
            SELECT first_name, last_name, nickname
            FROM users
            WHERE user_id=?
        """, (uid,)).fetchone()

        if not user_row:
            continue

        full_name = f"{user_row['nickname']} -- {user_row['first_name']} {user_row['last_name']} "
        attendance_data = []

        total_late = 0
        total_ot_before = 0
        total_ot_after = 0

        for day in range(1, num_days + 1):
            date_str = f"{year}-{month:02d}-{day:02d}"

            # ดึง Work Schedule
            row_sch = conn.execute("""
                SELECT planned_start_time, planned_end_time
                FROM work_schedules
                WHERE user_id = ? AND work_date = ?
            """, (uid, date_str)).fetchone()

            planned_start = row_sch['planned_start_time'] if row_sch else None
            planned_end = row_sch['planned_end_time'] if row_sch else None

            # ดึง Attendance
            row_att = conn.execute("""
                SELECT checkin_time, checkout_time
                FROM attendance
                WHERE user_id = ? AND work_date = ?
                LIMIT 1
            """, (uid, date_str)).fetchone()

            if row_att:
                checkin_time = row_att['checkin_time']
                checkout_time = row_att['checkout_time']

                # คำนวณมาสายและ OT
                late_minutes = calculate_late_minutes(planned_start, checkin_time)
                ot_before_midnight, ot_after_midnight = calculate_ot_split(planned_end, checkout_time)

                # สะสมค่ารวม
                total_late += late_minutes
                total_ot_before += ot_before_midnight
                total_ot_after += ot_after_midnight
            else:
                checkin_time = None
                checkout_time = None
                late_minutes = 0
                ot_before_midnight = 0
                ot_after_midnight = 0

            attendance_data.append({
                "date": date_str,
                "checkin_time": checkin_time,
                "checkout_time": checkout_time,
                "late_minutes": late_minutes,
                "ot_before_midnight": format_hh_mm(ot_before_midnight),
                "ot_after_midnight": format_hh_mm(ot_after_midnight),
            })

        users_data.append({
            "name": full_name,
            "attendance": attendance_data,
            "total_late": total_late,
            "total_ot_before": format_hh_mm(total_ot_before),
            "total_ot_after": format_hh_mm(total_ot_after)
        })

    conn.close()

    return render_template(
        "hr/ot_summary_step2.html",
        users_data=users_data,
        year=year,
        month=month
    )

@app.route('/hr/ot_summary_step3')
@role_required('HR', 'MANAGER', 'ADMIN')
def ot_summary_step3():
    """
    แสดงสรุปเวลาทำงานรวมของผู้ใช้ทั้งหมดในกลุ่ม subcat (2,4,5,6,7,9,10,11,12,16,17)
    สำหรับปีปัจจุบัน ตั้งแต่เดือน 1 ถึงเดือนปัจจุบัน
    """
    conn = get_db_connection()
    current_year = datetime.now().year
    current_month = datetime.now().month
    # กำหนดช่วงวันที่สำหรับสรุป (จาก 1 มกราคม ถึงวันสุดท้ายของเดือนปัจจุบัน)
    start_date = f"{current_year}-01-01"
    last_day = monthrange(current_year, current_month)[1]
    end_date = f"{current_year}-{current_month:02d}-{last_day:02d}"

    # กำหนดกลุ่ม subcat ที่ต้องการ
    subcat_ids = (2, 4, 5, 6, 7, 9, 10, 11, 12, 16, 17)
    placeholders = ','.join(['?'] * len(subcat_ids))
    
    # ดึงข้อมูลผู้ใช้จากตาราง users ที่มี sub_category_id ในกลุ่มนี้
    users = conn.execute(f"""
        SELECT user_id, first_name, last_name, role, nickname, start_date
        FROM users
        WHERE sub_category_id IN ({placeholders})
        ORDER BY start_date
    """, subcat_ids).fetchall()

    users_data = []
    for user in users:
        full_name = f"{user['nickname']} -- {user['first_name']} {user['last_name']} ({user['role']})"
        # สรุปข้อมูลจากตาราง attendance สำหรับผู้ใช้ในช่วงปีปัจจุบัน
        row = conn.execute("""
            SELECT 
              IFNULL(SUM(late_minutes), 0) AS total_late,
              IFNULL(SUM(ot_before_midnight), 0) AS total_ot_before,
              IFNULL(SUM(ot_after_midnight), 0) AS total_ot_after
            FROM attendance
            WHERE user_id = ?
              AND work_date BETWEEN ? AND ?
        """, (user['user_id'], start_date, end_date)).fetchone()
        total_late = row['total_late']
        total_ot_before = row['total_ot_before']
        total_ot_after = row['total_ot_after']

        users_data.append({
            "name": full_name,
            "total_late": total_late,
            "total_ot_before": format_hh_mm(total_ot_before),
            "total_ot_after": format_hh_mm(total_ot_after)
        })
    conn.close()

    return render_template(
        "hr/ot_summary_step3.html",
        users_data=users_data,
        year=current_year,
        month=current_month
    )


### -------------------------------------------
### Leave Request, Edit & Approval: จัดการวันลา
### -------------------------------------------
# Leave Request: พนักงานยื่นใบลา
@app.route('/leave_request', methods=['GET','POST'])
@role_required('EMPLOYEE','HR','MANAGER', 'SECRETARY')
def leave_request():
    success_message = None
    error_message = None

    user_id = session['user_id']
    nickname = session.get('nickname')
    first_name = session.get('first_name')
    current_subcat = session.get('sub_category_id')

    if request.method == 'POST':
        leave_type = request.form.get('leave_type', '')
        start_date_str = request.form.get('start_date', '')
        end_date_str   = request.form.get('end_date', '')
        reason = request.form.get('reason', '')

        # ตรวจสอบวันที่ (start <= end)
        try:
            start_dt = datetime.strptime(start_date_str, '%Y-%m-%d')
            end_dt   = datetime.strptime(end_date_str, '%Y-%m-%d')
        except Exception as e:
            error_message = "รูปแบบวันที่ไม่ถูกต้อง"
            return render_template('leave/leave_request.html', error_message=error_message)

        if start_dt > end_dt:
            error_message = "วันสิ้นสุดต้องไม่น้อยกว่าวันเริ่มต้น"
            return render_template('leave/leave_request.html', error_message=error_message)

        # ตรวจสอบว่าช่วงวันที่ซ้อนกับใบลาเดิมหรือไม่
        overlap = check_leave_overlap(user_id, start_date_str, end_date_str)
        if overlap:
            error_message = f"ช่วงวันลาที่ขอ ทับซ้อนกับคำขอลาเดิม: {overlap}"
            return render_template('leave/leave_request.html', error_message=error_message)

        # คำนวณจำนวนวันลา
        days_requested = (end_dt - start_dt).days + 1

        # ตรวจเงื่อนไข “ลาเทศกาล” ตาม festival_option
        month_start = start_dt.month
        if leave_type == 'ลาเทศกาล':
            conn = get_db_connection()
            row_fest = conn.execute("""
                SELECT festival_option
                FROM users
                WHERE user_id = ?
            """, (user_id,)).fetchone()
            fest_opt = row_fest['festival_option'] if row_fest else 1
            conn.close()
            # ตัวอย่าง policy: option2 ไม่อนุญาตลาเทศกาลในเดือน 1,4,12
            if fest_opt == 2 and month_start in [1, 4, 12]:
                error_message = f"ไม่สามารถลาเทศกาลในเดือน {month_start} ได้ (option2)"
                return render_template('leave/leave_request.html', error_message=error_message)

        # ตรวจสอบสิทธิ์ลา (leftover on-the-fly)
        req_year = start_dt.year
        detail = get_on_the_fly_leftover_detail(user_id, leave_type, req_year)
        leftover_total = detail['leftover_total']

        if (days_requested > leftover_total) and leave_type in [
            'ลาพักร้อน', 'ลากิจ', 'ลาป่วย', 'ลางานศพ (ไม่หักเงิน)', 'ลาเทศกาล'
        ]:
            error_message = f"สิทธิ์ {leave_type} คงเหลือทั้งหมด {leftover_total} วัน (ขอ {days_requested})"
            return render_template('leave/leave_request.html', error_message=error_message)

        # แจ้งเตือนเพิ่มเติมสำหรับลาป่วย/งานศพ
        if leave_type == 'ลาป่วย' and days_requested > 1:
            success_message = "กรุณาส่งใบรับรองแพทย์ประกอบคำขอลานี้"
        elif leave_type == 'ลางานศพ (ไม่หักเงิน)':
            success_message = "ลางานศพ (ไม่หักเงิน) ใช้ได้เฉพาะพ่อแม่ลูกสามีภรรยา"

        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # กำหนดสถานะใบลา
        if  current_subcat in (2, 4, 5, 6, 7):
            status = 'pending_final'
        elif current_subcat in (11, 12, 17):
            status = 'pending_hr'
        elif current_subcat in (3, 16):
            status = 'pending_doctor'
        else:
            status = 'pending'
        
        # บันทึกใบลาในฐานข้อมูล
        conn = get_db_connection()
        conn.execute("""
            INSERT INTO leave_requests (user_id, leave_type, start_date, end_date, reason, status, days_requested, created_at)
            VALUES (?,?,?,?,?,?,?,?)
        """, (user_id, leave_type, start_date_str, end_date_str, reason, status, days_requested, now_str))
        conn.commit()
        conn.close()

        add_notification_for_roles(['HR', 'MANAGER'], f"{nickname} -- {first_name} ยื่นใบลา {days_requested} วัน")
        success_message = success_message or f"บันทึก {leave_type} : {days_requested} วัน เรียบร้อย"
        return render_template('leave/leave_request.html', success_message=success_message)
    else:
        # GET: Render form โดยดึง festival_option
        conn = get_db_connection()
        fest_row = conn.execute("""
            SELECT festival_option
            FROM users
            WHERE user_id = ?
        """, (user_id,)).fetchone()
        fest_opt = fest_row['festival_option'] if fest_row else 1
        conn.close()

        return render_template('leave/leave_request.html',
                               success_message=success_message,
                               error_message=error_message,
                               festival_opt=fest_opt)

# My Leave Request: แสดงรายการคำขอลาของพนักงาน
@app.route('/my_leave_requests', methods=['GET'])
@role_required('EMPLOYEE', 'HR', 'MANAGER', 'SECRETARY')
def my_leave_requests():
    user_id = session['user_id']
    current_year = datetime.now().year

    conn = get_db_connection()
    # ดึงเฉพาะคำขอลาที่เกิดขึ้นในปีปัจจุบัน (โดยใช้ strftime เพื่อกรองปีจาก start_date)
    leave_requests = conn.execute("""
        SELECT leave_id, leave_type, start_date, end_date, reason, status, days_requested
        FROM leave_requests
        WHERE user_id=? AND strftime('%Y', start_date)=?
        ORDER BY start_date DESC
    """, (user_id, str(current_year))).fetchall()
    conn.close()

    return render_template('leave/my_leave_requests.html', leave_requests=leave_requests, current_year=current_year)

# Edit Leave Request: พนักงานแก้ไขคำขอลา
@app.route('/edit_leave_request/<int:leave_id>', methods=['GET', 'POST'])
@role_required('EMPLOYEE', 'HR', 'MANAGER', 'SECRETARY')
def edit_leave_request(leave_id):
    user_id = session['user_id']
    
    conn = get_db_connection()
    leave = conn.execute("""
        SELECT leave_id, leave_type, start_date, end_date, reason, status
        FROM leave_requests
        WHERE leave_id=? AND user_id=?
    """, (leave_id, user_id)).fetchone()

    if not leave:
        conn.close()
        return "ไม่พบคำขอลานี้"

    # อนุญาตให้แก้ไขได้เฉพาะใบลาที่ยังอยู่ในสถานะ pending (หรือ pending อะไรก็ตาม)
    if not leave['status'].startswith('pending'):
        conn.close()
        return "ไม่สามารถแก้ไขคำขอลาได้"

    if request.method == 'POST':
        # รับข้อมูลจาก form พร้อมลบช่องว่างที่ไม่จำเป็น
        leave_type = request.form.get('leave_type', '').strip()
        start_date = request.form.get('start_date', '').strip()  # ควรอยู่ในรูปแบบ YYYY-MM-DD
        end_date   = request.form.get('end_date', '').strip()    # ควรอยู่ในรูปแบบ YYYY-MM-DD
        reason     = request.form.get('reason', '').strip()

        # ตรวจสอบข้อมูลว่ามีครบถ้วนหรือไม่
        if not (leave_type and start_date and end_date and reason):
            flash("กรุณากรอกข้อมูลให้ครบถ้วน", "danger")
            conn.close()
            return render_template('leave/edit_leave_request.html', leave=leave)

        # ตรวจสอบรูปแบบวันที่ (ควรเป็น YYYY-MM-DD)
        try:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            end_dt   = datetime.strptime(end_date, '%Y-%m-%d')
        except Exception as e:
            flash("รูปแบบวันที่ไม่ถูกต้อง (ควรเป็น YYYY-MM-DD)", "danger")
            conn.close()
            return render_template('leave/edit_leave_request.html', leave=leave)

        # ตรวจสอบว่าหาก start_date > end_date ให้แจ้งเตือน
        if start_dt > end_dt:
            flash("วันสิ้นสุดต้องไม่น้อยกว่าวันเริ่มต้น", "danger")
            conn.close()
            return render_template('leave/edit_leave_request.html', leave=leave)

        # (หากต้องการตรวจสอบ overlap ของช่วงวันลาเพิ่มเติมก็สามารถเรียกใช้ check_leave_overlap() ที่มีอยู่)
        # ปรับปรุงข้อมูลในฐานข้อมูลด้วยคำสั่ง UPDATE
        conn.execute("""
            UPDATE leave_requests
            SET leave_type=?, start_date=?, end_date=?, reason=?
            WHERE leave_id=?
        """, (leave_type, start_date, end_date, reason, leave_id))
        conn.commit()
        conn.close()
        return redirect('/my_leave_requests')

    conn.close()
    # ในกรณี GET, ส่งข้อมูลใบลาที่ดึงมาจาก DB ไปให้ template
    return render_template('leave/edit_leave_request.html', leave=leave)

# Confirm Cancel Leave Request: พนักงานยืนยัน ยกเลิกการลา
@app.route('/cancel_leave_request/<int:leave_id>', methods=['POST'])
@role_required('EMPLOYEE', 'HR', 'MANAGER', 'SECRETARY')
def cancel_leave_request(leave_id):
    user_id = session['user_id']

    conn = get_db_connection()
    leave = conn.execute("""
        SELECT leave_id, leave_type, start_date, end_date, reason, status
        FROM leave_requests
        WHERE leave_id=? AND user_id=?
    """, (leave_id, user_id)).fetchone()

    if not leave:
        conn.close()
        flash("ไม่พบคำขอลานี้ หรือคุณไม่มีสิทธิ์ยกเลิกคำขอนี้", "danger")
        return redirect('/my_leave_requests')

    if not leave['status'].startswith('pending'):
        conn.close()
        flash("ไม่สามารถยกเลิกคำขอลาที่อนุมัติแล้วได้", "danger")
        return redirect('/my_leave_requests')

    # อัปเดตสถานะเป็น "cancel"
    conn.execute("""
        UPDATE leave_requests
        SET status = 'cancel'
        WHERE leave_id = ?
    """, (leave_id,))
    conn.commit()
    conn.close()

    flash("ยกเลิกคำขอลาเรียบร้อย", "success")
    return redirect('/my_leave_requests')

# Leave Approval List: แสดงรายการคำขอลาที่รออนุมัติ
@app.route('/leave_approval_list')
@role_required('HR', 'MANAGER')
def leave_approval_list():
    current_role = session.get('role')
    current_subcat = session.get('sub_category_id')
    conn = get_db_connection()
    
    if current_subcat == 2:
        # HR: แสดงใบลาในสถานะ pending_hr
        query = """
            SELECT lr.leave_id, lr.user_id, lr.leave_type, lr.start_date, lr.end_date, lr.status, lr.days_requested,
                   u.nickname || ' - ' || u.first_name AS full_name
            FROM leave_requests lr
            JOIN users u ON lr.user_id = u.user_id
            WHERE lr.status == 'pending_hr'
            ORDER BY lr.leave_id DESC
        """
        params = []
    elif current_role.startswith("MANAGER"):
        if str(current_subcat) == "3":
            # Manager (General): แสดงเฉพาะใบลาที่อยู่ในสถานะ pending_final
            query = """
                SELECT lr.leave_id, lr.user_id, lr.leave_type, lr.start_date, lr.end_date, lr.status, lr.days_requested,
                       u.nickname || ' - ' || u.first_name AS full_name
                FROM leave_requests lr
                JOIN users u ON lr.user_id = u.user_id
                WHERE lr.status = 'pending_final'
                ORDER BY lr.leave_id DESC
            """
            params = []
        else:
            # Manager (child): ดึงใบลาที่อยู่ในสถานะ pending เฉพาะใบลาของ employee ที่อยู่ใน subcategories ที่ได้รับอนุญาต
            allowed_employee_subcats = get_allowed_employee_subcategories(current_subcat)
            if not allowed_employee_subcats:
                conn.close()
                return render_template('leave/leave_approval_list.html', leave_requests=[])
            placeholders = ",".join("?" for _ in allowed_employee_subcats)
            query = f"""
                SELECT lr.leave_id, lr.user_id, lr.leave_type, lr.start_date, lr.end_date, lr.status, lr.days_requested,
                       u.first_name || ' ' || u.last_name AS full_name
                FROM leave_requests lr
                JOIN users u ON lr.user_id = u.user_id
                WHERE lr.status = 'pending' AND u.sub_category_id IN ({placeholders})
                ORDER BY lr.leave_id DESC
            """
            params = tuple(allowed_employee_subcats)
    else:
        query = "SELECT * FROM leave_requests WHERE 1=0"
        params = []
    
    rows = conn.execute(query, params).fetchall()
    conn.close()
    
    return render_template('leave/leave_approval_list.html', leave_requests=rows, current_role=current_role)

# Leave Approve: จัดการคำขอลา เมื่อ HR หรือ Manager กดปุ่ม 'approve', 'reject', 'conditional'
@app.route('/leave_approve', methods=['POST'])
@role_required('HR','MANAGER')
def leave_approve():
    """
    ฟังก์ชันอนุมัติใบลา:
      - HR และ Manager(child) => อนุมัติขั้นแรก → เปลี่ยนสถานะเป็น 'pending_final'
      - Manager(general) subcat=3 => final approve
    """
    leave_id = request.form['leave_id']
    leave_start = request.form['start_date']
    action = request.form['action']  # 'approve', 'reject', 'conditional'
    new_leave_type = request.form.get('new_leave_type', None)
    hr_comment = request.form.get('hr_comment', '')

    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    current_role = session.get('role')
    current_subcat = session.get('sub_category_id')
    current_manager_id = session.get('user_id')
    
    conn = get_db_connection()
    try:
        # 1) โหลดข้อมูลใบลา
        leave_req = conn.execute("""
            SELECT user_id, leave_type, days_requested, start_date, status
            FROM leave_requests
            WHERE leave_id = ?
        """, (leave_id,)).fetchone()
        if not leave_req:
            flash("ไม่พบคำขอลา", "warning")
            conn.close()
            return redirect(url_for('leave_approval_list'))
        
        employee_id = leave_req['user_id']
        old_leave_type = leave_req['leave_type']
        days_requested = leave_req['days_requested']
        old_status = leave_req['status']
        start_date_str = leave_req['start_date']
        req_year = int(start_date_str[:4])
        
        # หากมี new_leave_type => เปลี่ยนประเภทลา
        final_leave_type = new_leave_type if new_leave_type else old_leave_type
        
        # ถ้า current_role=='HR': => อนุญาตให้ทำงานเหมือน manager(child)

        # แยกเป็น 2 ส่วน: (1) HR หรือ Manager(child) subcat != 3, (2) Manager(general) subcat=3
        if (current_role == 'HR' or current_role.startswith("MANAGER")) and str(current_subcat) != "3":
            # ----- ส่วน HR กับ Manager(child) -----
            # (1) ถ้า action='approve' หรือ 'conditional' => เปลี่ยนสถานะเป็น 'pending_final'
            if action in ['approve','conditional']:
                # เช็ค leftover on-the-fly (ถ้าใบลาสถานะยังเป็น pending, กำลังจะ up เป็น 'pending_final')
                if old_status in ('pending', 'pending_hr'):
                    # leftover check
                    if final_leave_type in ['ลาพักร้อน','ลากิจ','ลาป่วย','ลางานศพ (ไม่หักเงิน)','ลาเทศกาล']:
                        leftover = get_on_the_fly_leftover_exclude(employee_id, final_leave_type, req_year, exclude_leave_id=leave_id)
                        if days_requested > leftover:
                            # Auto reject
                            flash(f"สิทธิ์ {final_leave_type} ไม่เพียงพอ (เหลือ {leftover}, ขอ {days_requested}) => auto-reject", "danger")
                            conn.execute("""
                                UPDATE leave_requests
                                SET status='rejected',
                                    hr_comment=?,
                                    updated_at=?
                                WHERE leave_id=?
                            """, (f"{hr_comment} (auto reject leftover not enough)", now_str, leave_id))
                            conn.commit()
                            conn.close()
                            return redirect(url_for('leave_approval_list'))
                
                # ดึง final manager(general) user_id
                employee_data = conn.execute("SELECT sub_category_id FROM users WHERE user_id=?", (employee_id,)).fetchone()
                if not employee_data:
                    flash("ไม่พบข้อมูล employee subcat", "warning")
                    conn.close()
                    return redirect(url_for('leave_approval_list'))
                employee_subcat = employee_data['sub_category_id']
                final_manager_id = get_parent_manager_for_employee(employee_subcat)  # manager(general)
                if not final_manager_id:
                    flash("ไม่พบ Manager General สำหรับส่งต่อใบลา", "warning")
                    conn.close()
                    return redirect(url_for('leave_approval_list'))
                
                new_status = 'pending_final'
                
                # update DB
                conn.execute("""
                    UPDATE leave_requests
                    SET status=?,
                        leave_type=?,
                        hr_comment=?,
                        updated_at=?,
                        first_approver_id=?,
                        final_approver_id=?
                    WHERE leave_id=?
                """, (new_status, final_leave_type, hr_comment, now_str, current_manager_id, final_manager_id, leave_id))
            
            elif action == 'reject':
                new_status = 'rejected'
                conn.execute("""
                    UPDATE leave_requests
                    SET status=?,
                        hr_comment=?,
                        updated_at=?
                    WHERE leave_id=?
                """, (new_status, hr_comment, now_str, leave_id))
            else:
                flash("ไม่รู้จัก action สำหรับ HR/Manager(child)", "danger")
                conn.close()
                return redirect(url_for('leave_approval_list'))
        
        elif (current_role.startswith("MANAGER") or current_role=='HR') and str(current_subcat) == "3":
            # ----- ส่วน Manager(general) subcat=3 => final approve -----
            if old_status != 'pending_final':
                flash("ใบลานี้ยังไม่ถึงขั้นตอนให้ ผจก. อนุมัติ", "warning")
                conn.close()
                return redirect(url_for('leave_approval_list'))
            
            if action in ['approve','conditional']:
                new_status = 'approved'
                if action == 'conditional' and new_leave_type:
                    conn.execute("""
                        UPDATE leave_requests
                        SET status=?,
                            leave_type=?,
                            hr_comment=?,
                            updated_at=?,
                            first_approver_id=?,
                            final_approver_id=?
                        WHERE leave_id=?
                    """, (new_status, final_leave_type, hr_comment, now_str, current_manager_id, current_manager_id, leave_id))
                else:
                    conn.execute("""
                        UPDATE leave_requests
                        SET status=?,
                            hr_comment=?,
                            updated_at=?
                        WHERE leave_id=?
                    """, (new_status, hr_comment, now_str, leave_id))
            elif action == 'reject':
                new_status = 'rejected'
                conn.execute("""
                    UPDATE leave_requests
                    SET status=?,
                        hr_comment=?,
                        updated_at=?
                    WHERE leave_id=?
                """, (new_status, hr_comment, now_str, leave_id))
            else:
                flash("ไม่รู้จัก action สำหรับ Manager(general)", "danger")
                conn.close()
                return redirect(url_for('leave_approval_list'))
        
        else:
            flash("ไม่อนุญาตให้ดำเนินการ (role/subcat ไม่เข้าเงื่อนไข)", "warning")
            conn.close()
            return redirect(url_for('leave_approval_list'))

        # แจ้งเตือน employee ทราบ
        if new_status == 'approved':
            message = f"ใบลาวันที่ {leave_start} ได้รับการอนุมัติ"
        elif new_status == 'rejected':
            message = f"ใบลาวันที่ {leave_start} ถูกปฏิเสธ: {hr_comment}"
        else:
            message = f"ใบลาวันที่ {leave_start} ถูกปรับเป็น: {final_leave_type}"

        add_notification_with_connection(conn, employee_id, message)

        conn.commit()
        flash("ดำเนินการใบลาเรียบร้อย", "success")
    except Exception as e:
        conn.rollback()
        flash(f"Database error: {e}", "danger")
    finally:
        conn.close()
    
    return redirect(url_for('leave_approval_list'))

# Leave Quota: HR สามารถจัดการสิทธิ์วันลาสำหรับพนักงาน
@app.route('/hr/leave_quota', methods=['GET','POST'])
@role_required('HR')
def leave_quota():
    """
    จัดการ “ยกมาจากปีก่อน” (carry_forward) ของลาพักร้อน (Vacation) 
    สำหรับพนักงานทุกคนในหน้าเดียว
    - GET => แสดงตาราง “ปัจจุบัน” + “แก้ไข”
    - POST => upsert ลง leave_quota (carry_forward=? where leave_type='ลาพักร้อน')
    """
    import datetime
    current_year = datetime.datetime.now().year

    conn = get_db_connection()

    if request.method == 'POST':
        user_ids = request.form.getlist('user_id')
        updated_count = 0

        for uid in user_ids:
            field_name = f"carry_forward_new_{uid}"
            cf_value_str = request.form.get(field_name, '0')
            try:
                cf_value = int(cf_value_str)
            except:
                cf_value = 0

            # upsert to leave_quota => leave_type='ลาพักร้อน'
            year = current_year

            row = conn.execute("""
                SELECT quota_id
                FROM leave_quota
                WHERE user_id=? AND leave_type='ลาพักร้อน' AND year=?
            """, (uid, year)).fetchone()

            if row:
                conn.execute("""
                    UPDATE leave_quota
                    SET carry_forward=?
                    WHERE quota_id=?
                """, (cf_value, row['quota_id']))
            else:
                conn.execute("""
                    INSERT INTO leave_quota (user_id, leave_type, carry_forward, total_days, year)
                    VALUES (?, 'ลาพักร้อน', ?, 0, ?)
                """, (uid, cf_value, year))

            updated_count += 1

        conn.commit()
        conn.close()
        flash(f"บันทึก carry_forward สำหรับ {updated_count} record เรียบร้อย", "success")
        return redirect(url_for('leave_quota'))

    else:
        # GET
        users = conn.execute("""
            SELECT user_id, first_name, last_name, nickname, start_date
            FROM users
            WHERE role in ('HR', 'EMPLOYEE', 'MANAGER', 'SECRETARY')
            ORDER BY start_date
        """).fetchall()

        # load carry_forward from DB
        year = current_year
        crows = conn.execute("""
            SELECT user_id, carry_forward
            FROM leave_quota
            WHERE leave_type='ลาพักร้อน' AND year=?
        """, (year,)).fetchall()
        conn.close()

        carry_forward_map = {}
        for c in crows:
            carry_forward_map[c['user_id']] = c['carry_forward']

        return render_template('hr/leave_quota.html',
                               users=users,
                               carry_forward_map=carry_forward_map,
                               year=year)

# Leftver Total
@app.route('/api/get_leftover_total', methods=['POST'])
def api_get_leftover_total():
    data = request.json
    user_id = session.get('user_id')
    leave_type = data.get('leave_type')
    start_date_str = data.get('start_date')
    # คำนวณ year จาก start_date_str
    if not start_date_str:
        return jsonify({"leftover_total": 0})

    req_year = int(start_date_str.split("-")[0])

    # เรียกฟังก์ชัน
    detail = get_on_the_fly_leftover_detail(user_id, leave_type, req_year)
    leftover_total = detail['leftover_total']
    return jsonify({"leftover_total": leftover_total})

# Leave Quota List: HR ดูสิทธิ์วันลาพนักงานทุกคน
@app.route('/hr/leave_quota_list')
@role_required('HR')
def hr_leave_quota_list():
    """
    แสดง "สรุปสิทธิ์วันลาของพนักงาน (HR)" ในรูปแบบ on-the-fly:
      - ลาพักร้อน: partial mid-year + carry_forward ที่ HR กรอก
      - ลากิจ (3 วันถ้าผ่านโปร), ลาป่วย (30), ลางานศพ (ไม่หักเงิน) (3), ลาเทศกาล (13/4/1)
      - leftover_present = (carry_forward + partialVacation) - used_past
        leftover_total = leftover_present - used_future
      - ส่วน leave_types extra => quota=0
      - แสดงปี (reverse) -> user -> 2 ตาราง
    """
    from datetime import datetime, date

    # 1) ประเภทลา
    LEAVE_TYPES_QUOTA = [
        'ลาพักร้อน',
        'ลากิจ',
        'ลาป่วย',
        'ลางานศพ (ไม่หักเงิน)',
        'ลาเทศกาล'
    ]
    LEAVE_TYPES_EXTRA = [
        'ลาหักเงิน',
        'ลาฉุกเฉิน',
        'ลางานศพ (หักเงิน)',
        'ลาอื่นๆ'
    ]
    ALL_TYPES = LEAVE_TYPES_QUOTA + LEAVE_TYPES_EXTRA

    conn = get_db_connection()

    # 2) ดึง user (non-Admin)
    user_rows = conn.execute("""
        SELECT user_id, first_name, last_name, start_date, 
               probation, festival_option, nickname
        FROM users
        WHERE role in ('HR', 'EMPLOYEE', 'MANAGER', 'SECRETARY')
        ORDER BY start_date
    """).fetchall()

    # user_info[user_id] = {...}
    user_info = {}
    for r in user_rows:
        user_info[r['user_id']] = {
            'name': f"{r['nickname']} -- {r['first_name']} {r['last_name']}",
            'start_date': r['start_date'] or '',
            'probation': r['probation'] or 1,
            'festival_option': r['festival_option'] or 1
        }

    # 3) ดึง carry_forward ของลาพักร้อน (ปีปัจจุบัน)
    current_year = date.today().year
    carry_rows = conn.execute("""
        SELECT user_id, carry_forward
        FROM leave_quota
        WHERE leave_type='ลาพักร้อน' AND year=?
    """, (current_year,)).fetchall()

    carry_map = {}
    for c in carry_rows:
        carry_map[c['user_id']] = c['carry_forward']

    # 4) ดึง leave_requests (approved)
    req_rows = conn.execute("""
        SELECT lr.user_id, lr.leave_type, lr.start_date, lr.days_requested
        FROM leave_requests lr
        JOIN users u ON lr.user_id=u.user_id
        WHERE lr.status='approved'
          AND u.role!='ADMIN'
    """).fetchall()
    conn.close()

    from collections import defaultdict
    data = defaultdict(lambda: defaultdict(lambda: {
        'used_past':0,'used_future':0,'quota':0,
        'leftover_present':0,'leftover_total':0
    }))

    today_dt = date.today()

    # 5) ใส่ used_past / used_future
    for row in req_rows:
        uid = row['user_id']
        lt = row['leave_type']
        sdt = datetime.strptime(row['start_date'],'%Y-%m-%d').date()
        yr = sdt.year

        rec = data[yr][uid].setdefault(lt, {
            'used_past':0,'used_future':0,'quota':0,
            'leftover_present':0,'leftover_total':0
        })
        if sdt <= today_dt:
            rec['used_past'] += row['days_requested']
        else:
            rec['used_future'] += row['days_requested']

    # สร้าง set ของปีทั้งหมด
    years_set = set(data.keys())
    years_set.add(today_dt.year)

    # 6) ฟังก์ชัน Partial Vacation
    def calc_vacation_partial_midyear(start_date_str, target_year):
        if not start_date_str:
            return 0
        from datetime import datetime
        start_dt = datetime.strptime(start_date_str, '%Y-%m-%d')
        jan1 = datetime(target_year,1,1)
        if start_dt > jan1:
            return 0
        one_year_anniv = start_dt.replace(year=start_dt.year+1)
        if one_year_anniv < jan1:
            return 7
        elif one_year_anniv.year>target_year:
            return 0
        else:
            m = one_year_anniv.month
            if m==1: return 7
            elif m in [2,3]: return 6
            elif m in [4,5]: return 5
            elif m in [6,7]: return 4
            elif m in [8,9]: return 3
            elif m in [10,11]: return 2
            else: return 1

    # 7) on-the-fly quota + leftover
    def get_on_the_fly_quota(lt, user_data, carry_fwd, target_year):
        """
        carry_fwd => จาก leave_quota(ลาพักร้อน) year=ปัจจุบัน
        """
        start_dt_str = user_data['start_date']
        prob = user_data['probation']
        fest_opt = user_data['festival_option']

        if lt=='ลาพักร้อน':
            partial = calc_vacation_partial_midyear(start_dt_str, target_year)
            return carry_fwd + partial  # รวม carry forward
        elif lt=='ลากิจ':
            return 3 if prob==0 else 0
        elif lt=='ลาป่วย':
            return 30
        elif lt=='ลางานศพ (ไม่หักเงิน)':
            return 3
        elif lt=='ลาเทศกาล':
            if fest_opt==2: return 4
            elif fest_opt==3: return 1
            else: return 13
        # extra => 0
        return 0

    for yr in years_set:
        for uid in user_info.keys():
            for lt in (LEAVE_TYPES_QUOTA + LEAVE_TYPES_EXTRA):
                rec = data[yr][uid].setdefault(lt, {
                    'used_past':0,'used_future':0,'quota':0,
                    'leftover_present':0,'leftover_total':0
                })
                # ตรงนี้ => ถ้าเป็นปีปัจจุบัน + ลาพักร้อน => carry_forward=carry_map.get(uid,0)
                # ถ้าคนละปี => cf=0
                # ถ้าไม่ใช่ลาพักร้อน => cf=0
                c_fwd = 0
                if lt=='ลาพักร้อน' and yr==current_year:
                    c_fwd = carry_map.get(uid,0)

                q = get_on_the_fly_quota(lt, user_info[uid], c_fwd, yr)
                rec['quota'] = q

                # leftover present
                lp = q - rec['used_past']
                if lp<0: lp=0
                rec['leftover_present'] = lp

                # leftover total
                lt_ = lp - rec['used_future']
                if lt_<0: lt_=0
                rec['leftover_total'] = lt_

    # สร้าง result => {year -> {uid -> [ ... ] } }
    from collections import defaultdict
    result = defaultdict(lambda: defaultdict(list))
    sorted_years = sorted(list(years_set), reverse=True)

    for yr in sorted_years:
        for uid in user_info.keys():
            for lt in (LEAVE_TYPES_QUOTA + LEAVE_TYPES_EXTRA):
                r = data[yr][uid][lt]
                # group => quota or extra
                group_name = 'quota' if lt in LEAVE_TYPES_QUOTA else 'extra'
                result[yr][uid].append({
                    'leave_type': lt,
                    'group': group_name,
                    # carry_forward => ถ้า year==current_year + lt=ลาพักร้อน => carry_map.get(uid,0)
                    'carry_forward': carry_map.get(uid,0) if lt=='ลาพักร้อน' and yr==current_year else 0,
                    'total_days': r['quota'],
                    'used_past': r['used_past'],
                    'used_future': r['used_future'],
                    'leftover_present': r['leftover_present'],
                    'leftover_total': r['leftover_total']
                })

    # สร้าง user_dict => {uid: "First Last"}
    user_dict = {}
    for uid, info in user_info.items():
        user_dict[uid] = info['name']

    return render_template('hr/leave_quota_list.html',
                           data=result,
                           user_dict=user_dict,
                           LEAVE_TYPES_QUOTA=LEAVE_TYPES_QUOTA,
                           LEAVE_TYPES_EXTRA=LEAVE_TYPES_EXTRA)

# My Leave Quota: พนักงานเรียกดูสิทธิ์วันลาคงเหลือของตัวเอง
@app.route('/my_leave_quota', methods=['GET'])
@role_required('EMPLOYEE','HR','MANAGER', 'SECRETARY')
def my_leave_quota():
    """
    แสดงสิทธิ์วันลาของพนักงาน (on-the-fly + carry_forward สำหรับลาพักร้อน)
    แบ่ง 2 กลุ่ม: LEAVE_TYPES_QUOTA vs LEAVE_TYPES_EXTRA
    leftover_present = quota - used_past
    leftover_total = leftover_present - used_future

    โค้ดนี้:
    - ลาพักร้อน => carry_forward + partial mid-year
    - ลากิจ => 3 วัน ถ้าผ่านโปร
    - ลาป่วย => 30
    - ลางานศพ (ไม่หักเงิน) => 3
    - ลาเทศกาล => 13/4/1 (festival_option)
    - ลาอื่นๆ => 0
    """
    from datetime import datetime, date
    today = date.today()
    current_year = today.year

    # ประเภทลา 2 กลุ่ม
    LEAVE_TYPES_QUOTA = [
        'ลาพักร้อน',
        'ลากิจ',
        'ลาป่วย',
        'ลางานศพ (ไม่หักเงิน)',
        'ลาเทศกาล'
    ]
    LEAVE_TYPES_EXTRA = [
        'ลาหักเงิน',
        'ลาฉุกเฉิน',
        'ลางานศพ (หักเงิน)',
        'ลาอื่นๆ'
    ]
    ALL_TYPES = LEAVE_TYPES_QUOTA + LEAVE_TYPES_EXTRA

    user_id = session.get('user_id')
    if not user_id:
        flash("กรุณา Login ก่อน", "danger")
        return redirect(url_for('index'))

    conn = get_db_connection()

    # 1) ดึงข้อมูล user => start_date, probation, festival_option
    user_row = conn.execute("""
        SELECT start_date, probation, festival_option
        FROM users
        WHERE user_id=?
    """, (user_id,)).fetchone()
    if not user_row:
        conn.close()
        return "ไม่พบข้อมูลผู้ใช้"

    start_date_str = user_row['start_date'] or ''
    probation_val = user_row['probation'] or 1
    festival_opt = user_row['festival_option'] or 1

    # 2) ดึง carry_forward ของลาพักร้อน (เฉพาะ year=ปัจจุบัน)
    c_row = conn.execute("""
        SELECT carry_forward
        FROM leave_quota
        WHERE user_id=? AND leave_type='ลาพักร้อน' AND year=?
    """, (user_id, current_year)).fetchone()

    carry_forward_vac = c_row['carry_forward'] if c_row else 0

    # 3) ดึงใบลา (approved) => used_past, used_future
    req_rows = conn.execute("""
        SELECT leave_type, start_date, days_requested
        FROM leave_requests
        WHERE user_id=? AND status='approved'
        ORDER BY start_date
    """, (user_id,)).fetchall()
    conn.close()

    from collections import defaultdict
    data = defaultdict(lambda: {})
    today_dt = datetime.strptime(today.strftime('%Y-%m-%d'), '%Y-%m-%d')

    # เก็บปีทั้งหมดจากใบลา + ปีปัจจุบัน
    years_set = set()
    for r in req_rows:
        sdt = datetime.strptime(r['start_date'],'%Y-%m-%d')
        years_set.add(sdt.year)
    years_set.add(current_year)

    # สรุป used
    for r in req_rows:
        lt = r['leave_type']
        sdt = datetime.strptime(r['start_date'],'%Y-%m-%d')
        y = sdt.year
        rec = data[y].setdefault(lt, {
            'used_past':0,'used_future':0,'quota':0,
            'leftover_present':0,'leftover_total':0
        })
        if sdt <= today_dt:
            rec['used_past'] += r['days_requested']
        else:
            rec['used_future'] += r['days_requested']

    # ฟังก์ชัน partial mid-year vacation
    def calc_vacation_partial_midyear(start_date_str, target_year):
        if not start_date_str:
            return 0
        sdt = datetime.strptime(start_date_str,'%Y-%m-%d')
        jan1 = datetime(target_year,1,1)
        if sdt>jan1:
            return 0
        one_year_anniv = sdt.replace(year=sdt.year+1)
        if one_year_anniv<jan1:
            return 7
        elif one_year_anniv.year>target_year:
            return 0
        else:
            m=one_year_anniv.month
            if m==1:return 7
            elif m in [2,3]:return 6
            elif m in [4,5]:return 5
            elif m in [6,7]:return 4
            elif m in [8,9]:return 3
            elif m in [10,11]:return 2
            else:return 1

    def get_quota_on_the_fly(lt, target_year):
        if lt=='ลาพักร้อน':
            partial = calc_vacation_partial_midyear(start_date_str, target_year)
            # ถ้าเป็นปีปัจจุบัน => บวก carry_forward_vac
            if target_year==current_year:
                return carry_forward_vac + partial
            else:
                # ปีอื่น => ไม่มี carry
                return partial
        elif lt=='ลากิจ':
            return 3 if probation_val==0 else 0
        elif lt=='ลาป่วย':
            return 30
        elif lt=='ลางานศพ (ไม่หักเงิน)':
            return 3
        elif lt=='ลาเทศกาล':
            if festival_opt==2: return 4
            elif festival_opt==3: return 1
            else: return 13
        return 0  # extra =>0

    # on-the-fly leftover
    for y in years_set:
        for lt in ALL_TYPES:
            rec = data[y].setdefault(lt, {
                'used_past':0,'used_future':0,'quota':0,
                'leftover_present':0,'leftover_total':0
            })
            q = get_quota_on_the_fly(lt, y)
            rec['quota'] = q
            # leftover present
            lp = q - rec['used_past']
            if lp<0: lp=0
            rec['leftover_present'] = lp
            # leftover total
            lt_ = lp - rec['used_future']
            if lt_<0: lt_=0
            rec['leftover_total'] = lt_

    # ส่งไป Template
    LEAVE_TYPES_QUOTA = [
        'ลาพักร้อน','ลากิจ','ลาป่วย','ลางานศพ (ไม่หักเงิน)','ลาเทศกาล'
    ]
    LEAVE_TYPES_EXTRA = [
        'ลาหักเงิน','ลาฉุกเฉิน','ลางานศพ (หักเงิน)','ลาอื่นๆ'
    ]

    quota_by_year = defaultdict(list)
    sorted_years = sorted(list(years_set), reverse=True)
    for y in sorted_years:
        for lt in (LEAVE_TYPES_QUOTA+LEAVE_TYPES_EXTRA):
            r = data[y][lt]
            group_name = 'quota' if lt in LEAVE_TYPES_QUOTA else 'extra'
            quota_by_year[y].append({
                'leave_type': lt,
                'group': group_name,
                'carry_forward': carry_forward_vac if (lt=='ลาพักร้อน' and y==current_year) else 0,
                'total_days': r['quota'],
                'used_past': r['used_past'],
                'used_future': r['used_future'],
                'leftover_present': r['leftover_present'],
                'leftover_total': r['leftover_total']
            })

    return render_template('leave/my_leave_quota.html',
                           quota_by_year=quota_by_year,
                           LEAVE_TYPES_QUOTA=LEAVE_TYPES_QUOTA,
                           LEAVE_TYPES_EXTRA=LEAVE_TYPES_EXTRA)

# Auto Generate Leave Quota
@app.route('/hr/auto_generate_quota/<int:year>', methods=['POST'])
@role_required('HR')
def auto_generate_quota(year):
    """
    HR เรียกเพื่อตั้งค่า quota ปีใหม่ให้พนักงานทุกคน (หรือ role in ('HR', 'EMPLOYEE', 'MANAGER', 'SECRETARY'))
    - ลาพักร้อน, ลากิจ, ลาป่วย, ลางานศพ(ไม่หักเงิน), ลาเทศกาล
    - คำนวณ carry_forward จาก leftover_total ปีก่อน
    """
    conn = get_db_connection()
    users = conn.execute("""
        SELECT user_id, start_date, probation, festival_option
        FROM users
        WHERE role in ('HR', 'EMPLOYEE', 'MANAGER', 'SECRETARY')
    """).fetchall()

    # 1) load leftover from year-1
    leftover_data = load_leftover_of_previous_year(conn, year-1)

    # 2) วน user => generate each leave type
    created_count = 0
    for u in users:
        uid = u['user_id']
        sdate = u['start_date']
        prob = u['probation']
        fest_option = u['festival_option'] or 1

        # 2.1 carry_forward = leftover_data[ (uid, 'ลาพักร้อน'), ... ] if any
        #    = leftover_total
        #    (แล้วแต่ policy ว่าลากิจ=0, ลาป่วย=0, funeral=0, etc.)
        carry_vac = leftover_data.get((uid, 'ลาพักร้อน'), 0)
        carry_per = 0  # ลากิจ=0
        carry_sick = 0
        carry_funeral = 0
        carry_festival = 0

        # 2.2 คำนวณ total_days
        vac_days = calculate_vacation_annual(sdate, year)
        per_days = calculate_personal_annual(sdate, prob, year)
        sick_days = 30
        funeral_days = 3
        festival_days = calculate_festival_days(fest_option)

        # 2.3 insert/update quota
        # (สมมติ replace old or insert new)
        upsert_quota(conn, uid, 'ลาพักร้อน', carry_vac, vac_days, year)
        upsert_quota(conn, uid, 'ลากิจ', carry_per, per_days, year)
        upsert_quota(conn, uid, 'ลาป่วย', carry_sick, sick_days, year)
        upsert_quota(conn, uid, 'ลางานศพ (ไม่หักเงิน)', carry_funeral, funeral_days, year)
        upsert_quota(conn, uid, 'ลาเทศกาล', carry_festival, festival_days, year)

        created_count += 5

    conn.commit()
    conn.close()

    flash(f"สร้าง/อัปเดต quota ปี {year} ให้ {len(users)} คน, ทั้งหมด {created_count} record", "success")
    return redirect(url_for('hr_dashboard'))

# CRON อัพเดทสิทธิ์ลาพักร้อน ของพนักงานที่อายุงานพึ่งครบ 1ปี
@app.route('/hr/cron_check_vacation_partial', methods=['GET'])
@role_required('HR')
def route_cron_check_vacation_partial():
    """
    เมื่อ HR กดลิงก์/ปุ่ม -> ระบบจะเรียก cron_check_vacation_partial 
    + บันทึกวันเวลาล่าสุดลง system_config
    """
    conn = get_db_connection()

    from datetime import datetime
    # เรียกฟังก์ชัน cron_check_vacation_partial() (หรือฟังก์ชันชื่ออื่น)
    count_updated, updated_users = cron_check_vacation_partial(conn)  # year=None => ใช้ year ปัจจุบัน
    # เสร็จแล้วบันทึกเวลา
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # update/insert config
    row = conn.execute("""
        SELECT config_key FROM system_config 
        WHERE config_key='cron_check_vacation_partial_update'
    """).fetchone()
    if row:
        conn.execute("""
            UPDATE system_config 
            SET config_value=?
            WHERE config_key='cron_check_vacation_partial_update'
        """, (now_str,))
    else:
        conn.execute("""
            INSERT INTO system_config (config_key, config_value)
            VALUES ('cron_check_vacation_partial_update', ?)
        """, (now_str,))
    conn.commit()
    conn.close()

    flash(f"อัปเดตพักร้อนกลางปีให้ {count_updated} คน (UID={updated_users}), เวลา {now_str}", "success")
    return redirect(url_for('hr_dashboard'))

# Festival Option พนักงานเลือก option ลาเทศกาล
@app.route('/festival_option', methods=['GET','POST'])
@role_required('EMPLOYEE','HR','MANAGER', 'SECRETARY')
def festival_option():
    """
    พนักงานเลือก option ลาเทศกาล (1=13,2=4,3=1)
    -> บันทึกลง festival_option_requests (status='pending')
    -> รอ HR อนุมัติ
    ตรวจสอบว่ามีคำขอ pending อยู่หรือไม่ เพื่อไม่ให้ส่งคำขอซ้ำ
    """
    user_id = session['user_id']

    if request.method == 'POST':
        conn = get_db_connection()
        # ตรวจสอบว่ามีคำขอ pending อยู่หรือไม่
        pending = conn.execute("""
            SELECT request_id 
            FROM festival_option_requests 
            WHERE user_id = ? AND status = 'pending'
        """, (user_id,)).fetchone()
        if pending:
            conn.close()
            flash("มีคำขอเปลี่ยน Option ลาเทศกาลค้างอยู่ กรุณารอ HR อนุมัติ", "warning")
            return redirect(url_for('festival_option'))

        # ดึง Option ปัจจุบันจากตาราง users ก่อนบันทึกคำขอ
        row = conn.execute("SELECT festival_option FROM users WHERE user_id=?", (user_id,)).fetchone()
        original_option = row['festival_option'] if row else 1

        chosen_opt = request.form.get('chosen_option','1')
        reason = request.form.get('reason','')
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        conn.execute("""
            INSERT INTO festival_option_requests
            (user_id, chosen_option, original_option, reason, status, created_at)
            VALUES (?,?,?,?, 'pending', ?)
        """, (user_id, int(chosen_opt), original_option, reason, now_str))
        conn.commit()
        conn.close()

        flash("ส่งคำขอเปลี่ยน Option ลาเทศกาลเรียบร้อย รอ HR อนุมัติ", "success")
        return redirect(url_for('festival_option'))
    else:
        # GET => แสดงฟอร์ม โดย query ค่า Option ปัจจุบันจาก users
        conn = get_db_connection()
        row = conn.execute("SELECT festival_option FROM users WHERE user_id=?", (user_id,)).fetchone()
        conn.close()
        current_option = row['festival_option'] if row else 1
        return render_template('leave/festival_option_select.html', current_option=current_option)

# HR อนุมัติ option ลาเทศกาล
@app.route('/hr/festival_option_approval', methods=['GET','POST'])
@role_required('HR')
def festival_option_approval():
    conn = get_db_connection()
    if request.method=='POST':
        action = request.form.get('action','approve')  # 'approve' or 'reject'
        request_id = request.form.get('request_id')
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        row = conn.execute("""
            SELECT user_id, chosen_option, original_option
            FROM festival_option_requests
            WHERE request_id=? AND status='pending'
        """, (request_id,)).fetchone()
        if row:
            uid = row['user_id']
            chosen_opt = row['chosen_option']
            # original_option = row['original_option']  # For display purposes, already stored
            if action=='approve':
                conn.execute("""
                    UPDATE users
                    SET festival_option=?
                    WHERE user_id=?
                """, (chosen_opt, uid))
                conn.execute("""
                    UPDATE festival_option_requests
                    SET status='approved', approved_at=?
                    WHERE request_id=?
                """,(now_str, request_id))
                flash("อนุมัติ Option สำเร็จ", "success")
            elif action=='reject':
                conn.execute("""
                    UPDATE festival_option_requests
                    SET status='rejected', approved_at=?
                    WHERE request_id=?
                """,(now_str, request_id))
                flash("ปฏิเสธ Option นี้", "warning")
        conn.commit()
        conn.close()
        return redirect(url_for('festival_option_approval'))
    else:
        # GET => แสดงประวัติทั้งหมด (pending, approved, rejected)
        rows = conn.execute("""
            SELECT r.request_id, r.user_id, r.chosen_option, r.original_option, r.reason, r.status,
                   u.first_name || ' ' || u.last_name AS full_name,
                   r.created_at
            FROM festival_option_requests r
            JOIN users u ON r.user_id = u.user_id
            ORDER BY r.created_at DESC
        """).fetchall()
        conn.close()
        # Group by year based on created_at
        from collections import defaultdict
        grouped = defaultdict(list)
        for r in rows:
            year = r['created_at'][:4]
            grouped[year].append(r)
        sorted_years = sorted(grouped.keys(), reverse=True)
        return render_template('hr/festival_option_approval.html', grouped_requests=grouped, sorted_years=sorted_years)



### -------------------------------------------
### หัก กยศ.
### -------------------------------------------
#หน้าเพิ่ม/แก้ไขค่าหัก กยศ.
@app.route('/hr/loan_deduction', methods=['GET', 'POST'])
@role_required('HR')
def loan_deduction():
    if request.method == 'POST':
        year = int(request.form.get('year'))
        month = int(request.form.get('month'))
        deductions = request.form.getlist('loan_deduction')
        user_ids = request.form.getlist('user_id')

        conn = get_db_connection()

        for user_id, deduction in zip(user_ids, deductions):
            deduction_value = float(deduction) if deduction else 0
            conn.execute("""
                INSERT INTO loan_deduction_records (user_id, year, month, loan_deduction)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id, year, month)
                DO UPDATE SET loan_deduction = excluded.loan_deduction, updated_at = CURRENT_TIMESTAMP
            """, (user_id, year, month, deduction_value))

        conn.commit()
        conn.close()

        return redirect(url_for('loan_deduction'))

    else:
        # GET Method - แสดงหน้าฟอร์ม
        today = datetime.today()
        current_year = today.year
        current_month = today.month

        conn = get_db_connection()
        users = conn.execute("""
            SELECT u.user_id, u.first_name, u.last_name, 
                   COALESCE(ld.loan_deduction, 0) AS loan_deduction
            FROM users u
            LEFT JOIN loan_deduction_records ld
            ON u.user_id = ld.user_id AND ld.year = ? AND ld.month = ?
            WHERE u.role in ('HR', 'EMPLOYEE', 'MANAGER', 'SECRETARY')
            ORDER BY u.user_id
        """, (current_year, current_month)).fetchall()
        conn.close()

        return render_template('hr/loan_deduction.html', users=users, current_year=current_year, current_month=current_month)

# หัก กยศ. (ประวัติย้อนหลัง 12 เดือน)
@app.route('/hr/loan_deduction_history', methods=['GET'])
@role_required('HR')
def loan_deduction_history():
    from datetime import datetime

    today = datetime.now()
    current_year = today.year
    current_month = today.month

    # สร้างรายการ (year, month) 12 ตัว (รวมเดือนปัจจุบันด้วย)
    # เรียงจาก "ใหม่ (ปัจจุบัน)" ไป "เก่ากว่า"
    month_list = []
    tmp_year = current_year
    tmp_month = current_month

    for _ in range(12):
        month_list.append((tmp_year, tmp_month))  
        # ถอยเดือน
        tmp_month -= 1
        if tmp_month == 0:
            tmp_month = 12
            tmp_year -= 1
    # ตอนนี้ month_list[0] = (ปัจจุบัน), month_list[1] = (เดือนก่อน), ... [11] = (เก่าสุด)

    # เนื่องจากใช้ 2 ปีใน record, เราจะ Query เฉพาะ (year >= minYear) and (year <= maxYear) 
    # หรือจะ fetch all in 2 year range
    # คำนวณ min_year
    min_year = month_list[-1][0]  # ปีของตัวที่เก่าสุด
    max_year = month_list[0][0]   # ปีของตัวใหม่สุด
    # (เผื่อกรณีแปลกๆ, แต่ส่วนใหญ่ 2 ปี +/1)

    conn = get_db_connection()
    # Query loan_deduction_records สองปีครอบคลุม
    records_raw = conn.execute("""
        SELECT u.user_id, u.first_name, u.last_name,
               ld.year, ld.month, ld.loan_deduction
        FROM loan_deduction_records ld
        JOIN users u ON ld.user_id = u.user_id
        WHERE ld.year >= ?
          AND ld.year <= ?
          AND u.role in ('HR', 'EMPLOYEE', 'MANAGER', 'SECRETARY')
        ORDER BY ld.year DESC, ld.month DESC, u.user_id
    """, (min_year, max_year)).fetchall()
    conn.close()

    # สร้าง pivot: deductions[user_id][(year,month)] = value
    # แต่ month_list เราเรียงจากใหม่ -> เก่า
    # เราต้องกรอง record ให้เฉพาะ (year, month) ใน month_list เท่านั้น
    month_set = set(month_list)

    deductions = {}
    user_info = {}

    for row in records_raw:
        y = row['year']
        m = row['month']
        if (y, m) not in month_set:
            continue  # ข้าม record นอก 12 เดือน

        uid = row['user_id']
        if uid not in deductions:
            deductions[uid] = {}
            user_info[uid] = (row['first_name'], row['last_name'])

        deductions[uid][(y, m)] = row['loan_deduction']

    # สร้าง user_list จาก keys ของ deductions (เฉพาะ user ที่มี record)
    user_list = sorted(deductions.keys())

    return render_template(
        'hr/loan_deduction_history.html',
        month_list=month_list,  # ใหม่ -> เก่า
        user_list=user_list,
        user_info=user_info,
        deductions=deductions
    )



### -------------------------------------------
### หัก ภาษี ณ ที่จ่าย
### -------------------------------------------
# หน้าเพิ่ม/แก้ไขค่าหัก ภาษี ณ ที่จ่าย
@app.route('/manager/tax_deduction', methods=['GET', 'POST'])
@role_required('SECRETARY')
@subcategory_required('tax_deduction')
def tax_deduction():
    from datetime import datetime

    if request.method == 'POST':
        year = int(request.form.get('year'))
        month = int(request.form.get('month'))
        deductions = request.form.getlist('tax_deduction')
        user_ids = request.form.getlist('user_id')

        conn = get_db_connection()

        for user_id, deduction in zip(user_ids, deductions):
            deduction_value = float(deduction) if deduction else 0
            conn.execute("""
                INSERT INTO tax_deduction_records (user_id, year, month, tax_deduction)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id, year, month)
                DO UPDATE SET tax_deduction = excluded.tax_deduction, updated_at = CURRENT_TIMESTAMP
            """, (user_id, year, month, deduction_value))

        conn.commit()
        conn.close()

        return redirect(url_for('tax_deduction'))

    else:
        # GET Method - แสดงหน้าฟอร์ม
        today = datetime.today()
        current_year = today.year
        current_month = today.month

        conn = get_db_connection()
        users = conn.execute("""
            SELECT u.user_id, u.first_name, u.last_name, 
                   COALESCE(td.tax_deduction, 0) AS tax_deduction
            FROM users u
            LEFT JOIN tax_deduction_records td
            ON u.user_id = td.user_id AND td.year = ? AND td.month = ?
            ORDER BY u.user_id
        """, (current_year, current_month)).fetchall()
        conn.close()

        return render_template('manager/tax_deduction.html', users=users, current_year=current_year, current_month=current_month)

# หัก ภาษี ณ ที่จ่าย (ประวัติย้อนหลัง 12 เดือน)
@app.route('/manager/tax_deduction_history', methods=['GET'])
@role_required('SECRETARY')
@subcategory_required('tax_deduction_history')
def tax_deduction_history():
    """
    แสดงประวัติค่าหัก ภาษี ณ ที่จ่าย ของพนักงานย้อนหลัง 12 เดือน
    """
    from datetime import datetime

    today = datetime.now()
    current_year = today.year
    current_month = today.month

    conn = get_db_connection()

    # ดึงข้อมูลค่าหัก ภาษี ณ ที่จ่าย ย้อนหลัง 12 เดือน
    records = conn.execute("""
        SELECT u.first_name, u.last_name, td.year, td.month, td.tax_deduction
        FROM tax_deduction_records td
        JOIN users u ON td.user_id = u.user_id
        WHERE (td.year = ? AND td.month <= ?)
           OR (td.year = ? AND td.month > ?)
        ORDER BY td.year DESC, td.month DESC, u.user_id
    """, (current_year, current_month, current_year - 1, current_month)).fetchall()

    conn.close()

    return render_template('manager/tax_deduction_history.html', records=records)



### -------------------------------------------
### เงินประกันสะสม Insurance Fund
### -------------------------------------------
# เพิ่มเงินประกันสะสม เริ่มต้น หรือ กรณีพิเศษ
@app.route('/hr/insurance_fund_add', methods=['GET','POST'])
@role_required('ADMIN')
def insurance_fund_add():
    """
    แสดงพนักงานทุกคน (ยกเว้น Admin) ในตาราง:
     - คอลัมน์ [#ลำดับ, ชื่อ-นามสกุล, balance ปัจจุบัน, deducted, contribute, withdraw, repay, comment]
     - เลือก month/year เดียวกันสำหรับทุกคน (Dropdown)
    หลังกด "บันทึก" => loop ทุก user => ถ้ามีกรอก (deduct>0, etc.) => insert insurance_fund
    แล้ว Flash Message + redirect กลับหน้าปัจจุบัน
    """

    conn = get_db_connection()
    # 1) ดึงพนักงาน (ไม่รวม Admin)
    users = conn.execute("""
        SELECT user_id, nickname, first_name, nickname, start_date
        FROM users
        WHERE role in ('HR', 'EMPLOYEE', 'MANAGER', 'SECRETARY')
        ORDER BY start_date
    """).fetchall()

    # 2) คำนวณ "ยอดคงเหลือปัจจุบัน" (balance) ของแต่ละ user
    #    balance = SUM(deduct + company_contribute - withdraw + repay)
    user_data = []
    total_all_balance = 0.0

    for u in users:
        uid = u['user_id']
        row_balance = conn.execute("""
            SELECT COALESCE(
              SUM(deducted_amount + company_contribute 
                  - withdraw_amount + repay_amount), 0
            ) AS balance
            FROM insurance_fund
            WHERE user_id=?
        """,(uid,)).fetchone()

        current_balance = float(row_balance['balance']) if row_balance else 0.0
        total_all_balance += current_balance

        user_data.append({
            'user_id': uid,
            'nickname':  u['nickname'],
            'first_name': u['first_name'],
            'balance':    current_balance
        })

    conn.close()

    if request.method == 'POST':
        # รับ month/year จากฟอร์ม (Dropdown)
        month_str = request.form.get('month')
        year_str  = request.form.get('year')

        if not month_str or not year_str:
            flash("กรุณาเลือกเดือน/ปี ก่อนบันทึก", "danger")
            return redirect(url_for('insurance_fund_add'))

        try:
            month = int(month_str)
            year  = int(year_str)
        except ValueError:
            flash("เดือน/ปี ไม่ถูกต้อง", "danger")
            return redirect(url_for('insurance_fund_add'))

        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        conn = get_db_connection()

        inserted_count = 0
        # loop user_data => อ่านฟอร์ม: deducted_xxx, contribute_xxx, withdraw_xxx, repay_xxx, comment_xxx
        for ud in user_data:
            uid = ud['user_id']

            ded_key = f"deducted_{uid}"
            cct_key = f"contribute_{uid}"
            wdr_key = f"withdraw_{uid}"
            rpy_key = f"repay_{uid}"
            cmt_key = f"comment_{uid}"

            ded_val = request.form.get(ded_key, "0")
            cct_val = request.form.get(cct_key, "0")
            wdr_val = request.form.get(wdr_key, "0")
            rpy_val = request.form.get(rpy_key, "0")
            cmt_val = request.form.get(cmt_key, "")

            try:
                deducted_amount   = float(ded_val)
                company_contribute= float(cct_val)
                withdraw_amount   = float(wdr_val)
                repay_amount      = float(rpy_val)
                comment_str       = cmt_val.strip()
            except ValueError:
                # ถ้าพิมพ์ผิด => ข้าม user นี้
                continue

            # ถ้าไม่มีการกรอก -> ข้าม
            if (deducted_amount == 0 and company_contribute == 0 
                and withdraw_amount == 0 and repay_amount == 0
                and comment_str == ""):
                continue

            # Insert ลง insurance_fund
            conn.execute("""
                INSERT INTO insurance_fund(
                  user_id, month, year,
                  deducted_amount, company_contribute,
                  withdraw_amount, repay_amount,
                  comment, created_at
                )
                VALUES (?,?,?,?,?,?,?,?,?)
            """,(uid, month, year,
                 deducted_amount, company_contribute,
                 withdraw_amount, repay_amount,
                 comment_str, now_str))
            inserted_count += 1

        conn.commit()
        conn.close()

        flash(f"บันทึก {inserted_count} record เรียบร้อย (เดือน {month}/{year})", "success")
        return redirect(url_for('insurance_fund_add'))

    else:
        # GET => render template + ส่ง user_data, total_all_balance
        return render_template(
            "hr/insurance_fund_add.html",
            user_data=user_data,
            total_all_balance=total_all_balance
        )

# CRON Auto-Generate อัพเดทเงินประกันสะสม (รายเดือน ทุกวันที่ 1)
@app.route('/hr/auto_generate_insurance_fund', methods=['POST','GET'])
@role_required('HR','ADMIN')
def auto_generate_insurance_fund():
    """
    เรียกฟังก์ชันนี้ (ด้วย Cron Job ทุกวันที่ 1)
    logic:
      - find today's month/year
      - for each user (role in ('HR', 'EMPLOYEE', 'MANAGER', 'SECRETARY'))
          - load monthly_deduction, active from insurance_fund_config
          - if active=1 => deduct => push insurance_fund record
            => company_contribute = min(deduct/2, 500)
          - else => skip
    """
    today = datetime.date.today()

    # เช็คว่าเป็น day=1 หรือเปล่า (อาจ check optional)
    if today.day != 1:
        flash("วันนี้ไม่ใช่วันที่ 1, การ generate อาจไม่เหมาะสม", "warning")
        # หรือจะทำต่อก็ได้
        # return redirect(url_for('dashboard'))

    year  = today.year
    month = today.month
    now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    conn = get_db_connection()

    # load users + config
    rows = conn.execute("""
        SELECT u.user_id, u.first_name, u.last_name,
               c.monthly_deduction, c.active
        FROM users u
        LEFT JOIN insurance_fund_config c ON u.user_id=c.user_id
        WHERE u.role!='ADMIN'
        ORDER BY u.user_id
    """).fetchall()

    inserted_count = 0

    for r in rows:
        uid = r['user_id']
        active = r['active']
        monthly_deduction = r['monthly_deduction'] or 1000  # ถ้า NULL, set default

        if active == 1:  # ยังหักอยู่
            deducted_amount = monthly_deduction
            # สมมติ company_contribute = min(deducted/2, 500)
            company_contribute = min(monthly_deduction / 2, 500)
        else:
            # หยุดหัก => skip or insert 0
            deducted_amount = 0
            company_contribute = 0

        # ถ้าทั้งคู่ = 0 => ข้าม
        if deducted_amount == 0 and company_contribute == 0:
            continue

        # insert into insurance_fund
        conn.execute("""
            INSERT INTO insurance_fund(
              user_id, month, year,
              deducted_amount, company_contribute,
              withdraw_amount, repay_amount,
              comment, created_at
            )
            VALUES (?,?,?,?,?,?,0,?,?)
        """,(
            uid, month, year,
            deducted_amount, company_contribute,
            0,             # withdraw=0
            0,             # repay=0
            "Auto-Generate by Cron", 
            now_str
        ))
        inserted_count += 1

    conn.commit()
    conn.close()

    flash(f"Auto-generate สำเร็จ: บันทึก {inserted_count} record (เดือน {month}/{year})", "success")
    return redirect(url_for('dashboard'))

# Edit ยอดเงินหักสะสมต่อเดือน
@app.route('/hr/edit_insurance_config', methods=['GET','POST'])
@role_required('HR','ADMIN')
def edit_insurance_config():
    """
    HR/ADMIN แก้ไขยอดเงินหัก (monthly_deduction) ของแต่ละ user 
    active_deduction=1 => หักอยู่, 0 => หยุดหัก

    - GET => แสดงพนักงาน (ยกเว้น Admin) พร้อมค่าปัจจุบัน (monthly_deduction, active_deduction)
    - POST => loop user => update/insert ลง insurance_fund_config
    """
    conn = get_db_connection()
    # 1) โหลด user + insurance_fund_config (ใช้ c.active_deduction แทน c.active)
    rows = conn.execute("""
        SELECT 
          u.user_id, 
          u.first_name, 
          u.last_name,
          COALESCE(c.monthly_deduction, 1000) AS monthly_deduction,
          COALESCE(c.active_deduction, 1) AS active_deduction
        FROM users u
        LEFT JOIN insurance_fund_config c ON u.user_id = c.user_id
        WHERE u.role in ('HR', 'EMPLOYEE', 'MANAGER', 'SECRETARY')
        ORDER BY u.user_id
    """).fetchall()
    conn.close()

    if request.method == 'POST':
        # 2) รับข้อมูลจากฟอร์ม
        conn = get_db_connection()
        updated_count = 0

        for r in rows:
            uid = r['user_id']
            ded_key = f"ded_{uid}"  # ช่อง input monthly_deduction
            act_key = f"act_{uid}"  # select หรือ radio => 1 / 0

            ded_val = request.form.get(ded_key, '1000')
            act_val = request.form.get(act_key, '0')  # '1' หรือ '0'

            try:
                monthly_ded = float(ded_val)
                active_flag = int(act_val)
            except ValueError:
                # ถ้ากรอกตัวเลขผิด
                continue

            # ตรวจว่ามี record ใน insurance_fund_config อยู่แล้วหรือไม่
            row_exist = conn.execute("""
                SELECT config_id 
                FROM insurance_fund_config
                WHERE user_id=?
            """,(uid,)).fetchone()

            now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            if row_exist:
                # update (คอลัมน์ active_deduction)
                conn.execute("""
                  UPDATE insurance_fund_config
                  SET monthly_deduction=?, 
                      active_deduction=?, 
                      created_at=?
                  WHERE user_id=?
                """,(monthly_ded, active_flag, now_str, uid))
            else:
                # insert
                conn.execute("""
                  INSERT INTO insurance_fund_config(
                    user_id, 
                    monthly_deduction, 
                    active_deduction, 
                    created_at
                  )
                  VALUES (?,?,?,?)
                """,(uid, monthly_ded, active_flag, now_str))

            updated_count += 1

        conn.commit()
        conn.close()

        flash(f"อัปเดต config {updated_count} record เรียบร้อย", "success")
        return redirect(url_for('edit_insurance_config'))

    else:
        # GET => ส่ง rows ไป Template แสดง
        return render_template("hr/edit_insurance_config.html", user_rows=rows)

# ขอหยุด / กลับมาหักเงินสะสม
@app.route('/insurance_stop_request', methods=['GET','POST'])
@role_required('EMPLOYEE','HR','MANAGER', 'SECRETARY')
def insurance_stop_request():
    """
    พนักงานยื่นคำขอ 'STOP' (หยุดหัก) หรือ 'REACTIVATE' (กลับมาหักใหม่)
    เงื่อนไข STOP => อายุงาน >= 8 เดือน + current_balance >= 12000
    ถ้าหากมีคำขอ pending อยู่แล้ว => ห้ามส่งคำขอใหม่
    """
    user_id = session['user_id']
    conn = get_db_connection()

    # โหลดข้อมูลชื่อพนักงาน + start_date + active_deduction
    row_user = conn.execute("""
        SELECT u.first_name, u.last_name, u.start_date,
               c.active_deduction
        FROM users u
        LEFT JOIN insurance_fund_config c ON u.user_id=c.user_id
        WHERE u.user_id=?
    """, (user_id,)).fetchone()
    if not row_user:
        conn.close()
        return "ไม่พบข้อมูลผู้ใช้"

    first_name = row_user['first_name']
    last_name  = row_user['last_name']
    start_date_str = row_user['start_date'] or ''
    current_active = row_user['active_deduction'] if row_user['active_deduction'] is not None else 1

    # คำนวณอายุงาน (month) -> year, month
    from datetime import datetime
    now_dt = datetime.now()
    diff_months = 0
    if start_date_str:
        s_yyyy, s_mm, s_dd = map(int, start_date_str.split('-'))
        start_dt = datetime(s_yyyy, s_mm, s_dd)
        diff_months = (now_dt.year - start_dt.year)*12 + (now_dt.month - start_dt.month)
        # หากต้องการคำนึงวันที่ด้วย:
        # if now_dt.day < s_dd:
        #     diff_months -= 1
    else:
        diff_months = 0

    year_of_service = diff_months // 12
    month_of_service= diff_months % 12

    # โหลดยอดสะสมปัจจุบัน (insurance_fund)
    row_balance = conn.execute("""
        SELECT COALESCE(SUM(deducted_amount + company_contribute 
                            - withdraw_amount + repay_amount), 0) AS balance
        FROM insurance_fund
        WHERE user_id=?
    """, (user_id,)).fetchone()
    current_balance = float(row_balance['balance']) if row_balance else 0.0

    # 1) ตรวจสอบว่ามีคำขอ pending อยู่หรือไม่
    row_pending = conn.execute("""
        SELECT stop_id, request_type
        FROM insurance_stop_request
        WHERE user_id=? AND status='pending'
        LIMIT 1
    """, (user_id,)).fetchone()
    has_pending_request = (row_pending is not None)  # True if pending

    # 2) เช็คเงื่อนไข STOP ได้หรือไม่
    #    => อายุงาน >=8 เดือน + current_balance>=12000
    can_stop = (diff_months >= 8 and current_balance >= 12000)

    if request.method=='POST':
        # ถ้ามี pending อยู่ => ห้ามส่งใหม่
        if has_pending_request:
            conn.close()
            flash("คุณมีคำขอที่ยังรออนุมัติอยู่ ไม่สามารถส่งคำขอซ้ำได้", "warning")
            return redirect(url_for('insurance_stop_request'))

        req_type = request.form.get('request_type','STOP')  # 'STOP' or 'REACTIVATE'
        reason   = request.form.get('reason','').strip()

        if req_type=='STOP':
            # ถ้าไม่เข้าเงื่อนไข => ป้องกันเรียก POST ตรงๆ
            if not can_stop:
                conn.close()
                flash("คุณไม่เข้าเงื่อนไขในการขอหยุดหักเงินสะสม", "danger")
                return redirect(url_for('insurance_stop_request'))

        # สร้างคำขอ
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        conn.execute("""
            INSERT INTO insurance_stop_request(
                user_id, request_date, request_type, reason, status
            )
            VALUES(?,?,?,?, 'pending')
        """, (user_id, now_str, req_type, reason))
        conn.commit()
        conn.close()

        # ส่ง Notification หา HR
        add_notification_for_roles(['HR'], f"User {user_id} ขอ {req_type} หักเงินประกันสะสม")

        flash("ส่งคำขอเรียบร้อย รอ HR อนุมัติ", "success")
        return redirect(url_for('dashboard'))
    else:
        # GET => แสดงฟอร์ม
        conn.close()
        return render_template(
            'user/insurance_stop_request.html',
            first_name=first_name,
            last_name=last_name,
            year_of_service=year_of_service,
            month_of_service=month_of_service,
            current_balance=current_balance,
            current_active=current_active,
            has_pending_request=has_pending_request,
            can_stop=can_stop
        )

# HR ดูคำขอ ขอหยุด / กลับมาหักเงินสะสม
@app.route('/hr/insurance_stop_list')
@role_required('HR')
def insurance_stop_list():
    """
    แสดงคำขอหยุด/กลับมาหักเงินสะสมทั้งหมด
    โดยจะแบ่งกลุ่มตาม (ปี,เดือน) ของ request_date
    แล้วค่อยส่งไป template
    """
    conn = get_db_connection()
    # ดึง request ทั้งหมด + user
    rows = conn.execute("""
        SELECT s.stop_id, s.user_id, s.request_date, s.request_type,
               s.reason, s.status, s.updated_at,
               u.first_name, u.last_name
        FROM insurance_stop_request s
        JOIN users u ON s.user_id = u.user_id
        ORDER BY s.request_date ASC, s.stop_id ASC
    """).fetchall()
    conn.close()

    # สร้าง dict เพื่อแยกตาม year-month
    from collections import OrderedDict, defaultdict
    requests_by_ym = OrderedDict()  
    # หรือ dict ธรรมดาได้ (Python 3.7+ จะรักษาลำดับ key)

    for r in rows:
        # r.request_date => '2025-02-15 10:20:30' (หรือ '2025-02-15')
        # ตัดเอา 'YYYY-MM'
        yyyymm = r['request_date'][:7]  # เช่น '2025-02'
        # เก็บลงใน requests_by_ym[yyyymm] = list
        if yyyymm not in requests_by_ym:
            requests_by_ym[yyyymm] = []
        requests_by_ym[yyyymm].append(r)

    # ข้อมูลเดือนภาษาไทย
    thai_months = {
        1: "มกราคม", 2: "กุมภาพันธ์", 3: "มีนาคม", 4: "เมษายน",
        5: "พฤษภาคม", 6: "มิถุนายน", 7: "กรกฎาคม", 8: "สิงหาคม",
        9: "กันยายน", 10: "ตุลาคม", 11: "พฤศจิกายน", 12: "ธันวาคม",
    }

    return render_template(
        'hr/insurance_stop_list.html',
        requests_by_ym=requests_by_ym,
        thai_months=thai_months
    )

# HR อนุมัติคำขอ ขอหยุด / กลับมาหักเงินสะสม
@app.route('/hr/insurance_stop_approve', methods=['POST'])
@role_required('HR')
def insurance_stop_approve():
    """
    HR อนุมัติ/ปฏิเสธ คำขอหยุด หรือกลับมาหัก
    """
    stop_id = request.form.get('stop_id')
    action = request.form.get('action')  # 'approve' or 'reject'
    now_str= datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    conn = get_db_connection()
    row_req = conn.execute("""
        SELECT stop_id, user_id, request_type, status
        FROM insurance_stop_request
        WHERE stop_id=?
    """,(stop_id,)).fetchone()

    if not row_req:
        conn.close()
        flash("ไม่พบคำขอนี้ในระบบ","warning")
        return redirect(url_for('insurance_stop_list'))

    if row_req['status'] != 'pending':
        conn.close()
        flash("คำขอนี้ไม่อยู่ในสถานะ pending","warning")
        return redirect(url_for('insurance_stop_list'))

    user_id    = row_req['user_id']
    req_type   = row_req['request_type']  # 'STOP' or 'REACTIVATE'
    old_status = row_req['status']

    new_status = 'approved' if (action=='approve') else 'rejected'

    # update status
    conn.execute("""
        UPDATE insurance_stop_request
        SET status=?, updated_at=?
        WHERE stop_id=?
    """,(new_status, now_str, stop_id))

    # ถ้าอนุมัติ => อัปเดต insurance_fund_config
    if new_status=='approved':
        if req_type=='STOP':
            # active_deduction=0 => หยุดหัก
            conn.execute("""
                UPDATE insurance_fund_config
                SET active_deduction=0
                WHERE user_id=?
            """,(user_id,))
        elif req_type=='REACTIVATE':
            # active_deduction=1 => กลับมาหักใหม่
            conn.execute("""
                UPDATE insurance_fund_config
                SET active_deduction=1
                WHERE user_id=?
            """,(user_id,))

    conn.commit()

    # แจ้ง user
    add_notification_for_roles(user_id, 
        f"คำขอ {req_type} หักเงินประกันสะสมของคุณถูก {new_status}")

    conn.close()
    flash(f"{req_type} => {new_status} เรียบร้อย","success")
    return redirect(url_for('insurance_stop_list'))
                                                                             
# ขอเบิกเงินสะสม
@app.route('/insurance_withdraw_request', methods=['GET','POST'])
@role_required('EMPLOYEE','HR','MANAGER', 'SECRETARY')
def insurance_withdraw_request():
    """
    พนักงานยื่นคำขอเบิกเงินสะสม (withdraw request):
      - ตรวจสอบ current_balance - withdraw_amount >= 12000
      - repay_months <=12
      - monthly_repay >=1000 (กรณี withdraw_amount > 0)
      - หากมี pending หรือผ่อนคืนอยู่ -> ไม่ให้สร้างคำขอใหม่
      - ถ้าอยู่ในสถานะผ่อนคืน (unpaid) -> แสดงปุ่ม/ฟอร์ม "Request Lumpsum Repay"

    การกดปุ่ม lumpsum_repay => สร้างคำขอ lumpsum_repay_request (status='pending')
       (ตัวอย่าง: เราอาจจะมี insurance_repay_stop_request หรือ insurance_lumpsum_request)
    """

    user_id = session['user_id']
    conn = get_db_connection()

    # 1) โหลดยอดสะสมปัจจุบัน
    row_balance = conn.execute("""
        SELECT COALESCE(
           SUM(deducted_amount + company_contribute
               - withdraw_amount + repay_amount),
           0
        ) AS balance
        FROM insurance_fund
        WHERE user_id=?
    """, (user_id,)).fetchone()
    current_balance = float(row_balance['balance']) if row_balance else 0.0

    # 2) ตรวจสอบว่าผู้ใช้มีคำขอ "pending" อยู่หรือไม่
    row_pending = conn.execute("""
        SELECT request_id, request_date, withdraw_amount, 
               repay_months, monthly_repay
        FROM insurance_withdraw_request
        WHERE user_id=? AND status='pending'
        ORDER BY request_date DESC
        LIMIT 1
    """,(user_id,)).fetchone()

    # 3) ตรวจสอบว่ามีการผ่อนคืน (unpaid) อยู่ไหม
    #    (อนุมัติแล้ว w.status='approved' แต่ยังมี r.status='unpaid')
    row_unpaid = conn.execute("""
        SELECT w.request_id, w.request_date,
               w.withdraw_amount, w.repay_months, w.monthly_repay
        FROM insurance_repay_plan r
        JOIN insurance_withdraw_request w
          ON r.request_id = w.request_id
        WHERE w.user_id=?
          AND w.status='approved'
          AND r.status='unpaid'
        ORDER BY w.request_date DESC
        LIMIT 1
    """,(user_id,)).fetchone()

    allow_new_request = True              # ให้ยื่นขอเบิกใหม่ได้?
    last_request_info = None              # เก็บข้อมูล "คำขอล่าสุด" หรือ "ผ่อนคืนล่าสุด"
    show_lumpsum_button = False           # ให้แสดงปุ่ม Lumpsum Repay?
    lumpsum_amount = 0.0                  # เงินก้อนที่ต้องจ่ายคืนจริง ๆ

    # ---------- เคสมี pending ----------
    if row_pending:
        allow_new_request = False
        last_request_info = {
            'status': 'pending',
            'request_date': row_pending['request_date'],
            'withdraw_amount': row_pending['withdraw_amount'],
            'repay_months': row_pending['repay_months'],
            'monthly_repay': row_pending['monthly_repay'],
        }

    # ---------- เคสมี unpaid ----------
    elif row_unpaid:
        allow_new_request = False
        last_request_info = {
            'status': 'approved',  # กำลังผ่อน
            'request_id': row_unpaid['request_id'],
            'request_date': row_unpaid['request_date'],
            'withdraw_amount': row_unpaid['withdraw_amount'],
            'repay_months': row_unpaid['repay_months'],
            'monthly_repay': row_unpaid['monthly_repay'],
        }
        show_lumpsum_button = True

        # --- คำนวณ leftover = (withdraw_amount - sum(repay_amount_paid)) ---
        # เช่น ถ้าผ่อนบางส่วนไปแล้ว => leftover = ส่วนที่เหลือ
        sum_paid_row = conn.execute("""
            SELECT COALESCE(SUM(repay_amount), 0) AS total_paid
            FROM insurance_repay_plan
            WHERE request_id=? AND status='paid'
        """,(row_unpaid['request_id'],)).fetchone()
        total_paid = float(sum_paid_row['total_paid']) if sum_paid_row else 0.0

        lumpsum_amount = float(row_unpaid['withdraw_amount'] or 0.0) - total_paid
        if lumpsum_amount < 0:
            lumpsum_amount = 0  # กันกรณี bug

    # =================== ตรวจว่า POST หรือไม่ ======================
    if request.method == 'POST':
        action = request.form.get('action', '')  # 'new_withdraw' หรือ 'lumpsum_repay'

        # ---------- ขอจ่ายเต็มก้อน (lumpsum_repay) ----------
        if action == 'lumpsum_repay':
            if not row_unpaid:
                conn.close()
                flash("ไม่พบสถานะผ่อนคืนที่ยังไม่เสร็จ ไม่สามารถขอจ่ายคืนเต็มก้อนได้", "warning")
                return redirect(url_for('insurance_withdraw_request'))

            lumpsum_str = request.form.get('lumpsum_amount', '0')
            try:
                lumpsum_val = float(lumpsum_str)
            except:
                lumpsum_val = 0

            # ต้องมากกว่า 0
            if lumpsum_val <= 0:
                conn.close()
                flash("จำนวนเงินจ่ายเต็มก้อนไม่ถูกต้อง (0 หรือติดลบ)", "danger")
                return redirect(url_for('insurance_withdraw_request'))

            # ตรวจว่ามี lumpsum request pending อยู่หรือไม่
            row_lumpsum_pending = conn.execute("""
                SELECT stop_id
                FROM insurance_repay_stop_request
                WHERE user_id=? 
                  AND request_id=? 
                  AND status='pending'
                LIMIT 1
            """, (user_id, row_unpaid['request_id'])).fetchone()
            if row_lumpsum_pending:
                conn.close()
                flash("คุณมีคำขอจ่ายคืนเต็มก้อน (lumpsum) ค้างอยู่ (pending)", "warning")
                return redirect(url_for('insurance_withdraw_request'))

            # สร้างคำขอ lumpsum
            now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            conn.execute("""
                INSERT INTO insurance_repay_stop_request(
                    user_id, request_date, request_id, lumpsum_amount, status
                )
                VALUES(?,?,?,?, 'pending')
            """,(user_id, now_str, row_unpaid['request_id'], lumpsum_val))
            conn.commit()
            conn.close()

            add_notification_for_roles(['HR'], 
                f"User {user_id} ขอจ่ายเต็มก้อน (lumpsum) request_id={row_unpaid['request_id']}")
            flash("ส่งคำขอจ่ายคืนเต็มก้อนเรียบร้อย รออนุมัติ", "success")
            return redirect(url_for('insurance_withdraw_request'))

        # ---------- ฟอร์มขอเบิกเงินสะสม (new_withdraw) ----------
        elif action == 'new_withdraw':
            if not allow_new_request:
                conn.close()
                flash("คุณไม่สามารถยื่นคำขอเบิกใหม่ได้ (มีคำขอ/ผ่อนคืนค้าง).", "warning")
                return redirect(url_for('insurance_withdraw_request'))

            withdraw_str = request.form.get('withdraw_amount','0')
            repay_months_str = request.form.get('repay_months','0')
            monthly_repay_str = request.form.get('monthly_repay','0')

            try:
                withdraw_amount = float(withdraw_str)
                repay_months    = int(repay_months_str)
                monthly_repay   = float(monthly_repay_str)
            except ValueError:
                conn.close()
                flash("กรอกตัวเลขไม่ถูกต้อง", "danger")
                return redirect(url_for('insurance_withdraw_request'))

            remain_after = current_balance - withdraw_amount
            if remain_after < 12000:
                conn.close()
                flash("ยอดคงเหลือหลังเบิกต้องไม่น้อยกว่า 12,000 บาท", "danger")
                return redirect(url_for('insurance_withdraw_request'))

            if repay_months < 1 or repay_months > 12:
                conn.close()
                flash("จำนวนเดือนที่ผ่อนคืนต้องอยู่ใน 1..12", "danger")
                return redirect(url_for('insurance_withdraw_request'))

            if withdraw_amount > 0 and monthly_repay < 1000:
                conn.close()
                flash("ต้องผ่อนคืนรายเดือนไม่น้อยกว่า 1,000 บาท", "danger")
                return redirect(url_for('insurance_withdraw_request'))

            # ตรวจซ้ำว่ามี pending ไหม
            row_pending_check = conn.execute("""
                SELECT request_id
                FROM insurance_withdraw_request
                WHERE user_id=? AND status='pending'
                LIMIT 1
            """,(user_id,)).fetchone()
            if row_pending_check:
                conn.close()
                flash("มีคำขอเบิกเงินสะสม pending อยู่ ไม่สามารถขอซ้ำได้", "warning")
                return redirect(url_for('insurance_withdraw_request'))

            now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            conn.execute("""
                INSERT INTO insurance_withdraw_request(
                    user_id, request_date, withdraw_amount,
                    repay_months, monthly_repay, status
                )
                VALUES(?,?,?,?,?,'pending')
            """, (
                user_id, now_str, withdraw_amount,
                repay_months, monthly_repay
            ))
            conn.commit()
            conn.close()

            add_notification_for_roles(['HR'], f"User {user_id} ขอเบิกเงินสะสม {withdraw_amount:.2f} บาท")
            flash("ส่งคำขอเบิกเงินสะสมเรียบร้อย (pending)", "success")
            return redirect(url_for('dashboard'))

        else:
            conn.close()
            flash("ไม่พบ action ที่ร้องขอ", "danger")
            return redirect(url_for('insurance_withdraw_request'))

    #================= GET Method ==================
    else:
        # สร้าง lumpsum_amount = leftover
        lumpsum_amount = 0.0
        if row_unpaid:
            # หา sum_paid
            sum_paid_row = conn.execute("""
                SELECT COALESCE(SUM(repay_amount), 0) AS total_paid
                FROM insurance_repay_plan
                WHERE request_id=? AND status='paid'
            """, (row_unpaid['request_id'],)).fetchone()
            total_paid = float(sum_paid_row['total_paid']) if sum_paid_row else 0.0

            lumpsum_amount = float(row_unpaid['withdraw_amount'] or 0) - total_paid
            if lumpsum_amount < 0:
                lumpsum_amount = 0

        conn.close()
        return render_template(
            'user/insurance_withdraw_request.html',
            current_balance=current_balance,
            allow_new_request=allow_new_request,
            recent_withdraw_info=last_request_info,
            show_lumpsum_button=show_lumpsum_button,
            lumpsum_amount=lumpsum_amount  # สำคัญ! ส่ง leftover ไปหน้า HTML
        )

# HR ดูคำขอ เบิกเงินสะสม
@app.route('/hr/insurance_withdraw_list')
@role_required('HR')
def hr_insurance_withdraw_list():
    """
    HR เรียกดูคำขอเบิกเงินสะสมทั้งหมด (ทุกสถานะ)
    """
    conn = get_db_connection()
    rows = conn.execute("""
        SELECT w.request_id,
               w.user_id,
               w.request_date,
               w.withdraw_amount,
               w.repay_months,
               w.monthly_repay,
               w.status,
               w.updated_at,
               u.first_name,
               u.last_name
        FROM insurance_withdraw_request w
        JOIN users u ON w.user_id = u.user_id
        ORDER BY w.request_date DESC
    """).fetchall()
    conn.close()

    return render_template('hr/insurance_withdraw_list.html', requests=rows)

# HR อนุมัติคำขอ เบิกเงินสะสม
# แก้ไข/ตรวจสอบว่าเรามีการ import นี้อยู่ข้างบนไฟล์ หรือข้างบนฟังก์ชัน
@app.route('/hr/insurance_withdraw_approve', methods=['POST'])
@role_required('HR')
def insurance_withdraw_approve():
    """
    HR อนุมัติ/ปฏิเสธคำขอเบิกเงินสะสม:
      - approve => update status='approved', updated_at
                   insert ลง insurance_fund (withdraw_amount)
                   generate repay plan ใน insurance_repay_plan
        เงื่อนไขเริ่มคืนเงิน:
          * ถ้า request_date < 10 => เริ่มคืนวันที่ 10 ของเดือนถัดไป
          * ถ้า request_date >=10 => เริ่มคืนวันที่ 10 อีกสองเดือนถัดไป
      - reject  => update status='rejected', updated_at
    """
    request_id = request.form.get('request_id')
    action = request.form.get('action')  # 'approve' หรือ 'reject'
    
    # เรียกใช้ datetime.now() ได้ทันที เพราะมี from datetime import datetime
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    conn = get_db_connection()

    row_req = conn.execute("""
        SELECT *
        FROM insurance_withdraw_request
        WHERE request_id = ?
    """, (request_id,)).fetchone()

    if not row_req:
        conn.close()
        flash("ไม่พบคำขอนี้ในระบบ", "warning")
        return redirect(url_for('hr_insurance_withdraw_list'))

    if row_req['status'] != 'pending':
        conn.close()
        flash("คำขอนี้ไม่อยู่ในสถานะ pending แล้ว", "warning")
        return redirect(url_for('hr_insurance_withdraw_list'))

    user_id_val   = row_req['user_id']
    withdraw_amt  = row_req['withdraw_amount']
    repay_months  = row_req['repay_months'] or 0
    monthly_rp    = row_req['monthly_repay'] or 0.0

    # วันที่ user ส่งคำขอ (STRING format: 'YYYY-MM-DD HH:MM:SS' หรือคล้าย)
    request_date_str = row_req['request_date']  
    # ถ้าใน DB เก็บเพียง 'YYYY-MM-DD' ก็ปรับ parse ให้ถูกตามจริง เช่น `datetime.strptime(request_date_str, '%Y-%m-%d')`

    if action == 'approve':
        # update status='approved'
        conn.execute("""
            UPDATE insurance_withdraw_request
            SET status = 'approved',
                updated_at = ?
            WHERE request_id = ?
        """, (now_str, request_id))

        # บันทึกลง insurance_fund (เป็นรายการ withdraw = x)
        trans_year  = now_str[:4]   # หรือ parse เป็น datetime object ก่อนแล้วเรียก .year
        trans_month = now_str[5:7]

        conn.execute("""
            INSERT INTO insurance_fund(
                user_id, month, year,
                withdraw_amount,
                created_at
            )
            VALUES (?, ?, ?, ?, ?)
        """, (
            user_id_val,
            trans_month,
            trans_year,
            withdraw_amt,
            now_str
        ))

        # -- สร้าง Repay Plan -- 
        # 1) parse request_date
        req_dt = datetime.strptime(request_date_str, '%Y-%m-%d %H:%M:%S')
        req_day = req_dt.day

        # 2) ตรวจ logic ก่อน/หลังวันที่ 10
        if req_day < 10:
            # เริ่มคืนวันที่ 10 เดือนถัดไป
            start_month = req_dt.month + 1
            start_year  = req_dt.year
        else:
            # request_date >= 10 => เริ่มคืนอีกสองเดือนถัดไป
            start_month = req_dt.month + 2
            start_year  = req_dt.year

        # ตรวจจับกรณี month>12 (เดือนเกินขอบเขต)
        if start_month > 12:
            extra_yr = (start_month - 1) // 12
            start_year += extra_yr
            start_month = ((start_month - 1) % 12) + 1

        # วนสร้าง repay_months งวด
        for i in range(repay_months):
            mm = start_month + i
            yy = start_year
            if mm > 12:
                extra_yr = (mm - 1) // 12
                yy += extra_yr
                mm = ((mm - 1) % 12) + 1

            # เก็บเป็น YYYYMM (year*100 + month)
            repay_period = yy * 100 + mm

            conn.execute("""
                INSERT INTO insurance_repay_plan(
                    request_id, user_id,
                    repay_month,
                    repay_amount,
                    status
                )
                VALUES(?,?, ?, ?, 'unpaid')
            """, (
                request_id,
                user_id_val,
                repay_period,
                monthly_rp
            ))

        conn.commit()
        conn.close()

        flash("อนุมัติคำขอเรียบร้อย สร้าง Repay Plan แล้ว", "success")
        add_notification(user_id_val, 
            f"คำขอเบิกเงินสะสม #{request_id} ของคุณได้รับการอนุมัติ")

    elif action == 'reject':
        # update status='rejected'
        conn.execute("""
            UPDATE insurance_withdraw_request
            SET status = 'rejected',
                updated_at = ?
            WHERE request_id = ?
        """, (now_str, request_id))
        conn.commit()
        conn.close()

        flash("ปฏิเสธคำขอเรียบร้อย", "success")
        add_notification(user_id_val,
            f"คำขอเบิกเงินสะสม #{request_id} ของคุณถูกปฏิเสธ")

    return redirect(url_for('hr_insurance_withdraw_list'))

# HR อนุมัติ/ปฏิเสธคำขอจ่ายคืนเต็มก้อน (Lumpsum Repay)
@app.route('/hr/insurance_repay_stop_list')
@role_required('HR')
def hr_insurance_repay_stop_list():
    """
    ฟังก์ชันนี้สำหรับ HR เพื่อดูรายการคำขอจ่ายคืนเต็มก้อน (Lumpsum Repay Requests)
    โดยจะดึงข้อมูลจากตาราง insurance_repay_stop_request
    พร้อม join กับตาราง users เพื่อแสดงชื่อ-นามสกุลของผู้ขอ
    จากนั้นส่งตัวแปร lumpsum_requests ไปยัง template insurance_repay_stop_list.html
    """
    conn = get_db_connection()
    lumpsum_requests = conn.execute("""
        SELECT r.stop_id, r.user_id, r.request_date, r.request_id, r.lumpsum_amount, r.status,
               u.first_name, u.last_name
        FROM insurance_repay_stop_request r
        JOIN users u ON r.user_id = u.user_id
        ORDER BY r.request_date DESC, r.stop_id DESC
    """).fetchall()
    conn.close()
    return render_template('hr/insurance_repay_stop_list.html', lumpsum_requests=lumpsum_requests)

# HR อนุมัติ/ปฏิเสธคำขอจ่ายคืนเต็มก้อน
@app.route('/hr/insurance_repay_stop_approve', methods=['POST'])
@role_required('HR')
def insurance_repay_stop_approve():
    """
    HR Approve Lumpsum Repay
    ฟังก์ชันนี้ให้ HR ตรวจสอบคำขอจ่ายคืนเต็มก้อนที่ถูกส่งเข้ามาในตาราง 
    insurance_repay_stop_request โดย:
      - ถ้า approve:
           - อัปเดตสถานะใน insurance_repay_stop_request เป็น 'approved'
           - เปลี่ยนสถานะของทุก record ใน insurance_repay_plan ที่เกี่ยวข้อง (request_id เดิม) 
             ที่ยังอยู่ในสถานะ 'unpaid' ให้เป็น 'paid'
           - **เพิ่มการบันทึก repayment ลงใน insurance_fund โดยบันทึก repay_amount = lumpsum_amount**
      - ถ้า reject:
           - อัปเดตสถานะใน insurance_repay_stop_request เป็น 'rejected'
    หลังจากดำเนินการแล้ว จะส่ง notification ไปยังผู้ใช้ที่เกี่ยวข้อง
    """
    # รับข้อมูลจากฟอร์ม
    stop_id = request.form.get('stop_id')
    action = request.form.get('action')  # ค่าที่รับได้: 'approve' หรือ 'reject'
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # กำหนดค่าปัจจุบันของเดือนและปี (สำหรับบันทึกใน insurance_fund)
    current_year = now_str[:4]
    current_month = now_str[5:7]

    conn = get_db_connection()

    # ดึงข้อมูลคำขอจ่ายคืนเต็มก้อนจากตาราง insurance_repay_stop_request
    lumpsum_req = conn.execute("""
        SELECT stop_id, user_id, request_id, lumpsum_amount, status
        FROM insurance_repay_stop_request
        WHERE stop_id = ?
    """, (stop_id,)).fetchone()

    if not lumpsum_req:
        conn.close()
        flash("ไม่พบคำขอจ่ายคืนเต็มก้อนในระบบ", "warning")
        return redirect(url_for('hr_insurance_withdraw_list'))

    # ตรวจสอบสถานะของคำขอ ต้องอยู่ในสถานะ 'pending' เท่านั้น
    if lumpsum_req['status'] != 'pending':
        conn.close()
        flash("คำขอจ่ายคืนเต็มก้อนนี้ไม่อยู่ในสถานะ pending", "warning")
        return redirect(url_for('hr_insurance_withdraw_list'))

    user_id_val = lumpsum_req['user_id']
    request_id_val = lumpsum_req['request_id']
    lumpsum_amount = lumpsum_req['lumpsum_amount']

    # กำหนดสถานะใหม่ตาม action ที่ได้รับ
    new_status = 'approved' if action == 'approve' else 'rejected'

    # อัปเดตสถานะของคำขอในตาราง insurance_repay_stop_request (ไม่อ้างอิง updated_at หากไม่มี column ดังกล่าว)
    conn.execute("""
        UPDATE insurance_repay_stop_request
        SET status = ?
        WHERE stop_id = ?
    """, (new_status, stop_id))

    if new_status == 'approved':
        # เมื่ออนุมัติแล้ว ให้ update ทุก record ใน insurance_repay_plan ที่เกี่ยวข้อง (request_id เดิม) ที่อยู่ในสถานะ 'unpaid'
        conn.execute("""
            UPDATE insurance_repay_plan
            SET status = 'paid'
            WHERE request_id = ? AND status = 'unpaid'
        """, (request_id_val,))
        # **เพิ่มการบันทึกลงใน insurance_fund เพื่อบันทึกการจ่ายคืนเต็มก้อน**
        conn.execute("""
            INSERT INTO insurance_fund(
                user_id, month, year, deducted_amount, company_contribute,
                withdraw_amount, repay_amount, comment, created_at
            )
            VALUES (?, ?, ?, 0, 0, 0, ?, ?, ?)
        """, (user_id_val, current_month, current_year, lumpsum_amount, "Lumpsum Repay Approved", now_str))
        
        flash("อนุมัติคำขอจ่ายคืนเต็มก้อนเรียบร้อย", "success")

    else:
        flash("ปฏิเสธคำขอจ่ายคืนเต็มก้อนเรียบร้อย", "success")

    conn.commit()
    conn.close()
    return redirect(url_for('hr_insurance_withdraw_list'))




# แบบฟอร์ม ขอเรียกดูเงินประกันสะสม
@app.route('/hr/insurance_fund_form', methods=['GET','POST'])
@role_required('HR','ADMIN')
def insurance_fund_form():
    conn = get_db_connection()
    rows = conn.execute("""
        SELECT user_id, first_name, last_name, nickname, start_date
        FROM users
        WHERE role in ('HR', 'EMPLOYEE', 'MANAGER', 'SECRETARY')
        ORDER BY start_date
    """).fetchall()
    conn.close()

    if request.method == 'POST':
        selected = request.form.get('user_id')  # ได้ค่าเช่น 'ALL' หรือ '5' (string)
        return redirect(url_for('insurance_fund_list', val=selected))
        # เราจะส่ง param val=selected ไปยังฟังก์ชัน insurance_fund_list(val)

    else:
        # GET -> แสดงหน้า HTML ฟอร์ม
        html = """
        <h1>ประวัติเงินประกันสะสม</h1>
        <form method="POST">
          <p>เลือกพนักงาน:
            <select name="user_id">
              <option value="ALL">-- ALL --</option>
        """
        for r in rows:
            uid = r['user_id']
            name = f"{r['first_name']} {r['last_name']}"
            html += f'<option value="{uid}">{uid}: {name}</option>'
        html += """
            </select>
          </p>
          <button type="submit">ดูประวัติเงินประกัน</button>
        </form>
        <p><a href="/dashboard">กลับสู่หน้าหลัก</a></p>
        """
        return html

@app.route('/hr/insurance_fund_list/<val>')
@role_required('HR','ADMIN')
def insurance_fund_list(val):
    """
    ถ้า val == 'ALL' => แสดงประกันสะสมของทุก user
    ถ้า val เป็น user_id => แสดงเฉพาะ user_id นั้น
    มีการ loop สำหรับคำนวณ total_deduct, total_contrib, total_withdraw, total_repay
    แล้วสรุปยอด balance
    """
    conn = get_db_connection()

    if val == 'ALL':
        # ดึงทุกคน
        rows = conn.execute("""
            SELECT f.*, u.first_name, u.last_name
            FROM insurance_fund f
            JOIN users u ON f.user_id=u.user_id
            ORDER BY f.fund_id DESC
        """).fetchall()
        conn.close()

        # ประกาศตัวแปรสะสม
        total_deduct = 0
        total_contrib = 0
        total_withdraw = 0
        total_repay = 0

        html = "<h1>ประวัติเงินประกันสะสม (ALL)</h1>"
        html += """
        <table border='1'>
          <tr><th>user_id</th><th>ชื่อ</th><th>เดือน</th><th>ปี</th>
              <th>งวดเงินประกัน</th><th>บริษัทสมทบเพิ่ม</th><th>เบิกเงินสะสม</th><th>คืนเงินเบิกสะสมกลับ</th><th>comment</th></tr>
        """

        for r in rows:
            uid = r['user_id']
            fname = r['first_name']
            lname = r['last_name']
            mm = r['month']
            yy = r['year']
            d  = r['deducted_amount']
            c  = r['company_contribute']
            w  = r['withdraw_amount']
            rp = r['repay_amount']
            cm = r['comment'] or ''

            # สะสมค่า
            total_deduct += d
            total_contrib += c
            total_withdraw += w
            total_repay += rp

            # สร้างแถวในตาราง
            html += f"""
            <tr>
              <td>{uid}</td>
              <td>{fname} {lname}</td>
              <td>{mm}</td>
              <td>{yy}</td>
              <td>{d}</td>
              <td>{c}</td>
              <td>{w}</td>
              <td>{rp}</td>
              <td>{cm}</td>
            </tr>
            """

        html += "</table>"

        # คำนวณ Balance รวมของทุกคน
        balance = (total_deduct + total_contrib) - total_withdraw + total_repay

        html += f"<p>รวมยอดสะสม (ทุกคน): {balance} บาท</p>"
        html += """<p><a href="/dashboard">กลับสู่หน้าหลัก</a></p>"""
        return html

    else:
        # val เป็น user_id (string) => แปลงเป็น int
        user_id = int(val)

        rows = conn.execute("""
            SELECT *
            FROM insurance_fund
            WHERE user_id=?
            ORDER BY fund_id DESC
        """,(user_id,)).fetchall()
        conn.close()

        # สะสมค่า
        total_deduct = 0
        total_contrib = 0
        total_withdraw = 0
        total_repay = 0

        html = f"<h1>ประวัติเงินประกันสะสม (user_id={user_id})</h1>"
        html += "<table border='1'>"
        html += "<tr><th>เดือน</th><th>ปี</th><th>งวดเงินประกัน</th><th>บริษัทสมทบเพิ่ม</th><th>เบิกเงินสะสม</th><th>คืนเงินเบิกสะสมกลับ</th><th>comment</th></tr>"

        for r in rows:
            mm = r['month']
            yy = r['year']
            d = r['deducted_amount']
            c = r['company_contribute']
            w = r['withdraw_amount']
            rp= r['repay_amount']
            cm= r['comment'] or ''

            total_deduct += d
            total_contrib += c
            total_withdraw += w
            total_repay += rp

            html += f"<tr><td>{mm}</td><td>{yy}</td><td>{d}</td><td>{c}</td><td>{w}</td><td>{rp}</td><td>{cm}</td></tr>"

        html += "</table>"

        # คำนวณ Balance เฉพาะพนักงานคนนี้
        balance = (total_deduct + total_contrib) - total_withdraw + total_repay
        html += f"<p>รวมยอดสะสม: {balance} บาท</p>"

        html += """<p><a href="/dashboard">กลับสู่หน้าหลัก</a></p>"""
        return html



### -------------------------------------------
### Notifications
### -------------------------------------------
@app.route('/my_notifications')
@role_required('EMPLOYEE', 'HR', 'MANAGER', 'ADMIN', 'SECRETARY')
def my_notifications():
    user_id = session['user_id']

    conn = get_db_connection()
    rows = conn.execute("""
        SELECT notif_id, message, is_read, created_at
        FROM notifications
        WHERE user_id=?
        ORDER BY notif_id DESC
    """, (user_id,)).fetchall()
    conn.close()

    notifications = [
        {"notif_id": row["notif_id"], "message": row["message"], "is_read": row["is_read"], "created_at": row["created_at"]}
        for row in rows
    ]

    return render_template('notifications/my_notifications.html', notifications=notifications)

@app.route('/read_notification/<int:nid>')
@role_required('EMPLOYEE','HR','MANAGER', 'ADMIN', 'SECRETARY')
def read_notification(nid):
    user_id = session['user_id']
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM notifications WHERE notif_id=?",(nid,)).fetchone()
    if not row:
        conn.close()
        return "ไม่พบ notification"
    if row['user_id']!=user_id:
        conn.close()
        return "ไม่มีสิทธิ์"
    conn.execute("UPDATE notifications SET is_read=1 WHERE notif_id=?",(nid,))
    conn.commit()
    conn.close()
    return redirect(url_for('my_notifications'))



### -------------------------------------------
### Export CSV for OT
### -------------------------------------------
@app.route('/export_attendance')
@role_required('Admin','HR')
def export_attendance():
    conn = get_db_connection()
    rows = conn.execute("""
        SELECT attendance_id, user_id, checkin_time, checkout_time, ot_status
        FROM attendance
        ORDER BY attendance_id
    """).fetchall()
    conn.close()

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["attendance_id","user_id","checkin_time","checkout_time","ot_status"])
    for r in rows:
        writer.writerow([r['attendance_id'], r['user_id'], r['checkin_time'], r['checkout_time'], r['ot_status']])

    resp = make_response(output.getvalue())
    resp.headers["Content-Disposition"] = "attachment; filename=attendance.csv"
    resp.headers["Content-type"] = "text/csv"
    return resp



### -------------------------------------------
### Salary Setup ปรับฐานเงินเดือน
### -------------------------------------------
# HR Salary setup ทีละคน
@app.route('/hr/salary_setup', methods=['GET', 'POST'])
@role_required('HR')
def salary_setup():
    conn = get_db_connection()

    if request.method == 'POST':
        user_id = request.form.get('user_id')
        new_base_salary = float(request.form.get('new_base_salary'))
        effective_date = request.form.get('effective_date')
        reason = request.form.get('reason', 'ปรับฐานเงินเดือน')

        daily_wage = new_base_salary / 30
        hourly_wage = daily_wage / 8

        import datetime
        now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        conn.execute("""
            INSERT INTO salary_records (user_id, base_salary, daily_wage, hourly_wage, effective_date, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, new_base_salary, daily_wage, hourly_wage, effective_date, now_str))

        conn.execute("""
            INSERT INTO salary_history (user_id, new_salary, reason, effective_date, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, new_base_salary, reason, effective_date, now_str))

        conn.commit()
        conn.close()

        return render_template("hr/salary_setup_success.html", user_id=user_id, new_base_salary=new_base_salary, effective_date=effective_date)

    else:
        users = conn.execute("""
            SELECT user_id, first_name, last_name, nickname, start_date
            FROM users
            WHERE role in ('HR', 'EMPLOYEE', 'MANAGER', 'SECRETARY')
            ORDER BY start_date
        """).fetchall()
        print("Users:", [dict(user) for user in users])  # Debug Users

        selected_user_id = request.args.get('user_id')
        current_salary_info = None

        if selected_user_id:
            row = conn.execute("""
                SELECT base_salary, daily_wage, hourly_wage, effective_date
                FROM salary_records
                WHERE user_id=?
                ORDER BY salary_id DESC
                LIMIT 1
            """, (selected_user_id,)).fetchone()
            if row:
                current_salary_info = {
                    "base_salary": row["base_salary"],
                    "daily_wage": row["daily_wage"],
                    "hourly_wage": row["hourly_wage"],
                    "effective_date": row["effective_date"]
                }

        conn.close()

        return render_template("hr/salary_setup.html", users=users, selected_user_id=selected_user_id, current_salary_info=current_salary_info)

# ADMIN Salary setup ทุกคน
@app.route('/admin/salary_setup', methods=['GET', 'POST'])
@role_required('ADMIN')
def admin_salary_setup():
    conn = get_db_connection()
    if request.method == 'POST':
        # รับค่าจาก form สำหรับวันที่มีผลและเหตุผล
        effective_date = request.form.get('effective_date')
        reason = request.form.get('reason', 'ปรับฐานเงินเดือน')
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # รับค่า user_id และ new_base_salary จากแต่ละแถวในตาราง
        user_ids = request.form.getlist('user_id')
        new_base_salaries = request.form.getlist('new_base_salary')
        
        # วนลูปเพื่ออัปเดตฐานเงินเดือนใหม่สำหรับพนักงานที่มีค่า new_base_salary ไม่ว่าง
        for uid, new_salary in zip(user_ids, new_base_salaries):
            if new_salary.strip() != "":
                new_salary = float(new_salary)
                daily_wage = new_salary / 30
                hourly_wage = daily_wage / 8
                
                conn.execute("""
                    INSERT INTO salary_records (user_id, base_salary, daily_wage, hourly_wage, effective_date, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (uid, new_salary, daily_wage, hourly_wage, effective_date, now_str))
                
                conn.execute("""
                    INSERT INTO salary_history (user_id, new_salary, reason, effective_date, created_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (uid, new_salary, reason, effective_date, now_str))
        
        conn.commit()
        conn.close()
        flash("บันทึกฐานเงินเดือนใหม่เรียบร้อย", "success")
        return redirect(url_for('admin_salary_setup'))
    else:
        # GET: ดึงรายชื่อพนักงานที่มี role ที่ต้องการ
        employees = conn.execute("""
            SELECT user_id, first_name, last_name, nickname
            FROM users
            WHERE role in ('HR', 'EMPLOYEE', 'MANAGER', 'SECRETARY')
            ORDER BY user_id
        """).fetchall()
        
        # ดึงฐานเงินเดือนปัจจุบันล่าสุดของแต่ละพนักงาน
        salary_info = {}
        for emp in employees:
            row = conn.execute("""
                SELECT base_salary
                FROM salary_records
                WHERE user_id=?
                ORDER BY salary_id DESC
                LIMIT 1
            """, (emp['user_id'],)).fetchone()
            salary_info[emp['user_id']] = row['base_salary'] if row else None
        conn.close()
        
        return render_template("admin/salary_setup.html", employees=employees, salary_info=salary_info)



### -------------------------------------------
### Payroll Summary
### ------------------------------------------- 
# Payroll Summary
@app.route('/payroll_summary', methods=['GET'])
@role_required('EMPLOYEE', 'HR', 'MANAGER', 'SECRETARY')
def payroll_summary():
    user_id = session['user_id']
    current_year = datetime.now().year
    current_month = datetime.now().month

    year = int(request.args.get('year', current_year))
    month = int(request.args.get('month', current_month))

    conn = get_db_connection()

    # 1) Load payday_config เฉพาะ user + (year,month)
    row_pd = conn.execute("""
        SELECT salary_pay_day, welfare_pay_day
        FROM payday_config
        WHERE user_id=? AND year=? AND month=?
    """, (user_id, year, month)).fetchone()

    if not row_pd:
        # fallback: user_id=0
        row_pd = conn.execute("""
            SELECT salary_pay_day, welfare_pay_day
            FROM payday_config
            WHERE user_id=0 AND year=? AND month=?
        """, (year, month)).fetchone()

    if row_pd:
        salary_day  = row_pd['salary_pay_day']
        welfare_day = row_pd['welfare_pay_day']
    else:
        # ไม่มีในตาราง => default
        salary_day  = 28
        welfare_day = 10

    # 2) ตรวจสอบไม่ให้เลือกอนาคต
    start_date_row = conn.execute("""
        SELECT start_date 
        FROM users 
        WHERE user_id=?
    """, (user_id,)).fetchone()

    if start_date_row and start_date_row['start_date']:
        start_yyyy, start_mm, _ = start_date_row['start_date'].split('-')
        start_year = int(start_yyyy)
        start_month = int(start_mm)
    else:
        # ถ้าไม่มี start_date → สมมติเป็นปีปัจจุบัน
        start_year = current_year
        start_month = current_month

    # ไม่ให้เลือกอนาคต
    if year > current_year or (year == current_year and month > current_month):
        return "ไม่สามารถเลือกเดือนในอนาคตได้"

    # ไม่ให้เลือกก่อนเริ่มงาน
    if year < start_year or (year == start_year and month < start_month):
        return "ไม่สามารถเลือกเดือนก่อนวันที่เริ่มงานได้"

    # 3) ดึงข้อมูล user
    user_details = get_user_detail(user_id)
    if not user_details:
        return "ไม่พบข้อมูลพนักงาน"
    gender = f"{user_details['gender']}"
    employee_name = f"{user_details['first_name']} {user_details['last_name']}"

    # 4) เรียก calculate_payroll
    payroll = calculate_payroll(user_id, month, year)
    if 'error' in payroll:
        return f"ข้อผิดพลาด: {payroll['error']}"

    # คำนวณ Payroll Period
    payroll_start = date(year, month, 1)
    today = date.today()
    if year == today.year and month == today.month:
        # ถ้าเป็นเดือนปัจจุบัน (ยังไม่ครบเดือน) ให้ใช้วันที่ปัจจุบันเป็นวันสิ้นสุด
        payroll_end = today
    else:
        # ถ้าไม่ใช่เดือนปัจจุบัน ให้ใช้วันสุดท้ายของเดือนนั้น
        last_day = monthrange(year, month)[1]
        payroll_end = date(year, month, last_day)
    # ดึงชื่อเดือนจาก get_months()
    months_list = get_months()
    month_name = months_list[month - 1]['name']
    payroll_period = f"{payroll_start.day} {month_name} {year} - {payroll_end.day} {month_name} {year}"

    conn.close()

    return render_template(
        'payroll/payroll_summary.html',
        payroll=payroll,
        month=month,
        year=year,
        gender=gender,
        employee_name=employee_name,
        months=get_months(),
        years=range(start_year, current_year + 1),
        start_year=start_year,
        current_year=current_year,
        payroll_period=payroll_period,
        salary_day=salary_day,
        welfare_day=welfare_day
    )

# Payroll Summary ( ALL )
@app.route('/payroll_summary_all', methods=['GET'])
@role_required('ADMIN')
def payroll_summary_all():

    # 1) รับเดือน/ปี จาก GET (หรือใช้ค่า default)
    today = date.today()
    default_year  = today.year
    default_month = today.month

    year  = int(request.args.get('year', default_year))
    month = int(request.args.get('month', default_month))

    conn = get_db_connection()

    # 2) ดึงรายชื่อ user ที่มี base_salary > 0 (ใช้ MAX(sr.base_salary) กันซ้ำ)
    user_rows = conn.execute("""
        SELECT DISTINCT
            u.user_id,
            u.first_name,
            u.last_name,
            u.nickname,
            MAX(sr.base_salary) AS base_salary
        FROM users u
        JOIN salary_records sr ON sr.user_id = u.user_id
        WHERE sr.base_salary > 0
        GROUP BY u.user_id
        ORDER BY u.user_id
    """).fetchall()

    conn.close()

    payrolls = {}

    # เซ็ตเก็บ description incomes/deductions ทั้งหมด เพื่อจัด sort/union
    income_descriptions_set = set()
    deduction_descriptions_set = set()

    # 3) เรียกฟังก์ชัน calculate_payroll ทีละ user
    for u in user_rows:
        uid = u['user_id']

        # เรียก calculate_payroll
        p = calculate_payroll(uid, month, year)

        # เก็บใน dict
        payrolls[uid] = p

        if 'error' in p:
            # ถ้ามี error ก็จะไม่มี incomes/deductions รายละเอียด
            continue

        # สะสม incomes และ deductions เพื่อจะได้รู้ว่ามี description อะไรบ้าง
        for inc in p['incomes']:
            income_descriptions_set.add(inc['description'])
        for dd in p['deductions']:
            deduction_descriptions_set.add(dd['description'])

    # แปลงเป็น list + sort
    income_descriptions_list = sorted(list(income_descriptions_set))
    deduction_descriptions_list = sorted(list(deduction_descriptions_set))

    # 4) สร้าง row_data
    row_data = []

    # 4.1) Base Salary
    base_row = {
        "type": "base_salary",
        "description": "ฐานเงินเดือน",
        "value_map": {}
    }
    for u in user_rows:
        uid = u['user_id']
        p = payrolls[uid]
        val = 0.0
        if 'error' not in p:
            val = p.get('base_salary', 0.0)
        base_row["value_map"][uid] = val
    row_data.append(base_row)

    # 4.2) incomes
    for desc in income_descriptions_list:
        row_obj = {
            "type": "income",
            "description": desc,
            "value_map": {}
        }
        for u in user_rows:
            uid = u['user_id']
            p = payrolls[uid]
            val = 0.0
            if 'error' not in p:
                # วนหา incomes ตรง description
                for inc in p['incomes']:
                    if inc['description'] == desc:
                        val = inc['amount']
                        break
            row_obj["value_map"][uid] = val
        row_data.append(row_obj)

    # 4.3) sum_income
    sum_income_row = {
        "type": "sum_income",
        "description": "รวมรายได้",
        "value_map": {}
    }
    for u in user_rows:
        uid = u['user_id']
        p = payrolls[uid]
        val = 0.0
        if 'error' not in p:
            val = p.get('total_income', 0.0)  # เป็นรายได้สวัสดิการ (ไม่รวม base_salary)
        sum_income_row["value_map"][uid] = val
    row_data.append(sum_income_row)

    # 4.4) deductions
    for desc in deduction_descriptions_list:
        row_obj = {
            "type": "deduction",
            "description": desc,
            "value_map": {}
        }
        for u in user_rows:
            uid = u['user_id']
            p = payrolls[uid]
            val = 0.0
            if 'error' not in p:
                for dd in p['deductions']:
                    if dd['description'] == desc:
                        val = dd['amount']
                        break
            row_obj["value_map"][uid] = val
        row_data.append(row_obj)

    # 4.5) sum_deduction
    sum_ded_row = {
        "type": "sum_deduction",
        "description": "รวมยอดหัก",
        "value_map": {}
    }
    for u in user_rows:
        uid = u['user_id']
        p = payrolls[uid]
        val = 0.0
        if 'error' not in p:
            val = p.get('total_deductions', 0.0)
        sum_ded_row["value_map"][uid] = val
    row_data.append(sum_ded_row)

    # 4.6) net_salary => base_salary + total_income - total_deductions - other_deductions?
    #    แต่ใน calculate_payroll มันมี 'net_salary' (ไม่รวม base) หรือไม่?
    #    ดู code calculate_payroll ว่า net_salary = total_income - total_deductions
    #    แล้วค่อย + base_salary เองก็ได้
    net_row = {
        "type": "net_salary",
        "description": "รายรับจริง",
        "value_map": {}
    }
    for u in user_rows:
        uid = u['user_id']
        p = payrolls[uid]
        val = 0.0
        if 'error' not in p:
            # net_salary(เดิม) = total_income - total_deductions
            # เราต้อง + base_salary เอง
            base_sal = p.get('base_salary', 0.0)
            net_s    = p.get('net_salary', 0.0) # ถ้า net_salary ใน code เดิม = incomes - ded
            # ถ้า code เดิม net_salary แล้ว(ไม่รวม base_salary) => val = base_sal + net_s
            val = base_sal + net_s
        net_row["value_map"][uid] = round(val,2)
    row_data.append(net_row)

    # 4.7) other_deduction
    other_row = {
        "type": "other_deduction",
        "description": "หักส่วนตัว",
        "value_map": {}
    }
    for u in user_rows:
        uid = u['user_id']
        p = payrolls[uid]
        val = 0.0
        if 'error' not in p:
            val = p.get('total_other_deductions', 0.0)
        other_row["value_map"][uid] = val
    row_data.append(other_row)

    # 4.8) final => transfer_amount = net_salary - total_other
    #    ใน code เดิม transfer_amount = (total_income - total_deductions) - total_other
    #    หรือ (net_s) - total_other
    final_row = {
        "type": "final",
        "description": "ยอดโอนจริง",
        "value_map": {}
    }
    for u in user_rows:
        uid = u['user_id']
        p = payrolls[uid]
        val = 0.0
        if 'error' not in p:
            val = p.get('transfer_amount', 0.0)
        final_row["value_map"][uid] = val
    row_data.append(final_row)

    return render_template(
        "payroll/payroll_summary_all.html",
        row_data=row_data,
        user_list=user_rows,
        year=year,
        month=month
    )

# Payday config จัดการวันที่เงินเดือน / ค่าคอมฯออก
@app.route('/hr/payday_config', methods=['GET', 'POST'])
@role_required('HR','ADMIN')
def manage_payday_config():
    """
    จัดการวันจ่ายเงินเดือน/สวัสดิการรายเดือน
    - ถ้า user_id=0 => default สำหรับเดือนนั้น
    - ถ้า user_id=x => override เฉพาะคนนั้น
    """
    conn = get_db_connection()

    # A) สร้าง list เดือน/ปี ที่จะโชว์ในหน้า
    today = date.today()
    default_year = today.year
    default_month = today.month
    year = int(request.args.get('year', default_year))
    month = int(request.args.get('month', default_month))

    # ดึงข้อมูลพนักงานจากฐานข้อมูลเฉพาะ role HR, EMPLOYEE, MANAGER เท่านั้น
    user_rows = conn.execute("""
        SELECT user_id, first_name, last_name, nickname, start_date
        FROM users
        WHERE role in ('HR', 'EMPLOYEE', 'MANAGER')
        ORDER BY start_date
    """).fetchall()

    if request.method == 'POST':
        action = request.form.get('action', '')
        posted_year = int(request.form.get('post_year', year))
        posted_month = int(request.form.get('post_month', month))

        if action == 'update_single':
            # รับค่าจาก form
            uid_str = request.form.get('user_id')
            s_str = request.form.get('salary_pay_day','28')
            w_str = request.form.get('welfare_pay_day','10')
            try:
                uid = int(uid_str)
                s_day = int(s_str)
                w_day = int(w_str)
            except:
                flash("Invalid input for update_single", "danger")
                conn.close()
                return redirect(url_for('manage_payday_config', year=posted_year, month=posted_month))

            now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            # INSERT OR REPLACE
            conn.execute("""
                INSERT INTO payday_config(user_id, year, month, salary_pay_day, welfare_pay_day, updated_at)
                VALUES (?,?,?,?,?,?)
                ON CONFLICT(user_id, year, month) DO UPDATE
                  SET salary_pay_day=excluded.salary_pay_day,
                      welfare_pay_day=excluded.welfare_pay_day,
                      updated_at=excluded.updated_at
            """, (uid, posted_year, posted_month, s_day, w_day, now_str))
            conn.commit()

            flash(f"อัปเดตวันจ่าย (User={uid}, {posted_month}/{posted_year}) => Salary={s_day}, Welfare={w_day}", "success")
            conn.close()
            return redirect(url_for('manage_payday_config', year=posted_year, month=posted_month))

        elif action == 'update_all':
            # apply to all => user_id=0
            s_str = request.form.get('salary_pay_day_all','28')
            w_str = request.form.get('welfare_pay_day_all','10')
            try:
                s_day = int(s_str)
                w_day = int(w_str)
            except:
                flash("Invalid input for update_all", "danger")
                conn.close()
                return redirect(url_for('manage_payday_config', year=posted_year, month=posted_month))

            now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            conn.execute("""
                INSERT INTO payday_config(user_id, year, month, salary_pay_day, welfare_pay_day, updated_at)
                VALUES (0,?,?,?,?,?)
                ON CONFLICT(user_id, year, month) DO UPDATE
                  SET salary_pay_day=excluded.salary_pay_day,
                      welfare_pay_day=excluded.welfare_pay_day,
                      updated_at=excluded.updated_at
            """, (posted_year, posted_month, s_day, w_day, now_str))
            conn.commit()

            flash(f"Apply to ALL (user_id=0) for {posted_month}/{posted_year} => Salary={s_day}, Welfare={w_day}", "success")
            conn.close()
            return redirect(url_for('manage_payday_config', year=posted_year, month=posted_month))
        else:
            conn.close()
            flash("Unknown action", "danger")
            return redirect(url_for('manage_payday_config', year=posted_year, month=posted_month))

    else:
        # GET => ต้องการโชว์ค่า
        # 1) ดึง config user_id=0
        row_global = conn.execute("""
            SELECT salary_pay_day, welfare_pay_day
            FROM payday_config
            WHERE user_id=0 AND year=? AND month=?
        """, (year, month)).fetchone()
        global_salary = row_global['salary_pay_day'] if row_global else 28
        global_welfare= row_global['welfare_pay_day'] if row_global else 10

        # 2) ดึงของแต่ละ user
        row_users_cfg = conn.execute("""
            SELECT user_id, salary_pay_day, welfare_pay_day
            FROM payday_config
            WHERE year=? AND month=?
        """, (year, month)).fetchall()

        cfg_map = {}
        for r in row_users_cfg:
            cfg_map[r['user_id']] = {
                "salary": r['salary_pay_day'],
                "welfare": r['welfare_pay_day']
            }

        conn.close()
        return render_template(
            'hr/payday_config.html',
            user_rows=user_rows,
            cfg_map=cfg_map,
            year=year, month=month,
            global_salary=global_salary,
            global_welfare=global_welfare
        )





# ------------------------------------------- #
# ------------------------------------------- #
# ------------------------------------------- #
#                   'OPD'                     #
# ------------------------------------------- #
# ------------------------------------------- #
# ------------------------------------------- #



# Generate HN Automatic
def generate_hn():
    """
    สร้าง HN ตามเงื่อนไข:
    - HN เป็นตัวเลข 6 หลัก
    - 2 หลักแรก เป็นเลขปี พ.ศ. (นำ 2 หลักสุดท้ายของปี พ.ศ.)
    - 4 หลักท้าย เป็นลำดับจาก 0001-9999 โดยตรวจสอบจากฐานข้อมูล
    """
    from datetime import datetime
    # คำนวณปี พ.ศ. และ prefix
    buddhist_year = datetime.now().year + 543  # ปี พ.ศ.
    # สมมติให้เอา 2 หลักสุดท้ายของปี พ.ศ. มาใช้เป็น prefix เช่น 2568 -> "68"
    prefix = str(buddhist_year)[-2:]
    
    # Query ค่าที่มากที่สุดของ HN ที่ขึ้นต้นด้วย prefix นั้น
    conn = get_db_connection()
    cur = conn.execute("SELECT MAX(hn) as max_hn FROM customers WHERE hn LIKE ?", (f"{prefix}%",))
    row = cur.fetchone()
    conn.close()
    
    if row['max_hn']:
        # แยกเลขลำดับ 4 หลักท้าย และเพิ่มค่า
        last_number = int(str(row['max_hn'])[2:])
        new_number = last_number + 1
    else:
        new_number = 1
    
    # Format เลขลำดับให้เป็น 4 หลัก
    new_hn = f"{prefix}{new_number:04d}"
    return new_hn


# Calculate Age
def calculate_age(birthday_str):
    try:
        birthday = datetime.strptime(birthday_str, '%Y-%m-%d')
    except Exception as e:
        return "N/A"  # กรณีข้อมูลไม่ถูกต้อง
    today = datetime.today()
    years = today.year - birthday.year - ((today.month, today.day) < (birthday.month, birthday.day))
    months = today.month - birthday.month
    if today.day < birthday.day:
        months -= 1
    if months < 0:
        months += 12
    return f"{years} ปี {months} เดือน"


### Daily Income Helper
# Calculate payment
def _calculate_payment(req):
    """
    อ่านและคำนวณยอดชำระเงินจาก request.form (deposit_x, cash, transfer, credit_card, credit_card_fee)
    ถ้ามี Error ในการ cast เป็นตัวเลข ให้ raise ValueError
    """
    try:
        deposit_sum = 0
        for key in req.form:
            if key.startswith('deposit_') and not key.startswith('deposit_date_'):
                deposit_sum += int(float(req.form.get(key, 0)))
        cash = int(float(req.form.get('cash', 0)))
        transfer = int(float(req.form.get('transfer', 0)))
        credit_card = int(float(req.form.get('credit_card', 0)))
        credit_card_fee = int(float(req.form.get('credit_card_fee', 0)))
    except Exception as e:
        raise ValueError("Please enter valid payment amounts")

    return deposit_sum, cash, transfer, credit_card, credit_card_fee

# Calculate total price from procedures
def _calculate_total_price_from_procedures(procedures_data):
    """
    วนลูปใน procedures_data แล้วคำนวณราคารวม (pr_price1 + pr_price2 + pr_price3)
    """
    total_price = 0
    for proc in procedures_data:
        try:
            pr_price1 = int(float(proc.get('pr_price1') or 0))
            pr_price2 = int(float(proc.get('pr_price2') or 0))
            pr_price3 = int(float(proc.get('pr_price3') or 0))
        except:
            pr_price1 = pr_price2 = pr_price3 = 0
        total_price += (pr_price1 + pr_price2 + pr_price3)
    return total_price

# Insert daily income detail
def _insert_daily_income_detail(conn, header_id, proc_dict, created_at):
    """
    Insert ลง daily_income_detail 1 record 
    ใช้ข้อมูล procedure_doctor, category, short_code, pr_price1..3
    """
    procedure_category = proc_dict.get('procedure_category')
    procedure_name = proc_dict.get('procedure_name')
    procedure_short_code = proc_dict.get('procedure_short_code')
    try:
        pr_price1 = int(float(proc_dict.get('pr_price1') or 0))
        pr_price2 = int(float(proc_dict.get('pr_price2') or 0))
        pr_price3 = int(float(proc_dict.get('pr_price3') or 0))
    except:
        pr_price1 = pr_price2 = pr_price3 = 0

    proc_price = pr_price1 + pr_price2 + pr_price3
    pr_code1 = proc_dict.get('pr_code1')
    pr_code2 = proc_dict.get('pr_code2')
    pr_code3 = proc_dict.get('pr_code3')
    procedure_doctor = proc_dict.get('procedure_doctor')

    conn.execute("""
        INSERT INTO daily_income_detail
        (header_id, procedure_doctor, procedure_category, procedure_name, 
         procedure_short_code, procedure_price,
         pr_code1, pr_price1, pr_code2, pr_price2, 
         pr_code3, pr_price3, created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        header_id,
        procedure_doctor,
        procedure_category,
        procedure_name,
        procedure_short_code,
        proc_price,
        pr_code1, pr_price1,
        pr_code2, pr_price2,
        pr_code3, pr_price3,
        created_at
    ))

# Update daily income header
def _update_daily_income_header(conn, header_id, deposit, deposit_date, cash, transfer, credit_card, credit_card_fee, total_price):
    """
    Update daily_income_header ด้วยค่าที่แก้ไขใหม่ (deposit, cash, transfer, etc.)
    """
    conn.execute("""
        UPDATE daily_income_header
        SET deposit = ?,
            deposit_date = ?,
            cash = ?,
            transfer = ?,
            credit_card = ?,
            credit_card_fee = ?,
            total_price = ?
        WHERE id = ?
    """, (
        deposit,
        deposit_date,
        cash,
        transfer,
        credit_card,
        credit_card_fee,
        total_price,
        header_id
    ))


# Parse float value ถ้าเป็นช่องว่าง ('') บันทึกค่าเป็น 0.0
def parse_float_value(form_dict, field_name):
    """
    ยูทิลิตี้: รับ form_dict และชื่อฟิลด์, ถ้าเป็นช่องว่าง ('') หรือไม่มี => 0.0
    ถ้าไม่ว่าง => แปลงเป็น float
    """
    val_str = form_dict.get(field_name, '').strip()
    if val_str == '':
        return 0.0
    return float(val_str)


# Check AES commission editable
def check_aes_commission_editable(record_dt, current_role):
    """
    ตรวจสอบว่าจากเงื่อนไข:
     - ถ้า employee => แก้ไขได้เฉพาะ "วันนี้" หรือ "เมื่อวาน"
     - ถ้า manager  => แก้ไขได้เฉพาะเคสที่อยู่ใน "เดือนปัจจุบัน" หรือ "เดือนก่อนปัจจุบัน 1 เดือน"

    return True/False
    """
    today = date.today()

    if current_role == "EMPLOYEE":
        # allow only today or yesterday
        delta_days = (today - record_dt).days
        # ถ้า 0 = วันนี้, 1 = เมื่อวาน => True, นอกนั้น False
        if delta_days in [0,1]:
            return True
        else:
            return False

    elif current_role == "MANAGER":
        # allow only "this month" or "previous month"
        # วิธีหนึ่ง: เทียบ (year, month) ของ record_dt กับ (year, month) ปัจจุบัน
        record_year = record_dt.year
        record_month = record_dt.month

        this_year = today.year
        this_month = today.month

        # สร้าง set ของ (year,month) ที่อนุญาต
        # 1) เดือนปัจจุบัน
        allowed = {(this_year, this_month)}
        # 2) เดือนก่อนปัจจุบัน (handle ข้ามปี)
        prev_month = this_month - 1
        prev_year = this_year
        if prev_month < 1:
            prev_month = 12
            prev_year -= 1
        allowed.add((prev_year, prev_month))

        if (record_year, record_month) in allowed:
            return True
        else:
            return False

    else:
        # role อื่นไม่ให้แก้
        return False


# Edit Translate Commission
def can_edit_translate(record_dt: date, user_role: str) -> bool:
    today = date.today()
    # แตกเดือน-ปีปัจจุบัน
    this_year, this_month = today.year, today.month
    # แตกเดือน-ปีของ record_dt
    ry, rm = record_dt.year, record_dt.month

    if user_role == 'EMPLOYEE':
        return (ry == this_year and rm == this_month)
    elif user_role in ('HR','ADMIN'):
        # เดือนปัจจุบัน + เดือนก่อน
        allowed = set()
        allowed.add((this_year,this_month))
        prev_m = this_month - 1
        prev_y = this_year
        if prev_m < 1:
            prev_m = 12
            prev_y -= 1
        allowed.add((prev_y, prev_m))
        return (ry, rm) in allowed
    else:
        return False



### -------------------------------------------
### Customer Registration
### ------------------------------------------- 
# 1. Customer Database TH
@app.route('/customer_database_th', methods=['GET', 'POST'])
@role_required('OPD', 'PATIENT')
def customer_database_th():
    if request.method == 'POST':

        HN                      = generate_hn()
        prefix                  = request.form.get('prefix')
        first_name              = request.form.get('first_name')
        last_name               = request.form.get('last_name')
        first_service_date      = datetime.now().strftime('%Y-%m-%d')  # วันที่เข้ารับบริการครั้งแรก
        nickname                = request.form.get('nickname')

        # เบอร์โทร และ รหัสประเทศ
        country_code = request.form.get('country_code')
        if country_code == "other":
            # หากเลือก "อื่นๆ" ให้ดึงค่าจาก custom_country_code
            custom_code = request.form.get('custom_country_code', '').strip()
            # ตรวจสอบว่า custom_code มีเครื่องหมาย '+' หรือไม่ ถ้าไม่มีก็เติมให้
            if not custom_code.startswith('+'):
                custom_code = '+' + custom_code
            country_code = custom_code
        phone_number = request.form.get('phone')
        # รายชื่อรหัสประเทศที่ต้องตัด trunk prefix (เช่นเลข 0) ออก
        countries_with_trunk_prefix = ['+66', '+62', '+60', '+95', '+856', '+855', '+44', '+61', '+81', '+86', '+49', '+33', '+91']
        # ถ้า country_code อยู่ในรายชื่อที่ต้องตัด trunk prefix และเบอร์โทรขึ้นต้นด้วย 0 ให้ตัดออก
        if country_code in countries_with_trunk_prefix and phone_number.startswith('0'):
            phone_number = phone_number[1:]
        phone = country_code + phone_number


        # เลขบัตรประชาชน (เพราะใน frontend ไม่มีตัวเลือก passport อีกแล้ว)
        id_value = request.form.get('id_value', '').strip()
        if not id_value.isdigit() or len(id_value) != 13:
            flash("กรุณากรอกเลขบัตรประจำตัวประชาชนให้ครบ 13 หลัก", "danger")
            return redirect(url_for('customer_database_th'))
        id_card_or_passport = id_value

        birthday                = request.form.get('birthday')

        # สัญชาติ
        nationality = request.form.get('nationality')
        if nationality == "อื่นๆ":
            nationality_other = request.form.get('nationality_other', '').strip()
            if nationality_other:
                nationality = nationality_other
            else:
                nationality = ""
                flash("กรุณาระบุสัญชาติในช่อง 'อื่นๆ'", "danger")

        address                 = request.form.get('address')
        occupation              = request.form.get('occupation')
        emergency_contact       = request.form.get('emergency_contact')
        emergency_relationship  = request.form.get('emergency_relationship')
        emergency_phone         = request.form.get('emergency_phone')

        # ประวัติแพ้ยา
        drug_allergy_choice = request.form.get('drug_allergy_history_choice')
        if drug_allergy_choice == 'มี':
            drug_allergy_history = request.form.get('drug_allergy_details', '').strip()
            symptoms = request.form.get('drug_allergy_symptoms', '').strip()
            if symptoms:
                drug_allergy_history = f"{drug_allergy_history} ({symptoms})"
        else:
            drug_allergy_history = ""
        drug_allergy_symptoms = ""

        # โรคประจำตัว
        chronic_disease_choice = request.form.get('chronic_disease_choice')
        if chronic_disease_choice == 'มี':
            chronic_disease = request.form.get('chronic_disease_details', '').strip()
        else:
            chronic_disease = ''

        # ยาที่ใช้อยู่ในปัจจุบัน
        current_medications_choice = request.form.get('current_medications_choice')
        if current_medications_choice == 'มี':
            current_medications = request.form.get('current_medications_details', '').strip()
        else:
            current_medications = ''

        # ศัลยกรรมที่เคยทำ (checkbox group)
        previous_surgeries_list = request.form.getlist('previous_surgeries')
        if "อื่นๆ" in previous_surgeries_list:
            other_surgery = request.form.get('surgery_other_text', '').strip()
            previous_surgeries_list.remove("อื่นๆ")
            if other_surgery:
                previous_surgeries_list.append(f"อื่นๆ: {other_surgery}")
            else:
                previous_surgeries_list.append("อื่นๆ")
        previous_surgeries = ", ".join(previous_surgeries_list)

        # ช่องทางที่รู้จักคลินิกของเรา (checkbox group)
        referral_channel_list = request.form.getlist('referral_channel')
        if "อื่นๆ" in referral_channel_list:
            referral_other = request.form.get('referral_other_text', '').strip()
            referral_channel_list.remove("อื่นๆ")
            if referral_other:
                referral_channel_list.append(f"อื่นๆ: {referral_other}")
            else:
                referral_channel_list.append("อื่นๆ")
        referral_channel = ", ".join(referral_channel_list)

        # เหตุผลที่เลือกคลินิกของเรา (checkbox group)
        reason_to_choose_clinic_list = request.form.getlist('reason_to_choose_clinic')
        if "อื่นๆ" in reason_to_choose_clinic_list:
            reason_other = request.form.get('reason_other_text', '').strip()
            reason_to_choose_clinic_list.remove("อื่นๆ")
            if reason_other:
                reason_to_choose_clinic_list.append(f"อื่นๆ: {reason_other}")
            else:
                reason_to_choose_clinic_list.append("อื่นๆ")
        reason_to_choose_clinic = ", ".join(reason_to_choose_clinic_list)

        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        conn = get_db_connection()
        try:
            conn.execute("""
                INSERT INTO customers 
                (hn, prefix, first_name, last_name, first_service_date, nickname, phone, birthday, nationality, address, occupation, id_card_or_passport, emergency_contact, emergency_relationship, emergency_phone, drug_allergy_history, drug_allergy_symptoms, chronic_disease, current_medications, previous_surgeries, referral_channel, reason_to_choose_clinic, created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                HN, prefix, first_name, last_name, first_service_date, nickname, phone, birthday, nationality, address, occupation, id_card_or_passport, emergency_contact, emergency_relationship, emergency_phone, drug_allergy_history, drug_allergy_symptoms, chronic_disease, current_medications, previous_surgeries, referral_channel, reason_to_choose_clinic, now_str
            ))
            conn.commit()
            flash("ลงทะเบียนลูกค้าสำเร็จ", "success")
        except Exception as e:
            conn.rollback()
            print("Error during INSERT:", e)
            flash(f"เกิดข้อผิดพลาด: {e}", "danger")
        finally:
            conn.close()
        return redirect(url_for('customer_database_th'))
    else:
        current_date = datetime.now().strftime('%Y-%m-%d')
        return render_template('opd/customer_database_th.html', current_date=current_date)

# 2. Customer Database EN
@app.route('/customer_database_en', methods=['GET', 'POST'])
@role_required('OPD', 'PATIENT')
def customer_database_en():
    if request.method == 'POST':

        HN                      = generate_hn()
        prefix                  = request.form.get('prefix')
        first_name              = request.form.get('first_name')
        last_name               = request.form.get('last_name')
        first_service_date      = datetime.now().strftime('%Y-%m-%d')  # วันที่เข้ารับบริการครั้งแรก
        nickname                = request.form.get('nickname')

        # เบอร์โทร และ รหัสประเทศ
        country_code = request.form.get('country_code')
        if country_code == "other":
            # หากเลือก "อื่นๆ" ให้ดึงค่าจาก custom_country_code
            custom_code = request.form.get('custom_country_code', '').strip()
            # ตรวจสอบว่า custom_code มีเครื่องหมาย '+' หรือไม่ ถ้าไม่มีก็เติมให้
            if not custom_code.startswith('+'):
                custom_code = '+' + custom_code
            country_code = custom_code

        phone_number = request.form.get('phone')

        # รายชื่อรหัสประเทศที่ต้องตัด trunk prefix (เช่นเลข 0) ออก
        countries_with_trunk_prefix = ['+66', '+62', '+60', '+95', '+856', '+855', '+44', '+61', '+81', '+86', '+49', '+33', '+91']

        # ถ้า country_code อยู่ในรายชื่อที่ต้องตัด trunk prefix และเบอร์โทรขึ้นต้นด้วย 0 ให้ตัดออก
        if country_code in countries_with_trunk_prefix and phone_number.startswith('0'):
            phone_number = phone_number[1:]
        phone = country_code + phone_number

        # เลขบัตรประชาชน/พาสปอร์ต
        id_value = request.form.get('id_value', '').strip()
        if not id_value:
            flash("Please enter Passport number", "danger")
            return redirect(url_for('customer_database_en'))
        id_card_or_passport = id_value

        birthday                = request.form.get('birthday')

        # สัญชาติ
        nationality = request.form.get('nationality')
        if nationality == "อื่นๆ":
            nationality_other = request.form.get('nationality_other', '').strip()
            if nationality_other:
                nationality = nationality_other
            else:
                nationality = ""
                flash("กรุณาระบุสัญชาติในช่อง 'อื่นๆ'", "danger")

        address                 = request.form.get('address')
        occupation              = request.form.get('occupation')
        emergency_contact       = request.form.get('emergency_contact')
        emergency_relationship  = request.form.get('emergency_relationship')
        emergency_phone         = request.form.get('emergency_phone')

        # ประวัติแพ้ยา
        drug_allergy_choice = request.form.get('drug_allergy_history_choice')
        if drug_allergy_choice == 'มี':
            drug_allergy_history = request.form.get('drug_allergy_details', '').strip()
            symptoms = request.form.get('drug_allergy_symptoms', '').strip()
            if symptoms:
                drug_allergy_history = f"{drug_allergy_history} ({symptoms})"
        else:
            drug_allergy_history = ""
        drug_allergy_symptoms = ""

        # โรคประจำตัว
        chronic_disease_choice = request.form.get('chronic_disease_choice')
        if chronic_disease_choice == 'มี':
            chronic_disease = request.form.get('chronic_disease_details', '').strip()
        else:
            chronic_disease = ''

        # ยาที่ใช้อยู่ในปัจจุบัน
        current_medications_choice = request.form.get('current_medications_choice')
        if current_medications_choice == 'มี':
            current_medications = request.form.get('current_medications_details', '').strip()
        else:
            current_medications = ''

        # ศัลยกรรมที่เคยทำ (checkbox group)
        previous_surgeries_list = request.form.getlist('previous_surgeries')
        if "อื่นๆ" in previous_surgeries_list:
            other_surgery = request.form.get('surgery_other_text', '').strip()
            previous_surgeries_list.remove("อื่นๆ")
            if other_surgery:
                previous_surgeries_list.append(f"อื่นๆ: {other_surgery}")
            else:
                previous_surgeries_list.append("อื่นๆ")
        previous_surgeries = ", ".join(previous_surgeries_list)

        # ช่องทางที่รู้จักคลินิกของเรา (checkbox group)
        referral_channel_list = request.form.getlist('referral_channel')
        if "อื่นๆ" in referral_channel_list:
            referral_other = request.form.get('referral_other_text', '').strip()
            referral_channel_list.remove("อื่นๆ")
            if referral_other:
                referral_channel_list.append(f"อื่นๆ: {referral_other}")
            else:
                referral_channel_list.append("อื่นๆ")
        referral_channel = ", ".join(referral_channel_list)

        # เหตุผลที่เลือกคลินิกของเรา (checkbox group)
        reason_to_choose_clinic_list = request.form.getlist('reason_to_choose_clinic')
        if "อื่นๆ" in reason_to_choose_clinic_list:
            reason_other = request.form.get('reason_other_text', '').strip()
            reason_to_choose_clinic_list.remove("อื่นๆ")
            if reason_other:
                reason_to_choose_clinic_list.append(f"อื่นๆ: {reason_other}")
            else:
                reason_to_choose_clinic_list.append("อื่นๆ")
        reason_to_choose_clinic = ", ".join(reason_to_choose_clinic_list)

        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        conn = get_db_connection()
        try:
            conn.execute("""
                INSERT INTO customers 
                (hn, prefix, first_name, last_name, first_service_date, nickname, phone, birthday, nationality, address, occupation, id_card_or_passport, emergency_contact, emergency_relationship, emergency_phone, drug_allergy_history, drug_allergy_symptoms, chronic_disease, current_medications, previous_surgeries, referral_channel, reason_to_choose_clinic, created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                HN, prefix, first_name, last_name, first_service_date, nickname, phone, birthday, nationality, address, occupation, id_card_or_passport, emergency_contact, emergency_relationship, emergency_phone, drug_allergy_history, drug_allergy_symptoms, chronic_disease, current_medications, previous_surgeries, referral_channel, reason_to_choose_clinic, now_str
            ))
            conn.commit()
            flash("ลงทะเบียนลูกค้าสำเร็จ", "success")
        except Exception as e:
            conn.rollback()
            print("Error during INSERT:", e)
            flash(f"เกิดข้อผิดพลาด: {e}", "danger")
        finally:
            conn.close()
        return redirect(url_for('customer_database_en'))
    else:
        current_date = datetime.now().strftime('%Y-%m-%d')
        return render_template('opd/customer_database_en.html', current_date=current_date)

# 3. Customer Database EN
@app.route('/customer_database_indo', methods=['GET', 'POST'])
@role_required('OPD', 'PATIENT')
def customer_database_indo():
    if request.method == 'POST':

        HN                      = generate_hn()
        prefix                  = request.form.get('prefix')
        first_name              = request.form.get('first_name')
        last_name               = request.form.get('last_name')
        first_service_date      = datetime.now().strftime('%Y-%m-%d')  # วันที่เข้ารับบริการครั้งแรก
        nickname                = request.form.get('nickname')

        # เบอร์โทร และ รหัสประเทศ
        country_code = request.form.get('country_code')
        if country_code == "other":
            # หากเลือก "อื่นๆ" ให้ดึงค่าจาก custom_country_code
            custom_code = request.form.get('custom_country_code', '').strip()
            # ตรวจสอบว่า custom_code มีเครื่องหมาย '+' หรือไม่ ถ้าไม่มีก็เติมให้
            if not custom_code.startswith('+'):
                custom_code = '+' + custom_code
            country_code = custom_code

        phone_number = request.form.get('phone')

        # รายชื่อรหัสประเทศที่ต้องตัด trunk prefix (เช่นเลข 0) ออก
        countries_with_trunk_prefix = ['+66', '+62', '+60', '+95', '+856', '+855', '+44', '+61', '+81', '+86', '+49', '+33', '+91']

        # ถ้า country_code อยู่ในรายชื่อที่ต้องตัด trunk prefix และเบอร์โทรขึ้นต้นด้วย 0 ให้ตัดออก
        if country_code in countries_with_trunk_prefix and phone_number.startswith('0'):
            phone_number = phone_number[1:]
        phone = country_code + phone_number

        # เลขบัตรประชาชน/พาสปอร์ต
        id_value = request.form.get('id_value', '').strip()
        if not id_value:
            flash("Please enter Passport number", "danger")
            return redirect(url_for('customer_database_indo'))
        id_card_or_passport = id_value

        birthday                = request.form.get('birthday')

        # สัญชาติ
        nationality = request.form.get('nationality')
        if nationality == "อื่นๆ":
            nationality_other = request.form.get('nationality_other', '').strip()
            if nationality_other:
                nationality = nationality_other
            else:
                nationality = ""
                flash("กรุณาระบุสัญชาติในช่อง 'อื่นๆ'", "danger")

        address                 = request.form.get('address')
        occupation              = request.form.get('occupation')
        emergency_contact       = request.form.get('emergency_contact')
        emergency_relationship  = request.form.get('emergency_relationship')
        emergency_phone         = request.form.get('emergency_phone')

        # ประวัติแพ้ยา
        drug_allergy_choice = request.form.get('drug_allergy_history_choice')
        if drug_allergy_choice == 'มี':
            drug_allergy_history = request.form.get('drug_allergy_details', '').strip()
            symptoms = request.form.get('drug_allergy_symptoms', '').strip()
            if symptoms:
                drug_allergy_history = f"{drug_allergy_history} ({symptoms})"
        else:
            drug_allergy_history = ""
        drug_allergy_symptoms = ""

        # โรคประจำตัว
        chronic_disease_choice = request.form.get('chronic_disease_choice')
        if chronic_disease_choice == 'มี':
            chronic_disease = request.form.get('chronic_disease_details', '').strip()
        else:
            chronic_disease = ''

        # ยาที่ใช้อยู่ในปัจจุบัน
        current_medications_choice = request.form.get('current_medications_choice')
        if current_medications_choice == 'มี':
            current_medications = request.form.get('current_medications_details', '').strip()
        else:
            current_medications = ''

        # ศัลยกรรมที่เคยทำ (checkbox group)
        previous_surgeries_list = request.form.getlist('previous_surgeries')
        if "อื่นๆ" in previous_surgeries_list:
            other_surgery = request.form.get('surgery_other_text', '').strip()
            previous_surgeries_list.remove("อื่นๆ")
            if other_surgery:
                previous_surgeries_list.append(f"อื่นๆ: {other_surgery}")
            else:
                previous_surgeries_list.append("อื่นๆ")
        previous_surgeries = ", ".join(previous_surgeries_list)

        # ช่องทางที่รู้จักคลินิกของเรา (checkbox group)
        referral_channel_list = request.form.getlist('referral_channel')
        if "อื่นๆ" in referral_channel_list:
            referral_other = request.form.get('referral_other_text', '').strip()
            referral_channel_list.remove("อื่นๆ")
            if referral_other:
                referral_channel_list.append(f"อื่นๆ: {referral_other}")
            else:
                referral_channel_list.append("อื่นๆ")
        referral_channel = ", ".join(referral_channel_list)

        # เหตุผลที่เลือกคลินิกของเรา (checkbox group)
        reason_to_choose_clinic_list = request.form.getlist('reason_to_choose_clinic')
        if "อื่นๆ" in reason_to_choose_clinic_list:
            reason_other = request.form.get('reason_other_text', '').strip()
            reason_to_choose_clinic_list.remove("อื่นๆ")
            if reason_other:
                reason_to_choose_clinic_list.append(f"อื่นๆ: {reason_other}")
            else:
                reason_to_choose_clinic_list.append("อื่นๆ")
        reason_to_choose_clinic = ", ".join(reason_to_choose_clinic_list)

        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        conn = get_db_connection()
        try:
            conn.execute("""
                INSERT INTO customers 
                (hn, prefix, first_name, last_name, first_service_date, nickname, phone, birthday, nationality, address, occupation, id_card_or_passport, emergency_contact, emergency_relationship, emergency_phone, drug_allergy_history, drug_allergy_symptoms, chronic_disease, current_medications, previous_surgeries, referral_channel, reason_to_choose_clinic, created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                HN, prefix, first_name, last_name, first_service_date, nickname, phone, birthday, nationality, address, occupation, id_card_or_passport, emergency_contact, emergency_relationship, emergency_phone, drug_allergy_history, drug_allergy_symptoms, chronic_disease, current_medications, previous_surgeries, referral_channel, reason_to_choose_clinic, now_str
            ))
            conn.commit()
            flash("ลงทะเบียนลูกค้าสำเร็จ", "success")
        except Exception as e:
            conn.rollback()
            print("Error during INSERT:", e)
            flash(f"เกิดข้อผิดพลาด: {e}", "danger")
        finally:
            conn.close()
        return redirect(url_for('customer_database_indo'))
    else:
        current_date = datetime.now().strftime('%Y-%m-%d')
        return render_template('opd/customer_database_indo.html', current_date=current_date)

# 4. View Customer List
@app.route('/customer_list')
@role_required('OPD', 'ADMIN', 'DOCTOR')
def customer_list():
    page = request.args.get('page', 1, type=int)
    per_page = 100
    offset = (page - 1) * per_page
    
    conn = get_db_connection()
    total = conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
    customers = conn.execute("SELECT * FROM customers ORDER BY hn DESC LIMIT ? OFFSET ?", (per_page, offset)).fetchall()
    conn.close()
    
    customer_list = []
    for customer in customers:
        customer_dict = dict(customer)
        birthday_val = customer_dict.get('birthday', '')
        customer_dict['calculated_age'] = calculate_age(birthday_val)
        customer_list.append(customer_dict)
     
    total_pages = (total + per_page - 1) // per_page

    return render_template('opd/customer_list.html', customers=customer_list, page=page, total_pages=total_pages)

# 5. Search Customer List
@app.route('/search_customer', methods=['GET'])
@role_required('OPD', 'ADMIN')
def search_customer():
    # รับค่า query จาก URL (เช่น /search_customer?q=some_keyword)
    query = request.args.get('q', '').strip()
    # รับค่า view_type จาก URL (เช่น ?view=daily_income หรือ ?view=customer_list)
    view_type = request.args.get('view', 'customer_list').strip()  # ค่าเริ่มต้นคือ customer_list

    conn = get_db_connection()
    results = []
    if query:
        search_term = f"%{query}%"
        sql = """
            SELECT * FROM customers
            WHERE hn LIKE ?
              OR first_name LIKE ?
              OR last_name LIKE ?
              OR nickname LIKE ?
              OR phone LIKE ?
            ORDER BY created_at DESC
        """
        results = conn.execute(sql, (search_term, search_term, search_term, search_term, search_term)).fetchall()
    
    # ดึงรายชื่อคนไข้ทั้งหมด (สำหรับแสดงตารางหลัก)
    all_customers = conn.execute("SELECT * FROM customers ORDER BY hn DESC").fetchall()
    conn.close()
    
    # หาก view_type เป็น daily_income ให้ส่งข้อมูลไปหน้า daily_income.html
    if view_type == 'daily_income':
        # นอกจากข้อมูลลูกค้าแล้ว ยังต้องส่งข้อมูลเพิ่มเติมสำหรับหน้า daily_income
        # (doctors, procedures, users, daily_income_list ฯลฯ) โดยดึงข้อมูลจากฐานข้อมูลเช่นเคย
        conn = get_db_connection()
        doctors = conn.execute("SELECT doctor_id, short_name FROM doctors").fetchall()
        procedures = conn.execute("SELECT id, category_name, procedure_name, short_code, price FROM procedures").fetchall()
        procedures = [dict(row) for row in procedures]
        users = conn.execute("SELECT user_id, pr_code FROM users").fetchall()
        daily_income_list = conn.execute("""
            SELECT dih.*, c.first_name || ' ' || c.last_name AS customer_name
            FROM daily_income_header dih
            JOIN customers c ON dih.customer_id = c.id
            ORDER BY dih.created_at DESC
        """).fetchall()
        conn.close()
        return render_template('opd/daily_income.html', 
                               search_results=results, 
                               search_query=query, 
                               customers=all_customers,
                               doctors=doctors, 
                               procedures=procedures, 
                               users=users, 
                               daily_income_list=daily_income_list)
    else:
        # ถ้า view_type ไม่ใช่ daily_income ให้ส่งไปหน้า customer_list ทั่วไป
        return render_template('opd/customer_list.html', 
                               search_results=results, 
                               search_query=query, 
                               customers=all_customers)



### -------------------------------------------
### Procedures
### ------------------------------------------- 
# 1. Add & View Procedures
@app.route('/procedures', methods=['GET', 'POST'])
@role_required("OPD", "ADMIN")
def procedures():
    # กำหนด valid subsets สำหรับ procedure_name สำหรับแต่ละ category
    valid_procedures = {
        "SX": ["จมูก(ปิด)", "จมูก(โอเพ่น)", "คาง", "เหนียง", "ปาก", "Fat Graft", "ตา คิ้ว", "ดึงหน้า", "หน้าอก"],
        "AES": ["แพ็คเกจรวม", "Botox", "Filler", "Fat", "ร้อยไหม", "ดริปวิตามิน", "งานผิว"],
        "AFC": ["Set AFC", "ยาทารอย", "Anita", "น้ำลดบวม", "น้ำยาบ้วนปาก", "ยาหยอด", "Cool Pack"],
        "ค่ายาและบริการ": ["ค่ายา", "ค่าโรงพยาบาล", "ตรวจแลป", "จ้างพยาบาล/ผู้ช่วย", "ทำแผล ตัดไหม"],
        "อื่นๆ": ["ปากกาลดน้ำหนัก", "ล้างเล็บ", "อื่นๆ"]
    }
    
    if request.method == 'POST':
        category_name   = request.form.get('category_name')
        # procedure_name ควรอยู่ใน subset ที่กำหนดไว้ เช่น "nose", "chin", "lip" สำหรับ surgery
        procedure_name  = request.form.get('procedure_name')
        # ในฟิลด์ short_code ให้เก็บชื่อเต็มหรือรายละเอียดจริงของ procedure
        short_code      = request.form.get('short_code')
        price           = request.form.get('price')
        now_str         = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # ตรวจสอบความถูกต้องของ category
        if category_name not in valid_procedures:
            flash("Invalid procedure category", "danger")
            return redirect(url_for('procedures'))
        
        # ตรวจสอบว่า procedure_name ที่ส่งมานั้นอยู่ใน subset ที่อนุญาตหรือไม่
        if procedure_name not in valid_procedures[category_name]:
            flash("Procedure name must be one of: " + ", ".join(valid_procedures[category_name]), "danger")
            return redirect(url_for('procedures'))
        
        # ตรวจสอบว่า short_code (ชื่อเต็มหรือรายละเอียด) ถูกระบุหรือไม่
        if not short_code:
            flash("Please provide the full procedure name in the Short Code field", "danger")
            return redirect(url_for('procedures'))
        
        conn = get_db_connection()
        try:
            conn.execute("""
                INSERT INTO procedures 
                (category_name, procedure_name, short_code, price, created_at)
                VALUES (?,?,?,?,?)
            """, (category_name, procedure_name, short_code, price, now_str))
            conn.commit()
            flash("Procedure added successfully", "success")
        except Exception as e:
            conn.rollback()
            flash(f"An error occurred: {e}", "danger")
        finally:
            conn.close()
        return redirect(url_for('procedures'))
    else:
        conn = get_db_connection()
        procedures = conn.execute("SELECT * FROM procedures ORDER BY procedure_name DESC").fetchall()
        procedures = [dict(row) for row in procedures]
        conn.close()
        return render_template('admin/procedures.html', procedure_list=procedures, valid_procedures=valid_procedures)

# 2. Edit Procedures
@app.route('/edit_procedure/<int:procedure_id>', methods=['GET', 'POST'])
@role_required("OPD", "ADMIN")
def edit_procedure(procedure_id):
    # กำหนด valid subsets สำหรับ procedure_name สำหรับแต่ละ category
    valid_procedures = {
        "SX": ["จมูก(ปิด)", "จมูก(โอเพ่น)", "คาง", "เหนียง", "ปาก", "Fat Graft", "ตา คิ้ว", "ดึงหน้า", "หน้าอก"],
        "AES": ["แพ็คเกจรวม", "Botox", "Filler", "Fat", "ร้อยไหม", "ดริปวิตามิน", "งานผิว"],
        "AFC": ["Set AFC", "ยาทารอย", "Anita", "น้ำลดบวม", "น้ำยาบ้วนปาก", "ยาหยอด", "Cool Pack"],
        "ค่ายาและบริการ": ["ค่ายา", "ค่าโรงพยาบาล", "ตรวจแลป", "จ้างพยาบาล/ผู้ช่วย", "ทำแผล ตัดไหม"],
        "อื่นๆ": ["ปากกาลดน้ำหนัก", "ล้างเล็บ", "อื่นๆ"]
    }
    
    conn = get_db_connection()
    if request.method == 'POST':
        category_name   = request.form.get('category_name')
        procedure_name  = request.form.get('procedure_name')
        short_code      = request.form.get('short_code')
        price           = request.form.get('price')
        now_str         = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # ตรวจสอบความถูกต้องของ category และ procedure_name
        if category_name not in valid_procedures:
            flash("Invalid procedure category", "danger")
            return redirect(url_for('edit_procedure', procedure_id=procedure_id))
        if procedure_name not in valid_procedures[category_name]:
            flash("Procedure name must be one of: " + ", ".join(valid_procedures[category_name]), "danger")
            return redirect(url_for('edit_procedure', procedure_id=procedure_id))
        if not short_code:
            flash("Please provide the full procedure name in the Short Code field", "danger")
            return redirect(url_for('edit_procedure', procedure_id=procedure_id))
        
        try:
            conn.execute("""
                UPDATE procedures
                SET category_name = ?,
                    procedure_name = ?,
                    short_code = ?,
                    price = ?,
                    created_at = ?
                WHERE id = ?
            """, (category_name, procedure_name, short_code, price, now_str, procedure_id))
            conn.commit()
            flash("Procedure updated successfully", "success")
        except Exception as e:
            conn.rollback()
            flash(f"An error occurred: {e}", "danger")
        finally:
            conn.close()
        return redirect(url_for('procedures'))
    else:
        procedure = conn.execute("SELECT * FROM procedures WHERE id = ?", (procedure_id,)).fetchone()
        procedures = [dict(row) for row in procedures]
        conn.close()
        if procedure is None:
            flash("Procedure not found", "danger")
            return redirect(url_for('procedures'))
        return render_template('admin/procedures.html', procedure=procedure, valid_procedures=valid_procedures)

# 3. Delete Procedures
@app.route('/delete_procedure/<int:procedure_id>', methods=['POST'])
@role_required("OPD", "ADMIN")
def delete_procedure(procedure_id):
    conn = get_db_connection()
    try:
        conn.execute("DELETE FROM procedures WHERE id = ?", (procedure_id,))
        conn.commit()
        flash("Procedure deleted successfully", "success")
    except Exception as e:
        conn.rollback()
        flash(f"An error occurred: {e}", "danger")
    finally:
        conn.close()
    return redirect(url_for('procedures'))



### -------------------------------------------
### Daily Income Sheet
### ------------------------------------------- 
# 1. Add & View Daily Income
@app.route('/daily_income', methods=['GET', 'POST'])
@role_required("OPD", "ADMIN")
@subcategory_required('daily_income')
def daily_income():
    if request.method == 'POST':
        # --- 1) อ่านค่าและ Validate ฝั่ง Backend ---
        customer_id = request.form.get('customer_id')
        deposit_date = request.form.get('deposit_date_0')

        # 1.1) คำนวณยอดการชำระเงิน (deposit, cash, transfer, credit_card, ...)
        try:
            deposit, cash, transfer, credit_card, credit_card_fee = _calculate_payment(request)
        except ValueError as e:
            flash(str(e), "danger")
            return redirect(url_for('daily_income'))

        # 1.2) ดึง Procedures JSON + คำนวณราคารวม
        try:
            procedures_data = json.loads(request.form.get('procedures_data', '[]'))
        except Exception as e:
            flash(f"Invalid procedures data: {e}", "danger")
            return redirect(url_for('daily_income'))

        total_price = _calculate_total_price_from_procedures(procedures_data)

        # 1.3) ตรวจสอบว่าราคารวม == ยอดชำระ
        total_payment = deposit + cash + transfer + credit_card
        if total_payment != total_price:
            flash(f"ยอดชำระ ({total_payment}) ไม่เท่ากับราคารวม ({total_price}) กรุณาตรวจสอบอีกครั้ง", "danger")
            return redirect(url_for('daily_income'))
        
        # --- 2) บันทึกลงฐานข้อมูล (Insert) ---
        record_date = datetime.now().strftime('%Y-%m-%d')
        created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        conn = get_db_connection()
        try:
            # Insert Header
            cursor = conn.execute("""
                INSERT INTO daily_income_header
                (record_date, customer_id, total_price, deposit, deposit_date,
                 cash, transfer, credit_card, credit_card_fee, created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?)
            """, (
                record_date,
                customer_id,
                total_price,
                deposit,
                deposit_date,
                cash,
                transfer,
                credit_card,
                credit_card_fee,
                created_at
            ))
            header_id = cursor.lastrowid

            # Insert Details
            for proc in procedures_data:
                _insert_daily_income_detail(conn, header_id, proc, created_at)

            conn.commit()
            flash("Daily income record added successfully", "success")
        
        except Exception as e:
            conn.rollback()
            flash(f"An error occurred: {e}", "danger")
        
        finally:
            conn.close()
        
        return redirect(url_for('daily_income'))
    
    else:
        # --- GET ---
        record_date = request.args.get('record_date', datetime.now().strftime('%Y-%m-%d'))
        current_date = datetime.now().strftime('%Y-%m-%d')
        
        conn = get_db_connection()
        daily_income_list = conn.execute("""
            SELECT 
                dih.id,
                dih.record_date,
                dih.customer_id,
                dih.total_price,
                dih.deposit,
                dih.deposit_date,
                dih.cash,
                dih.transfer,
                dih.credit_card,
                dih.credit_card_fee,
                c.first_name || ' ' || c.last_name as customer_name
            FROM daily_income_header dih
            JOIN customers c ON dih.customer_id = c.id
            WHERE dih.record_date = ?
            ORDER BY dih.id ASC
        """, (record_date,)).fetchall()

        # สะสมผลรวมใน Python
        sum_total_price = 0
        sum_deposit = 0
        sum_cash = 0
        sum_transfer = 0
        sum_credit_card = 0
        sum_credit_card_fee = 0
        
        for row in daily_income_list:
            sum_total_price += row['total_price'] or 0
            sum_deposit += row['deposit'] or 0
            sum_cash += row['cash'] or 0
            sum_transfer += row['transfer'] or 0
            sum_credit_card += row['credit_card'] or 0
            sum_credit_card_fee += row['credit_card_fee'] or 0

        # ดึงข้อมูลอื่น ๆ
        doctors = conn.execute("SELECT doctor_id, short_name FROM doctors").fetchall()
        procedures = conn.execute("SELECT id, category_name, procedure_name, short_code, price FROM procedures").fetchall()
        procedures = [dict(r) for r in procedures]
        users = conn.execute("SELECT user_id, pr_code FROM users").fetchall()
        conn.close()

        return render_template('opd/daily_income.html',
            current_date=current_date,
            record_date=record_date,
            daily_income_list=daily_income_list,
            doctors=doctors,
            procedures=procedures,
            users=users,
            # ส่งตัวแปรสรุปไป Template
            sum_total_price=sum_total_price,
            sum_deposit=sum_deposit,
            sum_cash=sum_cash,
            sum_transfer=sum_transfer,
            sum_credit_card=sum_credit_card,
            sum_credit_card_fee=sum_credit_card_fee
        )
    
# 1.1 Get Daily Income Detail
@app.route('/get_daily_income_detail', methods=['GET'])
@role_required("OPD", "ADMIN")
@subcategory_required('get_daily_income_detail')
def get_daily_income_detail():
    """
    ดึง daily_income_detail ทั้งหมดของ header_id ที่ส่งมา (ผ่าน query parameter: ?header_id=xxx)
    แล้วส่งกลับเป็น JSON สำหรับนำไปแสดงใน Modal ทางฝั่ง Frontend
    """
    header_id = request.args.get('header_id', type=int)
    if not header_id:
        return jsonify({"error": "header_id is required"}), 400
    
    conn = get_db_connection()
    detail_rows = conn.execute("""
        SELECT 
            id,
            header_id,
            procedure_doctor,
            procedure_category,
            procedure_name,
            procedure_short_code,
            procedure_price,
            pr_code1,
            pr_price1,
            pr_code2,
            pr_price2,
            pr_code3,
            pr_price3
        FROM daily_income_detail
        WHERE header_id = ?
        ORDER BY id ASC
    """, (header_id,)).fetchall()
    conn.close()

    # แปลง row ให้เป็น list ของ dict เพื่อง่ายต่อการ return เป็น JSON
    detail_list = []
    for row in detail_rows:
        detail_list.append({
            "id": row["id"],
            "header_id": row["header_id"],
            "procedure_doctor": row["procedure_doctor"],
            "procedure_category": row["procedure_category"],
            "procedure_name": row["procedure_name"],
            "procedure_short_code": row["procedure_short_code"],
            "procedure_price": row["procedure_price"],
            "pr_code1": row["pr_code1"],
            "pr_price1": row["pr_price1"],
            "pr_code2": row["pr_code2"],
            "pr_price2": row["pr_price2"],
            "pr_code3": row["pr_code3"],
            "pr_price3": row["pr_price3"]
        })
    
    return jsonify(detail_list)

# 2. Edit Daily Income
@app.route('/edit_daily_income/<int:income_id>', methods=['GET', 'POST'])
@role_required("OPD", "ADMIN")
@subcategory_required('edit_daily_income')
def edit_daily_income(income_id):
    """
    แก้ไขรายการ daily_income_header (header_id = income_id)
    รวมถึง daily_income_detail (ลบของเก่า เพิ่มของใหม่)
    """
    conn = get_db_connection()

    if request.method == 'POST':
        # 1) อ่านค่ายอดชำระ (deposit, cash, transfer, ฯลฯ) จาก _calculate_payment
        try:
            deposit, cash, transfer, credit_card, credit_card_fee = _calculate_payment(request)
        except ValueError as e:
            flash(str(e), "danger")
            conn.close()
            return redirect(url_for('edit_daily_income', income_id=income_id))

        # รับค่าจากฟอร์ม deposit_date_x (กรณีถ้าต้องการใช้ก็ขยาย logic ได้)
        # ในตัวอย่างนี้ หากต้องการเอาวันที่ล่าสุด/แรกสุด หรือไม่ใช้ก็ได้
        # สมมติว่าเอา deposit_date_0 เป็น deposit_date หลัก
        deposit_date = request.form.get('deposit_date_0')

        # 2) ดึง procedures_data (JSON) + คำนวณ total_price
        try:
            procedures_data = json.loads(request.form.get('procedures_data', '[]'))
        except Exception as e:
            flash(f"Invalid procedures data: {e}", "danger")
            conn.close()
            return redirect(url_for('edit_daily_income', income_id=income_id))

        total_price = _calculate_total_price_from_procedures(procedures_data)

        # 3) ตรวจสอบยอดชำระเท่ากับยอด procedures
        total_payment = deposit + cash + transfer + credit_card
        if total_payment != total_price:
            flash(f"The sum of deposit, cash, transfer, and credit card ({total_payment}) "
                  f"must equal the total procedure price ({total_price})", "danger")
            conn.close()
            return redirect(url_for('edit_daily_income', income_id=income_id))

        # 4) Update daily_income_header, ลบ detail เดิม, Insert ใหม่
        try:
            # update header
            _update_daily_income_header(
                conn, 
                income_id,
                deposit,
                deposit_date,
                cash,
                transfer,
                credit_card,
                credit_card_fee,
                total_price
            )

            # ลบ detail เก่า
            conn.execute("DELETE FROM daily_income_detail WHERE header_id = ?", (income_id,))

            # Insert detail ใหม่
            created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            for proc in procedures_data:
                _insert_daily_income_detail(conn, income_id, proc, created_at)

            conn.commit()
            flash("Daily income record updated successfully", "success")

        except Exception as e:
            conn.rollback()
            flash(f"An error occurred while updating: {e}", "danger")
        finally:
            conn.close()

        return redirect(url_for('daily_income'))

    else:
        # --- GET ---
        # 1) ดึง header + JOIN customers
        header_row = conn.execute("""
            SELECT dih.*,
                   c.first_name || ' ' || c.last_name AS customer_name
            FROM daily_income_header dih
            JOIN customers c ON c.id = dih.customer_id
            WHERE dih.id = ?
        """, (income_id,)).fetchone()

        if not header_row:
            conn.close()
            flash("Record not found", "danger")
            return redirect(url_for('daily_income'))

        # 2) ดึง detail
        detail_rows = conn.execute("""
            SELECT *
            FROM daily_income_detail
            WHERE header_id = ?
            ORDER BY id ASC
        """, (income_id,)).fetchall()

        # 3) ดึงข้อมูลอื่น ๆ
        doctors = conn.execute("SELECT doctor_id, short_name FROM doctors").fetchall()
        procedures = conn.execute("SELECT id, category_name, procedure_name, short_code, price FROM procedures").fetchall()
        procedures = [dict(r) for r in procedures]
        users = conn.execute("SELECT user_id, pr_code FROM users").fetchall()
        conn.close()

        # list ของ detail
        detail_list = [dict(d) for d in detail_rows]

        return render_template(
            'opd/edit_daily_income.html',
            header=dict(header_row),
            detail_list=detail_list,
            doctors=doctors,
            procedures=procedures,
            users=users
        )

# 3. Delete Daily Income
@app.route('/delete_daily_income/<int:income_id>', methods=['POST'])
@role_required("OPD", "ADMIN")
@subcategory_required('delete_daily_income')
def delete_daily_income(income_id):
    conn = get_db_connection()
    try:
        # 1) ตรวจสอบว่ารายการนี้มีจริงหรือไม่ และ record_date คือวันไหน
        header_row = conn.execute("""
            SELECT record_date
            FROM daily_income_header
            WHERE id = ?
        """, (income_id,)).fetchone()
        
        if not header_row:
            flash("Record not found", "danger")
            conn.close()
            return redirect(url_for('daily_income'))
        
        # 2) ถ้าต้องการลบได้เฉพาะวันปัจจุบัน ให้เช็ค
        current_date = datetime.now().strftime('%Y-%m-%d')
        if header_row["record_date"] != current_date:
            flash("Cannot delete records from past or future dates", "danger")
            conn.close()
            return redirect(url_for('daily_income', record_date=header_row["record_date"]))
        
        # 3) ลบ detail ก่อน
        conn.execute("DELETE FROM daily_income_detail WHERE header_id = ?", (income_id,))
        # 4) ลบ header
        conn.execute("DELETE FROM daily_income_header WHERE id = ?", (income_id,))
        
        conn.commit()
        flash("ลบรายการนี้สำเร็จ", "success")
    except Exception as e:
        conn.rollback()
        flash(f"An error occurred: {e}", "danger")
    finally:
        conn.close()
    return redirect(url_for('daily_income'))

# 4. Search Customer for Daily Income
@app.route('/search_customer_for_daily_income', methods=['GET'])
@role_required('OPD', 'ADMIN')
@subcategory_required('search_customer_for_daily_income')
def search_customer_for_daily_income():
    """
    ใช้สำหรับค้นหาลูกค้าเพื่อนำไป Add/Attach ใน Daily Income โดยเฉพาะ
    จะคืนค่าเฉพาะผลการค้นหา customers เป็น JSON หรือเป็น Partial Template ก็ได้
    """
    query = request.args.get('q', '').strip()
    
    conn = get_db_connection()
    results = []
    if query:
        search_term = f"%{query}%"
        sql = """
            SELECT *
            FROM customers
            WHERE hn LIKE ?
               OR first_name LIKE ?
               OR last_name LIKE ?
               OR nickname LIKE ?
               OR phone LIKE ?
            ORDER BY created_at DESC
        """
        results = conn.execute(sql, (search_term, search_term, search_term, search_term, search_term)).fetchall()
    
    conn.close()
    
    # สมมติว่าเราต้องการส่ง JSON กลับไปให้ JavaScript ฝั่ง Frontend Render เอง
    # จะได้ไม่ต้องโหลด daily_income_header มาคืน
    data_list = []
    for row in results:
        data_list.append({
            'id': row['id'],
            'hn': row['hn'],
            'first_name': row['first_name'],
            'last_name': row['last_name'],
            'nickname': row['nickname'],
            'phone': row['phone']
        })
    return jsonify(data_list)



### -------------------------------------------
### สรุปยอดรายเดือน
### -------------------------------------------
# PR Income Summary 
@app.route('/pr_income_summary', methods=['GET'])
@role_required('EMPLOYEE', 'MANAGER', 'SECRETARY')
@subcategory_required('pr_income_summary')
def pr_income_summary():
    """
    แสดงสรุปยอด pr_code ตามเดือน (form เลือก month)
    หลังจากนั้นแสดงตารางรายละเอียดเคส (เฉพาะของ user_pr_code ตนเอง) ด้านล่าง
    """

    # (1) สร้างรายการหมวดหลัก + procedure_name ที่ต้องการสรุป
    valid_procedures = {
        "SX": [
            "จมูก(ปิด)", "จมูก(โอเพ่น)", "คาง", "เหนียง", "ปาก",
            "Fat Graft", "ตา คิ้ว", "ดึงหน้า", "หน้าอก"
        ],
        "AES": [
            "แพ็คเกจรวม", "Botox", "Filler", "Fat", "ร้อยไหม",
            "ดริปวิตามิน", "งานผิว"
        ],
        "AFC": [
            "Set AFC", "ยาทารอย", "Anita", "น้ำลดบวม", "น้ำยาบ้วนปาก", "ยาหยอด", "Cool Pack"
        ],
    }

    # (2) สร้างโครงสร้าง cat_sums ไว้เก็บยอดรวม cat->name->sum
    cat_sums = {}
    for cat, name_list in valid_procedures.items():
        cat_sums[cat] = {}
        for nm in name_list:
            cat_sums[cat][nm] = 0

    # (3) หา pr_code ของ user นี้
    user_id = session.get('user_id', None)
    if not user_id:
        flash("กรุณาล็อกอินก่อน", "warning")
        return redirect(url_for('login'))

    conn = get_db_connection()
    row_user = conn.execute("SELECT pr_code FROM users WHERE user_id = ?", (user_id,)).fetchone()
    if not row_user:
        conn.close()
        flash("ไม่พบผู้ใช้ในระบบ", "danger")
        return redirect(url_for('login'))
    user_pr_code = row_user['pr_code'] or ""

    # (4) รับ month=YYYY-MM (default=เดือนปัจจุบัน)
    current_month_str = datetime.now().strftime('%Y-%m')
    selected_month_str = request.args.get('month', current_month_str).strip()

    # แปลงเป็น (year_int, month_int)
    try:
        year_str, mon_str = selected_month_str.split('-')
        year_int = int(year_str)
        month_int = int(mon_str)
    except:
        # fallback ถ้า parse ไม่ได้
        now = datetime.now()
        year_int = now.year
        month_int = now.month
        selected_month_str = f"{year_int:04d}-{month_int:02d}"

    # สร้าง start_date, end_date
    start_date = date(year_int, month_int, 1)
    last_day = calendar.monthrange(year_int, month_int)[1]
    end_date = date(year_int, month_int, last_day)

    # (5) ดึงข้อมูล daily_income_detail + daily_income_header เพื่อสรุป cat_sums
    rows = conn.execute("""
        SELECT
          dih.record_date,
          did.procedure_category,
          did.procedure_name,
          did.pr_code1, did.pr_price1,
          did.pr_code2, did.pr_price2,
          did.pr_code3, did.pr_price3
        FROM daily_income_detail did
        JOIN daily_income_header dih ON did.header_id = dih.id
        WHERE dih.record_date >= ? AND dih.record_date <= ?
        ORDER BY dih.record_date
    """, (start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))).fetchall()

    # วนเช็ค pr_code == user_pr_code
    for row in rows:
        cat = row['procedure_category']
        nm  = row['procedure_name']
        pr_income = 0
        # เผื่อหมวดไม่ตรง valid_procedures
        if cat not in valid_procedures:
            cat = "อื่นๆ"
            if cat not in cat_sums:
                cat_sums[cat] = {}
            if nm not in cat_sums[cat]:
                cat_sums[cat][nm] = 0

        if nm not in cat_sums[cat]:
            cat_sums[cat][nm] = 0  # สร้าง slot ถ้าไม่เคยมี

        # check pr_code matching
        if row['pr_code1'] == user_pr_code:
            pr_income += (row['pr_price1'] or 0)
        if row['pr_code2'] == user_pr_code:
            pr_income += (row['pr_price2'] or 0)
        if row['pr_code3'] == user_pr_code:
            pr_income += (row['pr_price3'] or 0)

        if pr_income > 0:
            cat_sums[cat][nm] += pr_income

    # รวมแต่ละ cat
    cat_totals = {}
    for cat, name_dict in cat_sums.items():
        cat_totals[cat] = sum(name_dict.values())

    # (6) ดึงข้อมูลรายละเอียดเคสของเดือนนั้น (เฉพาะ user_pr_code ตนเอง)
    #     ต้อง JOIN customer เพื่อดึงชื่อ-นามสกุล หรือ customers c?
    #     สมมติ customers c ON dih.customer_id = c.id
    #     (หาก DB ของคุณเก็บต่างกันโปรดปรับแก้)
    detail_rows = conn.execute("""
        SELECT
          dih.record_date,
          c.first_name || ' ' || c.last_name AS customer_name,
          did.procedure_category,
          did.procedure_name,
          did.procedure_short_code,
          (
            CASE WHEN did.pr_code1=? THEN did.pr_price1 ELSE 0 END +
            CASE WHEN did.pr_code2=? THEN did.pr_price2 ELSE 0 END +
            CASE WHEN did.pr_code3=? THEN did.pr_price3 ELSE 0 END
          ) AS pr_price
        FROM daily_income_detail did
        JOIN daily_income_header dih ON did.header_id = dih.id
        JOIN customers c ON c.id = dih.customer_id
        WHERE dih.record_date >= ? AND dih.record_date <= ?
          AND (
            did.pr_code1=? OR did.pr_code2=? OR did.pr_code3=?
          )
        ORDER BY dih.record_date ASC, did.id ASC
    """, (
        user_pr_code, user_pr_code, user_pr_code,
        start_date.strftime('%Y-%m-%d'),
        end_date.strftime('%Y-%m-%d'),
        user_pr_code, user_pr_code, user_pr_code
    )).fetchall()

    conn.close()

    return render_template(
        'user/pr_summary.html',
        selected_month=selected_month_str,
        valid_procedures=valid_procedures,
        cat_sums=cat_sums,
        cat_totals=cat_totals,
        detail_rows=detail_rows  # ส่งข้อมูลรายละเอียดให้ frontend แสดงตารางเคส
    )

# Commission Rate
@app.route('/admin/commission_settings', methods=['GET', 'POST'])
@role_required('ADMIN')
def commission_settings():
    """
    หน้า admin สำหรับกำหนด commission rate:
    - แสดงรายการ procedure_name (เรียงตามหมวด)
    - แก้ไขแบบเดี่ยว / หรือ Apply ทั้งหมวด
    """
    # 1) สร้าง dict valid_procedures
    valid_procedures = {
        "SX": [
            "จมูก(ปิด)", "จมูก(โอเพ่น)", "คาง", "เหนียง", "ปาก",
            "Fat Graft", "ตา คิ้ว", "ดึงหน้า", "หน้าอก"
        ],
        "AES": [
            "แพ็คเกจรวม", "Botox", "Filler", "Fat", "ร้อยไหม",
            "ดริปวิตามิน", "งานผิว"
        ],
        "AFC": [
            "Set AFC", "ยาทารอย", "Anita", "น้ำลดบวม", "น้ำยาบ้วนปาก", "ยาหยอด", "Cool Pack"
        ],
        "ค่ายาและบริการ": [
            "ค่ายา", "ค่าโรงพยาบาล", "ตรวจแลป", "จ้างพยาบาล/ผู้ช่วย", "ทำแผล ตัดไหม"
        ],
        "อื่นๆ": [
            "ปากกาลดน้ำหนัก", "ล้างเล็บ", "อื่นๆ"
        ]
    }

    conn = get_db_connection()

    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'update_single':
            # อัปเดตcommission ของ procedure_name เดียว
            proc_name = request.form.get('procedure_name','').strip()
            ctype = request.form.get('commission_type','').strip()
            cvalue_str = request.form.get('commission_value','0').strip()

            # แปลง cvalue เป็น float
            try:
                cvalue = float(cvalue_str)
            except:
                cvalue = 0.0

            # Upsert ลงตาราง commission_rates
            conn.execute("""
                INSERT INTO commission_rates (procedure_name, commission_type, commission_value)
                VALUES (?,?,?)
                ON CONFLICT(procedure_name) DO UPDATE 
                   SET commission_type=excluded.commission_type,
                       commission_value=excluded.commission_value
            """, (proc_name, ctype, cvalue))
            conn.commit()
            flash(f"อัปเดต {proc_name} เป็น {ctype}={cvalue} เรียบร้อย", "success")

        elif action == 'apply_category':
            # Apply commission rate ให้ทั้งหมวด
            category = request.form.get('category','').strip()
            ctype = request.form.get('commission_type_cat','').strip()
            cvalue_str = request.form.get('commission_value_cat','0').strip()

            try:
                cvalue = float(cvalue_str)
            except:
                cvalue = 0.0

            # วนทุก procedure_name ในหมวดแล้ว upsert
            if category in valid_procedures:
                for proc_name in valid_procedures[category]:
                    conn.execute("""
                        INSERT INTO commission_rates (procedure_name, commission_type, commission_value)
                        VALUES (?,?,?)
                        ON CONFLICT(procedure_name) DO UPDATE 
                           SET commission_type=excluded.commission_type,
                               commission_value=excluded.commission_value
                    """, (proc_name, ctype, cvalue))
                conn.commit()
                flash(f"ตั้งค่าคอมมิชชั่นหมวด '{category}' ทั้งหมดเป็น {ctype}={cvalue} เรียบร้อย", "success")
            else:
                flash("ไม่พบหมวดที่ระบุ", "danger")

    # ---- หลังจาก POST เสร็จ หรือ GET ----
    # 2) ดึงค่าปัจจุบันจาก commission_rates
    rows = conn.execute("SELECT * FROM commission_rates").fetchall()
    conn.close()

    # สร้าง dict commission_map = { "จมูก(ปิด)": {"type":..., "value":...}, ... }
    commission_map = {}
    for r in rows:
        commission_map[r['procedure_name']] = {
            "type": r['commission_type'],
            "value": r['commission_value']
        }

    return render_template('admin/commission_settings.html',
                           valid_procedures=valid_procedures,
                           commission_map=commission_map)

# Commission Rate by PR
@app.route('/admin/commission_users', methods=['GET','POST'])
@role_required('ADMIN')
def commission_users():
    """
    หน้า Admin จัดการ commission rate ต่อ user (pr_code) + procedure_name
    มีฟังก์ชัน:
      - update_single => อัปเดตเฉพาะ user_pr_code + procedure_name
      - apply_category => Apply หมวด 1 หมวดให้ user_pr_code เดียว
      - apply_category_all => Apply ให้ user ทุกคน
          * ถ้า procedure_name_all ไม่ว่าง => apply ให้เฉพาะ procedure_name นั้น
          * ถ้า procedure_name_all ว่าง => apply ทั้งหมวด
    """

    valid_procedures = {
        "SX": [
            "จมูก(ปิด)", "จมูก(โอเพ่น)", "คาง", "เหนียง", "ปาก",
            "Fat Graft", "ตา คิ้ว", "ดึงหน้า", "หน้าอก"
        ],
        "AES": [
            "แพ็คเกจรวม", "Botox", "Filler", "Fat", "ร้อยไหม",
            "ดริปวิตามิน", "งานผิว"
        ],
        "AFC": [
            "Set AFC", "ยาทารอย", "Anita", "น้ำลดบวม", "น้ำยาบ้วนปาก", "ยาหยอด", "Cool Pack"
        ],
        "ค่ายาและบริการ": [
            "ค่ายา", "ค่าโรงพยาบาล", "ตรวจแลป", "จ้างพยาบาล/ผู้ช่วย", "ทำแผล ตัดไหม"
        ],
        "อื่นๆ": [
            "ปากกาลดน้ำหนัก", "ล้างเล็บ", "อื่นๆ"
        ]
    }

    conn = get_db_connection()

    # ดึงรายชื่อ user (role=EMPLOYEE,MANAGER) ที่มี pr_code != ''
    user_list = conn.execute("""
        SELECT user_id, pr_code, first_name, last_name, role, start_date, nickname
        FROM users
        WHERE role IN ('EMPLOYEE','MANAGER')
          AND pr_code IS NOT NULL
          AND pr_code != ''
        ORDER BY start_date
    """).fetchall()

    if request.method == 'POST':
        action = request.form.get('action','')
        if action == 'update_single':
            # update user_pr_code + procedure_name เดียว
            user_pr_code = request.form.get('user_pr_code','').strip()
            proc_name = request.form.get('procedure_name','').strip()
            ctype = request.form.get('commission_type','PERCENT').strip()
            cval_str = request.form.get('commission_value','0').strip()
            try:
                cval = float(cval_str)
            except:
                cval = 0.0

            if user_pr_code and proc_name:
                conn.execute("""
                    INSERT INTO user_commissions (user_pr_code, procedure_name, commission_type, commission_value)
                    VALUES (?,?,?,?)
                    ON CONFLICT(user_pr_code, procedure_name) DO UPDATE
                      SET commission_type=excluded.commission_type,
                          commission_value=excluded.commission_value
                """, (user_pr_code, proc_name, ctype, cval))
                conn.commit()
                flash(f"Updated {user_pr_code} / {proc_name} => {ctype}={cval}", "success")

        elif action == 'apply_category':
            # apply หมวดให้ user_pr_code เดียว
            user_pr_code = request.form.get('user_pr_code_cat','').strip()
            category = request.form.get('category','').strip()
            ctype = request.form.get('commission_type_cat','PERCENT').strip()
            cval_str = request.form.get('commission_value_cat','0').strip()
            try:
                cval = float(cval_str)
            except:
                cval = 0.0

            if user_pr_code and category in valid_procedures:
                for pname in valid_procedures[category]:
                    conn.execute("""
                        INSERT INTO user_commissions (user_pr_code, procedure_name, commission_type, commission_value)
                        VALUES (?,?,?,?)
                        ON CONFLICT(user_pr_code, procedure_name) DO UPDATE
                          SET commission_type=excluded.commission_type,
                              commission_value=excluded.commission_value
                    """, (user_pr_code, pname, ctype, cval))
                conn.commit()
                flash(f"Apply '{category}' => {user_pr_code} = {ctype}={cval} สำเร็จ", "success")
            else:
                flash("Apply หมวด: ข้อมูลไม่สมบูรณ์", "danger")

        elif action == 'apply_category_all':
            # apply ให้ user ทุกคน (role=EMPLOYEE/MANAGER, pr_code != '')
            category_all = request.form.get('category_all','').strip()
            procedure_name_all = request.form.get('procedure_name_all','').strip()
            ctype_all = request.form.get('commission_type_all','PERCENT').strip()
            cval_str = request.form.get('commission_value_all','0').strip()
            try:
                cval_all = float(cval_str)
            except:
                cval_all = 0.0

            if category_all not in valid_procedures:
                flash("หมวดไม่ถูกต้อง", "danger")
            else:
                # ถ้าระบุ procedure_name_all => apply เฉพาะโปรซีเยอร์นี้
                # ถ้าปล่อยว่าง => apply ทั้งหมวด
                if procedure_name_all:
                    # เช็คว่า procedure_name_all อยู่ใน category_all จริงหรือไม่
                    if procedure_name_all not in valid_procedures[category_all]:
                        flash(f"Procedure '{procedure_name_all}' ไม่อยู่ในหมวด {category_all}", "danger")
                        conn.close()
                        return redirect(url_for('commission_users'))

                    for u in user_list:
                        upc = u['pr_code']
                        conn.execute("""
                            INSERT INTO user_commissions (user_pr_code, procedure_name, commission_type, commission_value)
                            VALUES (?,?,?,?)
                            ON CONFLICT(user_pr_code, procedure_name) DO UPDATE
                              SET commission_type=excluded.commission_type,
                                  commission_value=excluded.commission_value
                        """, (upc, procedure_name_all, ctype_all, cval_all))

                    conn.commit()
                    flash(f"Apply {procedure_name_all} in {category_all} => ALL users = {ctype_all}={cval_all}", "success")

                else:
                    # apply ทั้งหมวด
                    for u in user_list:
                        upc = u['pr_code']
                        for pname in valid_procedures[category_all]:
                            conn.execute("""
                                INSERT INTO user_commissions (user_pr_code, procedure_name, commission_type, commission_value)
                                VALUES (?,?,?,?)
                                ON CONFLICT(user_pr_code, procedure_name) DO UPDATE
                                  SET commission_type=excluded.commission_type,
                                      commission_value=excluded.commission_value
                            """, (upc, pname, ctype_all, cval_all))

                    conn.commit()
                    flash(f"Apply ทั้งหมวด '{category_all}' => ALL users = {ctype_all}={cval_all}", "success")

    # หลังอัปเดต หรือ GET: load commission_map
    rows_comm = conn.execute("""
        SELECT user_pr_code, procedure_name, commission_type, commission_value
        FROM user_commissions
    """).fetchall()
    conn.close()

    commission_map = {}
    for r in rows_comm:
        key = (r['user_pr_code'], r['procedure_name'])
        commission_map[key] = {
            "type": r['commission_type'],
            "value": r['commission_value']
        }

    return render_template('admin/commission_users.html',
                           user_list=user_list,
                           valid_procedures=valid_procedures,
                           commission_map=commission_map)

# Monthly Sales by PR
@app.route('/admin/monthly_sales', methods=['GET'])
@role_required('ADMIN')
def monthly_sales():
    """
    หน้า Admin: เลือกเดือน -> สรุปยอดขาย (บาท) + จำนวนเคส
    เฉพาะ procedure_category in ("SX","AES","AFC")
    สำหรับพนักงาน/manager ทุกคนที่มี pr_code
    แสดง user = pr_code + ชื่อ-นามสกุล
    Column = {SX(บาท), SX(เคส), AES(บาท), AES(เคส), AFC(บาท), AFC(เคส)}
    """

    # 1) รับค่า month=YYYY-MM (default = เดือนปัจจุบัน)
    current_month_str = datetime.now().strftime('%Y-%m')
    selected_month_str = request.args.get('month', current_month_str).strip()

    try:
        year_str, mon_str = selected_month_str.split('-')
        year_int = int(year_str)
        month_int = int(mon_str)
    except:
        year_int = datetime.now().year
        month_int = datetime.now().month
        selected_month_str = f"{year_int:04d}-{month_int:02d}"

    # หาวันเริ่ม - สิ้นสุดเดือน
    start_date = date(year_int, month_int, 1)
    last_day = calendar.monthrange(year_int, month_int)[1]
    end_date = date(year_int, month_int, last_day)

    # 2) ดึง user list: EMPLOYEE, MANAGER ที่มี pr_code
    conn = get_db_connection()
    user_rows = conn.execute("""
        SELECT user_id, pr_code, first_name, last_name, role, nickname, start_date
        FROM users
        WHERE role IN ('EMPLOYEE','MANAGER')
          AND pr_code IS NOT NULL
          AND pr_code != ''
        ORDER BY start_date
    """).fetchall()

    # สร้าง dict user_map ดีกว่า: key=pr_code => {info}
    user_map = {}
    for ur in user_rows:
        user_map[ur['pr_code']] = {
            "user_id": ur['user_id'],
            "pr_code": ur['pr_code'],
            "name": f"{ur['first_name']} {ur['last_name']}",
            "role": ur['role']
        }

    # 3) เตรียม data structure: sums[(pr_code, category)] = { "amount":..., "count":... }
    #    สนใจเฉพาะ 3 หมวด: "SX", "AES", "AFC"
    categories = ["SX","AES","AFC"]
    sums = {}  # key = (pr_code, category)
    for prc in user_map.keys():
        for cat in categories:
            sums[(prc, cat)] = {"amount": 0.0, "count": 0}

    # 4) Query daily_income_detail + daily_income_header เฉพาะ record_date ในช่วง
    #    แล้ว filter procedure_category in (3หมวด)
    rows = conn.execute("""
        SELECT dih.record_date,
               did.procedure_category AS cat,
               did.pr_code1, did.pr_price1,
               did.pr_code2, did.pr_price2,
               did.pr_code3, did.pr_price3
        FROM daily_income_detail did
        JOIN daily_income_header dih ON did.header_id = dih.id
        WHERE dih.record_date >= ? 
          AND dih.record_date <= ?
          AND did.procedure_category IN ('SX','AES','AFC')
        ORDER BY dih.record_date
    """, (start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))).fetchall()
    conn.close()

    # 5) Loop rows => บวกยอด & นับเคส
    for row in rows:
        cat = row['cat']
        # ตรวจ pr_code1..3
        # ถ้า pr_codeX อยู่ใน user_map => sums[(pr_codeX, cat)].amount += pr_priceX
        # และ sums[..].count += 1 (ถือว่า 1 เคส)

        # pr_code1
        pcode1 = row['pr_code1']
        price1 = row['pr_price1'] or 0
        if pcode1 in user_map and price1 > 0:
            sums[(pcode1, cat)]["amount"] += price1
            sums[(pcode1, cat)]["count"] += 1

        # pr_code2
        pcode2 = row['pr_code2']
        price2 = row['pr_price2'] or 0
        if pcode2 in user_map and price2 > 0:
            sums[(pcode2, cat)]["amount"] += price2
            sums[(pcode2, cat)]["count"] += 1

        # pr_code3
        pcode3 = row['pr_code3']
        price3 = row['pr_price3'] or 0
        if pcode3 in user_map and price3 > 0:
            sums[(pcode3, cat)]["amount"] += price3
            sums[(pcode3, cat)]["count"] += 1

    # 6) ส่งไป render
    # user_map => ข้อมูล user
    # sums => (pr_code, category)->{amount, count}
    return render_template('admin/monthly_sales.html',
                           selected_month=selected_month_str,
                           user_map=user_map,
                           categories=categories,
                           sums=sums)

# Monthly Sales by Procedure
@app.route('/admin/monthly_sales_details', methods=['GET'])
@role_required('ADMIN')
def monthly_sales_details():
    """
    หน้า Admin: เลือกเดือน -> สรุปยอดขายแบบละเอียด (by procedure_name)
    เฉพาะหมวด: SX, AES, AFC
    เฉพาะ user (EMPLOYEE, MANAGER) ที่มี pr_code

    แสดงในตาราง:
      user(pr_code+ชื่อ), category, procedure_name, total(บาท), count(เคส)
    """

    # 1) รับ month=YYYY-MM (default = ปัจจุบัน)
    current_month_str = datetime.now().strftime('%Y-%m')
    selected_month_str = request.args.get('month', current_month_str).strip()

    try:
        year_str, mon_str = selected_month_str.split('-')
        year_int = int(year_str)
        month_int = int(mon_str)
    except:
        year_int = datetime.now().year
        month_int = datetime.now().month
        selected_month_str = f"{year_int:04d}-{month_int:02d}"

    # กำหนดช่วงวัน
    start_date = date(year_int, month_int, 1)
    last_day = calendar.monthrange(year_int, month_int)[1]
    end_date = date(year_int, month_int, last_day)

    # 2) ดึง user list: EMPLOYEE,MANAGER + pr_code != ''
    conn = get_db_connection()
    user_rows = conn.execute("""
        SELECT user_id, pr_code, first_name, last_name, role, nickname, start_date
        FROM users
        WHERE role IN ('EMPLOYEE','MANAGER')
          AND pr_code IS NOT NULL
          AND pr_code != ''
        ORDER BY start_date
    """).fetchall()

    # user_map: key=pr_code -> { user_id, pr_code, name, role }
    user_map = {}
    for ur in user_rows:
        user_map[ur['pr_code']] = {
            "user_id": ur['user_id'],
            "pr_code": ur['pr_code'],
            "nickname": ur['nickname'],
            "name": f"{ur['first_name']} {ur['last_name']}",
            "role": ur['role']
        }

    # 3) สนใจหมวด: "SX", "AES", "AFC"
    categories = ["SX", "AES", "AFC"]

    # 4) Query จาก daily_income_detail + daily_income_header
    rows = conn.execute("""
        SELECT 
          dih.record_date,
          did.procedure_category AS cat,
          did.procedure_name AS pname,
          did.pr_code1, did.pr_price1,
          did.pr_code2, did.pr_price2,
          did.pr_code3, did.pr_price3
        FROM daily_income_detail did
        JOIN daily_income_header dih ON did.header_id = dih.id
        WHERE dih.record_date >= ? 
          AND dih.record_date <= ?
          AND did.procedure_category IN ('SX','AES','AFC')
        ORDER BY dih.record_date
    """, (start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))).fetchall()
    conn.close()

    # 5) สร้าง data structure เก็บสรุป: sums[(pr_code, cat, pname)] = {amount, count}
    sums = {}

    # วน loop row => pr_codeX => add to sums
    for row in rows:
        cat = row['cat']
        pname = row['pname'] or "ไม่ระบุ"

        # ตรวจ pr_code1..3
        # ถ้าพบว่า pr_codeX อยู่ใน user_map => sums[(pr_codeX, cat, pname)] += pr_priceX
        # เพิ่ม count +1
        for i in [(row['pr_code1'], row['pr_price1']),
                  (row['pr_code2'], row['pr_price2']),
                  (row['pr_code3'], row['pr_price3'])]:
            pcode = i[0]
            price = i[1] or 0
            if pcode in user_map and price > 0:
                key = (pcode, cat, pname)
                if key not in sums:
                    sums[key] = {"amount": 0.0, "count": 0}
                sums[key]["amount"] += price
                sums[key]["count"] += 1

    # 6) เราต้องการแสดงผลเป็น list of row (user, cat, pname, amount, count)
    # สร้าง structure list_rows -> ค่อย sort
    list_rows = []
    for (pcode, cat, pname), val in sums.items():
        # pcode => user_map => user_id, name, role
        list_rows.append({
            "user_pr_code": pcode,
            "user_nickname": user_map[pcode]["nickname"],
            "user_name": user_map[pcode]["name"],
            "user_role": user_map[pcode]["role"],
            "category": cat,
            "procedure_name": pname,
            "amount": val["amount"],
            "count": val["count"]
        })

    # 7) จัดเรียง list_rows: โดย user_id, แล้วตาม category, แล้ว procedure_name
    #   เราอาจต้องสร้าง map user_pr_code -> user_id เพื่อ sort
    prcode_to_userid = {}
    for pcode, info in user_map.items():
        prcode_to_userid[pcode] = info["user_id"]

    def sort_key(row):
        uid = prcode_to_userid[row["user_pr_code"]]
        cat_idx = categories.index(row["category"]) if row["category"] in categories else 999
        return (uid, cat_idx, row["procedure_name"])
    
    list_rows.sort(key=sort_key)

    return render_template(
        "admin/monthly_sales_details.html",
        selected_month=selected_month_str,
        list_rows=list_rows
    )

# Incentive User
@app.route('/incentive_users', methods=['GET','POST'])
@role_required('ADMIN')
def incentive_users():
    """
    แก้ไข incentive_xxx, credit, bonus, etc. ในตาราง users โดยตรง
    เฉพาะ user.role in (EMPLOYEE, MANAGER)
    """
    conn = get_db_connection()
    if request.method == 'POST':
        # อ่าน user_id[] ทั้งหมด
        user_ids = request.form.getlist('user_id[]')
        for uid in user_ids:
            # parse value จากฟอร์ม
            incentive_sx_rate  = parse_float_value(request.form, f'incentive_sx_rate_{uid}')
            incentive_aes_rate = parse_float_value(request.form, f'incentive_aes_rate_{uid}')
            incentive_afc_rate = parse_float_value(request.form, f'incentive_afc_rate_{uid}')
            credit      = parse_float_value(request.form, f'credit_{uid}')
            translate   = parse_float_value(request.form, f'translate_{uid}')
            or_aes      = parse_float_value(request.form, f'or_aes_{uid}')
            extra_travel      = parse_float_value(request.form, f'extra_travel_{uid}')
            extra_phone       = parse_float_value(request.form, f'extra_phone_{uid}')
            online_page = parse_float_value(request.form, f'online_page_{uid}')
            nurse       = parse_float_value(request.form, f'nurse_{uid}')
            pharmacy    = parse_float_value(request.form, f'pharmacy_{uid}')
            bonus       = parse_float_value(request.form, f'bonus_{uid}')
            manager     = parse_float_value(request.form, f'manager_{uid}')

            # update ลงตาราง users
            conn.execute("""
                UPDATE users
                SET 
                  incentive_sx_rate=?,
                  incentive_aes_rate=?,
                  incentive_afc_rate=?,
                  credit=?,
                  translate=?,
                  or_aes=?,
                  extra_travel=?,
                  extra_phone=?,
                  online_page=?,
                  nurse=?,
                  pharmacy=?,
                  bonus=?,
                  manager=?
                WHERE user_id=?
            """, (incentive_sx_rate, incentive_aes_rate, incentive_afc_rate,
                  credit, translate, or_aes, extra_travel, extra_phone, online_page,
                  nurse, pharmacy, bonus, manager, uid))
        conn.commit()
        conn.close()
        flash("Updated incentives for all users successfully!", "success")
        return redirect(url_for('incentive_users'))
    else:
        # GET => select user list
        rows_users = conn.execute("""
            SELECT
              user_id,
              role,
              pr_code,
              nickname,
              first_name,
              start_date,
              incentive_sx_rate,
              incentive_aes_rate,
              incentive_afc_rate,
              credit,
              translate,
              or_aes,
              extra_travel,
              extra_phone,
              online_page,
              nurse,
              pharmacy,
              bonus,
              manager
            FROM users
            WHERE role IN ('EMPLOYEE','MANAGER', 'SECRETARY')
            ORDER BY start_date
        """).fetchall()
        conn.close()

        return render_template('admin/incentive_users.html', users=rows_users)

# AES commission rate
@app.route('/aes_commission_rate', methods=['GET','POST'])
@role_required('MANAGER', 'ADMIN')
@subcategory_required('aes_commission_rate')
def aes_commission_rate():
    """
    Manager ปรับเรทค่ามือ AES แยกตาม short_code
    เก็บลง procedures.aes_commission_rate
    """
    conn = get_db_connection()

    if request.method == 'POST':
        # รับค่า input เป็น array
        short_codes = request.form.getlist('short_code[]')
        rates = request.form.getlist('aes_rate[]')

        # ทั้งสอง list มี length เดียวกัน
        for i, scode in enumerate(short_codes):
            try:
                val = float(rates[i] or 0.0)
                conn.execute("""
                    UPDATE procedures
                    SET aes_commission_rate = ?
                    WHERE short_code = ? AND category_name = 'AES'
                """, (val, scode))
            except Exception as e:
                print("Error updating short_code:", scode, e)

        conn.commit()
        flash("อัปเดตค่า aes_commission_rate สำเร็จ", "success")
        conn.close()
        return redirect(url_for('aes_commission_rate'))

    else:
        # GET: ดึงรายการ procedure ที่เป็น AES
        rows = conn.execute("""
            SELECT id, short_code, procedure_name, aes_commission_rate
            FROM procedures
            WHERE category_name = 'AES'
            ORDER BY short_code
        """).fetchall()
        conn.close()
        return render_template('or/aes_commission_rate.html', aes_list=rows)

# AES commission daily input
@app.route('/aes_commission', methods=['GET','POST'])
@role_required('EMPLOYEE','MANAGER', 'ADMIN')
@subcategory_required('aes_commission_assignment')
def aes_commission_assignment():
    conn = get_db_connection()

    current_role = session.get('role','')

    today = date.today()
    month = int(request.args.get('month', today.month))
    year = int(request.args.get('year', today.year))

    if request.method == 'POST':
        detail_ids = request.form.getlist('detail_id[]')
        user_ids = request.form.getlist('assigned_user_id[]')

        for i, detail_id_str in enumerate(detail_ids):
            assigned_uid = user_ids[i]
            if not detail_id_str:
                continue
            detail_id = int(detail_id_str)

            # ดึงข้อมูล record_date เพื่อตรวจสอบ editable
            row = conn.execute("""
                SELECT did.id, dih.record_date
                FROM daily_income_detail did
                JOIN daily_income_header dih ON did.header_id=dih.id
                WHERE did.id = ?
                  AND did.procedure_category='AES'
            """, (detail_id,)).fetchone()
            if not row:
                continue

            record_dt = datetime.strptime(row['record_date'], "%Y-%m-%d").date()
            can_edit = check_aes_commission_editable(record_dt, current_role)

            if can_edit:
                if assigned_uid == "":
                    assigned_uid = None
                conn.execute("""
                    UPDATE daily_income_detail
                    SET aes_assigned_user_id = ?
                    WHERE id = ?
                """, (assigned_uid, detail_id))

        conn.commit()
        flash("บันทึกข้อมูลสำเร็จ (เฉพาะรายการที่แก้ได้)", "success")
        conn.close()
        return redirect(url_for('aes_commission_assignment', month=month, year=year))

    else:
        # GET: load detail list
        rows = conn.execute("""
            SELECT did.id,
                   did.procedure_short_code AS short_code,
                   did.procedure_price,
                   dih.record_date,
                   did.aes_assigned_user_id
            FROM daily_income_detail did
            JOIN daily_income_header dih ON did.header_id = dih.id
            WHERE did.procedure_category='AES'
              AND strftime('%Y', dih.record_date)=?
              AND strftime('%m', dih.record_date)=?
            ORDER BY dih.record_date ASC, did.id
        """, (str(year), f"{month:02d}")).fetchall()

        # ดึงรายชื่อ user
        user_rows = conn.execute("""
            SELECT user_id, nickname, first_name, last_name, start_date
            FROM users
            WHERE sub_category_id=10 AND role='EMPLOYEE'
            ORDER BY start_date
        """).fetchall()
        conn.close()

        detail_list = []
        for r in rows:
            record_dt = datetime.strptime(r['record_date'], "%Y-%m-%d").date()
            can_edit = check_aes_commission_editable(record_dt, current_role)
            detail_list.append({
                "id": r['id'],
                "short_code": r['short_code'],
                "price": r['procedure_price'],
                "record_date": r['record_date'],
                "aes_assigned_user_id": r['aes_assigned_user_id'],
                "editable": can_edit
            })

        possible_months = range(1,13)
        possible_years = range(today.year-1, today.year+2)

        return render_template('or/aes_commission.html',
                               detail_list=detail_list,
                               user_list=user_rows,
                               month=month,
                               year=year,
                               possible_months=possible_months,
                               possible_years=possible_years)

# Translate commission
@app.route('/translate_commission', methods=['GET','POST'])
@role_required('EMPLOYEE', 'HR', 'ADMIN')
@subcategory_required('translate_commission')
def translate_commission():
    # 1) ดึง role + user_id จาก session
    user_role = session.get('role','EMPLOYEE')
    current_user_id = session.get('user_id', 0)

    # 2) รับเดือน/ปี + user_id (กรณี HR/ADMIN เลือกดู user ใด)
    today = date.today()
    default_year  = today.year
    default_month = today.month

    year  = int(request.args.get('year', default_year))
    month = int(request.args.get('month', default_month))

    # ถ้า HR/ADMIN อาจมีการเลือกดู user_id=? จาก querystring
    # หรือถ้าปล่อยว่าง "all" => แสดงทุกคน
    filter_user_id_str = request.args.get('user_id','')
    if user_role not in ('HR','ADMIN'):
        # ถ้าเป็น employee => fix user_id = current_user_id
        filter_user_id_str = str(current_user_id)  
    else:
        pass

    conn = get_db_connection()

    if request.method == 'POST':
        # POST => Save All
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # ส่วนรับค่า "รายการใหม่" (Section1)
        new_words = request.form.getlist('new_word_count[]')
        new_links = request.form.getlist('new_article_link[]')

        # ส่วนรับค่า "แก้ไขของเดิม" (Section2)
        row_ids    = request.form.getlist('row_id[]')
        row_words  = request.form.getlist('row_word_count[]')
        row_links  = request.form.getlist('row_article_link[]')

        # 2.1) Insert ของใหม่
        for i, w_str in enumerate(new_words):
            link_str = new_links[i] if i<len(new_links) else ""
            if not w_str and not link_str:
                continue
            try:
                w_int = int(w_str or 0)
            except:
                w_int = 0
            # สำหรับ user:
            # - ถ้า employee => user_id = current_user_id
            # - ถ้า HR/ADMIN => อาจจะ assign ใคร? หรือ assign ตัวเอง?
            #   * ตัวอย่างง่าย ๆ => เป็นคนบันทึก => user_id = current_user_id
            #   (คุณอาจให้ HR กรอกว่าบันทึกแทน user ไหนก็ได้)
            record_date_str = f"{year}-{month:02d}-01"
            conn.execute("""
                INSERT INTO translate_commission(user_id, record_date,
                  word_count, article_link,
                  created_at, updated_at)
                VALUES (?,?,?,?,?,?)
            """, (current_user_id, record_date_str, w_int, link_str, now_str, now_str))

        # 2.2) Update ของเดิม
        for i, rid_str in enumerate(row_ids):
            if not rid_str:
                continue
            row_id = int(rid_str)
            w_str = row_words[i] if i<len(row_words) else "0"
            link_str = row_links[i] if i<len(row_links) else ""
            try:
                w_int = int(w_str or 0)
            except:
                w_int = 0

            # ดึง record_date + user_id เดิม
            rowdata = conn.execute("""
                SELECT record_date, user_id
                FROM translate_commission
                WHERE id=?
            """,(row_id,)).fetchone()
            if not rowdata:
                continue
            row_user_id = rowdata['user_id']
            rec_dt = datetime.strptime(rowdata['record_date'], "%Y-%m-%d").date()

            # ตรวจสิทธิ์:
            #  - ถ้า employee => ต้องเป็น row ของตนเอง + can_edit_translate
            #  - ถ้า HR/ADMIN => can_edit_translate
            can_edit = False
            if user_role in ('HR','ADMIN'):
                # สามารถแก้ user ไหนก็ได้ => แค่ check can_edit_translate
                can_edit = can_edit_translate(rec_dt, user_role)
            else:
                # employee => check user_id + can_edit
                if row_user_id == current_user_id and can_edit_translate(rec_dt, user_role):
                    can_edit = True

            if can_edit:
                conn.execute("""
                    UPDATE translate_commission
                    SET word_count=?,
                        article_link=?,
                        updated_at=?
                    WHERE id=?
                """, (w_int, link_str, now_str, row_id))
            else:
                # ถ้าแก้ไม่ได้ => ข้าม
                pass

        conn.commit()
        conn.close()
        flash("บันทึกข้อมูลเรียบร้อย", "success")
        return redirect(url_for('translate_commission', year=year, month=month))
    else:
        # GET => Render
        # 3) สร้างเงื่อนไข WHERE
        where_clauses = ["strftime('%Y', record_date)=?", "strftime('%m', record_date)=?"]
        params = [str(year), f"{month:02d}"]

        # ถ้า employee => filter เฉพาะ user_id ตนเอง
        # ถ้า HR/ADMIN => ดู param filter_user_id_str
        #   ถ้า "" หรือ "all" => ทุกคน
        #   ถ้า ใส่ user_id => เฉพาะ user นั้น
        final_user_id = None
        if user_role in ('HR','ADMIN'):
            if filter_user_id_str not in ("", "all"):
                # สมมติเป็นตัวเลข user_id
                final_user_id = int(filter_user_id_str)
        else:
            final_user_id = current_user_id

        if final_user_id:
            where_clauses.append("user_id=?")
            params.append(final_user_id)

        where_sql = " AND ".join(where_clauses)
        
        rows = conn.execute(f"""
            SELECT id, user_id, record_date, word_count, article_link
            FROM translate_commission
            WHERE {where_sql}
            ORDER BY record_date DESC, id DESC
        """, params).fetchall()

        # ถ้า HR/ADMIN => ดึง list user ทั้งหมด (หรือเฉพาะ employee?)
        user_list = []
        if user_role in ('HR','ADMIN'):
            user_list = conn.execute("""
                SELECT user_id, nickname, first_name, role, start_date
                FROM users
                WHERE sub_category_id = 9
                ORDER BY start_date
            """).fetchall()

        conn.close()

        # สร้าง row_list + ตรวจ editable
        show_list = []
        for r in rows:
            rec_dt = datetime.strptime(r['record_date'], "%Y-%m-%d").date()
            row_user_id = r['user_id']
            # check edit
            if user_role in ('HR','ADMIN'):
                editable = can_edit_translate(rec_dt, user_role)
            else:
                # employee => ต้องเป็นของตนเองด้วย
                editable = (row_user_id == current_user_id) and can_edit_translate(rec_dt, user_role)
            
            show_list.append({
                "id": r['id'],
                "user_id": r['user_id'],
                "record_date": r['record_date'],
                "word_count": r['word_count'],
                "article_link": r['article_link'],
                "editable": editable
            })

        # เตรียมตัวเลือกปี/เดือน
        possible_years = range(today.year-1, today.year+2)
        possible_months = range(1,13)

        return render_template("pa/translate_commission.html",
            row_list=show_list,
            user_list=user_list,
            role=user_role,
            filter_user_id_str=filter_user_id_str,
            month=month,
            year=year,
            possible_years=possible_years,
            possible_months=possible_months
        )

# Credit commission
@app.route('/credit_commission', methods=['GET','POST'])
@role_required('HR','ADMIN')
def credit_commission():
    # 1) รับเดือน/ปี จาก query string หรือ default ปัจจุบัน
    today = date.today()
    default_year  = today.year
    default_month = today.month
    year  = int(request.args.get('year', default_year))
    month = int(request.args.get('month', default_month))

    conn = get_db_connection()

    # 2) ดึงรายชื่อ user ที่ sub_category_id=12
    #    สมมติ role=HR/ADMIN => เห็นทุกคน
    user_rows = conn.execute("""
        SELECT user_id, first_name, last_name, nickname, start_date
        FROM users
        WHERE sub_category_id=12
        ORDER BY start_date
    """).fetchall()

    if request.method == 'POST':
        # 2.1) รับค่าจากฟอร์ม => credit_value[] + user_id[] + hidden year, month
        posted_year  = int(request.form.get('post_year', year))
        posted_month = int(request.form.get('post_month', month))

        user_ids   = request.form.getlist('user_id[]')
        credits    = request.form.getlist('credit_value[]')

        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        for i, uid_str in enumerate(user_ids):
            try:
                uid = int(uid_str)
            except:
                continue
            c_str = credits[i] if i<len(credits) else "0"
            try:
                c_val = float(c_str)
            except:
                c_val = 0.0
            # INSERT OR REPLACE / ON CONFLICT
            conn.execute("""
                INSERT INTO credit_commission(user_id, year, month, credit_value, created_at, updated_at)
                VALUES (?,?,?,?,?,?)
                ON CONFLICT(user_id, year, month) DO UPDATE
                  SET credit_value=excluded.credit_value,
                      updated_at=excluded.updated_at
            """, (uid, posted_year, posted_month, c_val, now_str, now_str))

        conn.commit()
        conn.close()
        flash("บันทึก credit commission สำเร็จ", "success")
        return redirect(url_for('credit_commission', year=posted_year, month=posted_month))
    else:
        # GET => 2.2) ดึงค่าปัจจุบันในเดือน/ปีนั้น
        # สร้าง dict => user_id => credit_value
        row_cc = conn.execute("""
            SELECT user_id, credit_value
            FROM credit_commission
            WHERE year=? AND month=?
        """, (year, month)).fetchall()

        cc_map = { r['user_id']: r['credit_value'] for r in row_cc }

        # Section2 => History
        # ดึง list ของ year,month ทั้งหมด (group) เรียงจากใหม่ไปเก่า
        # สมมติ 2 ปีหลัง + data
        # หรือ SELECT DISTINCT year,month FROM ...
        # ORDER BY year DESC, month DESC
        row_hist = conn.execute("""
            SELECT year, month
            FROM credit_commission
            GROUP BY year, month
            ORDER BY year DESC, month DESC
        """).fetchall()
        
        # สร้าง structure => { (y,m): [ {user_id,..., credit_value}, ...], ... }
        # เอา user list => subcat=12 => join
        # อาจจะ loop row_hist => loop user_rows => find credit
        history_data = []
        for hm in row_hist:
            yy = hm['year']
            mm = hm['month']
            # ดึง credit ของ user subcat=12
            # or re-use user_rows
            # query credit_commission
            c_rows = conn.execute("""
                SELECT c.user_id, c.credit_value, u.first_name, u.last_name, u.nickname
                FROM credit_commission c
                JOIN users u ON c.user_id=u.user_id
                WHERE c.year=? AND c.month=?
                  AND u.sub_category_id=12
                ORDER BY c.user_id
            """, (yy,mm)).fetchall()
            # สร้าง list
            user_list2 = []
            for cr in c_rows:
                user_list2.append({
                    "user_id": cr['user_id'],
                    "nickname": cr['nickname'],
                    "fullname": f"{cr['first_name']} {cr['last_name']}",
                    "credit_value": cr['credit_value']
                })
            # เก็บลง history_data
            history_data.append({
                "year": yy,
                "month": mm,
                "items": user_list2
            })

        conn.close()

        return render_template('mkt/credit_commission.html',
                               year=year, month=month,
                               user_rows=user_rows,
                               cc_map=cc_map,  # ใช้ prefill ใน form
                               history_data=history_data
                              )



if __name__=='__main__':
    with app.app_context():
        init_db()
    populate_default_work_schedules(days_ahead=90)
    app.run(host="0.0.0.0", port=5000, debug=True)
