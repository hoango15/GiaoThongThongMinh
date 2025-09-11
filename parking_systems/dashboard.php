<?php
require_once 'includes/auth.php';
require_once 'config/database.php';

requireLogin();

$database = new Database();
$db = $database->getConnection();


$stats_query = "
    SELECT 
        COUNT(*) as total_vehicles,
        COUNT(CASE WHEN time_out IS NULL THEN 1 END) as vehicles_in,
        COUNT(CASE WHEN time_out IS NOT NULL THEN 1 END) as vehicles_out,
        COALESCE(SUM(CASE WHEN time_out IS NOT NULL THEN fee END), 0) as total_revenue
    FROM vehicles
";
$stats_stmt = $db->prepare($stats_query);
$stats_stmt->execute();
$stats = $stats_stmt->fetch(PDO::FETCH_ASSOC);

// Lấy cấu hình bãi xe
$config_query = "SELECT max_capacity, current_count FROM config LIMIT 1";
$config_stmt = $db->prepare($config_query);
$config_stmt->execute();
$config = $config_stmt->fetch(PDO::FETCH_ASSOC);

// Doanh thu theo ngày (7 ngày gần nhất)
$revenue_query = "
    SELECT 
        DATE(time_out) as date,
        COALESCE(SUM(fee), 0) as daily_revenue
    FROM vehicles 
    WHERE time_out IS NOT NULL 
        AND time_out >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
    GROUP BY DATE(time_out)
    ORDER BY date DESC
";
$revenue_stmt = $db->prepare($revenue_query);
$revenue_stmt->execute();
$daily_revenue = $revenue_stmt->fetchAll(PDO::FETCH_ASSOC);
?>
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dashboard - Hệ thống quản lý bãi đỗ xe</title>
    <link rel="stylesheet" href="assets/style.css">
</head>
<body>
    <div class="dashboard">
        <nav class="sidebar">
            <div class="sidebar-header">
                <h2 class="sidebar-title">🚗 Smart Parking</h2>
            </div>
            <ul class="sidebar-nav">
                <li><a href="dashboard.php" class="active">Dashboard</a></li>
                <li><a href="vehicles.php">Quản lý xe</a></li>
                <li><a href="reports.php">Báo cáo</a></li>
                <li><a href="logout.php">Đăng xuất</a></li>
            </ul>
        </nav>
        
        <main class="main-content">
            <div class="header">
                <h1 class="page-title">Dashboard</h1>
                <div class="user-info">
                    <span>Xin chào, <?php echo htmlspecialchars($_SESSION['admin_name']); ?></span>
                    <a href="logout.php" class="btn btn-secondary">Đăng xuất</a>
                </div>
            </div>
            
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-number"><?php echo $config['max_capacity']; ?></div>
                    <div class="stat-label">Sức chứa tối đa</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number"><?php echo $stats['vehicles_in']; ?></div>
                    <div class="stat-label">Xe đang đỗ</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number"><?php echo $stats['vehicles_out']; ?></div>
                    <div class="stat-label">Xe đã ra</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number"><?php echo number_format($stats['total_revenue']); ?>đ</div>
                    <div class="stat-label">Tổng doanh thu</div>
                </div>
            </div>
            
            <div class="card">
                <div class="card-header">
                    <h3 class="card-title">Doanh thu 7 ngày gần nhất</h3>
                </div>
                <div class="table-container">
                    <table class="table">
                        <thead>
                            <tr>
                                <th>Ngày</th>
                                <th>Doanh thu</th>
                            </tr>
                        </thead>
                        <tbody>
                            <?php foreach ($daily_revenue as $revenue): ?>
                            <tr>
                                <td><?php echo date('d/m/Y', strtotime($revenue['date'])); ?></td>
                                <td><?php echo number_format($revenue['daily_revenue']); ?>đ</td>
                            </tr>
                            <?php endforeach; ?>
                        </tbody>
                    </table>
                </div>
            </div>
        </main>
    </div>
</body>
</html>
