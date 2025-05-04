#include <Arduino.h>

// Define the pin numbers we want to control
const int outputPins[] = {6, 5, 4, 3, 2}; // Added pin 3
// Calculate number of pins *AFTER* defining the array
const int numPins = sizeof(outputPins) / sizeof(outputPins[0]);

// Define the *default* duration the pins should stay HIGH (in milliseconds)
const unsigned long defaultHighDuration = 1700;
// Define the special duration for the 'h2dim' command (in milliseconds)
const unsigned long dimHighDuration = 4000; // 3000 ms = 3 seconds

// --- Per-Pin Timer Variables ---
// Stores the time when each pin was last turned HIGH
unsigned long pinHighStartTime[numPins];
// Tracks if each pin is currently in its timed HIGH state
bool pinIsTimed[numPins];
// Stores the duration this specific pin should stay HIGH for its current timed event
unsigned long pinTargetDuration[numPins];

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
    pinTargetDuration[i] = 0;         // Target duration is 0 initially

    Serial.print(outputPins[i]);
    if (i < numPins - 1) {
      Serial.print(", ");
    }
  }
  Serial.println(" as OUTPUT, initially LOW.");

  // Print a message to the Serial Monitor
  Serial.println("Arduino is ready.");
  Serial.println("Send 'h' followed by pin number (6, 5, 4, 3, or 2) to turn it HIGH for 2 seconds.");
  Serial.println("Send 'h2dim' to turn pin 2 HIGH for 3 seconds.");
  Serial.println("Examples: send 'h6', 'h3', 'h2dim'");
}

void loop() {
  // --- Check for Serial Input Completion ---
  // (See serialEvent() function below for how inputString and stringComplete are set)
  if (stringComplete) {
    Serial.print("Received command: ");
    Serial.println(inputString);

    // --- Process the Received Command ---

    // Check for the special "h2dim" command FIRST
    if (inputString.equals("h2dim")) {
        int targetPin = 2;
        int targetIndex = -1;
        // Find the index for pin 2
        for (int i = 0; i < numPins; i++) {
            if (outputPins[i] == targetPin) {
                targetIndex = i;
                break;
            }
        }

        if (targetIndex != -1) {
            Serial.println("Activating pin 2 HIGH for 3 seconds (h2dim).");
            digitalWrite(targetPin, HIGH);          // Turn pin 2 HIGH
            pinHighStartTime[targetIndex] = millis(); // Record its start time
            pinTargetDuration[targetIndex] = dimHighDuration; // Set the 3-second duration
            pinIsTimed[targetIndex] = true;          // Mark it as timed
        } else {
             Serial.println("Error: Pin 2 is not configured in outputPins array!");
        }

    // Check for the standard 'h' + pin number command
    } else if (inputString.length() == 2 && inputString.startsWith("h")) {
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
        pinTargetDuration[targetIndex] = defaultHighDuration; // Set the default 2-second duration
        pinIsTimed[targetIndex] = true;         // Mark it as timed
      } else {
        Serial.print("Invalid pin specified: ");
        Serial.println(pinChar);
      }
    } else {
      Serial.println("Invalid command format. Use 'h' + pin number (e.g., h6) or 'h2dim'.");
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
    // Use the specific target duration stored for this pin's activation
    if (pinIsTimed[i] && (currentTime - pinHighStartTime[i] >= pinTargetDuration[i])) {
      digitalWrite(outputPins[i], LOW); // Turn this specific pin LOW
      pinIsTimed[i] = false;            // Reset its timed flag
      //pinTargetDuration[i] = 0; // Optional: Reset duration, not strictly necessary
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
    // Optional: Add a check for maximum input string length to prevent buffer overflows
    if (inputString.length() > 20) { // Example limit
        Serial.println("Input buffer overflow! Clearing.");
        inputString = "";
        stringComplete = false; // Prevent processing partial overflowed command
    }
  }
}