<?php
$servername = "localhost"; 
$username   = "root";      
$password   = "root";        
$dbname     = "water_data";

$conn = new mysqli($servername, $username, $password, $dbname);
if ($conn->connect_error) {
    die("Connection failed: " . $conn->connect_error);
}

$rawData = file_get_contents("php://input");
parse_str($rawData, $data);

if (isset($data['ph']) && isset($data['ntu']) && isset($data['tds'])) {
    $ph  = floatval($data['ph']);
    $ntu = floatval($data['ntu']);
    $tds = floatval($data['tds']);

    $sql = "INSERT INTO sensor (ph, ntu, tds) VALUES ('$ph', '$ntu', '$tds')";
    if ($conn->query($sql) === TRUE) {
        echo "Insert thành công: pH=$ph, NTU=$ntu, TDS=$tds";
    } else {
        echo "Lỗi MySQL: " . $conn->error;
    }
} else {
    echo "Không có dữ liệu cảm biến được gửi đến.";
}

$conn->close();
?>
