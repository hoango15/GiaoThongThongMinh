import tkinter as tk
from tkinter import filedialog, messagebox
from turtle import left
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
        # temp detected items (shared between windows if desired)
        self.detected_plate = None
        self.detected_vehicle_img = None
        self.detected_plate_img = None

    def reset_stop(self):
        self.stop_event.clear()

    def request_stop(self):
        self.stop_event.set()


# ====== MAIN MENU ======
class MainApp(tk.Tk, BaseWindow):
    def __init__(self):
        tk.Tk.__init__(self)
        BaseWindow.__init__(self, self)

        self.title("🚦 Hệ thống bãi đỗ xe - Quản lý")
        self.geometry("750x450")
        self.configure(bg="#f2f6fa")  # nền sáng nhẹ
        self.resizable(False, False)

        self.create_widgets()

    def create_widgets(self):
        tk.Label(self, text="HỆ THỐNG QUẢN LÝ BÃI ĐỖ", font=("Arial", 18, "bold"), bg="#f2f6fa", fg="#222").pack(pady=20)

        btn_frame = tk.Frame(self, bg="#f2f6fa")
        btn_frame.pack(pady=20)

        style = {"width": 22, "height": 2, "font": ("Arial", 12), "relief": "raised"}

        tk.Button(btn_frame, text="🚗 Xe vào", bg="#4CAF50", fg="white", command=self.open_entry_window, **style).grid(row=0, column=0, padx=12, pady=10)
        tk.Button(btn_frame, text="🚙 Xe ra", bg="#E53935", fg="white", command=self.open_exit_window, **style).grid(row=0, column=1, padx=12, pady=10)
        tk.Button(btn_frame, text="🔍 Tìm xe", bg="#2196F3", fg="white", command=self.open_search_window, **style).grid(row=1, column=0, padx=12, pady=10)
        tk.Button(btn_frame, text="🎞 Xử lý Video", bg="#FF9800", fg="white", command=self.open_video_process_dialog, **style).grid(row=1, column=1, padx=12, pady=10)

        tk.Label(self, text="ℹ️ Lưu ý: Các module xử lý ảnh / DB cần đặt cùng thư mục.",
                 font=("Arial", 10), bg="#f2f6fa", fg="gray").pack(pady=10)

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
        self.geometry("1000x640")
        self.resizable(False, False)

        self.status_var = tk.StringVar(value="Sẵn sàng...")
        self.create_widgets()
        self.camera_thread = None

    def create_widgets(self):
        left = tk.LabelFrame(self, text="Điều khiển", padx=10, pady=10)
        left.place(x=10, y=10, width=300, height=300)

        tk.Label(left, text="Nguồn:").pack(anchor="w")
        self.source_var = tk.StringVar(value="camera")
        tk.Radiobutton(left, text="Camera realtime", variable=self.source_var, value="camera").pack(anchor="w")
        tk.Radiobutton(left, text="File video", variable=self.source_var, value="video").pack(anchor="w")

        tk.Button(left, text="▶ BẮT ĐẦU", bg="green", fg="white", command=self.start).pack(fill="x", pady=(10,5))
        tk.Button(left, text="❌ Thoát", bg="red", fg="white", command=self.exit_window).pack(fill="x")

        tk.Button(left, text="💾 XÁC NHẬN LƯU (Xe vào)", bg="blue", fg="white", command=self.confirm_save).pack(fill="x", pady=(20,5))
        tk.Label(left, text="(Lưu khi đã nhận diện được biển số)", font=("Arial", 9), fg="gray").pack()
        # Right: video + info
        self.video_label = tk.Label(self, bg="black")
        self.video_label.place(x=320, y=10, width=640, height=480)

        info_frame = tk.LabelFrame(self, text="Thông tin", padx=10, pady=10)
        info_frame.place(x=10, y=320, width=960, height=300)

        self.info_text = tk.Label(info_frame, text="Chưa có dữ liệu nhận diện...", anchor="nw", justify="left")
        self.info_text.pack(fill="x")

        # frame for small images
        imgs = tk.Frame(info_frame)
        imgs.pack(pady=6)
        self.vehicle_img_label = tk.Label(imgs, text="Ảnh xe")
        self.vehicle_img_label.grid(row=0, column=0, padx=8)
        self.plate_img_label = tk.Label(imgs, text="Ảnh biển số")
        self.plate_img_label.grid(row=0, column=1, padx=8)

        status_bar = tk.Label(self, textvariable=self.status_var, bd=1, relief="sunken", anchor="w")
        status_bar.place(x=0, y=620, relwidth=1)

    def exit_window(self):
        """Thoát về menu chính"""
        self.stop()   # dừng camera/video nếu đang chạy
        self.destroy()

    def start(self):
        src = self.source_var.get()
        self.reset_stop()
        self.status_var.set("Đang chạy...")
        if src == "camera":
            # start camera thread
            self.camera_thread = threading.Thread(target=self.process_camera, daemon=True)
            self.camera_thread.start()
        else:
            # choose video file and run processing -> then display preview
            video_file = filedialog.askopenfilename(title="Chọn video", filetypes=[("Video files", "*.mp4 *.avi *.mov")])
            if not video_file:
                self.status_var.set("Hủy chọn video.")
                return
            self.video_thread = threading.Thread(target=self.process_video_file, args=(video_file,), daemon=True)
            self.video_thread.start()

    def stop(self):
        # yêu cầu dừng các thread
        self.request_stop()
        self.video_running = False
        self.status_var.set("Đã dừng.")
        # clear video display
        self.video_label.config(image="", text="")

    def process_camera(self):
        """
        Gọi hàm nhận diện camera. Cố gắng truyền stop_event nếu hàm hỗ trợ.
        Nếu không, fallback gọi hàm gốc (vẫn hy vọng hàm gốc kiểm tra app.video_running/self.stop_event).
        """
        self.video_running = True
        try:
            # nhiều khả năng bạn đã triển khai Recognize... để chấp nhận stop_event
            recognize_license_plate_from_camera(self, mode="in", stop_event=self.stop_event)
        except TypeError:
            # fallback: gọi không truyền stop_event — hy vọng bên trong hàm đó kiểm tra self.video_running
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
        # gọi pipeline xử lý video (nặng)
        try:
            process_video_from_file(video_file)
            add_missing_data_main("output_video/results.csv", "output_video/results_interpolated.csv")
            visualize_main(video_file, "output_video/output_video.mp4", "output_video/results_interpolated.csv")
            # hiển thị kết quả
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

    # Hàm helper để GUI bên trong hoặc module nhận diện gọi khi có kết quả
    def update_detected(self, plate, vpath, ppath):
        """Cập nhật ảnh/biển số khi có kết quả nhận diện - có thể được gọi bởi module camera"""
        self.detected_plate = plate
        self.detected_vehicle_img = vpath
        self.detected_plate_img = ppath
        # cập nhật text/ảnh trên GUI
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
        # play rendered output video in label
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
        left.place(x=10, y=10, width=300, height=300)

        tk.Label(left, text="Nhập mã vé (xe ra):").pack(anchor="w")
        tk.Entry(left, textvariable=self.ticket_var, width=25).pack(anchor="w", pady=(0,10))
        tk.Button(left, text="📂 Truy xuất vé", command=self.fetch_ticket).pack(fill="x", pady=(0,10))


        tk.Label(left, text="Nguồn:").pack(anchor="w")
        tk.Radiobutton(left, text="Camera realtime", variable=self.source_var, value="camera").pack(anchor="w")
        tk.Radiobutton(left, text="Video file", variable=self.source_var, value="video").pack(anchor="w")

        tk.Button(left, text="▶ BẮT ĐẦU", bg="green", fg="white", command=self.start).pack(fill="x", pady=(10,5))
        tk.Button(left, text="❌ Thoát", bg="red", fg="white", command=self.exit_window).pack(fill="x")
        tk.Button(left, text="Xác nhận (so sánh & ra)", bg="blue", fg="white", command=self.confirm_exit).pack(fill="x", pady=(20,5))

        # Right: video + info
        self.video_label = tk.Label(self, bg="black")
        self.video_label.place(x=320, y=10, width=640, height=480)

        info_frame = tk.LabelFrame(self, text="Thông tin", padx=10, pady=10)
        info_frame.place(x=10, y=320, width=960, height=300)

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
            # tương tự EntryWindow: cố gắng truyền stop_event
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
        db_plate = row[1]  # license_plate
        if db_plate == self.detected_plate:
            try:
                cost = update_vehicle_exit(ticket_code, time.time())
                self.info_text.config(text=f"Xe ra!\nBiển số: {self.detected_plate}\nMã vé: {ticket_code}\nPhí: {cost} VND")
                messagebox.showinfo("Thành công", f"Xe ra hợp lệ!\nChi phí: {cost} VND")
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

    def exit_window(self):
        """Thoát về menu chính"""
        self.stop()
        self.destroy()


