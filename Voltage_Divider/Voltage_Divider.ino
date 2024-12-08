// Define the analog input pins
const int analogPin1 = A0;
const int analogPin2 = A1;
const int analogPin3 = A2;
const int analogPin4 = A3;

// Power monitoring configuration (commented out but preserved)
/*
const int PULSE_INPUT_PIN = 2;    // Digital pin for pulse input
const float WHPP = 0.375;         // Watt-hours per pulse (example for 15A CT on 3Y-208)
const unsigned long DEBOUNCE_DELAY = 50;
const unsigned long UPDATE_INTERVAL = 1000;  // Update interval (ms)

// Power calculation variables
volatile unsigned long pulseCount = 0;
volatile unsigned long lastPulseTime = 0;
unsigned long lastUpdateTime = 0;
float instantPower = 0.0;

void ICACHE_RAM_ATTR pulseCounter() {
  unsigned long currentTime = millis();
  if ((currentTime - lastPulseTime) > DEBOUNCE_DELAY) {
    pulseCount++;
    lastPulseTime = currentTime;
  }
}

void calculatePower() {
  noInterrupts();
  unsigned long pulses = pulseCount;
  pulseCount = 0;
  interrupts();
  
  // Calculate power based on pulse count over the last interval
  instantPower = (float)pulses * WHPP * (3600.0 / (UPDATE_INTERVAL / 1000.0));
}
*/

// Simulated power value (reasonable for a chiller system)
float simulatedPower = 25000.0; // Starting at 25kW

// Variables to store sensor readings
int sensorValue1 = 0;
int sensorValue2 = 0;
int sensorValue3 = 0;
int sensorValue4 = 0;

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
    
    // Power monitoring setup (commented out)
    /*
    pinMode(PULSE_INPUT_PIN, INPUT_PULLUP);
    attachInterrupt(digitalPinToInterrupt(PULSE_INPUT_PIN), pulseCounter, FALLING);
    */
}

void loop() {
    // Read values from sensors
    sensorValue1 = analogRead(analogPin1);
    sensorValue2 = analogRead(analogPin2);
    sensorValue3 = analogRead(analogPin3);
    sensorValue4 = analogRead(analogPin4);

    // Calculate voltage for temperature sensors
    float voltage1 = sensorValue1 * (5.0 / 1023.0);
    float voltage2 = sensorValue2 * (5.0 / 1023.0);

    // Calculate resistance for temperature sensors
    float resistance1 = R1 * voltage1 / (5.0 - voltage1);
    float resistance2 = R2 * voltage2 / (5.0 - voltage2);

    // Calculate temperatures
    float temp1 = calculateTemperature(resistance1);
    float temp2 = calculateTemperature(resistance2);

    // Calculate pressures
    float pres1 = sensorValue3 * (1.0 / 1023.0) * 300;
    float pres2 = sensorValue4 * (1.0 / 1023.0) * 300;

    // Power calculation code (commented out)
    /*
    if (millis() - lastUpdateTime >= UPDATE_INTERVAL) {
        calculatePower();
        lastUpdateTime = millis();
    }
    */

    // Instead, use simulated power value
    simulatedPower += random(-500, 500);  // Add random variation
    if (simulatedPower < 20000) simulatedPower = 20000;  // Min 20kW
    if (simulatedPower > 30000) simulatedPower = 30000;  // Max 30kW

    // Send data: T1,T2,Pres1,Pres2,Power
    Serial.print(temp1, 1);
    Serial.print(",");
    Serial.print(temp2, 1);
    Serial.print(",");
    Serial.print(pres1, 1);
    Serial.print(",");
    Serial.print(pres2, 1);
    Serial.print(",");
    Serial.println(simulatedPower, 1);

    delay(1000); // Wait for a second before next reading
}