import mysql.connector
from datetime import datetime
import math

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

# ================== VEHICLES ==================
def insert_vehicle(plate, ticket_code, vehicle_img, plate_img):
    conn = get_connection()
    cur = conn.cursor()
    sql = """INSERT INTO vehicles 
             (license_plate, ticket_code, time_in, vehicle_img_path, plate_img_path)
             VALUES (%s, %s, %s, %s, %s)"""
    cur.execute(sql, (plate, ticket_code, datetime.now(), vehicle_img, plate_img))
    conn.commit()
    cur.close(); conn.close()

def update_vehicle_exit(ticket_code, rate_per_hour=10000):
    """
    Cập nhật xe ra + tính phí dựa theo số giờ gửi.
    - rate_per_hour: phí gửi theo giờ (mặc định 10k/h)
    """
    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    # Lấy thời gian vào
    cur.execute("SELECT time_in FROM vehicles WHERE ticket_code=%s AND time_out IS NULL", (ticket_code,))
    row = cur.fetchone()
    if not row:
        cur.close(); conn.close()
        raise Exception("Không tìm thấy xe hoặc xe đã ra")

    time_in = row["time_in"]
    time_out = datetime.now()

    # Tính số giờ, làm tròn lên
    diff_hours = (time_out - time_in).total_seconds() / 3600
    fee = max(rate_per_hour, math.ceil(diff_hours) * rate_per_hour)

    # Cập nhật DB
    cur.execute("UPDATE vehicles SET time_out=%s, fee=%s WHERE ticket_code=%s",
                (time_out, fee, ticket_code))
    conn.commit()
    cur.close(); conn.close()
    return fee

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
        SELECT id, license_plate, ticket_code, time_in, time_out, fee
        FROM vehicles 
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
    ⏰ Giờ vào: {vehicle['time_in'].strftime('%d/%m/%Y %H:%M:%S')}
    ⏰ Giờ ra: {vehicle['time_out'].strftime('%d/%m/%Y %H:%M:%S') if vehicle['time_out'] else 'Chưa ra'}
    💰 Phí: {vehicle['fee'] if vehicle['fee'] else 'Chưa tính'}
    """.strip()
