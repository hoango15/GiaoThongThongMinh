import tkinter as tk
from tkinter import filedialog, messagebox
import cv2
from PIL import Image, ImageTk
import csv
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
        self.root.title("Ứng Dụng Nhận Diện Biển Số Xe Trong Bãi Đỗ Xe")
        self.root.geometry("1000x600")
        self.root.resizable(False, False)
        self.refresh_task_id = None
        self.video_running = False
        self.license_plate_images = {}  # lưu ảnh cho nhận diện từ ảnh

        self.create_widgets()

    def create_widgets(self):
        title_label = tk.Label(
            self.root,
            text="Ứng Dụng Nhận Diện Biển Số Xe Trong Bãi Đỗ Xe phát triển bởi nhóm 4",
            font=("Arial", 16, "bold"),
            bg="lightblue",
            fg="white"
        )
        title_label.place(x=0, y=0, relwidth=1, height=40)

        # Nút chọn phương thức
        self.btn_camera = tk.Button(self.root, text="Nhận diện qua camera", width=30, command=self.process_camera)
        self.btn_video = tk.Button(self.root, text="Nhận diện trong video", width=30, command=self.process_video)
        self.btn_image = tk.Button(self.root, text="Nhận diện trong ảnh", width=30, command=self.process_image)

        self.btn_camera.place(x=10, y=50)
        self.btn_video.place(x=350, y=50)
        self.btn_image.place(x=690, y=50)

        # Khung hiển thị
        self.image_label = tk.Label(
            self.root, text="Khu vực hiển thị kết quả", bg="white",
            width=90, height=20, relief="solid"
        )
        self.image_label.place(x=10, y=100, width=650, height=400)

        list_label = tk.Label(self.root, text="Danh sách biển số đã nhận diện", font=("Arial", 14))
        list_label.place(x=680, y=100)

        self.license_plate_listbox = tk.Listbox(self.root, font=("Arial", 12), width=30, height=20)
        self.license_plate_listbox.place(x=680, y=140, width=300, height=360)
        self.license_plate_listbox.bind("<<ListboxSelect>>", self.display_annotated_image)

        self.progress_label = tk.Label(self.root, text="Tiến trình: ", font=("Arial", 12), fg="blue")
        self.show_video_button = tk.Button(self.root, text="Hiển thị Video", command=self.display_full_video)

    def toggle_progress_widgets(self, show):
        if show:
            self.progress_label.place(x=10, y=520, width=650, height=30)
            self.show_video_button.place(x=10, y=560, width=150, height=30)
        else:
            self.progress_label.place_forget()
            self.show_video_button.place_forget()

    def stop_refresh_task(self):
        if self.refresh_task_id:
            self.root.after_cancel(self.refresh_task_id)
            self.refresh_task_id = None

    def stop_video(self):
        self.video_running = False
        self.image_label.config(image='', text="Khu vực hiển thị kết quả")
        self.image_label.image = None

    # ========== Xử lý Camera ==========
    def process_camera(self):
        if self.video_running:
            self.stop_video()
        self.toggle_progress_widgets(False)
        self.image_label.config(image='', text="Khu vực hiển thị kết quả")
        self.license_plate_listbox.delete(0, tk.END)

        threading.Thread(target=self.run_camera_recognition, daemon=True).start()

    def run_camera_recognition(self):
        self.load_license_plates_for_camera()
        self.refresh_task_id = self.root.after(3000, self.refresh_license_plate_list)
        recognize_license_plate_from_camera()

    def refresh_license_plate_list(self):
        self.load_license_plates_for_camera()
        self.refresh_task_id = self.root.after(3000, self.refresh_license_plate_list)

    # ========== Xử lý Ảnh ==========
    def process_image(self):
        self.stop_refresh_task()
        if self.video_running:
            self.stop_video()
        self.toggle_progress_widgets(False)

        input_file = filedialog.askopenfilename(title="Chọn ảnh", filetypes=[("Image files", "*.jpg *.jpeg *.png")])
        if not input_file:
            return

        output_folder = os.path.join("NDBSX", "output_img")
        os.makedirs(output_folder, exist_ok=True)
        output_csv_file = os.path.join(output_folder, "license_plate_results.csv")

        process_image(input_file, os.getcwd(), output_folder, output_csv_file)

        annotated_image_path = os.path.join(output_folder, f"annotated_{os.path.basename(input_file)}")
        if os.path.exists(annotated_image_path):
            img = Image.open(annotated_image_path)
            img.thumbnail((650, 400))
            self.displayed_image = ImageTk.PhotoImage(img)
            self.image_label.config(image=self.displayed_image)
            self.image_label.image = self.displayed_image
            self.load_license_plates_for_photo()
        else:
            messagebox.showerror("Lỗi", "Không tìm thấy ảnh đã chú thích.")

    # ========== Xử lý Video ==========
    def process_video(self):
        video_file = filedialog.askopenfilename(title="Chọn video", filetypes=[("Video files", "*.mp4 *.avi")])
        if not video_file:
            return
        threading.Thread(target=self.run_video_recognition, args=(video_file,), daemon=True).start()

    def run_video_recognition(self, video_file):
        self.stop_refresh_task()
        self.toggle_progress_widgets(True)

        cap = cv2.VideoCapture(video_file)
        if not cap.isOpened():
            messagebox.showerror("Lỗi", "Không thể mở video.")
            return

        ret, frame = cap.read()
        if not ret:
            messagebox.showerror("Lỗi", "Không thể đọc frame đầu tiên.")
            cap.release()
            return

        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(frame_rgb)
        img.thumbnail((650, 400))
        self.displayed_image = ImageTk.PhotoImage(img)
        self.image_label.config(image=self.displayed_image)
        self.image_label.image = self.displayed_image
        self.progress_label.config(text="Đang xử lý video... Tiến trình: 10%")

        results = process_video_from_file(video_file)
        self.progress_label.config(text="Đang nhận diện biển số... 30%")

        intermediate_csv = os.path.join("output_video", "results.csv")
        output_csv = os.path.join("output_video", "results_interpolated.csv")
        os.makedirs("output_video", exist_ok=True)
        add_missing_data_main(intermediate_csv, output_csv)
        self.progress_label.config(text="Đang xử lý dữ liệu... 60%")

        output_video_path = os.path.join("output_video", "output_video.mp4")
        self.progress_label.config(text="Đang tạo video đầu ra... 90%")
        self.load_license_plates_for_video()
        visualize_main(video_file, output_video_path, output_csv)

        self.display_output_video(output_video_path)
        self.progress_label.config(text="Nhận diện hoàn tất!")
        cap.release()

    # ========== Hiển thị ==========
    def display_output_video(self, video_file):
        cap = cv2.VideoCapture(video_file)
        self.video_running = True

        def update_frame():
            if not self.video_running:
                cap.release()
                return
            ret, frame = cap.read()
            if not ret:
                cap.release()
                return
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(frame_rgb)
            img.thumbnail((650, 400))
            self.displayed_image = ImageTk.PhotoImage(img)
            self.image_label.config(image=self.displayed_image)
            self.image_label.image = self.displayed_image
            self.root.after(30, update_frame)

        update_frame()

    def display_full_video(self):
        self.stop_refresh_task()
        self.display_output_video(os.path.join("output_video", "output_video.mp4"))

    # ========== Load dữ liệu ==========
    def load_license_plates_for_photo(self):
        self.license_plate_listbox.delete(0, tk.END)
        self.license_plate_images = {}
        output_csv_file = os.path.join("NDBSX", "output_img", "license_plate_results.csv")

        if os.path.exists(output_csv_file):
            with open(output_csv_file, mode='r', newline='', encoding='utf-8') as csv_file:
                reader = csv.reader(csv_file)
                next(reader, None)
                for row in reader:
                    license_plate = row[2].replace('\n', ' ')
                    annotated_image_path = row[3]
                    self.license_plate_images[license_plate] = annotated_image_path
                    self.license_plate_listbox.insert(tk.END, license_plate)

    def load_license_plates_for_camera(self):
        self.license_plate_listbox.delete(0, tk.END)
        output_csv_file = os.path.join("output_camera", "camera_results.csv")

        if os.path.exists(output_csv_file):
            with open(output_csv_file, mode='r', newline='', encoding='utf-8') as csv_file:
                reader = csv.reader(csv_file)
                next(reader, None)
                for row in reader:
                    license_plate = row[1].replace('\n', ' ')
                    self.license_plate_listbox.insert(tk.END, license_plate)

    def load_license_plates_for_video(self):
        self.license_plate_listbox.delete(0, tk.END)
        output_csv_file = os.path.join("output_video", "results_interpolated.csv")

        if os.path.exists(output_csv_file):
            unique_license_plates = set()
            with open(output_csv_file, mode='r', newline='', encoding='utf-8') as csv_file:
                reader = csv.reader(csv_file)
                next(reader, None)
                for row in reader:
                    frame_nmr = row[0]
                    license_plate = row[4].replace('\n', ' ')
                    if license_plate not in unique_license_plates:
                        unique_license_plates.add(license_plate)
                        self.license_plate_listbox.insert(tk.END, f"{frame_nmr}: {license_plate}")

    # ========== Hiển thị ảnh/khung hình ==========
    def display_annotated_image(self, event):
        selected_idx = self.license_plate_listbox.curselection()
        if not selected_idx:
            return
        selected_item = self.license_plate_listbox.get(selected_idx)

        if ":" in selected_item:
            frame_number = selected_item.split(":")[0].strip()
            self.display_frame_from_video(frame_number)
        else:
            annotated_image_path = self.license_plate_images.get(selected_item)
            if annotated_image_path and os.path.exists(annotated_image_path):
                img = Image.open(annotated_image_path)
                img.thumbnail((650, 400))
                self.displayed_image = ImageTk.PhotoImage(img)
                self.image_label.config(image=self.displayed_image)
                self.image_label.image = self.displayed_image

    def display_frame_from_video(self, frame_number):
        if self.video_running:
            self.stop_video()
        video_file = os.path.join("output_video", "output_video.mp4")
        cap = cv2.VideoCapture(video_file)
        if not cap.isOpened():
            messagebox.showerror("Lỗi", "Không thể mở video.")
            return
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(frame_number))
        ret, frame = cap.read()
        if not ret:
            messagebox.showerror("Lỗi", f"Không đọc được khung hình {frame_number}.")
            cap.release()
            return

        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(frame_rgb)
        img.thumbnail((650, 400))
        self.displayed_image = ImageTk.PhotoImage(img)
        self.image_label.config(image=self.displayed_image)
        self.image_label.image = self.displayed_image
        cap.release()


if __name__ == "__main__":
    root = tk.Tk()
    app = LicensePlateApp(root)
    root.mainloop()
