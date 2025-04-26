import serial
import serial.tools.list_ports
import time
from flask import Flask, render_template_string, request, redirect, url_for, flash

# --- Configuration ---
# Try to automatically find the Arduino port
# Common Arduino VID/PID pairs (you might need to add yours)
ARDUINO_VIDS_PIDS = [
    (0x2341, 0x0043),  # Arduino Uno R3
    (0x2341, 0x0001),  # Arduino Uno
    (0x2A03, 0x0043),  # Arduino Uno R3 Clone (CH340)
    (0x1A86, 0x7523),  # Common CH340 chip used in clones
    (0x239A, 0x800B)   # Adafruit Feather M0
]

SERIAL_PORT = None
ports = serial.tools.list_ports.comports()
print("Available serial ports:")
for port, desc, hwid in sorted(ports):
    print(f"- {port}: {desc} [{hwid}]")
    # Check VID/PID
    try:
        vid = port.vid
        pid = port.pid
        if (vid, pid) in ARDUINO_VIDS_PIDS:
            SERIAL_PORT = port.device
            print(f"  -> Found potential Arduino on {SERIAL_PORT}")
            break # Use the first one found
    except AttributeError:
        # Some devices might not have vid/pid attributes easily accessible
        # Attempt matching based on description (less reliable)
        if "arduino" in desc.lower() or "ch340" in desc.lower():
             SERIAL_PORT = port.device
             print(f"  -> Found potential Arduino (by desc) on {SERIAL_PORT}")
             break # Use the first one found

if not SERIAL_PORT:
    print("\n---! Arduino Not Found Automatically !---")
    print("Please set the SERIAL_PORT variable manually in the script.")
    # Exit or set a default that will likely fail, prompting user input
    # For example, on Windows: SERIAL_PORT = 'COM3'
    # On Linux: SERIAL_PORT = '/dev/ttyACM0' or '/dev/ttyUSB0'
    # On macOS: SERIAL_PORT = '/dev/cu.usbmodemXXXX' or '/dev/tty.usbmodemXXXX'
    # Example:
    # SERIAL_PORT = '/dev/ttyACM0' # <--- !!! MANUALLY SET THIS IF NEEDED !!!
    exit("Exiting: Serial port not set.")


BAUD_RATE = 9600
# ---------------------

app = Flask(__name__)
app.secret_key = 'your_very_secret_key' # Needed for flashing messages

# Global variable for the serial connection
ser = None

def init_serial():
    """Initializes the serial connection."""
    global ser
    try:
        print(f"Attempting to connect to {SERIAL_PORT} at {BAUD_RATE} baud...")
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        time.sleep(2) # Give Arduino time to reset after connection
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

# Simple HTML template using an f-string
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Arduino LED Control</title>
    <style>
        body {{ font-family: sans-serif; text-align: center; margin-top: 50px; }}
        .button {{
            padding: 15px 30px;
            font-size: 18px;
            cursor: pointer;
            margin: 10px;
            border: none;
            border-radius: 5px;
            color: white;
        }}
        .on-button {{ background-color: #4CAF50; }} /* Green */
        .off-button {{ background-color: #f44336; }} /* Red */
        .status {{ margin-top: 20px; font-style: italic; color: #555; }}
        .error {{ color: red; font-weight: bold; }}
        .message {{ color: blue; font-weight: bold; }}
    </style>
</head>
<body>
    <h1>Arduino LED Control</h1>

    <!-- Flash Messages -->
    {% with messages = get_flashed_messages(with_categories=true) %}
      {% if messages %}
        <div>
          {% for category, message in messages %}
            <p class="{{ category }}">{{ message }}</p>
          {% endfor %}
        </div>
      {% endif %}
    {% endwith %}

    {% if serial_status == 'connected' %}
        <form method="POST" action="/control">
            <button class="button on-button" type="submit" name="action" value="on">Turn LED ON (h)</button>
            <button class="button off-button" type="submit" name="action" value="off">Turn LED OFF (l)</button>
        </form>
        <p class="status">Serial Port: {{ port }} | Status: Connected</p>
    {% else %}
        <p class="error">Error: Cannot connect to Arduino on {{ port }}.</p>
        <p>Please check:</p>
        <ul>
            <li>Is the Arduino plugged in?</li>
            <li>Is the correct SERIAL_PORT ('{{ port }}') set in app.py?</li>
            <li>Does the user running this script have permission for the serial port? (e.g., add to 'dialout' group on Linux)</li>
            <li>Is the Arduino IDE's Serial Monitor closed?</li>
        </ul>
        <form method="POST" action="/retry_serial">
             <button type="submit">Retry Connection</button>
        </form>

    {% endif %}

</body>
</html>
"""

@app.route('/')
def index():
    """Renders the main control page."""
    status = 'connected' if ser and ser.is_open else 'disconnected'
    return render_template_string(HTML_TEMPLATE, serial_status=status, port=SERIAL_PORT or "Not Set")

@app.route('/control', methods=['POST'])
def control_led():
    """Handles the button clicks to send commands."""
    global ser
    if not ser or not ser.is_open:
        flash("Serial port is not connected. Cannot send command.", "error")
        return redirect(url_for('index'))

    action = request.form.get('action')

    if action == 'on':
        command = b'h' # Send 'h' as bytes
        message = "Sent ON command (h)"
    elif action == 'off':
        command = b'l' # Send 'l' as bytes
        message = "Sent OFF command (l)"
    else:
        flash("Invalid action.", "error")
        return redirect(url_for('index'))

    try:
        ser.write(command)
        # Optional: Read response from Arduino if you implemented one
        # response = ser.readline().decode().strip()
        # print(f"Arduino response: {response}")
        flash(message, "message")
        print(message)
    except serial.SerialException as e:
        flash(f"Serial communication error: {e}", "error")
        print(f"Serial communication error: {e}")
        # Optionally try to close and re-open
        try:
            ser.close()
        except:
            pass
        ser = None # Mark as disconnected
    except Exception as e:
        flash(f"An unexpected error occurred: {e}", "error")
        print(f"An unexpected error occurred: {e}")

    return redirect(url_for('index'))

@app.route('/retry_serial', methods=['POST'])
def retry_serial_connection():
    """Attempts to re-initialize the serial connection."""
    if init_serial():
        flash("Serial connection successful!", "message")
    else:
        flash("Failed to connect to serial port.", "error")
    return redirect(url_for('index'))


# Graceful shutdown
import atexit
def close_serial_on_exit():
    if ser and ser.is_open:
        try:
            # Maybe send a final 'off' command before closing?
            # ser.write(b'l')
            # time.sleep(0.1)
            ser.close()
            print("Serial port closed.")
        except Exception as e:
            print(f"Error closing serial port on exit: {e}")

atexit.register(close_serial_on_exit)


if __name__ == '__main__':
    # Make accessible on your local network, use 127.0.0.1 for local only
    app.run(host='0.0.0.0', port=5000, debug=True)