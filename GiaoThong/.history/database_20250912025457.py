import mysql.connector
from datetime import datetime
import math

# ================== CONNECT DB ==================
def get_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",        # đổi user nếu khác
        password="",        # nhập mật khẩu MySQL của bạn
        database="parking_system"
    )

# ================== CONFIG ==================
def can_vehicle_enter():
    """Kiểm tra bãi còn chỗ trống không"""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT max_capacity, current_count FROM config LIMIT 1")
    max_cap, cur_count = cur.fetchone()
    cur.close(); conn.close()
    return cur_count < max_cap

def get_current_count():
    """Lấy số lượng xe hiện tại trong bãi"""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT current_count FROM config LIMIT 1")
    count, = cur.fetchone()
    cur.close(); conn.close()
    return count

# ================== VEHICLES ==================
def insert_vehicle(plate, ticket_code, vehicle_img_in, plate_img):
    """Thêm xe vào DB khi gửi"""
    conn = get_connection()
    cur = conn.cursor()
    sql = """
        INSERT INTO vehicles 
        (license_plate, ticket_code, time_in, vehicle_img_in_path, plate_img_path)
        VALUES (%s, %s, %s, %s, %s)
    """
    cur.execute(sql, (plate, ticket_code, datetime.now(), vehicle_img_in, plate_img))

    # tăng số lượng xe trong config
    cur.execute("UPDATE config SET current_count = current_count + 1")
    conn.commit()
    cur.close(); conn.close()

def update_vehicle_exit(ticket_code, vehicle_img_out=None):
    """
    Cập nhật xe ra + tính phí:
      - <= 10h : 10k
      - >10h & <=24h : 30k
      - >24h : ceil(số giờ) * 5k
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

    # Tính số giờ gửi
    diff_hours = (time_out - time_in).total_seconds() / 3600
    diff_hours_ceil = math.ceil(diff_hours)

    # Tính phí theo quy tắc
    if diff_hours_ceil <= 10:
        fee = 10000
    elif diff_hours_ceil <= 24:
        fee = 30000
    else:
        fee = diff_hours_ceil * 5000

    # Cập nhật DB (thêm ảnh xe ra nếu có)
    if vehicle_img_out:
        cur.execute(
            "UPDATE vehicles SET time_out=%s, fee=%s, vehicle_img_out_path=%s WHERE ticket_code=%s",
            (time_out, fee, vehicle_img_out, ticket_code)
        )
    else:
        cur.execute(
            "UPDATE vehicles SET time_out=%s, fee=%s WHERE ticket_code=%s",
            (time_out, fee, ticket_code)
        )

    # giảm số lượng xe trong config
    cur.execute("UPDATE config SET current_count = current_count - 1")

    conn.commit()
    cur.close(); conn.close()
    return fee

def find_vehicle_by_ticket(ticket_code):
    """Tìm xe theo mã vé"""
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM vehicles WHERE ticket_code=%s", (ticket_code,))
    row = cur.fetchone()
    cur.close(); conn.close()
    return row

def find_vehicle_by_plate(plate):
    """Tìm xe theo biển số (lấy bản ghi mới nhất)"""
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("""
        SELECT id, license_plate, ticket_code, time_in, time_out, fee, 
               vehicle_img_in_path, vehicle_img_out_path, plate_img_path
        FROM vehicles 
        WHERE license_plate=%s 
        ORDER BY time_in DESC 
        LIMIT 1
    """, (plate,))
    row = cur.fetchone()
    cur.close(); conn.close()
    return row

# ================== FORMAT INFO ==================
def pretty_vehicle_info(vehicle):
    """Trả về chuỗi mô tả thông tin xe"""
    if not vehicle:
        return "❌ Không tìm thấy xe"
    
    return f"""
    🚗 Biển số: {vehicle['license_plate']}
    🎫 Mã vé: {vehicle['ticket_code']}
    ⏰ Giờ vào: {vehicle['time_in'].strftime('%d/%m/%Y %H:%M:%S')}
    ⏰ Giờ ra: {vehicle['time_out'].strftime('%d/%m/%Y %H:%M:%S') if vehicle['time_out'] else 'Chưa ra'}
    💰 Phí: {vehicle['fee'] if vehicle['fee'] else 'Chưa tính'}
    📷 Ảnh vào: {vehicle['vehicle_img_in_path'] if vehicle['vehicle_img_in_path'] else 'Không có'}
    📷 Ảnh ra: {vehicle['vehicle_img_out_path'] if vehicle['vehicle_img_out_path'] else 'Chưa chụp'}
    🪪 Ảnh biển số: {vehicle['plate_img_path'] if vehicle['plate_img_path'] else 'Không có'}
    """.strip()
