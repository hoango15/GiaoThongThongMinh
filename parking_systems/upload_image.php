<?php
require_once 'middleware.php';
require_once 'includes/auth.php';
require_once 'config/database.php';

requireLogin();

header('Content-Type: application/json');

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    http_response_code(405);
    echo json_encode(['success' => false, 'message' => 'Method not allowed']);
    exit;
}

$vehicle_id = $_POST['vehicle_id'] ?? '';
$image_type = $_POST['image_type'] ?? ''; // 'vehicle_in', 'plate_in', 'vehicle_out', 'plate_out'

if (!$vehicle_id || !$image_type) {
    echo json_encode(['success' => false, 'message' => 'Thiếu thông tin bắt buộc']);
    exit;
}

$allowed_types = ['vehicle_in', 'plate_in', 'vehicle_out', 'plate_out'];
if (!in_array($image_type, $allowed_types)) {
    echo json_encode(['success' => false, 'message' => 'Loại ảnh không hợp lệ']);
    exit;
}

if (!isset($_FILES['image']) || $_FILES['image']['error'] !== UPLOAD_ERR_OK) {
    echo json_encode(['success' => false, 'message' => 'Không có file ảnh hoặc có lỗi upload']);
    exit;
}

$file = $_FILES['image'];
$allowed_extensions = ['jpg', 'jpeg', 'png', 'gif'];
$file_extension = strtolower(pathinfo($file['name'], PATHINFO_EXTENSION));

if (!in_array($file_extension, $allowed_extensions)) {
    echo json_encode(['success' => false, 'message' => 'Chỉ chấp nhận file ảnh (jpg, jpeg, png, gif)']);
    exit;
}

// Kiểm tra kích thước file (max 5MB)
if ($file['size'] > 5 * 1024 * 1024) {
    echo json_encode(['success' => false, 'message' => 'File ảnh quá lớn (tối đa 5MB)']);
    exit;
}

// Tạo thư mục uploads nếu chưa có
$upload_dir = 'uploads/';
if (!is_dir($upload_dir)) {
    mkdir($upload_dir, 0755, true);
}

// Tạo tên file unique
$filename = $vehicle_id . '_' . $image_type . '_' . time() . '.' . $file_extension;
$filepath = $upload_dir . $filename;

if (!move_uploaded_file($file['tmp_name'], $filepath)) {
    echo json_encode(['success' => false, 'message' => 'Không thể lưu file ảnh']);
    exit;
}

// Cập nhật database
try {
    $database = new Database();
    $db = $database->getConnection();
    
    $column_map = [
        'vehicle_in' => 'vehicle_img_in_path',
        'plate_in' => 'plate_img_in_path',
        'vehicle_out' => 'vehicle_img_out_path',
        'plate_out' => 'plate_img_out_path'
    ];
    
    $column = $column_map[$image_type];
    

    $old_query = "SELECT $column FROM vehicles WHERE id = :vehicle_id";
    $old_stmt = $db->prepare($old_query);
    $old_stmt->bindParam(':vehicle_id', $vehicle_id);
    $old_stmt->execute();
    $old_result = $old_stmt->fetch(PDO::FETCH_ASSOC);
    
    if ($old_result && $old_result[$column] && file_exists($old_result[$column])) {
        unlink($old_result[$column]);
    }
    
    // Cập nhật đường dẫn ảnh mới
    $query = "UPDATE vehicles SET $column = :filepath WHERE id = :vehicle_id";
    $stmt = $db->prepare($query);
    $stmt->bindParam(':filepath', $filepath);
    $stmt->bindParam(':vehicle_id', $vehicle_id);
    
    if ($stmt->execute()) {
        echo json_encode([
            'success' => true, 
            'message' => 'Upload ảnh thành công',
            'filepath' => $filepath
        ]);
    } else {
        // Xóa file nếu không cập nhật được database
        unlink($filepath);
        echo json_encode(['success' => false, 'message' => 'Không thể cập nhật database']);
    }
    
} catch (Exception $e) {
    // Xóa file nếu có lỗi
    if (file_exists($filepath)) {
        unlink($filepath);
    }
    echo json_encode(['success' => false, 'message' => 'Lỗi hệ thống: ' . $e->getMessage()]);
}
?>
