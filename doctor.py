from flask import Blueprint, render_template, request, session, redirect, url_for, flash
import calendar
from datetime import date, datetime
from db import get_db_connection
from auth_decorators import role_required, get_months

doctor_bp = Blueprint('doctor', __name__, url_prefix='/doctor')

@doctor_bp.route('/doctor_income_summary', methods=['GET'])
@role_required('DOCTOR')
def doctor_income_summary():
    """
    แสดงสรุปรายได้ของแพทย์ (short_name ของตัวเอง) ในเดือนที่เลือก
    1) สรุปตามหมวด procedure_category = 'SX' กับ 'AES'
    2) คำนวณค่าแพทย์ = (sx_sum * df_surgery) + (aes_sum * df_aesthetic)
    3) แสดงตารางเคสแยกเป็น 2 ส่วน: SX, AES
    """
    user_id = session.get('user_id')
    if not user_id:
        flash("กรุณาล็อกอินก่อน", "warning")
        return redirect(url_for('login'))

    conn = get_db_connection()
    # โหลดข้อมูล user -> doctor
    row_user = conn.execute("""
        SELECT u.user_id, u.doctor_id, d.short_name,
               d.df_surgery, d.df_aesthetic
        FROM users u
        JOIN doctors d ON u.doctor_id = d.doctor_id
        WHERE u.user_id = ?
    """, (user_id,)).fetchone()

    if not row_user:
        conn.close()
        flash("ไม่พบข้อมูลแพทย์ หรือผู้ใช้นี้ไม่ใช่แพทย์", "danger")
        return redirect(url_for('index'))

    doctor_short_name = row_user['short_name']
    df_surgery    = float(row_user['df_surgery']    or 0.0)  # เช่น 0.7 = 70%
    df_aesthetic  = float(row_user['df_aesthetic']  or 0.0)  # เช่น 0.5 = 50%

    # รับ month/year
    today = date.today()
    default_year  = today.year
    default_month = today.month

    year  = int(request.args.get('year',  default_year))
    month = int(request.args.get('month', default_month))

    # สร้าง start_date, end_date
    start_dt = date(year, month, 1)
    last_day = calendar.monthrange(year, month)[1]
    end_dt   = date(year, month, last_day)

    # ---- 1) สรุปยอด SX, AES ----
    sx_sum  = 0.0
    aes_sum = 0.0

    rows_cat = conn.execute("""
        SELECT did.procedure_category AS cat,
               SUM(did.procedure_price) AS cat_sum
        FROM daily_income_detail did
        JOIN daily_income_header dih ON did.header_id = dih.id
        WHERE did.procedure_doctor = ?
          AND dih.record_date >= ? 
          AND dih.record_date <= ?
          AND did.procedure_category IN ('SX','AES')
        GROUP BY did.procedure_category
    """, (doctor_short_name, start_dt, end_dt)).fetchall()

    for r in rows_cat:
        cat     = r['cat']
        cat_sum = float(r['cat_sum'] or 0.0)
        if cat == 'SX':
            sx_sum += cat_sum
        elif cat == 'AES':
            aes_sum += cat_sum

    # ---- 2) คำนวณ "ค่าแพทย์" (Doctor Fee) ----
    # ถ้า df_surgery, df_aesthetic เป็น fraction (0.7 => 70%)
    sx_fee  = sx_sum  * ( df_surgery / 100.0 )
    aes_fee = aes_sum * ( df_aesthetic / 100.0 )

    # ---- 3) ดึงรายการเคสแบบละเอียด แยก SX, AES ----
    #    (ดูว่า detail_id ไม่มี => ใช้ did.id แทน)
    detail_sx_rows = conn.execute("""
        SELECT dih.record_date,
               c.first_name || ' ' || c.last_name AS customer_name,
               did.procedure_category,
               did.procedure_name,
               did.procedure_short_code,
               did.procedure_price
        FROM daily_income_detail did
        JOIN daily_income_header dih ON did.header_id = dih.id
        JOIN customers c ON c.id = dih.customer_id
        WHERE did.procedure_doctor = ?
          AND dih.record_date >= ? AND dih.record_date <= ?
          AND did.procedure_category = 'SX'
        ORDER BY dih.record_date ASC, did.id ASC
    """, (doctor_short_name, start_dt, end_dt)).fetchall()

    detail_aes_rows = conn.execute("""
        SELECT dih.record_date,
               c.first_name || ' ' || c.last_name AS customer_name,
               did.procedure_category,
               did.procedure_name,
               did.procedure_short_code,
               did.procedure_price
        FROM daily_income_detail did
        JOIN daily_income_header dih ON did.header_id = dih.id
        JOIN customers c ON c.id = dih.customer_id
        WHERE did.procedure_doctor = ?
          AND dih.record_date >= ? AND dih.record_date <= ?
          AND did.procedure_category = 'AES'
        ORDER BY dih.record_date ASC, did.id ASC
    """, (doctor_short_name, start_dt, end_dt)).fetchall()

    conn.close()

    months = get_months()

    return render_template(
        'doctor/doctor_income_summary.html',
        year=year,
        month=month,
        months=months,
        sx_sum=sx_sum,
        aes_sum=aes_sum,
        sx_fee=sx_fee,
        aes_fee=aes_fee,
        # ตาราง SX, AES
        detail_sx_rows=detail_sx_rows,
        detail_aes_rows=detail_aes_rows
    )
