<?php

require_once 'includes/auth.php';

enforceLogin();


if (isLoggedIn()) {
    header('Location: dashboard.php');
    exit();
}


header('Location: login.php');
exit();
?>
