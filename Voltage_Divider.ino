// Define the analog input pins
const int analogPin1 = A0;
const int analogPin2 = A1;

// Variables to store sensor readings
int sensorValue1 = 0;
int sensorValue2 = 0;

// Known resistor values (10k ohms)
float R1 = 10000.00;
float R2 = 10000.00;

// Steinhart-Hart coefficients
const float A = 0.001028904003803319;
const float B = 0.00023917243029486095;
const float C = 1.5647042887059707e-07;

// Function to calculate temperature from resistance
float calculateTemperature(float resistance) {
    float steinhart;
    steinhart = log(resistance);
    steinhart = A + B * steinhart + C * steinhart * steinhart * steinhart;
    steinhart = 1.0 / steinhart;
    steinhart -= 273.15;
    return steinhart;
}

void setup() {
    Serial.begin(9600);
}

void loop() {
    // Read values from both sensors
    sensorValue1 = analogRead(analogPin1);
    sensorValue2 = analogRead(analogPin2);
    
    // Calculate voltage for both sensors
    float voltage1 = sensorValue1 * (5.0 / 1023.0);
    float voltage2 = sensorValue2 * (5.0 / 1023.0);
    
    // Calculate resistance for both sensors
    float resistance1 = R1 * voltage1 / (5.0 - voltage1);
    float resistance2 = R2 * voltage2 / (5.0 - voltage2);
    
    // Calculate temperature for both sensors
    float temp1 = calculateTemperature(resistance1);
    float temp2 = calculateTemperature(resistance2);
    
    // Send data in a format easy to parse: "temp1,temp2"
    Serial.print(temp1);
    Serial.print(",");
    Serial.println(temp2);
    
    delay(1000); // Wait for a second before next reading
}