import serial
import serial.tools.list_ports
import time
from flask import Flask, render_template_string, request, redirect, url_for, flash
import atexit

# --- Configuration ---
# Try to automatically find the Arduino port
# Common Arduino VID/PID pairs (you might need to add yours)
ARDUINO_VIDS_PIDS = [
    (0x2341, 0x0043),  # Arduino Uno R3
    (0x2341, 0x0001),  # Arduino Uno
    (0x2A03, 0x0043),  # Arduino Uno R3 Clone (CH340)
    (0x1A86, 0x7523),  # Common CH340 chip used in clones
    (0x239A, 0x800B),  # Adafruit Feather M0
    (0x10C4, 0xEA60)   # CP210x UART Bridge (used in some ESP32/ESP8266)
]

SERIAL_PORT = None # Start with None, try to find it
BAUD_RATE = 9600
PINS_TO_CONTROL = [6, 5, 4, 2] # Define the controllable pins here

# --- Auto-detect Port ---
ports = serial.tools.list_ports.comports()
print("Available serial ports:")
found_port = False
for port_info in sorted(ports):
    port = port_info.device
    desc = port_info.description
    hwid = port_info.hwid
    print(f"- {port}: {desc} [{hwid}]")
    # Check VID/PID
    if port_info.vid is not None and port_info.pid is not None:
        if (port_info.vid, port_info.pid) in ARDUINO_VIDS_PIDS:
            SERIAL_PORT = port
            print(f"  -> Found potential Arduino (VID/PID match) on {SERIAL_PORT}")
            found_port = True
            break # Use the first one found

if not found_port:
    # Fallback to description matching if VID/PID didn't work
    for port_info in sorted(ports):
        port = port_info.device
        desc = port_info.description.lower()
        if "arduino" in desc or "ch340" in desc or "cp210x" in desc or "usb serial" in desc:
            SERIAL_PORT = port
            print(f"  -> Found potential Arduino (by description) on {SERIAL_PORT}")
            found_port = True
            break # Use the first one found

if not found_port:
    print("\n---! Arduino Not Found Automatically !---")
    print("Please check connections and ensure the correct port is available.")
    print("You may need to manually set the SERIAL_PORT variable in the script.")
    # Example:
    # SERIAL_PORT = '/dev/ttyACM0' # <--- !!! MANUALLY SET THIS IF NEEDED !!!
    # Or on Windows: SERIAL_PORT = 'COM3'
    # exit("Exiting: Serial port not set.") # Decide if you want to exit or proceed
    print("Warning: Proceeding without a detected serial port.")


# ---------------------

app = Flask(__name__)
app.secret_key = 'your_very_secret_key_change_me' # Change this! Needed for flashing messages

# Global variable for the serial connection
ser = None

def init_serial():
    """Initializes or re-initializes the serial connection."""
    global ser
    if ser and ser.is_open:
        print("Serial port already open.")
        return True
    if not SERIAL_PORT:
        print("Serial port not configured.")
        return False

    try:
        print(f"Attempting to connect to {SERIAL_PORT} at {BAUD_RATE} baud...")
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        # It's crucial to wait for the Arduino to reset after opening the serial connection.
        # The exact time can vary depending on the board and OS.
        print("Waiting for Arduino to initialize...")
        time.sleep(2.5) # Give Arduino time to reset (adjust if needed)
        # Maybe read any startup messages from Arduino
        # initial_lines = ser.read_until(b'\n', 5).decode(errors='ignore') # Read for up to 5s
        # print(f"Initial Arduino Output: {initial_lines.strip()}")
        ser.reset_input_buffer() # Clear any data sent during reset
        print("Serial connection established.")
        return True
    except serial.SerialException as e:
        print(f"Error opening serial port {SERIAL_PORT}: {e}")
        ser = None
        return False
    except Exception as e:
        print(f"An unexpected error occurred during serial init: {e}")
        ser = None
        return False

