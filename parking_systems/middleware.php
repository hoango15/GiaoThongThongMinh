<?php
session_start();

$public_pages = [
    'login.php'
];

$current_page = basename($_SERVER['PHP_SELF']);

if (!in_array($current_page, $public_pages)) {
    require_once 'includes/auth.php';
    
    if (!isLoggedIn()) {
        session_unset();
        session_destroy();
        header('Location: login.php?required=1&redirect=' . urlencode($_SERVER['REQUEST_URI']));
        exit();
    }
    
    if (isset($_SESSION['login_time']) && (time() - $_SESSION['login_time']) > 86400) {
        require_once 'includes/auth.php';
        logout();
    }
}
?>
