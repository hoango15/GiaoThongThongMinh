import tkinter as tk
from tkinter import filedialog, messagebox
import cv2
from PIL import Image, ImageTk
import os
import threading
import time
import random, string
import traceback

# các module phụ
from IdentifiedViaCamera import recognize_license_plate_from_camera
from Video_recognition import main as process_video_from_file
from add_missing_data import main as add_missing_data_main
from visualize import main as visualize_main
from database import (
    insert_vehicle, find_vehicle_by_ticket, update_vehicle_exit,
    can_vehicle_enter, update_vehicle_count, get_current_count
)

# cố gắng import hàm tìm theo biển số
try:
    from database import find_vehicle_by_plate
except Exception:
    find_vehicle_by_plate = None


class BaseWindow:
    def __init__(self, root):
        self.root = root
        self.stop_event = threading.Event()
        self.video_running = False
        self.displayed_image = None
        self.detected_plate = None
        self.detected_vehicle_img = None
        self.detected_plate_img = None

    def reset_stop(self):
        self.stop_event.clear()

    def request_stop(self):
        self.stop_event.set()

    def show_capacity_info(self, parent):
        """Thêm label hiển thị số xe hiện tại và sức chứa còn lại"""
        frame = tk.Frame(parent)
        frame.pack(pady=4)
        count = get_current_count()
        text = f"🚗 Hiện có {count} xe trong bãi."
        self.capacity_label = tk.Label(frame, text=text, fg="blue")
        self.capacity_label.pack()

    def refresh_capacity(self):
        try:
            count = get_current_count()
            self.capacity_label.config(text=f"🚗 Hiện có {count} xe trong bãi.")
        except Exception:
            pass


class MainApp(tk.Tk, BaseWindow):
    def __init__(self):
        tk.Tk.__init__(self)
        BaseWindow.__init__(self, self)
        self.title("Hệ thống bãi đỗ xe - Quản lý")
        self.geometry("720x400")
        self.resizable(False, False)
        self.create_widgets()

    def create_widgets(self):
        tk.Label(self, text="HỆ THỐNG QUẢN LÝ BÃI ĐỖ - CHỌN CHỨC NĂNG", font=("Arial", 14)).pack(pady=12)
        btn_frame = tk.Frame(self)
        btn_frame.pack(pady=10)
        tk.Button(btn_frame, text="🚗 Xử lý - Xe vào", width=20, command=self.open_entry_window).grid(row=0, column=0, padx=8, pady=6)
        tk.Button(btn_frame, text="🚙 Xử lý - Xe ra", width=20, command=self.open_exit_window).grid(row=0, column=1, padx=8, pady=6)
        tk.Button(btn_frame, text="🔍 Tìm xe theo biển số", width=20, command=self.open_search_window).grid(row=1, column=0, padx=8, pady=6)
        tk.Button(btn_frame, text="🎞 Xử lý Video (batch)", width=20, command=self.open_video_process_dialog).grid(row=1, column=1, padx=8, pady=6)
        tk.Label(self, text="Ghi chú: Nhớ để các module xử lý ảnh / DB cùng folder.", fg="gray").pack(pady=8)
        self.show_capacity_info(self)

    def open_entry_window(self):
        EntryWindow(self)

    def open_exit_window(self):
        ExitWindow(self)

    def open_search_window(self):
        SearchWindow(self)

    def open_video_process_dialog(self):
        VideoProcessWindow(self)


class EntryWindow(tk.Toplevel, BaseWindow):
    def __init__(self, master):
        tk.Toplevel.__init__(self, master)
        BaseWindow.__init__(self, master)
        self.title("Xe vào - Nhận diện biển số")
        self.geometry("1000x680")
        self.resizable(False, False)

        self.status_var = tk.StringVar(value="Sẵn sàng...")
        self.create_widgets()
        self.camera_thread = None

    def create_widgets(self):
        left = tk.LabelFrame(self, text="Điều khiển", padx=10, pady=10)
        left.place(x=10, y=10, width=300, height=340)

        tk.Label(left, text="Nguồn:").pack(anchor="w")
        self.source_var = tk.StringVar(value="camera")
        tk.Radiobutton(left, text="Camera realtime", variable=self.source_var, value="camera").pack(anchor="w")
        tk.Radiobutton(left, text="File video", variable=self.source_var, value="video").pack(anchor="w")

        tk.Button(left, text="▶ BẮT ĐẦU", bg="green", fg="white", command=self.start).pack(fill="x", pady=(10,5))
        tk.Button(left, text="⏹ DỪNG", bg="red", fg="white", command=self.stop).pack(fill="x")
        tk.Button(left, text="💾 XÁC NHẬN LƯU (Xe vào)", bg="blue", fg="white", command=self.confirm_save).pack(fill="x", pady=(20,5))
        tk.Button(left, text="❌ Exit", bg="gray", command=self.destroy).pack(fill="x", pady=(20,5))

        self.show_capacity_info(left)

        # Right: video + info
        self.video_label = tk.Label(self, bg="black")
        self.video_label.place(x=320, y=10, width=640, height=480)

        info_frame = tk.LabelFrame(self, text="Thông tin", padx=10, pady=10)
        info_frame.place(x=10, y=360, width=960, height=300)
        self.info_text = tk.Label(info_frame, text="Chưa có dữ liệu nhận diện...", anchor="nw", justify="left")
        self.info_text.pack(fill="x")

    def confirm_save(self):
        if not self.detected_plate:
            messagebox.showwarning("Chưa có dữ liệu", "Chưa nhận diện được biển số để lưu!")
            return
        if not can_vehicle_enter():
            messagebox.showerror("Bãi đầy", "Không thể cho xe vào, bãi đã đầy!")
            return
        ts = time.time()
        ticket_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        try:
            insert_vehicle(self.detected_plate, ticket_code, self.detected_vehicle_img, self.detected_plate_img)
            update_vehicle_count(+1)  # tăng số xe trong bãi
            self.refresh_capacity()
            self.info_text.config(text=f"Xe vào!\nBiển số: {self.detected_plate}\nMã vé: {ticket_code}\nThời gian: {time.ctime(ts)}")
            messagebox.showinfo("Thành công", f"Lưu xe vào thành công!\nMã vé: {ticket_code}")
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Lỗi", f"Lưu vào DB thất bại:\n{e}")


