#include <Arduino.h>

// Define the pin numbers we want to control
const int outputPins[] = {6, 5, 4, 2}; // Array of pin numbers
const int numPins = sizeof(outputPins) / sizeof(outputPins[0]); // Calculate number of pins

// Define the duration the pins should stay HIGH (in milliseconds)
const unsigned long highDuration = 2000; // 2000 ms = 2 seconds

// --- Per-Pin Timer Variables ---
// Stores the time when each pin was last turned HIGH
unsigned long pinHighStartTime[numPins];
// Tracks if each pin is currently in its timed HIGH state
bool pinIsTimed[numPins];

// --- Input Handling Variables ---
String inputString = "";       // A String to hold incoming data
bool stringComplete = false;  // Whether the string is complete

void setup() {
  // Initialize Serial communication at 9600 bits per second (bps)
  Serial.begin(9600);
  while (!Serial); // Wait for serial port to connect

  inputString.reserve(10); // Reserve some memory for the input String (optional optimization)

  // Configure all specified pins as OUTPUT and initialize timer states
  Serial.print("Setting up pins: ");
  for (int i = 0; i < numPins; i++) {
    pinMode(outputPins[i], OUTPUT);
    digitalWrite(outputPins[i], LOW); // Start LOW
    pinIsTimed[i] = false;            // Not initially timed
    pinHighStartTime[i] = 0;          // Start time is 0

    Serial.print(outputPins[i]);
    if (i < numPins - 1) {
      Serial.print(", ");
    }
  }
  Serial.println(" as OUTPUT, initially LOW.");

  // Print a message to the Serial Monitor
  Serial.println("Arduino is ready.");
  Serial.println("Send 'h' followed by pin number (6, 5, 4, or 2) to turn it HIGH for 2 seconds.");
  Serial.println("Example: send 'h6' or 'h2'");
}

void loop() {
  // --- Check for Serial Input Completion ---
  // (See serialEvent() function below for how inputString and stringComplete are set)
  if (stringComplete) {
    Serial.print("Received command: ");
    Serial.println(inputString);

    // --- Process the Received Command ---
    if (inputString.length() == 2 && inputString.startsWith("h")) {
      char pinChar = inputString.charAt(1); // Get the second character (the pin digit)
      int targetPin = -1; // Variable to hold the pin number if found
      int targetIndex = -1; // Variable to hold the index in our arrays

      // Find the matching pin and its index in our array
      for (int i = 0; i < numPins; i++) {
        // Convert pin number to char for comparison
        // Note: This simple conversion only works for single-digit pins (0-9)
        if (pinChar == (outputPins[i] + '0')) {
          targetPin = outputPins[i];
          targetIndex = i;
          break; // Found the pin, stop searching
        }
      }

      // If a valid pin command was found
      if (targetPin != -1 && targetIndex != -1) {
        Serial.print("Activating pin ");
        Serial.print(targetPin);
        Serial.println(" HIGH for 2 seconds.");

        digitalWrite(targetPin, HIGH);       // Turn the specific pin HIGH
        pinHighStartTime[targetIndex] = millis(); // Record its start time
        pinIsTimed[targetIndex] = true;         // Mark it as timed
      } else {
        Serial.print("Invalid pin specified: ");
        Serial.println(pinChar);
      }
    } else {
      Serial.println("Invalid command format. Use 'h' + pin number (e.g., h6).");
    }

    // Clear the string and reset the flag for the next command
    inputString = "";
    stringComplete = false;
  }

  // --- Check All Pin Timers ---
  // This runs independently of serial input
  unsigned long currentTime = millis();
  for (int i = 0; i < numPins; i++) {
    // Check if this specific pin is currently timed HIGH AND its time has expired
    if (pinIsTimed[i] && (currentTime - pinHighStartTime[i] >= highDuration)) {
      digitalWrite(outputPins[i], LOW); // Turn this specific pin LOW
      pinIsTimed[i] = false;            // Reset its timed flag
      Serial.print("Pin ");
      Serial.print(outputPins[i]);
      Serial.println(" LOW (timer expired).");
    }
  }
}

/*
  SerialEvent occurs whenever a new data comes in the hardware serial RX. This
  routine is run between each time loop() runs, so using delay inside loop can
  delay response. Multiple bytes of data may be available.
*/
void serialEvent() {
  while (Serial.available()) {
    // Get the new byte:
    char inChar = (char)Serial.read();
    // Add it to the inputString:
    inputString += inChar;
    // If the incoming character is a newline, set a flag so the main loop can
    // do something about it:
    if (inChar == '\n') {
      inputString.trim(); // Remove any leading/trailing whitespace (like \r)
      stringComplete = true;
    }
  }
}