import tkinter as tk
from tkinter import filedialog, messagebox
import cv2
from PIL import Image, ImageTk
import os
import threading

from IdentifiedByPhoto import process_image
from IdentifiedViaCamera import recognize_license_plate_from_camera
from Video_recognition import main as process_video_from_file
from add_missing_data import main as add_missing_data_main
from visualize import main as visualize_main


class LicensePlateApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Hệ thống bãi đỗ xe - Nhận diện biển số")
        self.root.geometry("1200x700")
        self.root.resizable(False, False)

        self.source_var = tk.StringVar(value="camera")
        self.mode_var = tk.StringVar(value="in")
        self.ticket_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Sẵn sàng...")

        self.video_running = False

        self.create_widgets()

    def create_widgets(self):
        # khung trái
        control_frame = tk.LabelFrame(self.root, text="Điều khiển", padx=10, pady=10)
        control_frame.place(x=10, y=10, width=250, height=400)

        tk.Label(control_frame, text="Nguồn nhận diện:").pack(anchor="w")
        tk.Radiobutton(control_frame, text="Camera realtime", variable=self.source_var, value="camera").pack(anchor="w")
        tk.Radiobutton(control_frame, text="Video file", variable=self.source_var, value="video").pack(anchor="w")
        tk.Radiobutton(control_frame, text="Ảnh", variable=self.source_var, value="photo").pack(anchor="w")

        tk.Label(control_frame, text="Loại sự kiện:").pack(anchor="w", pady=(10,0))
        tk.Button(control_frame, text="Xe vào", command=lambda: self.set_mode("in")).pack(side="left", padx=5, pady=5)
        tk.Button(control_frame, text="Xe ra", command=lambda: self.set_mode("out")).pack(side="left", padx=5, pady=5)

        tk.Label(control_frame, text="Mã vé (khi xe ra):").pack(anchor="w", pady=(10,0))
        tk.Entry(control_frame, textvariable=self.ticket_var, width=20).pack(anchor="w")

        tk.Button(control_frame, text="▶ BẮT ĐẦU", bg="green", fg="white", command=self.start).pack(fill="x", pady=(20,5))
        tk.Button(control_frame, text="⏹ DỪNG", bg="red", fg="white", command=self.stop).pack(fill="x")

        # khung giữa
        self.video_label = tk.Label(self.root, bg="black")
        self.video_label.place(x=270, y=10, width=640, height=480)

        # khung phải
        info_frame = tk.LabelFrame(self.root, text="Thông tin sự kiện", padx=10, pady=10)
        info_frame.place(x=930, y=10, width=250, height=480)

        self.info_text = tk.Label(info_frame, text="Chưa có sự kiện...", justify="left", anchor="nw")
        self.info_text.pack(fill="x")

        self.vehicle_img_label = tk.Label(info_frame, text="Ảnh xe")
        self.vehicle_img_label.pack(pady=5)

        self.plate_img_label = tk.Label(info_frame, text="Ảnh biển số")
        self.plate_img_label.pack(pady=5)

        # status bar
        status_bar = tk.Label(self.root, textvariable=self.status_var, bd=1, relief="sunken", anchor="w")
        status_bar.pack(side="bottom", fill="x")

    def update_info(self, plate, ticket_code, ts, vehicle_img_path, plate_img_path):
        self.info_text.config(
            text=f"Biển số: {plate}\nThời gian: {ts}\nMã vé: {ticket_code or '-'}"
        )
        if vehicle_img_path and os.path.exists(vehicle_img_path):
            vimg = Image.open(vehicle_img_path).resize((200,120))
            self.vehicle_img_label.imgtk = ImageTk.PhotoImage(vimg)
            self.vehicle_img_label.config(image=self.vehicle_img_label.imgtk)
        if plate_img_path and os.path.exists(plate_img_path):
            pimg = Image.open(plate_img_path).resize((200,60))
            self.plate_img_label.imgtk = ImageTk.PhotoImage(pimg)
            self.plate_img_label.config(image=self.plate_img_label.imgtk)

    def set_mode(self, mode):
        self.mode_var.set(mode)
        self.status_var.set(f"Chế độ: Xe {'vào' if mode=='in' else 'ra'}")

    def start(self):
        src = self.source_var.get()
        if src == "camera":
            threading.Thread(target=self.process_camera, daemon=True).start()
        elif src == "video":
            self.process_video()
        elif src == "photo":
            self.process_image()

    def stop(self):
        self.video_running = False
        self.video_label.config(image="", text="")
        self.status_var.set("Đã dừng.")

    def process_camera(self):
        self.status_var.set("Đang nhận diện từ camera...")
        recognize_license_plate_from_camera(self)
        self.status_var.set("Xong camera.")

    def process_image(self):
        input_file = filedialog.askopenfilename(title="Chọn ảnh", filetypes=[("Image files", "*.jpg *.jpeg *.png")])
        if not input_file: return
        output_folder = os.path.join("NDBSX", "output_img")
        os.makedirs(output_folder, exist_ok=True)
        output_csv_file = os.path.join(output_folder, "license_plate_results.csv")

        process_image(input_file, os.getcwd(), output_folder, output_csv_file)
        annotated_image_path = os.path.join(output_folder, f"annotated_{os.path.basename(input_file)}")
        if os.path.exists(annotated_image_path):
            img = Image.open(annotated_image_path).resize((640,480))
            self.displayed_image = ImageTk.PhotoImage(img)
            self.video_label.config(image=self.displayed_image)
            self.video_label.image = self.displayed_image
            self.status_var.set("Xử lý ảnh xong.")
        else:
            messagebox.showerror("Lỗi", "Không tìm thấy ảnh đã chú thích.")

    def process_video(self):
        video_file = filedialog.askopenfilename(title="Chọn video", filetypes=[("Video files", "*.mp4 *.avi")])
        if not video_file: return
        self.status_var.set("Đang xử lý video...")
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
