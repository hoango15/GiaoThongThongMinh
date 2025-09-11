import tkinter as tk
from tkinter import ttk, messagebox
import random, string, time, traceback

from database import (
    insert_vehicle, find_vehicle_by_ticket, update_vehicle_exit,
    find_vehicle_by_plate, can_vehicle_enter, update_vehicle_count,
    get_current_count, get_connection
)

# ============= BaseWindow =============
class BaseWindow:
    def __init__(self, master):
        self.master = master

# ============= EntryWindow (Xe vào) =============
class EntryWindow(tk.Toplevel, BaseWindow):
    def __init__(self, master):
        tk.Toplevel.__init__(self, master)
        BaseWindow.__init__(self, master)
        self.title("🚗 Xe vào")
        self.geometry("500x350")
        self.detected_plate = None
        self.detected_vehicle_img = None
        self.detected_plate_img = None

        self.info_text = tk.Label(self, text="Chưa nhận diện biển số", font=("Arial", 12))
        self.info_text.pack(pady=20)

        ttk.Button(self, text="Nhận diện & Lưu xe", command=self.confirm_save).pack(pady=10)
        ttk.Button(self, text="Exit", command=self.destroy).pack(pady=5)

    def confirm_save(self):
        # giả lập biển số ngẫu nhiên
        self.detected_plate = "29A-" + str(random.randint(10000, 99999))

        if not can_vehicle_enter():
            messagebox.showwarning("Bãi xe đầy", "Không thể cho xe vào nữa!")
            return

        ts = time.time()
        ticket_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        try:
            insert_vehicle(self.detected_plate, ticket_code, "vehicle.jpg", "plate.jpg")
            update_vehicle_count(+1)   # tăng số xe
            self.info_text.config(text=f"Xe vào!\nBiển số: {self.detected_plate}\nMã vé: {ticket_code}\nThời gian: {time.ctime(ts)}")
            messagebox.showinfo("Thành công", f"Lưu xe vào thành công!\nMã vé: {ticket_code}")
            self.master.update_capacity_label()
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Lỗi", f"Lưu vào DB thất bại:\n{e}")

# ============= ExitWindow (Xe ra) =============
class ExitWindow(tk.Toplevel, BaseWindow):
    def __init__(self, master):
        tk.Toplevel.__init__(self, master)
        BaseWindow.__init__(self, master)
        self.title("🚙 Xe ra")
        self.geometry("500x350")
        self.detected_plate = None

        self.ticket_var = tk.StringVar()

        tk.Label(self, text="Nhập mã vé:", font=("Arial", 12)).pack(pady=5)
        ttk.Entry(self, textvariable=self.ticket_var, font=("Arial", 12)).pack(pady=5)

        ttk.Button(self, text="Xác nhận ra", command=self.confirm_exit).pack(pady=10)
        ttk.Button(self, text="Exit", command=self.destroy).pack(pady=5)

        self.info_text = tk.Label(self, text="", font=("Arial", 12))
        self.info_text.pack(pady=15)

    def confirm_exit(self):
        ticket_code = self.ticket_var.get().strip()
        if not ticket_code:
            messagebox.showerror("Lỗi", "Cần nhập mã vé để xác nhận xe ra")
            return
        try:
            row = find_vehicle_by_ticket(ticket_code)
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Lỗi DB", f"Lỗi khi truy vấn vé: {e}")
            return
        if not row:
            messagebox.showerror("Sai mã vé", f"Không tìm thấy vé {ticket_code}")
            return

        # giả lập nhận diện biển số
        self.detected_plate = row["license_plate"]

        db_plate = row["license_plate"]
        if db_plate == self.detected_plate:
            try:
                fee = 10000
                update_vehicle_exit(ticket_code, fee)
                update_vehicle_count(-1)   # giảm số xe
                self.info_text.config(text=f"Xe ra!\nBiển số: {self.detected_plate}\nMã vé: {ticket_code}\nPhí: {fee} VND")
                messagebox.showinfo("Thành công", f"Xe ra hợp lệ!\nChi phí: {fee} VND")
                self.master.update_capacity_label()
            except Exception as e:
                traceback.print_exc()
                messagebox.showerror("Lỗi", f"Cập nhật DB thất bại: {e}")
        else:
            messagebox.showerror("Sai biển số", "Biển số không khớp với vé!")