class SearchWindow(tk.Toplevel):
    """Tìm xe theo biển số: hiện ảnh xe + thời gian vào"""
    def __init__(self, master):
        super().__init__(master)
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

        self.info_text = tk.Label(frame, text="Kết quả sẽ hiển thị ở đây...", anchor="nw", justify="left")
        self.info_text.grid(row=1, column=0, columnspan=3, sticky="w", pady=(10,0))

        imgs = tk.Frame(frame)
        imgs.grid(row=2, column=0, columnspan=3, pady=10)
        self.vehicle_img_label = tk.Label(imgs, text="Ảnh xe")
        self.vehicle_img_label.grid(row=0, column=0, padx=8)
        self.plate_img_label = tk.Label(imgs, text="Ảnh biển số")
        self.plate_img_label.grid(row=0, column=1, padx=8)

    def search(self):
        plate = self.plate_var.get().strip()
        if not plate:
            messagebox.showwarning("Thiếu dữ liệu", "Nhập biển số cần tìm")
            return
        if not find_vehicle_by_plate:
            messagebox.showerror("Chưa hỗ trợ", "Hàm find_vehicle_by_plate chưa được cài trong database.py. "
                                 "Vui lòng thêm hàm:\n\n"
                                 "def find_vehicle_by_plate(plate):\n"
                                 "    # return latest row for that plate\n"
                                 "    ...\n")
            return
        try:
            row = find_vehicle_by_plate(plate)
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Lỗi DB", f"Lỗi khi truy vấn DB:\n{e}")
            return
        if not row:
            messagebox.showinfo("Không tìm thấy", f"Không có bản ghi cho biển số: {plate}")
            return

      
        try:
            ticket_code = row[2]
            entry_time = row[3]
            vimg_path = row[4] if len(row) > 4 else None
            pimg_path = row[5] if len(row) > 5 else None
        except Exception:
            # fallback: show raw row
            self.info_text.config(text=f"Tìm được: {row}")
            return

        self.info_text.config(text=f"Biển số: {plate}\nMã vé: {ticket_code}\nThời gian vào: {time.ctime(entry_time)}")
        if vimg_path and os.path.exists(vimg_path):
            try:
                vimg = Image.open(vimg_path).resize((300, 180))
                self.vehicle_img_label.imgtk = ImageTk.PhotoImage(vimg)
                self.vehicle_img_label.config(image=self.vehicle_img_label.imgtk)
            except Exception:
                pass
        if pimg_path and os.path.exists(pimg_path):
            try:
                pimg = Image.open(pimg_path).resize((300, 80))
                self.plate_img_label.imgtk = ImageTk.PhotoImage(pimg)
                self.plate_img_label.config(image=self.plate_img_label.imgtk)
            except Exception:
                pass


