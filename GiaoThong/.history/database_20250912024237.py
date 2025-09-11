import mysql.connector
from datetime import datetime
import math

# ================== KẾT NỐI ==================
def get_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",        # đổi user nếu khác
        password="",        # nhập mật khẩu MySQL của bạn
        database="parking_system"
    )

# ================== CONFIG ==================
def can_vehicle_enter():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT max_capacity, current_count FROM config LIMIT 1")
    max_cap, cur_count = cur.fetchone()
    cur.close(); conn.close()
    return cur_count < max_cap

def get_current_count():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT current_count FROM config LIMIT 1")
    count, = cur.fetchone()
    cur.close(); conn.close()
    return count

# ================== XE VÀO ==================
def insert_vehicle(plate, ticket_code, vehicle_type, vehicle_img_in, plate_img_in):
    """
    Thêm xe vào DB + cập nhật số lượng xe hiện tại.
    """
    conn = get_connection()
    cur = conn.cursor()
    sql = """INSERT INTO vehicles 
             (license_plate, ticket_code, vehicle_type, time_in, vehicle_img_in_path, plate_img_in_path)
             VALUES (%s, %s, %s, %s, %s, %s)"""
    cur.execute(sql, (plate, ticket_code, vehicle_type, datetime.now(), vehicle_img_in, plate_img_in))

    # tăng số lượng xe hiện tại
    cur.execute("UPDATE config SET current_count = current_count + 1 WHERE id=1")

    conn.commit()
    cur.close(); conn.close()

# ================== XE RA ==================
def update_vehicle_exit(ticket_code, vehicle_img_out=None, plate_img_out=None):
    """
    Cập nhật xe ra + tính phí tự động theo loại xe + lưu ảnh ra + giảm số lượng xe.
    """
    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    # Lấy thông tin xe
    cur.execute("SELECT time_in, vehicle_type FROM vehicles WHERE ticket_code=%s AND time_out IS NULL", (ticket_code,))
    row = cur.fetchone()
    if not row:
        cur.close(); conn.close()
        raise Exception("❌ Không tìm thấy xe hoặc xe đã ra")

    time_in = row["time_in"]
    vehicle_type = row["vehicle_type"]
    time_out = datetime.now()

    # Tính số giờ gửi (làm tròn lên)
    diff_hours = (time_out - time_in).total_seconds() / 3600
    diff_hours = math.ceil(diff_hours)

    # Quy tắc tính phí
    if vehicle_type == "Xe máy":
        if diff_hours <= 24:
            fee = 10000
        else:
            fee = 50000

    elif vehicle_type == "Ô tô":
        if diff_hours <= 24:
            fee = 50000
        else:
            fee = diff_hours * 20000

    elif vehicle_type == "Xe tải trọng lớn":
        fee = diff_hours * 10000

    else:
        fee = 0  # fallback nếu loại xe không hợp lệ

    # Cập nhật DB: thêm ảnh xe ra
    cur.execute("""
        UPDATE vehicles 
        SET time_out=%s, fee=%s, vehicle_img_out_path=%s, plate_img_out_path=%s
        WHERE ticket_code=%s
    """, (time_out, fee, vehicle_img_out, plate_img_out, ticket_code))

    # giảm số lượng xe đang gửi
    cur.execute("UPDATE config SET current_count = current_count - 1 WHERE id=1 AND current_count > 0")

    conn.commit()
    cur.close(); conn.close()
    return fee

# ================== TRA CỨU ==================
def find_vehicle_by_ticket(ticket_code):
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM vehicles WHERE ticket_code=%s", (ticket_code,))
    row = cur.fetchone()
    cur.close(); conn.close()
    return row

def find_vehicle_by_plate(plate):
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("""
        SELECT * FROM vehicles 
        WHERE license_plate=%s 
        ORDER BY time_in DESC 
        LIMIT 1
    """, (plate,))
    row = cur.fetchone()
    cur.close(); conn.close()
    return row

def pretty_vehicle_info(vehicle):
    if not vehicle:
        return "❌ Không tìm thấy xe"
    
    return f"""
    🚗 Biển số: {vehicle['license_plate']}
    🎫 Mã vé: {vehicle['ticket_code']}
    Loại xe: {vehicle['vehicle_type']}
    ⏰ Giờ vào: {vehicle['time_in'].strftime('%d/%m/%Y %H:%M:%S')}
    ⏰ Giờ ra: {vehicle['time_out'].strftime('%d/%m/%Y %H:%M:%S') if vehicle['time_out'] else 'Chưa ra'}
    💰 Phí: {vehicle['fee'] if vehicle['fee'] else 'Chưa tính'}
    """.strip()
