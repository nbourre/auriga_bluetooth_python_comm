// Pin for the buzzer (adjust to your hardware setup)
const int buzzerPin = 45;

void setup() {
  // Initialize serial communication
  Serial.begin(115200);
  
  // Setup buzzer pin as output
  pinMode(buzzerPin, OUTPUT);
}

void loop() {
  // Check if there's enough data available on the serial port
  if (Serial.available() >= 4) { // We need at least 4 bytes (0xFF, 0x55, and two data bytes)
    
    // Read the first two bytes and check if they are 0xFF and 0x55
    if (Serial.read() == 0xFF && Serial.read() == 0x55) {
      
      // Read the remaining data as a string
      String input = Serial.readString();
      
      // Trim any whitespace or newline characters
      input.trim();
      Serial.print("echo : ");
      Serial.println(input);
      
      // Check if the received string is "9999"
      if (input == "9999") {
        // Make the robot beep
        beepOnce();
      }
    }
  }
}

void beepOnce() {
  // Play a beep sound (adjust duration and frequency as needed)
  tone(buzzerPin, 1000, 200);  // 1000 Hz tone for 200 milliseconds
  delay(300);  // Small delay to prevent overlapping beeps
  noTone(buzzerPin);
}