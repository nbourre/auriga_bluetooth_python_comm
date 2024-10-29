unsigned long currentTime = 0;

String serialMessage;

void setup() {
  Serial.begin(115200);

}

void loop() {
  currentTime = millis();
  
  serialPrintTask(currentTime);

}

void serialPrintTask(unsigned long ct) {
  static unsigned long lastTime = 0;
  const unsigned int rate = 1000;
  
  if (ct - lastTime < rate) return;
  
  lastTime = ct;
  
  Serial.println(ct);
  
}

void serialEvent() {
  if (!Serial.available()) return;
  
  serialMessage = Serial.readString();
  
  if (serialMessage.length() > 2) {
    // Removing 0xFF55
    serialMessage.remove(0, 2);
  }
  
  Serial.print ("Robot a reçu : ");
  Serial.println(serialMessage);
}