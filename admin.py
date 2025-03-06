# admin_user.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from datetime import date, datetime
import calendar

from db import get_db_connection
from auth_decorators import role_required

admin_bp = Blueprint('admin_bp', __name__, url_prefix='/admin')

### -------------------------------
### System Management
### -------------------------------
# Workflow Config
@admin_bp.route('/workflow_config', methods=['GET', 'POST'])
@role_required('ADMIN')
def workflow_config_dashboard():
    conn = get_db_connection()
    try:
        if request.method == 'POST':
            # รับข้อมูลจากฟอร์มสำหรับแต่ละ configuration row
            config_id = request.form.get('config_id')
            require_subcategory = request.form.get('require_subcategory', '0')
            # รับค่าใหม่จาก multi-select ที่ชื่อ new_allowed_subcategory_ids
            new_allowed_list = request.form.getlist('new_allowed_subcategory_ids')
            description = request.form.get('description', '')
            
            # ดึงค่าที่มีอยู่ในปัจจุบันของ allowed_subcategory_ids จากตาราง workflow_config
            current_row = conn.execute("""
                SELECT allowed_subcategory_ids 
                FROM workflow_config 
                WHERE config_id = ?
            """, (config_id,)).fetchone()
            current_allowed = []
            if current_row and current_row['allowed_subcategory_ids']:
                # แปลง string เป็น list โดยใช้ comma เป็นตัวแบ่ง
                current_allowed = [x.strip() for x in current_row['allowed_subcategory_ids'].split(',') if x.strip()]
            
            # รวมค่าใหม่กับค่าเดิม (โดยไม่ให้เกิด duplicate)
            combined_allowed = list(set(current_allowed + new_allowed_list))
            # เรียงลำดับตัวเลข (ถ้าต้องการ)
            combined_allowed.sort(key=int)
            # รวมค่ากลับเป็น string ที่ใช้ comma เป็นตัวแบ่ง
            new_allowed_subcategory_ids = ",".join(combined_allowed)
            
            conn.execute("""
                UPDATE workflow_config
                SET require_subcategory = ?,
                    allowed_subcategory_ids = ?,
                    description = ?
                WHERE config_id = ?
            """, (int(require_subcategory), new_allowed_subcategory_ids, description, config_id))
            conn.commit()
            flash("ปรับปรุง Workflow Configuration สำเร็จ", "success")
            return redirect(url_for('admin_bp.workflow_config_dashboard'))
        else:
            # GET: ดึงข้อมูล configuration ทั้งหมดเรียงตาม config_id จากน้อยไปมาก
            configs = conn.execute("""
                SELECT * FROM workflow_config
                ORDER BY config_id ASC
            """).fetchall()
            # ดึงข้อมูล subcategories ทั้งหมด
            subcategories = conn.execute("""
                SELECT sub_category_id, sub_category_name
                FROM sub_categories
                ORDER BY sub_category_name ASC
            """).fetchall()
            
            # แปลงข้อมูลในแต่ละ configuration ให้มี key allowed_list เป็นลิสต์
            configs_processed = []
            for config in configs:
                allowed_list = []
                if config['allowed_subcategory_ids']:
                    allowed_list = [s.strip() for s in config['allowed_subcategory_ids'].split(',') if s.strip()]
                config_dict = dict(config)
                config_dict['allowed_list'] = allowed_list
                configs_processed.append(config_dict)
            
            return render_template('admin/workflow_config_dashboard.html', 
                                   configs=configs_processed, 
                                   subcategories=subcategories)
    except Exception as e:
        conn.rollback()
        flash(f"เกิดข้อผิดพลาดในการอัปเดต: {e}", "danger")
        return redirect(url_for('admin_bp.workflow_config_dashboard'))
    finally:
        conn.close()

# Workflow Config; Delete allowed subcategory
@admin_bp.route('/delete_allowed_subcategory', methods=['POST'])
@role_required('ADMIN')
def delete_allowed_subcategory():
    config_id = request.form.get('config_id')
    subcat_id = request.form.get('sub_category_id')
    if not config_id or not subcat_id:
        flash("Missing parameters for deletion", "danger")
        return redirect(url_for('admin_bp.workflow_config_dashboard'))
    conn = get_db_connection()
    try:
        row = conn.execute("""
            SELECT allowed_subcategory_ids 
            FROM workflow_config 
            WHERE config_id = ?
        """, (config_id,)).fetchone()
        if not row:
            flash("Configuration not found", "danger")
            return redirect(url_for('admin_bp.workflow_config_dashboard'))
        current_allowed = []
        if row['allowed_subcategory_ids']:
            current_allowed = [x.strip() for x in row['allowed_subcategory_ids'].split(',') if x.strip()]
        if subcat_id in current_allowed:
            current_allowed.remove(subcat_id)
        new_allowed = ",".join(current_allowed)
        conn.execute("""
            UPDATE workflow_config
            SET allowed_subcategory_ids = ?
            WHERE config_id = ?
        """, (new_allowed, config_id))
        conn.commit()
        flash("ลบ Allowed Subcategory สำเร็จ", "success")
    except Exception as e:
        conn.rollback()
        flash(f"เกิดข้อผิดพลาดในการลบ: {e}", "danger")
    finally:
        conn.close()
    return redirect(url_for('admin_bp.workflow_config_dashboard'))


