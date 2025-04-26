#include <Arduino.h>

void setup() {
  // Initialize serial communication at 9600 bits per second:
  Serial.begin(9600);

  // Set the LED pin as an output:
  pinMode(LED_BUILTIN, OUTPUT);

  // Optional: Turn the LED off initially
  digitalWrite(LED_BUILTIN, LOW);

  // Optional: Print a message to the Serial Monitor to know it's ready
  Serial.println("Serial LED Control Ready");
  Serial.println("Send 'h' to turn LED ON, 'l' to turn LED OFF");
}

void loop() {
  // Check if data is available to read from the serial port:
  if (Serial.available() > 0) {
    // Read the incoming byte (character):
    char incomingChar = Serial.read();

    // Print the received character to the Serial Monitor (optional feedback)
    Serial.print("Received: ");
    Serial.println(incomingChar);

    // Check if the received character is 'h' (for high/on):
    if (incomingChar == 'h') {
      digitalWrite(LED_BUILTIN, HIGH); // Turn the LED ON
      Serial.println("LED ON");       // Confirm action on Serial Monitor
    }
    // Check if the received character is 'l' (for low/off):
    else if (incomingChar == 'l') {
      digitalWrite(LED_BUILTIN, LOW);  // Turn the LED OFF
      Serial.println("LED OFF");       // Confirm action on Serial Monitor
    }
    // You could add an 'else' here to handle other characters if needed
  }
  // No delay needed here, the loop will run quickly checking Serial.available()
}