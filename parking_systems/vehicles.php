<?php
require_once 'middleware.php';
require_once 'includes/auth.php';
require_once 'config/database.php';

requireLogin();

// === START: Serve image từ folder ngoài webroot ===
$baseImagePath = "D:\\He_Nam2\\GiaoThongThongMinh\\GiaoThong\\output\\";

function serveImage($filename) {
    global $baseImagePath;

    $safeFile = basename($filename); // tránh path traversal
    $fullPath = $baseImagePath . $safeFile;

    if (!file_exists($fullPath)) {
        http_response_code(404);
        exit('File not found');
    }

    $finfo = finfo_open(FILEINFO_MIME_TYPE);
    $mime = finfo_file($finfo, $fullPath);
    finfo_close($finfo);

    header('Content-Type: ' . $mime);
    readfile($fullPath);
    exit;
}

// Nếu có query serve_image thì trả ảnh luôn
if (isset($_GET['serve_image'])) {
    serveImage($_GET['serve_image']);
}

// Hàm tạo URL hiển thị ảnh
function getVehicleImageUrl($filename) {
    if (!$filename) return '';
    return $_SERVER['PHP_SELF'] . '?serve_image=' . urlencode($filename);
}
// === END: Serve image ===

$database = new Database();
$db = $database->getConnection();

// Xử lý filters
$date_from = $_GET['date_from'] ?? '';
$date_to = $_GET['date_to'] ?? '';
$status = $_GET['status'] ?? '';
$search = $_GET['search'] ?? '';

// Pagination
$page = isset($_GET['page']) ? (int)$_GET['page'] : 1;
$limit = 10;
$offset = ($page - 1) * $limit;

// Build query với filters
$where_conditions = [];
$params = [];

if ($date_from) {
    $where_conditions[] = "DATE(time_in) >= :date_from";
    $params[':date_from'] = $date_from;
}

if ($date_to) {
    $where_conditions[] = "DATE(time_in) <= :date_to";
    $params[':date_to'] = $date_to;
}

if ($status === 'in') {
    $where_conditions[] = "time_out IS NULL";
} elseif ($status === 'out') {
    $where_conditions[] = "time_out IS NOT NULL";
}

if ($search) {
    $where_conditions[] = "(license_plate LIKE :search OR ticket_code LIKE :search)";
    $params[':search'] = '%' . $search . '%';
}

$where_clause = $where_conditions ? 'WHERE ' . implode(' AND ', $where_conditions) : '';

// Count total records
$count_query = "SELECT COUNT(*) as total FROM vehicles $where_clause";
$count_stmt = $db->prepare($count_query);
$count_stmt->execute($params);
$total_records = $count_stmt->fetch(PDO::FETCH_ASSOC)['total'];
$total_pages = ceil($total_records / $limit);

// Get vehicles data
$query = "
    SELECT 
        id, license_plate, ticket_code, time_in, time_out, fee,
        vehicle_img_in_path, plate_img_in_path, vehicle_img_out_path, plate_img_out_path,
        CASE 
            WHEN time_out IS NULL THEN 'in'
            ELSE 'out'
        END as status
    FROM vehicles 
    $where_clause
    ORDER BY time_in DESC 
    LIMIT :limit OFFSET :offset
";

$stmt = $db->prepare($query);
foreach ($params as $key => $value) {
    $stmt->bindValue($key, $value);
}
$stmt->bindValue(':limit', $limit, PDO::PARAM_INT);
$stmt->bindValue(':offset', $offset, PDO::PARAM_INT);
$stmt->execute();
$vehicles = $stmt->fetchAll(PDO::FETCH_ASSOC);
?>
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Quản lý xe - Hệ thống quản lý bãi đỗ xe</title>
    <link rel="stylesheet" href="assets/style.css">
