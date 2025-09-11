import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
import traceback, math
from datetime import datetime
import threading

from database import (
    can_vehicle_enter, update_vehicle_count, get_current_count,
    insert_vehicle, update_vehicle_exit, find_vehicle_by_ticket, find_vehicle_by_plate
)
from IdentifiedViaCamera import recognize_license_plate_from_camera

# ================== Entry Window ==================
class EntryWindow(tk.Toplevel):
    def __init__(self, root):
        super().__init__(root)
        self.title("Xe Vào")
        self.geometry("900x600")
        self.video_label = None
        self.detected_plate = None
        self.vehicle_img_path = None
        self.plate_img_path = None
        self.stop_event = threading.Event()
        self.create_widgets()

    def create_widgets(self):
        left = tk.Frame(self)
        left.pack(side="left", padx=10, pady=10, fill="y")

        self.video_label = tk.Label(self)
        self.video_label.pack(side="left", padx=10, pady=10)

        self.status_var = tk.StringVar(value="Chưa nhận diện")
        tk.Label(left, textvariable=self.status_var, fg="blue").pack(pady=5)

        tk.Button(left, text="⏹ DỪNG", bg="red", fg="white",
                  command=lambda: self.stop_event.set()).pack(fill="x", pady=5)
        tk.Button(left, text="✅ XÁC NHẬN LƯU", bg="green", fg="white",
                  command=self.confirm_save).pack(fill="x", pady=5)
        tk.Button(left, text="❌ THOÁT", bg="gray", fg="white",
                  command=self.destroy).pack(fill="x", pady=5)

        recognize_license_plate_from_camera(self, mode="in", stop_event=self.stop_event)

    def update_detected(self, plate, vpath, ppath):
        self.detected_plate = plate
        self.vehicle_img_path = vpath
        self.plate_img_path = ppath
        self.status_var.set(f"Nhận diện: {plate}")

    def confirm_save(self):
        if not self.detected_plate:
            messagebox.showerror("Lỗi", "Chưa có biển số!")
            return
        if not can_vehicle_enter():
            messagebox.showwarning("Đầy bãi", "Không thể cho xe vào, bãi đã đầy")
            return
        try:
            ticket_code = f"T{int(datetime.now().timestamp())}"
            insert_vehicle(self.detected_plate, ticket_code, self.vehicle_img_path, self.plate_img_path)
            update_vehicle_count(1)
            messagebox.showinfo("Thành công", f"Đã lưu xe {self.detected_plate}, mã vé: {ticket_code}")
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Lỗi DB", str(e))

# ================== Exit Window ==================
class ExitWindow(tk.Toplevel):
    def __init__(self, root):
        super().__init__(root)
        self.title("Xe Ra")
        self.geometry("900x600")
        self.video_label = None
        self.detected_plate = None
        self.stop_event = threading.Event()
        self.create_widgets()

    def create_widgets(self):
        left = tk.Frame(self)
        left.pack(side="left", padx=10, pady=10, fill="y")

        self.video_label = tk.Label(self)
        self.video_label.pack(side="left", padx=10, pady=10)

        self.ticket_var = tk.StringVar()
        tk.Entry(left, textvariable=self.ticket_var).pack(pady=5)

        self.info_text = tk.Label(left, text="", fg="blue")
        self.info_text.pack(pady=5)

        tk.Button(left, text="⏹ DỪNG", bg="red", fg="white",
                  command=lambda: self.stop_event.set()).pack(fill="x", pady=5)
        tk.Button(left, text="✅ XÁC NHẬN XE RA", bg="green", fg="white",
                  command=self.confirm_exit).pack(fill="x", pady=5)
        tk.Button(left, text="❌ THOÁT", bg="gray", fg="white",
                  command=self.destroy).pack(fill="x", pady=5)

        recognize_license_plate_from_camera(self, mode="out", stop_event=self.stop_event)

    def update_detected(self, plate, vpath, ppath):
        self.detected_plate = plate
        self.info_text.config(text=f"Nhận diện: {plate}")

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

        db_plate = row["license_plate"]
        time_in = row["time_in"]

        if db_plate == self.detected_plate:
            try:
                now = datetime.now()
                duration = (now - time_in).total_seconds() / 3600
                hours = math.ceil(duration)
                fee = hours * 5000

                update_vehicle_exit(ticket_code, fee)
                update_vehicle_count(-1)

                self.info_text.config(text=f"Xe ra!\nBiển số: {self.detected_plate}\nMã vé: {ticket_code}\nPhí: {fee} VND")
                messagebox.showinfo("Thành công", f"Xe ra hợp lệ!\nChi phí: {fee} VND")
            except Exception as e:
                traceback.print_exc()
                messagebox.showerror("Lỗi", f"Cập nhật DB thất bại: {e}")
        else:
            messagebox.showerror("Sai biển số", "Biển số không khớp với vé!")

# ================== Search Window ==================
class SearchWindow(tk.Toplevel):
    def __init__(self, root):
        super().__init__(root)
        self.title("Tra cứu xe")
        self.geometry("600x400")

        tk.Label(self, text="Nhập biển số:").pack(pady=5)
        self.plate_var = tk.StringVar()
        tk.Entry(self, textvariable=self.plate_var).pack(pady=5)

        tk.Button(self, text="Tìm", command=self.search).pack(pady=5)
        tk.Button(self, text="❌ THOÁT", bg="gray", fg="white",
                  command=self.destroy).pack(pady=5)

        self.result_text = tk.Label(self, text="", justify="left")
        self.result_text.pack(pady=10)

    def search(self):
        plate = self.plate_var.get().strip()
        if not plate:
            return
        row = find_vehicle_by_plate(plate)
        if not row:
            self.result_text.config(text="Không tìm thấy xe")
            return
        txt = f"Biển số: {row['license_plate']}\nMã vé: {row['ticket_code']}\nVào lúc: {row['time_in']}\n"
        if row['time_out']:
            txt += f"Ra lúc: {row['time_out']}\nPhí: {row['fee']} VND"
        else:
            txt += "Chưa ra bãi"
        self.result_text.config(text=txt)

# ================== Main App ==================
class ParkingApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Hệ thống bãi xe")
        self.geometry("400x300")

        ttk.Button(self, text="🚗 Xe vào", command=lambda: EntryWindow(self)).pack(pady=10)
        ttk.Button(self, text="🏍️ Xe ra", command=lambda: ExitWindow(self)).pack(pady=10)
        ttk.Button(self, text="🔍 Tra cứu", command=lambda: SearchWindow(self)).pack(pady=10)

        self.count_var = tk.StringVar(value=f"Xe hiện tại: {get_current_count()}")
        tk.Label(self, textvariable=self.count_var, fg="blue").pack(pady=20)

        self.update_count_loop()

    def update_count_loop(self):
        self.count_var.set(f"Xe hiện tại: {get_current_count()}")
        self.after(5000, self.update_count_loop)

if __name__ == "__main__":
    app = ParkingApp()
    app.mainloop()
