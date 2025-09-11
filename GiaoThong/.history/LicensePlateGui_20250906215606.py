import tkinter as tk
from tkinter import filedialog, messagebox
import cv2
from PIL import Image, ImageTk
import os
import threading
import time
import random, string
import traceback

# các module phụ (giữ nguyên như project của bạn)
from IdentifiedViaCamera import recognize_license_plate_from_camera
from Video_recognition import main as process_video_from_file
from add_missing_data import main as add_missing_data_main
from visualize import main as visualize_main
from database import insert_vehicle, find_vehicle_by_ticket, update_vehicle_exit

# cố gắng import hàm tìm theo biển số; nếu database.py chưa có thì sẽ báo khi dùng
try:
    from database import find_vehicle_by_plate
except Exception:
    find_vehicle_by_plate = None


class BaseWindow:
    """Common helpers for windows"""
    def __init__(self, root):
        self.root = root
        self.stop_event = threading.Event()
        self.video_running = False
        self.displayed_image = None  # to keep reference
        # temp detected items
        self.detected_plate = None
        self.detected_vehicle_img = None
        self.detected_plate_img = None

    def reset_stop(self):
        self.stop_event.clear()

    def request_stop(self):
        self.stop_event.set()


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

    def open_entry_window(self):
        EntryWindow(self)

    def open_exit_window(self):
        ExitWindow(self)

    def open_search_window(self):
        SearchWindow(self)

    def open_video_process_dialog(self):
        VideoProcessWindow(self)


