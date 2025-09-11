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

from matplotlib import style

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
        tk.Label(
            self,
            text="HỆ THỐNG QUẢN LÝ BÃI ĐỖ",
            font=("Arial", 18, "bold"),
            bg="#f2f6fa",
            fg="#222"
        ).pack(pady=20)

        btn_frame = tk.Frame(self, bg="#f2f6fa")
        btn_frame.pack(pady=20)

        style = {"width": 22, "height": 2, "font": ("Arial", 12), "relief": "raised"}

        tk.Button(
            btn_frame,
            text="🚗 Xe vào",
            bg="#4CAF50",
            fg="white",
            command=self.open_entry_window,
            **style
        ).grid(row=0, column=0, padx=12, pady=10)

        tk.Button(
            btn_frame,
            text="🚙 Xe ra",
            bg="#E53935",
            fg="white",
            command=self.open_exit_window,
            **style
        ).grid(row=0, column=1, padx=12, pady=10)

        tk.Button(
            btn_frame,
            text="🔍 Tìm xe",
            bg="#2196F3",
            fg="white",
            command=self.open_search_window,
            **style
        ).grid(row=1, column=0, padx=12, pady=10)

        # 👉 Nút Thoát thay cho "Xử lý Video"
        tk.Button(
            btn_frame,
            text="❌ Thoát",
            bg="#9E9E9E",
            fg="white",
            command=self.quit,
            **style
        ).grid(row=1, column=1, padx=12, pady=10)


    def open_entry_window(self):
        EntryWindow(self)

    def open_exit_window(self):
        ExitWindow(self)

    def open_search_window(self):
        SearchWindow(self)

class EntryWindow(tk.Toplevel, BaseWindow):
    def __init__(self, master):
        tk.Toplevel.__init__(self, master)
        BaseWindow.__init__(self, master)
        self.title("Xe vào - Nhận diện biển số")
        self.geometry("1000x750")
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

        tk.Label(left, text="Loại xe:").pack(anchor="w", pady=(10,2))
        self.vehicle_type_var = tk.StringVar(value="Xe máy")
        self.vehicle_type_combo = tk.Combobox(left, textvariable=self.vehicle_type_var, state="readonly")
        self.vehicle_type_combo["values"] = ["Xe máy", "Ô tô", "Xe tải trọng lớn"]
        self.vehicle_type_combo.pack(fill="x")

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
     
        self.video_running = True
        try:
            
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
        self.geometry("1500x750")
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
    """Tìm xe theo biển số: hiện ảnh xe + thời gian vào/ra + phí"""
    def __init__(self, master):
        super().__init__(master)
        self.title("🔍 Tìm xe theo biển số")
        self.geometry("900x750")
        self.resizable(False, False)
        self.configure(bg="#f0f4f7")
        self.create_widgets()

    def create_widgets(self):
        # Thanh tìm kiếm
        frame = tk.Frame(self, padx=10, pady=10, bg="#f0f4f7")
        frame.pack(fill="x")

        tk.Label(frame, text="Nhập biển số:", bg="#f0f4f7",
                 font=("Arial", 11, "bold")).grid(row=0, column=0, sticky="w")
        self.plate_var = tk.StringVar()
        tk.Entry(frame, textvariable=self.plate_var, width=30,
                 font=("Arial", 11)).grid(row=0, column=1, sticky="w", padx=5)
        tk.Button(frame, text="🔍 Tìm", command=self.search, bg="#2196F3", fg="white",
                  font=("Arial", 10, "bold"), padx=10, pady=4).grid(row=0, column=2, padx=8)

        # Thông tin xe
        info_frame = tk.LabelFrame(self, text="Thông tin xe", padx=10, pady=10,
                                   bg="#ffffff", font=("Arial", 11, "bold"))
        info_frame.pack(fill="x", padx=10, pady=10)

        self.info_text = tk.Label(info_frame, text="Kết quả sẽ hiển thị ở đây...",
                                  anchor="w", justify="left", bg="#ffffff", font=("Arial", 11))
        self.info_text.pack(fill="x")

        # Ảnh xe và biển số
        imgs = tk.Frame(self, bg="#f0f4f7")
        imgs.pack(fill="both", expand=True, padx=10, pady=10)

        # Placeholder cho ảnh xe
        ph_vehicle = ImageTk.PhotoImage(Image.new("RGB", (500, 350), color="gray"))
        self.vehicle_img_label = tk.Label(imgs, image=ph_vehicle, bg="#cccccc")
        self.vehicle_img_label.imgtk = ph_vehicle
        self.vehicle_img_label.grid(row=0, column=0, padx=8)

        # Placeholder cho ảnh biển số
        ph_plate = ImageTk.PhotoImage(Image.new("RGB", (500, 350), color="gray"))
        self.plate_img_label = tk.Label(imgs, image=ph_plate, bg="#cccccc")
        self.plate_img_label.imgtk = ph_plate
        self.plate_img_label.grid(row=0, column=1, padx=8)

        # Nút thoát
        tk.Button(self, text="❌ Thoát", command=self.destroy, bg="#E53935", fg="white",
                  font=("Arial", 11, "bold"), padx=15, pady=6).pack(pady=8)

    def search(self):
        plate = self.plate_var.get().strip()
        if not plate:
            messagebox.showwarning("Thiếu dữ liệu", "Nhập biển số cần tìm")
            return

        try:
            row = find_vehicle_by_plate(plate)   # Hàm này có sẵn trong database.py
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Lỗi DB", f"Lỗi khi truy vấn DB:\n{e}")
            return

        if not row:
            messagebox.showinfo("Không tìm thấy", f"Không có bản ghi cho biển số: {plate}")
            return

        try:
            plate_number = row["license_plate"]
            entry_time = row["time_in"].strftime("%d/%m/%Y %H:%M:%S") if row["time_in"] else "Không có"
            exit_time = row["time_out"].strftime("%d/%m/%Y %H:%M:%S") if row["time_out"] else "Chưa ra"
            fee = f"{row['fee']:,.0f} VND" if row["fee"] else "Chưa tính"
            vimg_path = row.get("vehicle_img_path")
            pimg_path = row.get("plate_img_path")
        except Exception:
            self.info_text.config(text=f"Tìm được: {row}")
            return

        # Hiển thị thông tin
        info = (
            f"⏰ Thời gian vào: {entry_time}\n"
            f"⏰ Thời gian ra: {exit_time}\n"
            f"🚗 Biển số xe: {plate_number}\n"
            f"💰 Phí: {fee}"
        )
        self.info_text.config(text=info)

        # Hiện ảnh xe
        if vimg_path and os.path.exists(vimg_path):
            try:
                vimg = Image.open(vimg_path).resize((400, 300))
                self.vehicle_img_label.imgtk = ImageTk.PhotoImage(vimg)
                self.vehicle_img_label.config(image=self.vehicle_img_label.imgtk)
            except Exception as e:
                print("Lỗi ảnh xe:", e)

        # Hiện ảnh biển số
        if pimg_path and os.path.exists(pimg_path):
            try:
                pimg = Image.open(pimg_path).resize((400, 300))
                self.plate_img_label.imgtk = ImageTk.PhotoImage(pimg)
                self.plate_img_label.config(image=self.plate_img_label.imgtk)
            except Exception as e:
                print("Lỗi ảnh biển số:", e)



if __name__ == "__main__":
    app = MainApp()
    app.mainloop()