# Attempt to initialize serial connection on startup
init_serial()

# Updated HTML template with buttons for each pin
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Arduino Pin Control</title>
    <style>
    {{ '{%' }} raw {{ '%}' }} {# <--- Jinja needs these to ignore CSS as template code #}
        body {{ font-family: sans-serif; text-align: center; margin-top: 30px; }}
        h1 {{ margin-bottom: 30px; }}
        .button {{
            padding: 12px 25px;
            font-size: 16px;
            cursor: pointer;
            margin: 8px;
            border: none;
            border-radius: 5px;
            color: white;
            min-width: 150px; /* Ensure buttons have similar width */
        }}
        .pin-button {{ background-color: #007bff; }} /* Blue */
        .pin-button:hover {{ background-color: #0056b3; }}
        .status {{ margin-top: 25px; font-style: italic; color: #555; }}
        .error {{ color: red; font-weight: bold; background-color: #ffe0e0; padding: 10px; border-radius: 5px; display: inline-block; margin-bottom:15px; }}
        .message {{ color: blue; font-weight: bold; background-color: #e0e0ff; padding: 10px; border-radius: 5px; display: inline-block; margin-bottom:15px; }}
        ul {{ list-style: none; padding: 0; }}
        li {{ margin-bottom: 5px; }}
        .retry-button {{
            padding: 8px 15px; background-color: #ffc107; color: black;
            border: none; border-radius: 4px; cursor: pointer; margin-top: 10px;
        }}
         .retry-button:hover {{ background-color: #e0a800; }}
    {{ '{%' }} endraw {{ '%}' }} {# <--- End of raw block #}
    </style>
</head>
<body>
    <h1>Arduino Pin Control</h1>
    <p>Click a button to trigger the corresponding pin HIGH for 2 seconds.</p>

    <!-- Flash Messages -->
    {{ '{%' }} with messages = get_flashed_messages(with_categories=true) {{ '%}' }}
      {{ '{%' }} if messages {{ '%}' }}
        <div>
          {{ '{%' }} for category, message in messages {{ '%}' }}
            <p class="{{ category }}">{{ message }}</p>
          {{ '{%' }} endfor {{ '%}' }}
        </div>
      {{ '{%' }} endif {{ '%}' }}
    {{ '{%' }} endwith {{ '%}' }}


    {{ '{%' }} if serial_status == 'connected' {{ '%}' }}
        <form method="POST" action="/control">
            {{ '{%' }} for pin in pins {{ '%}' }} {# Loop through pins passed from Flask #}
                 <button class="button pin-button" type="submit" name="pin" value="{{ pin }}">
                     Trigger Pin {{ pin }}
                 </button>
            {{ '{%' }} endfor {{ '%}' }}
        </form>
        <p class="status">Serial Port: {{ port }} | Status: Connected</p>

    {{ '{%' }} else {{ '%}' }}
        <p class="error">Error: Cannot connect to Arduino{{ ' on ' + port if port else '' }}.</p>
        <p>Please check:</p>
        <ul>
            <li>Is the Arduino plugged in and running the correct sketch?</li>
            <li>Is the correct SERIAL_PORT ('{{ port or 'Not Set' }}') detected/set in the script?</li>
            <li>Does the user running this script have permission for the serial port? (e.g., add to 'dialout' group on Linux: `sudo usermod -a -G dialout $USER`)</li>
            <li>Is the Arduino IDE's Serial Monitor or another program using the port closed?</li>
        </ul>
        <form method="POST" action="/retry_serial">
             <button type="submit" class="retry-button">Retry Connection</button>
        </form>

    {{ '{%' }} endif {{ '%}' }}

</body>
</html>
"""

@app.route('/')
def index():
    """Renders the main control page."""
    status = 'connected' if ser and ser.is_open else 'disconnected'
    # Pass the list of pins to the template
    return render_template_string(HTML_TEMPLATE,
                                  serial_status=status,
                                  port=SERIAL_PORT,
                                  pins=PINS_TO_CONTROL)

@app.route('/control', methods=['POST'])
def control_pin():
    """Handles the button clicks to send pin-specific commands."""
    global ser
    if not ser or not ser.is_open:
        if not init_serial(): # Try to reconnect if disconnected
             flash("Serial port is not connected. Cannot send command.", "error")
             return redirect(url_for('index'))
        else:
             flash("Reconnected to serial port.", "message")


    # Get the pin number from the button that was clicked
    pin_str = request.form.get('pin')

    # Validate the input
    try:
        pin_num = int(pin_str)
        if pin_num not in PINS_TO_CONTROL:
            raise ValueError("Invalid pin number")
    except (TypeError, ValueError):
         flash(f"Invalid pin value received: {pin_str}", "error")
         return redirect(url_for('index'))

    # Construct the command string (e.g., "h6") and add newline for Arduino's serialEvent
    command_str = f"h{pin_num}\n"
    # Encode the command to bytes for sending over serial
    command_bytes = command_str.encode('ascii') # Use 'ascii' or 'utf-8'

    try:
        ser.write(command_bytes)
        # Optional: Short delay might sometimes help if commands are sent too rapidly,
        # but usually the Arduino side handles it.
        # time.sleep(0.05)

        # Optional: Read response from Arduino if you implemented one
        # try:
        #     response = ser.readline().decode('ascii').strip()
        #     print(f"Arduino response: {response}")
        #     if response:
        #          flash(f"Arduino: {response}", "message")
        # except serial.SerialTimeoutException:
        #      print("No response from Arduino within timeout.")
        # except Exception as read_e:
        #      print(f"Error reading Arduino response: {read_e}")

        message = f"Sent command '{command_str.strip()}' to trigger Pin {pin_num}"
        flash(message, "message")
        print(message)

    except serial.SerialException as e:
        flash(f"Serial communication error: {e}", "error")
        print(f"Serial communication error during write: {e}")
        # Attempt to close the faulty connection
        try:
            ser.close()
        except:
            pass
        ser = None # Mark as disconnected
        # Redirect back to index, which will show the disconnected state
        return redirect(url_for('index'))
    except Exception as e:
        flash(f"An unexpected error occurred sending command: {e}", "error")
        print(f"An unexpected error occurred sending command: {e}")

    return redirect(url_for('index'))

@app.route('/retry_serial', methods=['POST'])
def retry_serial_connection():
    """Attempts to re-initialize the serial connection via button press."""
    print("Attempting to reconnect via button...")
    if init_serial():
        flash("Serial connection successful!", "message")
    else:
        flash(f"Failed to connect to serial port {SERIAL_PORT or 'Not Set'}.", "error")
    return redirect(url_for('index'))


# Graceful shutdown
def close_serial_on_exit():
    if ser and ser.is_open:
        try:
            print("Closing serial port...")
            # Maybe send a command to ensure all pins are off? Depends on Arduino code.
            # Example: ser.write(b'off_all\n')
            # time.sleep(0.1)
            ser.close()
            print("Serial port closed.")
        except Exception as e:
            print(f"Error closing serial port on exit: {e}")

atexit.register(close_serial_on_exit)


if __name__ == '__main__':
    print("--- Starting Flask App ---")
    if SERIAL_PORT:
        print(f"Target Serial Port: {SERIAL_PORT}")
    else:
         print("Warning: SERIAL_PORT not set. Connection attempts will fail until set or detected.")
    print(f"Controllable Pins: {PINS_TO_CONTROL}")
    print(f"Flask server running on http://0.0.0.0:5000")
    print("Access the control page in your browser.")
    # Make accessible on your local network, use 127.0.0.1 for local only
    # debug=True is helpful for development, but turn off for production
    app.run(host='0.0.0.0', port=5000, debug=True)