</head>
<body>
<div class="dashboard">
    <nav class="sidebar">
        <div class="sidebar-header">
            <h2 class="sidebar-title">🚗 Smart Parking</h2>
        </div>
        <ul class="sidebar-nav">
            <li><a href="dashboard.php">Dashboard</a></li>
            <li><a href="vehicles.php" class="active">Quản lý xe</a></li>
            <li><a href="reports.php">Báo cáo</a></li>
            <li><a href="logout.php">Đăng xuất</a></li>
        </ul>
    </nav>

    <main class="main-content">
        <div class="header">
            <h1 class="page-title">Quản lý xe</h1>
            <div class="user-info">
                <span>Xin chào, <?php echo htmlspecialchars($_SESSION['admin_name']); ?></span>
            </div>
        </div>

        <div class="card">
            <div class="card-header">
                <h3 class="card-title">Bộ lọc</h3>
            </div>
            <form method="GET" class="filters">
                <div class="filter-group">
                    <label>Từ ngày:</label>
                    <input type="date" name="date_from" class="form-input" value="<?php echo htmlspecialchars($date_from); ?>">
                </div>
                <div class="filter-group">
                    <label>Đến ngày:</label>
                    <input type="date" name="date_to" class="form-input" value="<?php echo htmlspecialchars($date_to); ?>">
                </div>
                <div class="filter-group">
                    <label>Trạng thái:</label>
                    <select name="status" class="form-input">
                        <option value="">Tất cả</option>
                        <option value="in" <?php echo $status === 'in' ? 'selected' : ''; ?>>Đang đỗ</option>
                        <option value="out" <?php echo $status === 'out' ? 'selected' : ''; ?>>Đã ra</option>
                    </select>
                </div>
                <div class="filter-group">
                    <label>Tìm kiếm:</label>
                    <input type="text" name="search" class="form-input" placeholder="Biển số hoặc mã vé" value="<?php echo htmlspecialchars($search); ?>">
                </div>
                <div class="filter-group">
                    <label>&nbsp;</label>
                    <button type="submit" class="btn btn-primary">Lọc</button>
                </div>
            </form>
        </div>

        <div class="card">
            <div class="card-header">
                <h3 class="card-title">Danh sách xe (<?php echo $total_records; ?> kết quả)</h3>
            </div>
            <div class="table-container">
                <table class="table">
                    <thead>
                    <tr>
                        <th>Biển số</th>
                        <th>Mã vé</th>
                        <th>Thời gian vào</th>
                        <th>Thời gian ra</th>
                        <th>Phí</th>
                        <th>Trạng thái</th>
                        <th>Ảnh vào</th>
                        <th>Ảnh ra</th>
                      
                    </tr>
                    </thead>
                    <tbody>
                    <?php foreach ($vehicles as $vehicle):
                        $vehicleInImg = getVehicleImageUrl($vehicle['vehicle_img_in_path']);
                        $plateInImg   = getVehicleImageUrl($vehicle['plate_img_in_path']);
                        $vehicleOutImg = getVehicleImageUrl($vehicle['vehicle_img_out_path']);
                        $plateOutImg   = getVehicleImageUrl($vehicle['plate_img_out_path']);
                        ?>
                        <tr>
                            <td><?php echo htmlspecialchars($vehicle['license_plate']); ?></td>
                            <td><?php echo htmlspecialchars($vehicle['ticket_code']); ?></td>
                            <td><?php echo date('d/m/Y H:i', strtotime($vehicle['time_in'])); ?></td>
                            <td>
                                <?php if ($vehicle['time_out']): ?>
                                    <?php echo date('d/m/Y H:i', strtotime($vehicle['time_out'])); ?>
                                <?php else: ?>
                                    <span class="status-badge status-in">Đang đỗ</span>
                                <?php endif; ?>
                            </td>
                            <td>
                                <?php echo $vehicle['fee'] ? number_format($vehicle['fee']) . 'đ' : '-'; ?>
                            </td>
                            <td>
                                <span class="status-badge status-<?php echo $vehicle['status']; ?>">
                                    <?php echo $vehicle['status'] === 'in' ? 'Đang đỗ' : 'Đã ra'; ?>
                                </span>
                            </td>
                            <!-- Ảnh vào -->
                            <td class="image-cell">
                                <div class="image-group">
                                    <div class="image-item">
                                        <label>Xe vào:</label>
                                        <?php if ($vehicleInImg): ?>
                                            <img src="<?php echo $vehicleInImg; ?>" alt="Xe vào" class="vehicle-image"
                                                 onclick="showImageModal('<?php echo $vehicleInImg; ?>')">
                                        <?php else: ?>
                                            <button class="btn btn-sm btn-upload"
                                                    onclick="openUploadModal(<?php echo $vehicle['id']; ?>, 'vehicle_in')">📷 Upload
                                            </button>
                                        <?php endif; ?>
                                    </div>
                                    <div class="image-item">
                                        <label>Biển số vào:</label>
                                        <?php if ($plateInImg): ?>
                                            <img src="<?php echo $plateInImg; ?>" alt="Biển số vào" class="vehicle-image"
                                                 onclick="showImageModal('<?php echo $plateInImg; ?>')">
                                        <?php else: ?>
                                            <button class="btn btn-sm btn-upload"
                                                    onclick="openUploadModal(<?php echo $vehicle['id']; ?>, 'plate_in')">📷 Upload
                                            </button>
                                        <?php endif; ?>
                                    </div>
                                </div>
                            </td>
                            <!-- Ảnh ra -->
                            <td class="image-cell">
                                <div class="image-group">
                                    <div class="image-item">
                                        <label>Xe ra:</label>
                                        <?php if ($vehicleOutImg): ?>
                                            <img src="<?php echo $vehicleOutImg; ?>" alt="Xe ra" class="vehicle-image"
                                                 onclick="showImageModal('<?php echo $vehicleOutImg; ?>')">
                                        <?php else: ?>
                                            <button class="btn btn-sm btn-upload"
                                                    onclick="openUploadModal(<?php echo $vehicle['id']; ?>, 'vehicle_out')">📷 Upload
                                            </button>
                                        <?php endif; ?>
                                    </div>
                                    <div class="image-item">
                                        <label>Biển số ra:</label>
                                        <?php if ($plateOutImg): ?>
                                            <img src="<?php echo $plateOutImg; ?>" alt="Biển số ra" class="vehicle-image"
                                                 onclick="showImageModal('<?php echo $plateOutImg; ?>')">
                                        <?php else: ?>
                                            <button class="btn btn-sm btn-upload"
                                                    onclick="openUploadModal(<?php echo $vehicle['id']; ?>, 'plate_out')">📷 Upload
                                            </button>
                                        <?php endif; ?>
                                    </div>
                                </div>
                            </td>
                            
                        </tr>
                    <?php endforeach; ?>
                    </tbody>
                </table>
            </div>

            <?php if ($total_pages > 1): ?>
                <div class="pagination">
                    <?php if ($page > 1): ?>
                        <a href="?<?php echo http_build_query(array_merge($_GET, ['page' => $page - 1])); ?>">« Trước</a>
                    <?php endif; ?>

                    <?php for ($i = max(1, $page - 2); $i <= min($total_pages, $page + 2); $i++): ?>
                        <?php if ($i == $page): ?>
                            <span class="current"><?php echo $i; ?></span>
                        <?php else: ?>
                            <a href="?<?php echo http_build_query(array_merge($_GET, ['page' => $i])); ?>"><?php echo $i; ?></a>
                        <?php endif; ?>
                    <?php endfor; ?>

                    <?php if ($page < $total_pages): ?>
                        <a href="?<?php echo http_build_query(array_merge($_GET, ['page' => $page + 1])); ?>">Sau »</a>
                    <?php endif; ?>
                </div>
            <?php endif; ?>
        </div>
    </main>
</div>


<script>
    function openUploadModal(vehicleId, imageType) {
        document.getElementById('vehicleId').value = vehicleId;
        document.getElementById('imageType').value = imageType;
        document.getElementById('uploadModal').style.display = 'block';
    }

    function closeUploadModal() {
        document.getElementById('uploadModal').style.display = 'none';
        document.getElementById('uploadForm').reset();
    }

    function showImageModal(imagePath) {
        document.getElementById('modalImage').src = imagePath;
        document.getElementById('imageModal').style.display = 'block';
    }

    function closeImageModal() {
        document.getElementById('imageModal').style.display = 'none';
    }

    

    
</script>
</body>
</html>
