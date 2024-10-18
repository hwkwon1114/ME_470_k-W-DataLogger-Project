let myChart;
let data;
let columns;

function fetchData() {
    $.getJSON('/get_data', function (response) {
        data = response.data;
        columns = response.columns;

        if (!myChart) {
            populateDropdown('#x-axis', columns);
            populateDropdown('#y-axis', columns);

            $('#x-axis').val('Timestamp');
            $('#y-axis').val(columns[1]);

            createChart();
        } else {
            updateChart();
        }
    });
}

$(document).ready(function () {
    fetchData();
    setInterval(fetchData, 5000);  // Fetch new data every 5 seconds
});

function populateDropdown(selector, options) {
    const dropdown = $(selector);
    dropdown.empty();
    $.each(options, function (i, option) {
        dropdown.append($('<option></option>').attr('value', option).text(option));
    });
}

function createChart() {
    const ctx = document.getElementById('myChart').getContext('2d');
    myChart = new Chart(ctx, {
        type: 'line',
        data: {
            datasets: [{
                label: $('#y-axis').val(),
                data: [],
                borderColor: 'rgb(75, 192, 192)',
                tension: 0.1
            }]
        },
        options: {
            responsive: true,
            scales: {
                x: {
                    type: 'time',
                    time: {
                        unit: 'minute',
                        displayFormats: {
                            minute: 'HH:mm'
                        }
                    },
                    title: {
                        display: true,
                        text: 'Time'
                    }
                },
                y: {
                    title: {
                        display: true,
                        text: $('#y-axis').val()
                    }
                }
            }
        }
    });
    updateChart();
}

function updateChart() {
    const xAxis = $('#x-axis').val();
    const yAxis = $('#y-axis').val();

    myChart.data.datasets[0].label = yAxis;
    myChart.data.datasets[0].data = data.map(item => ({
        x: new Date(item[xAxis]),
        y: parseFloat(item[yAxis])
    }));

    myChart.options.scales.y.title.text = yAxis;

    myChart.update();
}

$('#x-axis, #y-axis').change(updateChart);