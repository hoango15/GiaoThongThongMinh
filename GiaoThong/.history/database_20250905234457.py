import mysql.connector
from datetime import datetime

def get_connection():
    return mysql.connector.connect(
        host="localhost",
        user="parking",
        password="",   # mật khẩu của bạn
        database="parking_system"
    )

# Kiểm tra còn chỗ không
def can_vehicle_enter():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT max_capacity, current_count FROM config LIMIT 1")
    max_cap, cur_count = cur.fetchone()
    cur.close(); conn.close()
    return cur_count < max_cap

# Cập nhật số xe
def update_vehicle_count(change):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE config SET current_count = current_count + %s WHERE id=1", (change,))
    conn.commit()
    cur.close(); conn.close()

# Thêm xe vào
def insert_vehicle(plate, ticket_code, vehicle_img, plate_img):
    conn = get_connection()
    cur = conn.cursor()
    sql = """INSERT INTO vehicles 
             (license_plate, ticket_code, time_in, vehicle_img_path, plate_img_path)
             VALUES (%s, %s, %s, %s, %s)"""
    cur.execute(sql, (plate, ticket_code, datetime.now(), vehicle_img, plate_img))
    conn.commit()
    cur.close(); conn.close()

# Xe ra bãi
def update_vehicle_exit(ticket_code, fee):
    conn = get_connection()
    cur = conn.cursor()
    sql = """UPDATE vehicles 
             SET time_out=%s, fee=%s WHERE ticket_code=%s"""
    cur.execute(sql, (datetime.now(), fee, ticket_code))
    conn.commit()
    cur.close(); conn.close()

# Lấy số xe hiện tại
def get_current_count():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT current_count FROM config LIMIT 1")
    count, = cur.fetchone()
    cur.close(); conn.close()
    return count

# Doanh thu hôm nay
def get_today_revenue():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT IFNULL(SUM(fee),0) FROM vehicles WHERE DATE(time_out)=CURDATE()")
    total, = cur.fetchone()
    cur.close(); conn.close()
    return total
