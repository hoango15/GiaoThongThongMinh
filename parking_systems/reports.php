<?php
require_once 'includes/auth.php';
require_once 'config/database.php';

requireLogin();

$database = new Database();
$db = $database->getConnection();

// Xử lý filters cho báo cáo
$report_date_from = $_GET['report_date_from'] ?? date('Y-m-01'); // Đầu tháng hiện tại
$report_date_to = $_GET['report_date_to'] ?? date('Y-m-t'); // Cuối tháng hiện tại

// Báo cáo doanh thu theo ngày
$revenue_query = "
    SELECT 
        DATE(time_out) as date,
        COUNT(*) as total_vehicles,
        COALESCE(SUM(fee), 0) as daily_revenue
    FROM vehicles 
    WHERE time_out IS NOT NULL 
        AND DATE(time_out) BETWEEN :date_from AND :date_to
    GROUP BY DATE(time_out)
    ORDER BY date DESC
";

$revenue_stmt = $db->prepare($revenue_query);
$revenue_stmt->bindParam(':date_from', $report_date_from);
$revenue_stmt->bindParam(':date_to', $report_date_to);
$revenue_stmt->execute();
$revenue_report = $revenue_stmt->fetchAll(PDO::FETCH_ASSOC);

// Tổng kết trong khoảng thời gian
$summary_query = "
    SELECT 
        COUNT(*) as total_vehicles,
        COALESCE(SUM(fee), 0) as total_revenue,
        COALESCE(AVG(fee), 0) as avg_fee
    FROM vehicles 
    WHERE time_out IS NOT NULL 
        AND DATE(time_out) BETWEEN :date_from AND :date_to
";

$summary_stmt = $db->prepare($summary_query);
$summary_stmt->bindParam(':date_from', $report_date_from);
$summary_stmt->bindParam(':date_to', $report_date_to);
$summary_stmt->execute();
$summary = $summary_stmt->fetch(PDO::FETCH_ASSOC);

// Top 10 xe có phí cao nhất
$top_vehicles_query = "
    SELECT license_plate, ticket_code, time_in, time_out, fee
    FROM vehicles 
    WHERE time_out IS NOT NULL 
        AND DATE(time_out) BETWEEN :date_from AND :date_to
        AND fee IS NOT NULL
    ORDER BY fee DESC
    LIMIT 10
";

$top_vehicles_stmt = $db->prepare($top_vehicles_query);
$top_vehicles_stmt->bindParam(':date_from', $report_date_from);
$top_vehicles_stmt->bindParam(':date_to', $report_date_to);
$top_vehicles_stmt->execute();
$top_vehicles = $top_vehicles_stmt->fetchAll(PDO::FETCH_ASSOC);
?>
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Báo cáo - Hệ thống quản lý bãi đỗ xe</title>
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
                <li><a href="vehicles.php">Quản lý xe</a></li>
                <li><a href="reports.php" class="active">Báo cáo</a></li>
                <li><a href="logout.php">Đăng xuất</a></li>
            </ul>
        </nav>
        
        <main class="main-content">
            <div class="header">
                <h1 class="page-title">Báo cáo doanh thu</h1>
                <div class="user-info">
                    <span>Xin chào, <?php echo htmlspecialchars($_SESSION['admin_name']); ?></span>
                </div>
            </div>
            
            <div class="card">
                <div class="card-header">
                    <h3 class="card-title">Chọn khoảng thời gian</h3>
                </div>
                <form method="GET" class="filters">
                    <div class="filter-group">
                        <label>Từ ngày:</label>
                        <input type="date" name="report_date_from" class="form-input" value="<?php echo htmlspecialchars($report_date_from); ?>">
                    </div>
                    <div class="filter-group">
                        <label>Đến ngày:</label>
                        <input type="date" name="report_date_to" class="form-input" value="<?php echo htmlspecialchars($report_date_to); ?>">
                    </div>
                    <div class="filter-group">
                        <label>&nbsp;</label>
                        <button type="submit" class="btn btn-primary">Xem báo cáo</button>
                    </div>
                </form>
            </div>
            
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-number"><?php echo $summary['total_vehicles']; ?></div>
                    <div class="stat-label">Tổng số xe</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number"><?php echo number_format($summary['total_revenue']); ?>đ</div>
                    <div class="stat-label">Tổng doanh thu</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number"><?php echo number_format($summary['avg_fee']); ?>đ</div>
                    <div class="stat-label">Phí trung bình</div>
                </div>
            </div>
            
            <div class="card">
                <div class="card-header">
                    <h3 class="card-title">Doanh thu theo ngày</h3>
                </div>
                <div class="table-container">
                    <table class="table">
                        <thead>
                            <tr>
                                <th>Ngày</th>
                                <th>Số xe</th>
                                <th>Doanh thu</th>
                            </tr>
                        </thead>
                        <tbody>
                            <?php if (empty($revenue_report)): ?>
                            <tr>
                                <td colspan="3" style="text-align: center; color: var(--muted-foreground);">
                                    Không có dữ liệu trong khoảng thời gian này
                                </td>
                            </tr>
                            <?php else: ?>
                                <?php foreach ($revenue_report as $report): ?>
                                <tr>
                                    <td><?php echo date('d/m/Y', strtotime($report['date'])); ?></td>
                                    <td><?php echo $report['total_vehicles']; ?></td>
                                    <td><?php echo number_format($report['daily_revenue']); ?>đ</td>
                                </tr>
                                <?php endforeach; ?>
                            <?php endif; ?>
                        </tbody>
                    </table>
                </div>
            </div>
            
            <div class="card">
                <div class="card-header">
                    <h3 class="card-title">Top 10 xe có phí cao nhất</h3>
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
                            </tr>
                        </thead>
                        <tbody>
                            <?php if (empty($top_vehicles)): ?>
                            <tr>
                                <td colspan="5" style="text-align: center; color: var(--muted-foreground);">
                                    Không có dữ liệu trong khoảng thời gian này
                                </td>
                            </tr>
                            <?php else: ?>
                                <?php foreach ($top_vehicles as $vehicle): ?>
                                <tr>
                                    <td><?php echo htmlspecialchars($vehicle['license_plate']); ?></td>
                                    <td><?php echo htmlspecialchars($vehicle['ticket_code']); ?></td>
                                    <td><?php echo date('d/m/Y H:i', strtotime($vehicle['time_in'])); ?></td>
                                    <td><?php echo date('d/m/Y H:i', strtotime($vehicle['time_out'])); ?></td>
                                    <td><?php echo number_format($vehicle['fee']); ?>đ</td>
                                </tr>
                                <?php endforeach; ?>
                            <?php endif; ?>
                        </tbody>
                    </table>
                </div>
            </div>
        </main>
    </div>
</body>
</html>
