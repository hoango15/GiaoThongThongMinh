<?php
require_once 'includes/auth.php';
require_once 'config/database.php';

requireLogin();

$database = new Database();
$db = $database->getConnection();

// Xử lý filters cho báo cáo
$report_date_from = $_GET['report_date_from'] ?? date('Y-m-01'); // Đầu tháng hiện tại
$report_date_to = $_GET['report_date_to'] ?? date('Y-m-t'); // Cuối tháng hiện tại
$report_type = $_GET['report_type'] ?? 'daily'; // daily hoặc monthly

if ($report_type === 'monthly') {
    $selected_month = $_GET['selected_month'] ?? date('Y-m');
    $month_start = $selected_month . '-01';
    $month_end = date('Y-m-t', strtotime($month_start));
    
    // Báo cáo xe vào theo tháng
    $monthly_in_query = "
        SELECT 
            DATE(time_in) as date,
            COUNT(*) as vehicles_in
        FROM vehicles 
        WHERE DATE(time_in) BETWEEN :month_start AND :month_end
        GROUP BY DATE(time_in)
        ORDER BY date ASC
    ";
    
    $monthly_in_stmt = $db->prepare($monthly_in_query);
    $monthly_in_stmt->bindParam(':month_start', $month_start);
    $monthly_in_stmt->bindParam(':month_end', $month_end);
    $monthly_in_stmt->execute();
    $monthly_in_report = $monthly_in_stmt->fetchAll(PDO::FETCH_ASSOC);
    
    // Báo cáo xe ra theo tháng
    $monthly_out_query = "
        SELECT 
            DATE(time_out) as date,
            COUNT(*) as vehicles_out,
            COALESCE(SUM(fee), 0) as daily_revenue
        FROM vehicles 
        WHERE time_out IS NOT NULL 
            AND DATE(time_out) BETWEEN :month_start AND :month_end
        GROUP BY DATE(time_out)
        ORDER BY date ASC
    ";
    
    $monthly_out_stmt = $db->prepare($monthly_out_query);
    $monthly_out_stmt->bindParam(':month_start', $month_start);
    $monthly_out_stmt->bindParam(':month_end', $month_end);
    $monthly_out_stmt->execute();
    $monthly_out_report = $monthly_out_stmt->fetchAll(PDO::FETCH_ASSOC);
    
    // Tổng kết tháng
    $monthly_summary_query = "
        SELECT 
            (SELECT COUNT(*) FROM vehicles WHERE DATE(time_in) BETWEEN :month_start AND :month_end) as total_in,
            (SELECT COUNT(*) FROM vehicles WHERE time_out IS NOT NULL AND DATE(time_out) BETWEEN :month_start AND :month_end) as total_out,
            (SELECT COALESCE(SUM(fee), 0) FROM vehicles WHERE time_out IS NOT NULL AND DATE(time_out) BETWEEN :month_start AND :month_end) as total_revenue,
            (SELECT COUNT(*) FROM vehicles WHERE time_out IS NULL AND DATE(time_in) BETWEEN :month_start AND :month_end) as still_parked
    ";
    
    $monthly_summary_stmt = $db->prepare($monthly_summary_query);
    $monthly_summary_stmt->bindParam(':month_start', $month_start);
    $monthly_summary_stmt->bindParam(':month_end', $month_end);
    $monthly_summary_stmt->execute();
    $monthly_summary = $monthly_summary_stmt->fetch(PDO::FETCH_ASSOC);
}

// Báo cáo doanh thu theo ngày (code cũ)
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
    <style>
        /* Container cho báo cáo theo ngày */
.daily-report-card {
    background-color: #f9fafb;
    border: 1px solid #e5e7eb;
    border-radius: 0.5rem;
    padding: 20px;
    margin-bottom: 20px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.05);
}

/* Header của báo cáo theo ngày */
.daily-report-card .card-header {
    background-color: #1e3a8a;
    color: #ffffff;
    padding: 15px 20px;
    border-radius: 0.5rem 0.5rem 0 0;
    font-size: 1.2rem;
    font-weight: 600;
}

/* Table trong báo cáo theo ngày */
.daily-report-card .table {
    width: 100%;
    border-collapse: collapse;
    margin-top: 15px;
}

.daily-report-card .table th,
.daily-report-card .table td {
    padding: 12px;
    border-bottom: 1px solid #d1d5db;
    text-align: left;
}

