<?php
require_once 'includes/auth.php';

$error = '';
$success = '';


if (isset($_GET['logged_out'])) {
    $success = 'Bạn đã đăng xuất thành công!';
}

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $username = $_POST['username'] ?? '';
    $password = $_POST['password'] ?? '';
    
    if (login($username, $password)) {
       
        $redirect = $_GET['redirect'] ?? 'dashboard.php';
        header('Location: ' . $redirect);
        exit();
    } else {
        $error = 'Tên đăng nhập hoặc mật khẩu không đúng!';
    }
}


if (isLoggedIn()) {
    header('Location: dashboard.php');
    exit();
}
?>
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Đăng nhập - Hệ thống quản lý bãi đỗ xe</title>
    <link rel="stylesheet" href="assets/style.css">
</head>
<body>
    <div class="login-container">
        <div class="login-card">
            <div class="login-header">
                <h1 class="login-title">🚗 Smart Parking</h1>
                <p class="login-subtitle">Hệ thống quản lý bãi đỗ xe thông minh</p>
                
            </div>
            
            <?php if ($error): ?>
                <div class="alert alert-error">
                    <?php echo htmlspecialchars($error); ?>
                </div>
            <?php endif; ?>
            
            <?php if ($success): ?>
                <div class="alert alert-success">
                    <?php echo htmlspecialchars($success); ?>
                </div>
            <?php endif; ?>
            
            <form method="POST" action="">
                <div class="form-group">
                    <label for="username" class="form-label">Tên đăng nhập</label>
                    <input type="text" id="username" name="username" class="form-input" required autofocus>
                </div>
                
                <div class="form-group">
                    <label for="password" class="form-label">Mật khẩu</label>
                    <input type="password" id="password" name="password" class="form-input" required>
                </div>
                
                <button type="submit" class="btn btn-primary">Đăng nhập</button>
            </form>
            
          
        </div>
    </div>
</body>
</html>
