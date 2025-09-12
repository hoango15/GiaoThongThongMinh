<?php
require_once 'middleware.php';
require_once 'includes/auth.php';
require_once 'config/database.php';

requireLogin();

$database = new Database();
$db = $database->getConnection();

header('Content-Type: application/json');

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    http_response_code(405);
    echo json_encode(['success' => false, 'message' => 'Method not allowed']);
    exit;
}

$input = json_decode(file_get_contents('php://input'), true);
$action = $input['action'] ?? '';

try {
    if ($action === 'delete_single') {
        $vehicleId = $input['vehicle_id'] ?? 0;
        
        if (!$vehicleId) {
            throw new Exception('ID xe không hợp lệ');
        }
        
        // Get vehicle info before deleting to remove image files
        $stmt = $db->prepare("SELECT vehicle_img_in_path, plate_img_in_path, vehicle_img_out_path, plate_img_out_path FROM vehicles WHERE id = :id");
        $stmt->bindParam(':id', $vehicleId, PDO::PARAM_INT);
        $stmt->execute();
        $vehicle = $stmt->fetch(PDO::FETCH_ASSOC);
        
        if (!$vehicle) {
            throw new Exception('Không tìm thấy xe');
        }
        
        // Delete vehicle record
        $stmt = $db->prepare("DELETE FROM vehicles WHERE id = :id");
        $stmt->bindParam(':id', $vehicleId, PDO::PARAM_INT);
        $stmt->execute();
        
        // Delete image files if they exist
        $baseImagePath = "D:\\He_Nam2\\GiaoThongThongMinh\\GiaoThong\\output\\";
        $imageFields = ['vehicle_img_in_path', 'plate_img_in_path', 'vehicle_img_out_path', 'plate_img_out_path'];
        
        foreach ($imageFields as $field) {
            if ($vehicle[$field]) {
                $imagePath = $baseImagePath . basename($vehicle[$field]);
                if (file_exists($imagePath)) {
                    unlink($imagePath);
                }
            }
        }
        
        echo json_encode(['success' => true, 'message' => 'Đã xóa xe thành công']);
        
    } elseif ($action === 'delete_by_date') {
        $dateFrom = $input['date_from'] ?? '';
        $dateTo = $input['date_to'] ?? '';
        
        if (!$dateFrom || !$dateTo) {
            throw new Exception('Vui lòng chọn khoảng thời gian');
        }
        
        // Get all vehicles in date range to delete their images
        $stmt = $db->prepare("
            SELECT vehicle_img_in_path, plate_img_in_path, vehicle_img_out_path, plate_img_out_path 
            FROM vehicles 
            WHERE DATE(time_in) >= :date_from AND DATE(time_in) <= :date_to
        ");
        $stmt->bindParam(':date_from', $dateFrom);
        $stmt->bindParam(':date_to', $dateTo);
        $stmt->execute();
        $vehicles = $stmt->fetchAll(PDO::FETCH_ASSOC);
        
        // Delete vehicle records
        $stmt = $db->prepare("DELETE FROM vehicles WHERE DATE(time_in) >= :date_from AND DATE(time_in) <= :date_to");
        $stmt->bindParam(':date_from', $dateFrom);
        $stmt->bindParam(':date_to', $dateTo);
        $stmt->execute();
        $deletedCount = $stmt->rowCount();
        
        // Delete image files
        $baseImagePath = "D:\\He_Nam2\\GiaoThongThongMinh\\GiaoThong\\output\\";
        $imageFields = ['vehicle_img_in_path', 'plate_img_in_path', 'vehicle_img_out_path', 'plate_img_out_path'];
        
        foreach ($vehicles as $vehicle) {
            foreach ($imageFields as $field) {
                if ($vehicle[$field]) {
                    $imagePath = $baseImagePath . basename($vehicle[$field]);
                    if (file_exists($imagePath)) {
                        unlink($imagePath);
                    }
                }
            }
        }
        
        echo json_encode([
            'success' => true, 
            'message' => "Đã xóa {$deletedCount} xe từ {$dateFrom} đến {$dateTo}"
        ]);
        
    } else {
        throw new Exception('Hành động không hợp lệ');
    }
    
} catch (Exception $e) {
    http_response_code(400);
    echo json_encode(['success' => false, 'message' => $e->getMessage()]);
}
?>