class ExitWindow(tk.Toplevel, BaseWindow):
    def __init__(self, master):
        tk.Toplevel.__init__(self, master)
        BaseWindow.__init__(self, master)
        self.title("Xe ra - Xác nhận và tính phí")
        self.geometry("1000x680")
        self.resizable(False, False)

        self.status_var = tk.StringVar(value="Sẵn sàng...")
        self.ticket_var = tk.StringVar()
        self.source_var = tk.StringVar(value="camera")

        self.create_widgets()
        self.camera_thread = None

    def create_widgets(self):
        left = tk.LabelFrame(self, text="Điều khiển", padx=10, pady=10)
        left.place(x=10, y=10, width=300, height=340)

        tk.Label(left, text="Nhập mã vé (xe ra):").pack(anchor="w")
        tk.Entry(left, textvariable=self.ticket_var, width=25).pack(anchor="w", pady=(0,10))
        tk.Button(left, text="Xác nhận (so sánh & ra)", bg="blue", fg="white", command=self.confirm_exit).pack(fill="x", pady=(10,5))
        tk.Button(left, text="❌ Exit", bg="gray", command=self.destroy).pack(fill="x", pady=(20,5))

        self.show_capacity_info(left)

        # Right
        self.video_label = tk.Label(self, bg="black")
        self.video_label.place(x=320, y=10, width=640, height=480)
        self.info_text = tk.Label(self, text="Chưa có dữ liệu...", anchor="nw", justify="left")
        self.info_text.place(x=10, y=360, width=960, height=300)

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
        db_plate = row[1]  # license_plate
        if db_plate == self.detected_plate:
            try:
                cost = update_vehicle_exit(ticket_code, time.time())
                update_vehicle_count(-1)  # giảm số xe
                self.refresh_capacity()
                self.info_text.config(text=f"Xe ra!\nBiển số: {self.detected_plate}\nMã vé: {ticket_code}\nPhí: {cost} VND")
                messagebox.showinfo("Thành công", f"Xe ra hợp lệ!\nChi phí: {cost} VND")
            except Exception as e:
                traceback.print_exc()
                messagebox.showerror("Lỗi", f"Cập nhật DB thất bại: {e}")
        else:
            messagebox.showerror("Sai biển số", "Biển số không khớp với vé!")


class SearchWindow(tk.Toplevel, BaseWindow):
    def __init__(self, master):
        super().__init__(master)
        BaseWindow.__init__(self, master)
        self.title("Tìm xe theo biển số")
        self.geometry("700x420")
        self.resizable(False, False)
        self.create_widgets()

    def create_widgets(self):
        frame = tk.Frame(self, padx=10, pady=10)
        frame.pack(fill="both", expand=True)
        tk.Label(frame, text="Nhập biển số:").grid(row=0, column=0, sticky="w")
        self.plate_var = tk.StringVar()
        tk.Entry(frame, textvariable=self.plate_var, width=30).grid(row=0, column=1, sticky="w")
        tk.Button(frame, text="🔍 Tìm", command=self.search).grid(row=0, column=2, padx=8)
        tk.Button(frame, text="❌ Exit", command=self.destroy).grid(row=0, column=3, padx=8)
        self.info_text = tk.Label(frame, text="Kết quả sẽ hiển thị ở đây...", anchor="nw", justify="left")
        self.info_text.grid(row=1, column=0, columnspan=4, sticky="w", pady=(10,0))


class VideoProcessWindow(tk.Toplevel, BaseWindow):
    def __init__(self, master):
        super().__init__(master)
        BaseWindow.__init__(self, master)
        self.title("Xử lý Video")
        self.geometry("500x200")
        self.resizable(False, False)
        self.create_widgets()

    def create_widgets(self):
        frame = tk.Frame(self, padx=10, pady=10)
        frame.pack(fill="both", expand=True)
        tk.Button(frame, text="Chọn video & Xử lý", command=self.choose_and_process).pack(pady=10)
        tk.Button(frame, text="❌ Exit", command=self.destroy).pack(pady=10)
        self.status_label = tk.Label(frame, text="Trạng thái: chờ...")
        self.status_label.pack(pady=6)
