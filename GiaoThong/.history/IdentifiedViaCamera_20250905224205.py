import cv2
import os
import csv
import torch
from time import time
from ultralytics import YOLO
from IdentifiedByPhoto import license_plate_show, validate_and_correct_plate
from PIL import Image, ImageTk

# Lưu kết quả CSV
output_folder = './output'
os.makedirs(output_folder, exist_ok=True)
output_csv_file = os.path.join(output_folder, 'camera_results.csv')
if not os.path.exists(output_csv_file):
    with open(output_csv_file, 'w', newline='', encoding='utf-8') as f:
        csv.writer(f).writerow(['Frame', 'License Plate', 'Bounding Box'])

def is_plate_in_csv(file_path, plate):
    with open(file_path, mode='r', newline='', encoding='utf-8') as f:
        return any(plate in row for row in csv.reader(f))

def put_plate_on_image(img, bbox, text):
    x1, y1, x2, y2 = bbox
    cv2.rectangle(img, (x1, y1), (x2, y2), (0,0,255), 2)
    cv2.putText(img, text, (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 
                1, (0,255,255), 2, cv2.LINE_AA)
    return img

def init_models(det_path='./models/license_plate_detector_v4.pt', rec_path='./models/last.pt'):
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model_detect = YOLO(det_path).to(device)
    model_rec = YOLO(rec_path).to(device)
    return model_detect, model_rec

def recognize_license_plate_from_camera(app):
    cap = cv2.VideoCapture(0)
    model_detect, model_rec = init_models()
    start_time, plate_counts = time(), []

    def update():
        nonlocal start_time, plate_counts
        ret, frame = cap.read()
        if not ret:
            cap.release()
            return

        results_detect = model_detect(frame, conf=0.4)
        for result in results_detect:
            for box in result.boxes:
                r = box.xyxy[0].cpu().numpy().astype(int)
                crop = frame[r[1]:r[3], r[0]:r[2]]
                results_rec = model_rec(crop, conf=0.4)

                labels, xs, ys = [], [], []
                for rec_result in results_rec:
                    for rec_box in rec_result.boxes:
                        labels.append(int(rec_box.cls.cpu().numpy().item()))
                        xs.append(rec_box.xywh[0][0].cpu().numpy().item())
                        ys.append(rec_box.xywh[0][1].cpu().numpy().item())

                if labels:
                    plate_predict, is_single = license_plate_show(labels, xs, ys)
                    corrected_plate = validate_and_correct_plate(plate_predict, is_single)
                    if corrected_plate:
                        plate_counts.append(corrected_plate)
                        if time() - start_time >= 2:  # mỗi 2 giây kiểm tra
                            count = plate_counts.count(corrected_plate)
                            if count > 5 and not is_plate_in_csv(output_csv_file, corrected_plate):
                                with open(output_csv_file, 'a', newline='', encoding='utf-8') as f:
                                    csv.writer(f).writerow(
                                        [cap.get(cv2.CAP_PROP_POS_FRAMES), corrected_plate, r.tolist()]
                                    )
                                # lưu ảnh
                                vpath = os.path.join(output_folder, 'vehicle.jpg')
                                ppath = os.path.join(output_folder, 'plate.jpg')
                                cv2.imwrite(vpath, frame)
                                cv2.imwrite(ppath, frame[r[1]:r[3], r[0]:r[2]])
                                # cập nhật GUI
                                ts = time()
                                app.update_info(corrected_plate, None, ts, vpath, ppath)
                            plate_counts, start_time = [], time()
                        frame = put_plate_on_image(frame, r, corrected_plate)

        # hiển thị lên Tkinter
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(frame_rgb).resize((640,480))
        imgtk = ImageTk.PhotoImage(img)
        app.video_label.imgtk = imgtk
        app.video_label.configure(image=imgtk)

        app.root.after(30, update)

    update()