.daily-report-card .table th {
    background-color: #e5e7eb;
    font-weight: 600;
}

.daily-report-card .table tbody tr:hover {
    background-color: #f3f4f6;
}

/* Nút chức năng báo cáo */
.report-actions {
    display: flex;
    gap: 10px;
    margin-bottom: 20px;
}

.report-actions .btn {
    padding: 10px 18px;
    border-radius: 0.5rem;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s ease-in-out;
    display: inline-flex;
    align-items: center;
    gap: 5px;
}

/* Nút Xuất Excel */
.report-actions .btn-success {
    background-color: #16a34a;
    color: #ffffff;
    border: none;
}

.report-actions .btn-success:hover {
    background-color: #15803d;
    transform: translateY(-1px);
}

/* Nút In báo cáo */
.report-actions .btn-info {
    background-color: #3b82f6;
    color: #ffffff;
    border: none;
}

.report-actions .btn-info:hover {
    background-color: #2563eb;
    transform: translateY(-1px);
}

/* Nút Làm mới */
.report-actions .btn-secondary {
    background-color: #6b7280;
    color: #ffffff;
    border: none;
}

.report-actions .btn-secondary:hover {
    background-color: #4b5563;
    transform: translateY(-1px);
}

/* Responsive */
@media (max-width: 768px) {
    .report-actions {
        flex-direction: column;
        align-items: stretch;
    }

    .report-actions .btn {
        width: 100%;
        justify-content: center;
    }
}