class VideoProcessWindow(tk.Toplevel):
    """Một dialog đơn giản để chạy pipeline xử lý video (giống Entry/Exit nhưng batch)"""
    def __init__(self, master):
        super().__init__(master)
        self.title("Xử lý Video")
        self.geometry("500x200")
        self.resizable(False, False)
        self.create_widgets()

    def create_widgets(self):
        frame = tk.Frame(self, padx=10, pady=10)
        frame.pack(fill="both", expand=True)

        tk.Button(frame, text="Chọn video & Xử lý", command=self.choose_and_process).pack(pady=10)
        self.status_label = tk.Label(frame, text="Trạng thái: chờ...")
        self.status_label.pack(pady=6)

    def choose_and_process(self):
        video_file = filedialog.askopenfilename(title="Chọn video", filetypes=[("Video files", "*.mp4 *.avi *.mov")])
        if not video_file:
            return
        self.status_label.config(text="Đang xử lý...")
        threading.Thread(target=self.run_pipeline, args=(video_file,), daemon=True).start()

    def run_pipeline(self, video_file):
        try:
            process_video_from_file(video_file)
            add_missing_data_main("output_video/results.csv", "output_video/results_interpolated.csv")
            visualize_main(video_file, "output_video/output_video.mp4", "output_video/results_interpolated.csv")
            self.status_label.config(text="Xử lý xong. File: output_video/output_video.mp4")
            messagebox.showinfo("Xong", "Xử lý video xong.")
        except Exception as e:
            traceback.print_exc()
            self.status_label.config(text="Lỗi khi xử lý.")
            messagebox.showerror("Lỗi", f"Lỗi pipeline: {e}")


if __name__ == "__main__":
    app = MainApp()
    app.mainloop()
