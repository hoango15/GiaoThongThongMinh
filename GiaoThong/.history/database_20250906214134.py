import mysql.connector
from datetime import datetime

def get_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",         # đổi nếu user khác
        password="",         # nhập mật khẩu MySQL của bạn
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

def update_vehicle_count(change):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE config SET current_count = current_count + %s WHERE id=1", (change,))
    conn.commit()
    cur.close(); conn.close()

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

def update_vehicle_exit(ticket_code, fee):
    conn = get_connection()
    cur = conn.cursor()
    sql = """UPDATE vehicles 
             SET time_out=%s, fee=%s WHERE ticket_code=%s"""
    cur.execute(sql, (datetime.now(), fee, ticket_code))
    conn.commit()
    cur.close(); conn.close()

def find_vehicle_by_ticket(ticket_code):
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM vehicles WHERE ticket_code=%s", (ticket_code,))
    row = cur.fetchone()
    cur.close(); conn.close()
    return row

# ================== USERS ==================
def add_user(username, password_hash, role="staff"):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO users (username, password_hash, role) VALUES (%s,%s,%s)", 
                (username, password_hash, role))
    conn.commit()
    cur.close(); conn.close()

def get_user(username):
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM users WHERE username=%s", (username,))
    row = cur.fetchone()
    cur.close(); conn.close()
    return row

def find_vehicle_by_plate(plate):
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    # Lấy bản ghi mới nhất (nếu có nhiều lần xe vào với cùng biển số)
    cur.execute("""
        SELECT * FROM vehicles 
        WHERE license_plate=%s 
        ORDER BY time_in DESC 
        LIMIT 1
    """, (plate,))
    row = cur.fetchone()
    cur.close(); conn.close()
    return row

# ================== REVENUE ==================
def get_today_revenue():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT IFNULL(total_fee,0) FROM revenue WHERE date=CURDATE()")
    total, = cur.fetchone()
    cur.close(); conn.close()
    return total
