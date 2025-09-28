<?php
$servername = "localhost";
$username   = "root";
$password   = "root";
$dbname     = "water_data";

$conn = new mysqli($servername, $username, $password, $dbname);
if ($conn->connect_error) {
    die("Kết nối thất bại: " . $conn->connect_error);
}

$sql = "SELECT id, ph, ntu, tds, created_at FROM sensor ORDER BY created_at DESC LIMIT 50"; 
$result = $conn->query($sql);

$labels = [];
$phData = [];
$ntuData = [];
$tdsData = [];

if ($result->num_rows > 0) {
    while ($row = $result->fetch_assoc()) {
        $labels[] = $row["created_at"];
        $phData[] = $row["ph"];
        $ntuData[] = $row["ntu"];
        $tdsData[] = $row["tds"];
        $rows[] = $row;
    }
}
$conn->close();
?>
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <title>Dữ liệu cảm biến nước</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body { font-family: Arial, sans-serif; }
        h2, h3 { text-align: center; }

        /* Biểu đồ */
        #charts { width: 90%; margin: auto; }
        .chart-box {
            width: 100%;
            height: 400px;
            margin: 20px 0;
        }

        /* Nhóm 3 biểu đồ nhỏ */
        .chart-row {
            display: flex;
            justify-content: space-between;
            gap: 10px;
            margin: 20px auto;
            width: 90%;
        }
        .chart-small {
            flex: 1;
            height: 300px;
        }

        /* Bảng */
        table {
            border-collapse: collapse;
            width: 80%;
            margin: 20px auto;
        }
        th, td {
            border: 1px solid #333;
            padding: 8px;
            text-align: center;
        }
        th { background-color: #ddd; }
    </style>
</head>
<body>
    <h2>Biểu đồ cảm biến nước</h2>
    <div id="charts">
        <!-- Biểu đồ tổng hợp -->
        <div class="chart-box"><canvas id="chartAll"></canvas></div>

        <!-- Hàng 3 biểu đồ nhỏ -->
        <div class="chart-row">
            <div class="chart-small"><canvas id="chartPH"></canvas></div>
            <div class="chart-small"><canvas id="chartNTU"></canvas></div>
            <div class="chart-small"><canvas id="chartTDS"></canvas></div>
        </div>
    </div>

    <h2>Dữ liệu cảm biến nước (bảng)</h2>
    <table>
        <tr>
            <th>ID</th>
            <th>pH</th>
            <th>Độ đục (NTU)</th>
            <th>TDS</th>
            <th>Thời gian</th>
        </tr>
        <?php
        if (!empty($rows)) {
            foreach ($rows as $row) {
                echo "<tr>
                        <td>".$row["id"]."</td>
                        <td>".$row["ph"]."</td>
                        <td>".$row["ntu"]."</td>
                        <td>".$row["tds"]."</td>
                        <td>".$row["created_at"]."</td>
                      </tr>";
            }
        } else {
            echo "<tr><td colspan='5'>Không có dữ liệu</td></tr>";
        }
        ?>
    </table>

    <script>
    const labels = <?php echo json_encode(array_reverse($labels)); ?>;
    const phData = <?php echo json_encode(array_reverse($phData)); ?>;
    const ntuData = <?php echo json_encode(array_reverse($ntuData)); ?>;
    const tdsData = <?php echo json_encode(array_reverse($tdsData)); ?>;

    // Hàm vẽ biểu đồ
    function drawChart(canvasId, label, data, color, multi=false) {
        const ctx = document.getElementById(canvasId).getContext('2d');
        new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: multi ? data : [{
                    label: label,
                    data: data,
                    borderColor: color,
                    backgroundColor: color,
                    fill: false,
                    tension: 0.1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { position: 'top' } },
                scales: { y: { beginAtZero: true } }
            }
        });
    }

    // Biểu đồ tổng hợp
    drawChart("chartAll", "", [
        { label: "pH", data: phData, borderColor: "red", fill: false, tension: 0.1 },
        { label: "NTU", data: ntuData, borderColor: "blue", fill: false, tension: 0.1 },
        { label: "TDS", data: tdsData, borderColor: "green", fill: false, tension: 0.1 }
    ], "", true);

    // Biểu đồ riêng
    drawChart("chartPH", "pH", phData, "red");
    drawChart("chartNTU", "NTU", ntuData, "blue");
    drawChart("chartTDS", "TDS", tdsData, "green");
    </script>
</body>
</html>
