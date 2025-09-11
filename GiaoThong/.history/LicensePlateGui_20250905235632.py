import tkinter as tk
from tkinter import filedialog, messagebox
import cv2
from PIL import Image, ImageTk
import os
import threading
import time
import random, string

from IdentifiedViaCamera import recognize_license_plate_from_camera
from Video_recognition import main as process_video_from_file
from add_missing_data import main as add_missing_data_main
from visualize import main as visualize_main
from database import insert_vehicle, get_vehicle_by_ticket, update_vehicle_exit


class LicensePlateApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Hệ thống bãi đỗ xe - Nhận diện biển số")
        self.root.geometry("1280x720")
        self.root.resizable(False, False)

        self.mode_var = tk.StringVar(value="in")   # xe vào / xe ra
        self.source_var = tk.StringVar(value="camera")  # camera / video
        self.ticket_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Sẵn sàng...")

        self.video_running = False

        # giữ tạm biển số mới nhận diện
        self.detected_plate = None
        self.detected_vehicle_img = None
        self.detected_plate_img = None

        self.create_widgets()

    def create_widgets(self):
        # ===== Khung trái: Điều khiển =====
        control_frame = tk.LabelFrame(self.root, text="Điều khiển", padx=10, pady=10)
        control_frame.place(x=10, y=10, width=250, height=550)

        # Chế độ xe vào / xe ra
        tk.Label(control_frame, text="Chế độ:").pack(anchor="w")
        tk.Radiobutton(control_frame, text="Xe vào", variable=self.mode_var, value="in").pack(anchor="w")
        tk.Radiobutton(control_frame, text="Xe ra", variable=self.mode_var, value="out").pack(anchor="w")

        # Nguồn nhận diện
        source_frame = tk.LabelFrame(control_frame, text="Nguồn nhận diện")
        source_frame.pack(fill="x", pady=10)
        tk.Radiobutton(source_frame, text="Camera realtime", variable=self.source_var, value="camera").pack(anchor="w")
        tk.Radiobutton(source_frame, text="Video file", variable=self.source_var, value="video").pack(anchor="w")

        # Mã vé khi xe ra
        tk.Label(control_frame, text="Mã vé (xe ra):").pack(anchor="w", pady=(10,0))
        tk.Entry(control_frame, textvariable=self.ticket_var, width=20).pack(anchor="w")

        # Nút điều khiển
        tk.Button(control_frame, text="▶ BẮT ĐẦU", bg="green", fg="white", command=self.start).pack(fill="x", pady=(20,5))
        tk.Button(control_frame, text="⏹ DỪNG", bg="red", fg="white", command=self.stop).pack(fill="x")

        # Nút xác nhận
        tk.Button(control_frame, text="💾 XÁC NHẬN LƯU", bg="blue", fg="white", command=self.confirm_save).pack(fill="x", pady=(40,5))

        # ===== Khung giữa: Video =====
        self.video_label = tk.Label(self.root, bg="black")
        self.video_label.place(x=280, y=10, width=640, height=480)

        # ===== Khung phải: Thông tin =====
        info_frame = tk.LabelFrame(self.root, text="Thông tin sự kiện", padx=10, pady=10)
        info_frame.place(x=940, y=10, width=320, height=480)

        self.info_text = tk.Label(info_frame, text="Chưa có sự kiện...", justify="left", anchor="nw")
        self.info_text.pack(fill="x")

        self.vehicle_img_label = tk.Label(info_frame, text="Ảnh xe")
        self.vehicle_img_label.pack(pady=5)
        self.plate_img_label = tk.Label(info_frame, text="Ảnh biển số")
        self.plate_img_label.pack(pady=5)

        # ===== Status bar =====
        status_bar = tk.Label(self.root, textvariable=self.status_var, bd=1, relief="sunken", anchor="w")
        status_bar.pack(side="bottom", fill="x")

    # hiển thị tạm thời kết quả nhận diện
    def update_detected(self, plate, vpath, ppath):
        self.detected_plate = plate
        self.detected_vehicle_img = vpath
        self.detected_plate_img = ppath
        self.info_text.config(text=f"Nhận diện: {plate}\n(chưa lưu)")
        if vpath and os.path.exists(vpath):
            vimg = Image.open(vpath).resize((200,120))
            self.vehicle_img_label.imgtk = ImageTk.PhotoImage(vimg)
            self.vehicle_img_label.config(image=self.vehicle_img_label.imgtk)
        if ppath and os.path.exists(ppath):
            pimg = Image.open(ppath).resize((200,60))
            self.plate_img_label.imgtk = ImageTk.PhotoImage(pimg)
            self.plate_img_label.config(image=self.plate_img_label.imgtk)

    # xác nhận lưu
    def confirm_save(self):
        if not self.detected_plate:
            messagebox.showwarning("Chưa có dữ liệu", "Chưa nhận diện được biển số để lưu!")
            return

        ts = time.time()
        mode = self.mode_var.get()
        if mode == "in":
            # tạo ticket
            ticket_code = ''.join(random.choices(string.ascii_uppercase+string.digits, k=6))
            insert_vehicle(ticket_code, self.detected_plate, ts, self.detected_vehicle_img, self.detected_plate_img)
            self.info_text.config(text=f"Xe vào!\nBiển số: {self.detected_plate}\nMã vé: {ticket_code}")
            messagebox.showinfo("Thành công", f"Lưu xe vào thành công!\nMã vé: {ticket_code}")
        elif mode == "out":
            ticket_code = self.ticket_var.get().strip()
            if not ticket_code:
                messagebox.showerror("Lỗi", "Cần nhập mã vé để xác nhận xe ra")
                return
            row = get_vehicle_by_ticket(ticket_code)
            if not row:
                messagebox.showerror("Sai mã vé", f"Không tìm thấy vé {ticket_code}")
                return
            # so sánh biển số
            if row[1] == self.detected_plate:  # plate match
                cost = update_vehicle_exit(ticket_code, ts)
                self.info_text.config(text=f"Xe ra!\nBiển số: {self.detected_plate}\nMã vé: {ticket_code}\nPhí: {cost} VND")
                messagebox.showinfo("Thành công", f"Xe ra hợp lệ!\nChi phí: {cost} VND")
            else:
                messagebox.showerror("Sai biển số", "Biển số không khớp với vé!")

    # ====== xử lý ======
    def start(self):
        mode, src = self.mode_var.get(), self.source_var.get()
        if src == "camera":
            threading.Thread(target=self.process_camera, daemon=True).start()
        elif src == "video":
            self.process_video()

    def stop(self):
        self.video_running = False
        self.video_label.config(image="", text="")
        self.status_var.set("Đã dừng.")

    def process_camera(self):
        self.status_var.set(f"Đang nhận diện từ camera ({self.mode_var.get()})...")
        recognize_license_plate_from_camera(self, mode=self.mode_var.get())
        self.status_var.set("Xong camera.")

    def process_video(self):
        video_file = filedialog.askopenfilename(title="Chọn video", filetypes=[("Video files", "*.mp4 *.avi")])
        if not video_file: return
        self.status_var.set(f"Đang xử lý video ({self.mode_var.get()})...")
        threading.Thread(target=self.run_video, args=(video_file,), daemon=True).start()

    def run_video(self, video_file):
        process_video_from_file(video_file)
        add_missing_data_main("output_video/results.csv", "output_video/results_interpolated.csv")
        visualize_main(video_file, "output_video/output_video.mp4", "output_video/results_interpolated.csv")
        self.display_output_video("output_video/output_video.mp4")
        self.status_var.set("Xử lý video xong.")

    def display_output_video(self, video_file):
        cap = cv2.VideoCapture(video_file)
        self.video_running = True
        def update():
            if not self.video_running: cap.release(); return
            ret, frame = cap.read()
            if not ret: cap.release(); return
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(frame_rgb).resize((640,480))
            self.displayed_image = ImageTk.PhotoImage(img)
            self.video_label.config(image=self.displayed_image)
            self.video_label.image = self.displayed_image
            self.root.after(30, update)
        update()


if __name__ == "__main__":
    root = tk.Tk()
    app = LicensePlateApp(root)
    root.mainloop()