# ============= SearchWindow (Tìm xe) =============
class SearchWindow(tk.Toplevel, BaseWindow):
    def __init__(self, master):
        tk.Toplevel.__init__(self, master)
        BaseWindow.__init__(self, master)
        self.title("🔍 Tìm xe")
        self.geometry("500x350")

        self.plate_var = tk.StringVar()
        tk.Label(self, text="Nhập biển số:", font=("Arial", 12)).pack(pady=5)
        ttk.Entry(self, textvariable=self.plate_var, font=("Arial", 12)).pack(pady=5)

        ttk.Button(self, text="Tìm", command=self.search).pack(pady=10)
        ttk.Button(self, text="Exit", command=self.destroy).pack(pady=5)

        self.info_text = tk.Label(self, text="", font=("Arial", 12))
        self.info_text.pack(pady=15)

    def search(self):
        plate = self.plate_var.get().strip()
        if not plate:
            messagebox.showerror("Lỗi", "Cần nhập biển số để tìm")
            return
        try:
            row = find_vehicle_by_plate(plate)
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Lỗi DB", f"Lỗi khi truy vấn: {e}")
            return
        if not row:
            self.info_text.config(text=f"Không tìm thấy xe {plate}")
        else:
            self.info_text.config(text=f"Xe: {row['license_plate']}\nMã vé: {row['ticket_code']}\nVào lúc: {row['time_in']}")

# ============= MainApp =============
class MainApp(tk.Tk, BaseWindow):
    def __init__(self):
        tk.Tk.__init__(self)
        BaseWindow.__init__(self, self)
        self.title("🚦 Hệ thống quản lý bãi đỗ xe")
        self.geometry("600x400")
        self.resizable(False, False)

        style = ttk.Style(self)
        style.configure("TButton", font=("Arial", 12), padding=8)

        self.create_widgets()
        self.update_capacity_label()

    def create_widgets(self):
        tk.Label(self, text="HỆ THỐNG QUẢN LÝ BÃI ĐỖ XE", 
                 font=("Arial", 16, "bold"), fg="blue").pack(pady=20)

        btn_frame = ttk.Frame(self)
        btn_frame.pack(pady=15)

        ttk.Button(btn_frame, text="🚗 Xe vào", width=20, command=self.open_entry_window).grid(row=0, column=0, padx=15, pady=10)
        ttk.Button(btn_frame, text="🚙 Xe ra", width=20, command=self.open_exit_window).grid(row=0, column=1, padx=15, pady=10)
        ttk.Button(btn_frame, text="🔍 Tìm xe", width=43, command=self.open_search_window).grid(row=1, column=0, columnspan=2, pady=10)

        # Label hiển thị số lượng xe
        self.capacity_var = tk.StringVar(value="Đang tải...")
        tk.Label(self, textvariable=self.capacity_var, font=("Arial", 12), fg="darkgreen").pack(pady=10)

    def update_capacity_label(self):
        try:
            count = get_current_count()
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("SELECT max_capacity FROM config LIMIT 1")
            max_cap, = cur.fetchone()
            cur.close(); conn.close()

            self.capacity_var.set(f"🚘 Trong bãi: {count}/{max_cap}")
        except Exception as e:
            self.capacity_var.set(f"Lỗi tải số lượng: {e}")

    def open_entry_window(self):
        EntryWindow(self)

    def open_exit_window(self):
        ExitWindow(self)

    def open_search_window(self):
        SearchWindow(self)

if __name__ == "__main__":
    app = MainApp()
    app.mainloop()