class EntryWindow(tk.Toplevel, BaseWindow):
    """Cửa sổ xử lý xe vào"""
    def __init__(self, master):
        tk.Toplevel.__init__(self, master)
        BaseWindow.__init__(self, master)
        self.title("Xe vào - Nhận diện biển số")
        self.geometry("1000x640")
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
        tk.Button(left, text="❌ Thoát", bg="gray", fg="white", command=self.destroy).pack(fill="x", pady=(10,5))

        # Right: video + info
        self.video_label = tk.Label(self, bg="black")
        self.video_label.place(x=320, y=10, width=640, height=480)

        info_frame = tk.LabelFrame(self, text="Thông tin", padx=10, pady=10)
        info_frame.place(x=10, y=360, width=960, height=250)

        self.info_text = tk.Label(info_frame, text="Chưa có dữ liệu nhận diện...", anchor="nw", justify="left")
        self.info_text.pack(fill="x")

        imgs = tk.Frame(info_frame)
        imgs.pack(pady=6)
        self.vehicle_img_label = tk.Label(imgs, text="Ảnh xe")
        self.vehicle_img_label.grid(row=0, column=0, padx=8)
        self.plate_img_label = tk.Label(imgs, text="Ảnh biển số")
        self.plate_img_label.grid(row=0, column=1, padx=8)

        status_bar = tk.Label(self, textvariable=self.status_var, bd=1, relief="sunken", anchor="w")
        status_bar.place(x=0, y=620, relwidth=1)

    def start(self):
        src = self.source_var.get()
        self.reset_stop()
        self.status_var.set("Đang chạy...")
        if src == "camera":
            self.camera_thread = threading.Thread(target=self.process_camera, daemon=True)
            self.camera_thread.start()
        else:
            video_file = filedialog.askopenfilename(title="Chọn video", filetypes=[("Video files", "*.mp4 *.avi *.mov")])
            if not video_file:
                self.status_var.set("Hủy chọn video.")
                return
            self.video_thread = threading.Thread(target=self.process_video_file, args=(video_file,), daemon=True)
            self.video_thread.start()

    def stop(self):
        self.request_stop()
        self.video_running = False
        self.status_var.set("Đã dừng.")
        self.video_label.config(image="", text="")

    def process_camera(self):
        self.video_running = True
        try:
            recognize_license_plate_from_camera(self, mode="in", stop_event=self.stop_event)
        except TypeError:
            try:
                recognize_license_plate_from_camera(self, mode="in")
            except Exception as e:
                traceback.print_exc()
                messagebox.showerror("Lỗi", f"Lỗi khi gọi recognize_license_plate_from_camera:\n{e}")
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Lỗi", f"Lỗi khi xử lý camera:\n{e}")

        self.video_running = False
        if not self.stop_event.is_set():
            self.status_var.set("Hoàn tất nhận diện camera.")
        else:
            self.status_var.set("Nhận diện camera đã dừng bởi người dùng.")

    def process_video_file(self, video_file):
        try:
            process_video_from_file(video_file)
            add_missing_data_main("output_video/results.csv", "output_video/results_interpolated.csv")
            visualize_main(video_file, "output_video/output_video.mp4", "output_video/results_interpolated.csv")
            self.display_output_video("output_video/output_video.mp4")
            self.status_var.set("Xử lý video xong.")
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Lỗi", f"Lỗi xử lý video:\n{e}")
            self.status_var.set("Lỗi xử lý video.")

    def confirm_save(self):
        if not self.detected_plate:
            messagebox.showwarning("Chưa có dữ liệu", "Chưa nhận diện được biển số để lưu!")
            return
        ts = time.time()
        ticket_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        try:
            insert_vehicle(self.detected_plate, ticket_code, self.detected_vehicle_img, self.detected_plate_img)
            self.info_text.config(text=f"Xe vào!\nBiển số: {self.detected_plate}\nMã vé: {ticket_code}\nThời gian: {time.ctime(ts)}")
            messagebox.showinfo("Thành công", f"Lưu xe vào thành công!\nMã vé: {ticket_code}")
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Lỗi", f"Lưu vào DB thất bại:\n{e}")

    def update_detected(self, plate, vpath, ppath):
        self.detected_plate = plate
        self.detected_vehicle_img = vpath
        self.detected_plate_img = ppath
        self.info_text.config(text=f"Nhận diện: {plate}\n(chưa lưu)")
        if vpath and os.path.exists(vpath):
            try:
                vimg = Image.open(vpath).resize((200, 120))
                self.vehicle_img_label.imgtk = ImageTk.PhotoImage(vimg)
                self.vehicle_img_label.config(image=self.vehicle_img_label.imgtk)
            except Exception:
                pass
        if ppath and os.path.exists(ppath):
            try:
                pimg = Image.open(ppath).resize((200, 60))
                self.plate_img_label.imgtk = ImageTk.PhotoImage(pimg)
                self.plate_img_label.config(image=self.plate_img_label.imgtk)
            except Exception:
                pass

    def display_output_video(self, video_file):
        if not os.path.exists(video_file):
            messagebox.showwarning("Không tìm thấy", f"Không tìm thấy file: {video_file}")
            return
        cap = cv2.VideoCapture(video_file)
        self.video_running = True

        def update():
            if not self.video_running or self.stop_event.is_set():
                cap.release()
                return
            ret, frame = cap.read()
            if not ret:
                cap.release()
                self.video_running = False
                return
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(frame_rgb).resize((640, 480))
            self.displayed_image = ImageTk.PhotoImage(img)
            self.video_label.config(image=self.displayed_image)
            self.video_label.image = self.displayed_image
            self.after(30, update)

        update()