### -------------------------------
### Doctor Management
### -------------------------------
# Verify Doctor
@admin_bp.route('/manage_doctors', methods=['GET', 'POST'])
@role_required('ADMIN')
def manage_doctors():
    """
    ตัวอย่างหน้า Admin สำหรับจัดการผู้ใช้ (manage doctors)
    """
    conn = get_db_connection()

    if request.method == 'POST':
        # ตัวอย่างการอัปเดต sub_category หรือ role หรืออื่น ๆ
        action_type = request.form.get('action_type')
        user_id = request.form.get('user_id')

        # ตรวจสอบว่า user นี้มีอยู่จริงไหม
        user = conn.execute("""
            SELECT user_id, role, first_name, last_name
            FROM users
            WHERE user_id = ?
        """, (user_id,)).fetchone()
        if not user:
            flash("ไม่พบผู้ใช้ในระบบ", "warning")
            conn.close()
            return redirect(url_for('admin_bp.manage_doctors'))

        try:
            if action_type == 'update_role':
                new_role = request.form.get('role')
                conn.execute("""
                    UPDATE users
                    SET role=?
                    WHERE user_id=?
                """, (new_role, user_id))
                conn.commit()
                flash(f"อัปเดต role ของ {user['first_name']} {user['last_name']} เป็น {new_role}", "success")

            elif action_type == 'update_doctor_id':
                new_doctor_id = request.form.get('doctor_id')
                conn.execute("""
                    UPDATE users
                    SET doctor_id=?
                    WHERE user_id=?
                """, (new_doctor_id, user_id))
                conn.commit()
                flash("แม็พ Doctor ID เรียบร้อย", "success")

        except Exception as e:
            conn.rollback()
            flash(f"Error updating user: {e}", "danger")

    # ส่วนแสดงผล (GET หรือหลัง POST เสร็จ)
    # ตัวอย่าง: ดึง users ทั้งหมด, หรือเฉพาะ role=DOCTOR
    users = conn.execute("""
        SELECT 
            u.user_id, u.username, u.first_name, u.last_name, u.role, 
            u.doctor_id,
            d.thai_full_name AS doctor_name
        FROM users u
        LEFT JOIN doctors d ON u.doctor_id = d.doctor_id
        ORDER BY u.user_id
    """).fetchall()

    # ดึงรายการ doctor เพื่อใส่ใน dropdown matching
    doctors = conn.execute("""
        SELECT doctor_id, thai_full_name, license_number 
        FROM doctors
        ORDER BY doctor_id
    """).fetchall()

    conn.close()

    return render_template('admin/manage_doctors.html',
                           users=users,
                           doctors=doctors)

# Doctor Income Summary (ALL)
@admin_bp.route('/doctor_income_summary', methods=['GET'])
@role_required('ADMIN')  # ให้เฉพาะ Admin เท่านั้นที่เข้าถึงได้
def admin_doctor_income_summary():
    """
    แสดงสรุปยอดรายเดือนของแพทย์ทั้งหมด (เฉพาะยอดรวมและค่าแพทย์)
    โดยไม่แสดงรายละเอียดของแต่ละเคส
    """
    # รับค่า month/year จาก GET parameter
    today = date.today()
    default_year  = today.year
    default_month = today.month

    year  = int(request.args.get('year',  default_year))
    month = int(request.args.get('month', default_month))

    # สร้างวันที่เริ่มต้นและสิ้นสุดของเดือนที่เลือก
    start_dt = date(year, month, 1)
    last_day = calendar.monthrange(year, month)[1]
    end_dt   = date(year, month, last_day)

    conn = get_db_connection()

    # ดึงข้อมูลสรุปยอดของแพทย์ทั้งหมด
    # Query นี้จะรวมยอดของแต่ละหมวด (SX, AES) และดึงค่า df_surgery, df_aesthetic จากตาราง doctors
    # (ต้องปรับ JOIN ให้สอดคล้องกับ schema ที่แท้จริงของคุณ)
    rows = conn.execute("""
        SELECT d.doctor_id, d.short_name, d.df_surgery, d.df_aesthetic,
               SUM(CASE WHEN did.procedure_category = 'SX' THEN did.procedure_price ELSE 0 END) AS sx_sum,
               SUM(CASE WHEN did.procedure_category = 'AES' THEN did.procedure_price ELSE 0 END) AS aes_sum
        FROM daily_income_detail did
        JOIN daily_income_header dih ON did.header_id = dih.id
        JOIN doctors d ON did.procedure_doctor = d.short_name
        WHERE dih.record_date >= ? AND dih.record_date <= ?
        GROUP BY d.doctor_id, d.short_name, d.df_surgery, d.df_aesthetic
        ORDER BY d.short_name ASC
    """, (start_dt, end_dt)).fetchall()
    conn.close()

    # คำนวณค่าแพทย์สำหรับแต่ละแพทย์ (df_surgery, df_aesthetic เก็บเป็นเปอร์เซ็นต์)
    summaries = []
    for row in rows:
        short_name    = row['short_name']
        sx_sum        = float(row['sx_sum'] or 0.0)
        aes_sum       = float(row['aes_sum'] or 0.0)
        df_surgery    = float(row['df_surgery'] or 0.0)
        df_aesthetic  = float(row['df_aesthetic'] or 0.0)
        # หากค่าในฐานข้อมูลเป็นเปอร์เซ็นต์ เช่น 70 สำหรับ 70% ให้หาร 100
        sx_fee = sx_sum * (df_surgery / 100.0)
        aes_fee = aes_sum * (df_aesthetic / 100.0)
        total_fee = sx_fee + aes_fee

        summaries.append({
            'doctor_id': row['doctor_id'],
            'short_name': short_name,
            'sx_sum': sx_sum,
            'aes_sum': aes_sum,
            'sx_fee': sx_fee,
            'aes_fee': aes_fee,
            'total_fee': total_fee
        })

    # ส่งข้อมูลสรุปไปยัง template สำหรับ Admin
    return render_template(
        'admin/doctor_income_summary.html',
        year=year,
        month=month,
        summaries=summaries
    )



