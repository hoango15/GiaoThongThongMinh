<?php
session_start();

// Xóa toàn bộ session
$_SESSION = [];
session_unset();
session_destroy();

// Chuyển hướng về trang login kèm thông báo
header("Location: login.php?logged_out=1");
exit();