class ExitWindow(tk.Toplevel, BaseWindow):
    """Cửa sổ xử lý xe ra"""
    def __init__(self, master):
        tk.Toplevel.__init__(self, master)
        BaseWindow.__init__(self, master)
        self.title("Xe ra - Xác nhận và tính phí")
        self.geometry("1000x640")
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

        tk.Label(left, text="Nguồn:").pack(anchor="w")
        tk.Radiobutton(left, text="Camera realtime", variable=self.source_var, value="camera").pack(anchor="w")
        tk.Radiobutton(left, text="Video file", variable=self.source_var, value="video").pack(anchor="w")

        tk.Button(left, text="▶ BẮT ĐẦU", bg="green", fg="white", command=self.start).pack(fill="x", pady=(10,5))
        tk.Button(left, text="⏹ DỪNG", bg="red", fg="white", command=self.stop).pack(fill="x")
        tk.Button(left, text="Xác nhận (so sánh & ra)", bg="blue", fg="white", command=self.confirm_exit).pack(fill="x", pady=(20,5))
        tk.Button(left, text="❌ Thoát", bg="gray", fg="white", command=self.destroy).pack(fill="x", pady=(10,5))

        self.video_label = tk.Label(self, bg="black")
        self.video_label.place(x=320, y=10, width=640, height=480)

        info_frame = tk.LabelFrame(self, text="Thông tin", padx=10, pady=10)
        info_frame.place(x=10, y=360, width=960, height=250)

        self.info_text = tk.Label(info_frame, text="Chưa có dữ liệu nhận diện...", anchor="nw", justify="left")
        self.info_text.pack(fill="x")

        imgs = tk.Frame(info_frame)
        imgs.pack(pady=6)
        self.vehicle_img_label = tk.Label(imgs, text="Ảnh xe")
        self.vehicle_img_label.grid(row=0, column=0, padx=8)
        self.plate_img_label = tk.Label(imgs, text="Ảnh biển số")
        self.plate_img_label.grid(row=0, column=1, padx=8)

        status_bar = tk.Label(self, textvariable=self.status_var, bd=1, relief="sunken", anchor="w")
        status_bar.place(x=0, y=620, relwidth=1)

    def start(self):
        src = self.source_var.get()
        self.reset_stop()
        self.status_var.set("Đang chạy...")
        if src == "camera":
            self.camera_thread = threading.Thread(target=self.process_camera, daemon=True)
            self.camera_thread.start()
        else:
            video_file = filedialog.askopenfilename(title="Chọn video", filetypes=[("Video files", "*.mp4 *.avi *.mov")])
            if not video_file:
                self.status_var.set("Hủy chọn video.")
                return
            self.video_thread = threading.Thread(target=self.process_video_file, args=(video_file,), daemon=True)
            self.video_thread.start()

    def stop(self):
        self.request_stop()
        self.video_running = False
        self.status_var.set("Đã dừng.")
        self.video_label.config(image="", text="")

    def process_camera(self):
        self.video_running = True
        try:
            recognize_license_plate_from_camera(self, mode="out", stop_event=self.stop_event)
        except TypeError:
            try:
                recognize_license_plate_from_camera(self, mode="out")
            except Exception as e:
                traceback.print_exc()
                messagebox.showerror("Lỗi", f"Lỗi khi gọi recognize_license_plate_from_camera:\n{e}")
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Lỗi", f"Lỗi khi xử lý camera:\n{e}")

        self.video_running = False
        if not self.stop_event.is_set():
            self.status_var.set("Hoàn tất nhận diện camera.")
        else:
            self.status_var.set("Nhận diện camera đã dừng bởi người dùng.")

    def process_video_file(self, video_file):
        try:
            process_video_from_file(video_file)
            add_missing_data_main("output_video/results.csv", "output_video/results_interpolated.csv")
            visualize_main(video_file, "output_video/output_video.mp4", "output_video/results_interpolated.csv")
            self.display_output_video("output_video/output_video.mp4")
            self.status_var.set("Xử lý video xong.")
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Lỗi", f"Lỗi xử lý video:\n{e}")
            self.status_var.set("Lỗi xử lý video.")

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

        db_plate = row[1]      # license_plate
        entry_time = row[3]    # thời gian vào

        if db_plate == self.detected_plate:
            try:
                exit_time = time.time()
                duration = exit_time - entry_time
                hours = max(1, int(duration // 3600))   # làm tròn xuống, tối thiểu 1 giờ
                rate_per_hour = 5000
                cost = hours * rate_per_hour

                update_vehicle_exit(ticket_code, exit_time, cost)

                self.info_text.config(
                    text=f"Xe ra!\nBiển số: {self.detected_plate}\nMã vé: {ticket_code}"
                         f"\nThời gian vào: {time.ctime(entry_time)}"
                         f"\nThời gian ra: {time.ctime(exit_time)}"
                         f"\nPhí: {cost:,} VND"
                )
                messagebox.showinfo("Thành công", f"Xe ra hợp lệ!\nChi phí: {cost:,} VND")
            except Exception as e:
                traceback.print_exc()
                messagebox.showerror("Lỗi", f"Cập nhật DB thất bại: {e}")
        else:
            messagebox.showerror("Sai biển số", "Biển số không khớp với vé!")

    def update_detected(self, plate, vpath, ppath):
        self.detected_plate = plate
        self.detected_vehicle_img = vpath
        self.detected_plate_img = ppath
        self.info_text.config(text=f"Nhận diện: {plate}\n(chưa xác nhận)")
        if vpath