/* Print-friendly: chỉ in báo cáo theo ngày */
@media print {
    body * {
        visibility: hidden;
    }

    .daily-report-card, .daily-report-card * {
        visibility: visible;
    }

    .daily-report-card {
        position: absolute;
        left: 0;
        top: 0;
        width: 100%;
        box-shadow: none;
        border: none;
        padding: 0;
    }

    .report-actions {
        display: none;
    }
}

    </style>
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
                <h1 class="page-title">Báo cáo hệ thống</h1>
                <div class="user-info">
                    <span>Xin chào, <?php echo htmlspecialchars($_SESSION['admin_name']); ?></span>
                </div>
            </div>

            <!-- Thêm tabs để chuyển đổi giữa báo cáo ngày và tháng -->
            <div class="report-tabs">
                <button class="tab-button <?php echo $report_type === 'daily' ? 'active' : ''; ?>" 
                        onclick="switchReportType('daily')">Báo cáo theo ngày</button>
                <button class="tab-button <?php echo $report_type === 'monthly' ? 'active' : ''; ?>" 
                        onclick="switchReportType('monthly')">Báo cáo theo tháng</button>
            </div>

            <!-- Thêm các nút chức năng báo cáo -->
            <div class="report-actions">
                <button onclick="exportReport()" class="btn btn-success">📊 Xuất Excel</button>
                <button onclick="printReport()" class="btn btn-info">🖨️ In báo cáo</button>
                <button onclick="refreshReport()" class="btn btn-secondary">🔄 Làm mới</button>
            </div>
            
            <?php if ($report_type === 'monthly'): ?>
            <!-- Giao diện báo cáo tháng mới -->
            <div class="card">
                <div class="card-header">
                    <h3 class="card-title">Chọn tháng báo cáo</h3>
                </div>
                <form method="GET" class="filters">
                    <input type="hidden" name="report_type" value="monthly">
                    <div class="filter-group">
                        <label>Chọn tháng:</label>
                        <input type="month" name="selected_month" class="form-input" 
                               value="<?php echo $selected_month ?? date('Y-m'); ?>">
                    </div>
                    <div class="filter-group">
                        <label>&nbsp;</label>
                        <button type="submit" class="btn btn-primary">Xem báo cáo tháng</button>
                    </div>
                </form>
            </div>

            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-number"><?php echo $monthly_summary['total_in']; ?></div>
                    <div class="stat-label">Tổng xe vào</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number"><?php echo $monthly_summary['total_out']; ?></div>
                    <div class="stat-label">Tổng xe ra</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number"><?php echo $monthly_summary['still_parked']; ?></div>
                    <div class="stat-label">Xe đang đỗ</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number"><?php echo number_format($monthly_summary['total_revenue']); ?>đ</div>
                    <div class="stat-label">Doanh thu tháng</div>
                </div>
            </div>

            <div class="monthly-grid">
                <div class="card">
                    <div class="card-header">
                        <h3 class="card-title">Xe vào theo ngày</h3>
                    </div>
                    <div class="table-container">
                        <table class="table">
                            <thead>
                                <tr>
                                    <th>Ngày</th>
                                    <th>Số xe vào</th>
                                </tr>
                            </thead>
                            <tbody>
                                <?php if (empty($monthly_in_report)): ?>
                                <tr>
                                    <td colspan="2" style="text-align: center; color: #666;">
                                        Không có dữ liệu xe vào trong tháng này
                                    </td>
                                </tr>
                                <?php else: ?>
                                    <?php foreach ($monthly_in_report as $report): ?>
                                    <tr>
                                        <td><?php echo date('d/m/Y', strtotime($report['date'])); ?></td>
                                        <td><strong><?php echo $report['vehicles_in']; ?></strong></td>
                                    </tr>
                                    <?php endforeach; ?>
                                <?php endif; ?>
                            </tbody>
                        </table>
                    </div>
                </div>

                <div class="card">
                    <div class="card-header">
                        <h3 class="card-title">Xe ra theo ngày</h3>
                    </div>
                    <div class="table-container">
                        <table class="table">
                            <thead>
                                <tr>
                                    <th>Ngày</th>
                                    <th>Số xe ra</th>
                                    <th>Doanh thu</th>
                                </tr>
                            </thead>
                            <tbody>
                                <?php if (empty($monthly_out_report)): ?>
                                <tr>
                                    <td colspan="3" style="text-align: center; color: #666;">
                                        Không có dữ liệu xe ra trong tháng này
                                    </td>
                                </tr>
                                <?php else: ?>
                                    <?php foreach ($monthly_out_report as $report): ?>
                                    <tr>
                                        <td><?php echo date('d/m/Y', strtotime($report['date'])); ?></td>
                                        <td><strong><?php echo $report['vehicles_out']; ?></strong></td>
                                        <td><?php echo number_format($report['daily_revenue']); ?>đ</td>
                                    </tr>
                                    <?php endforeach; ?>
                                <?php endif; ?>
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>

            <?php else: ?>
            <!-- Giao diện báo cáo ngày (code cũ) -->
            <div class="card">
                <div class="card-header">
                    <h3 class="card-title">Chọn khoảng thời gian</h3>
                </div>
                <form method="GET" class="filters">
                    <input type="hidden" name="report_type" value="daily">
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
                                <td colspan="3" style="text-align: center; color: #666;">
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
                                <td colspan="5" style="text-align: center; color: #666;">
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
            <?php endif; ?>
        </main>
    </div>

    <script>
        function switchReportType(type) {
            const url = new URL(window.location);
            url.searchParams.set('report_type', type);
            if (type === 'monthly') {
                url.searchParams.delete('report_date_from');
                url.searchParams.delete('report_date_to');
            } else {
                url.searchParams.delete('selected_month');
            }
            window.location.href = url.toString();
        }

        function printReport() {
            window.print();
        }

        function refreshReport() {
            window.location.reload();
        }

        function exportReport() {
            // Tạo dữ liệu CSV từ bảng hiện tại
            const tables = document.querySelectorAll('.table');
            let csvContent = "data:text/csv;charset=utf-8,";
            
            tables.forEach((table, index) => {
                const title = table.closest('.card').querySelector('.card-title').textContent;
                csvContent += title + "\n";
                
                const rows = table.querySelectorAll('tr');
                rows.forEach(row => {
                    const cols = row.querySelectorAll('th, td');
                    const rowData = Array.from(cols).map(col => 
                        '"' + col.textContent.trim().replace(/"/g, '""') + '"'
                    ).join(',');
                    csvContent += rowData + "\n";
                });
                csvContent += "\n";
            });

            const encodedUri = encodeURI(csvContent);
            const link = document.createElement("a");
            link.setAttribute("href", encodedUri);
            link.setAttribute("download", "bao_cao_" + new Date().toISOString().split('T')[0] + ".csv");
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        }

        // Tự động làm mới dữ liệu mỗi 5 phút
        setInterval(function() {
            if (confirm('Dữ liệu có thể đã thay đổi. Bạn có muốn làm mới báo cáo?')) {
                refreshReport();
            }
        }, 300000); // 5 phút
    </script>
</body>
</html>
