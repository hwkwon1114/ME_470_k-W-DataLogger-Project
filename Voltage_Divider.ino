// Define the analog input pin
const int analogPin = A0;    // Using A0 as our input pin
int sensorValue = 0;         // Variable to store the sensor reading
float R1 = 100000.00;         // Known resistor value (10k ohms)

void setup() {
    // Initialize serial communication at 9600 baud rate
    Serial.begin(9600);
}

void loop() {
    sensorValue = analogRead(analogPin);
    
    // Print raw ADC value (should be 0-1023)
    Serial.print("ADC Raw: ");
    Serial.print(sensorValue);
    
    float voltage = sensorValue * (5.0 / 1023.0);
    Serial.print(", Voltage: ");
    Serial.print(voltage, 3);  // Print with 3 decimal places
    
    float resistance = R1 * voltage / (5.0 - voltage);
    Serial.print(", Resistance: ");
    Serial.println(resistance);
    
    delay(1000);
}