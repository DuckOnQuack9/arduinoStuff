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
# This list is now less directly used for buttons, but good for reference
CONTROLLABLE_PINS_INFO = {
    'light_on': {'pin': 2, 'cmd': 'h2'},
    'light_dim': {'pin': 2, 'cmd': 'h2dim'},
    'fan_high': {'pin': 3, 'cmd': 'h3'},
    'fan_off': {'pin': 4, 'cmd': 'h4'},
    'fan_medium': {'pin': 5, 'cmd': 'h5'},
    'fan_low': {'pin': 6, 'cmd': 'h6'}
}

# --- Map user-friendly actions to Arduino commands ---
COMMAND_MAP = {
    "light_on": "h2\n",
    "light_dim": "h2dim\n",
    "fan_high": "h3\n",
    "fan_medium": "h5\n",
    "fan_low": "h6\n",
    "fan_off": "h4\n",
}

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
        print("Waiting for Arduino to initialize...")
        time.sleep(2.5) # Give Arduino time to reset (adjust if needed)
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

# --- Updated HTML Template ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Arduino Device Control</title>
    <style>
    {% raw %} {# Standard Jinja tag for raw block #}
        body { font-family: sans-serif; text-align: center; margin-top: 30px; background-color: #f4f4f4; }
        h1 { margin-bottom: 20px; color: #333; }
        p { color: #555; }
        .control-section {
            background-color: #fff;
            padding: 20px;
            margin: 20px auto;
            border-radius: 8px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            max-width: 500px;
        }
        .control-section h2 {
            margin-top: 0;
            margin-bottom: 15px;
            color: #444;
            border-bottom: 1px solid #eee;
            padding-bottom: 10px;
        }
        .button {
            padding: 10px 20px;
            font-size: 16px;
            cursor: pointer;
            margin: 5px;
            border: none;
            border-radius: 5px;
            color: white;
            min-width: 120px; /* Uniform button width */
            transition: background-color 0.2s ease;
        }
        .light-button { background-color: #ffc107; color: #333; } /* Yellow for light */
        .light-button:hover { background-color: #e0a800; }
        .fan-button { background-color: #17a2b8; } /* Cyan for fan */
        .fan-button:hover { background-color: #138496; }
        .off-button { background-color: #dc3545; } /* Red for off */
        .off-button:hover { background-color: #c82333; }

        .status { margin-top: 25px; font-style: italic; color: #666; }
        .error { color: red; font-weight: bold; background-color: #ffe0e0; padding: 10px; border-radius: 5px; display: inline-block; margin-bottom:15px; }
        .message { color: blue; font-weight: bold; background-color: #e0e0ff; padding: 10px; border-radius: 5px; display: inline-block; margin-bottom:15px; }
        ul { list-style: none; padding: 0; }
        li { margin-bottom: 5px; text-align: left; margin-left: 30px;}
        .retry-button {
            padding: 8px 15px; background-color: #28a745; color: white; /* Green for retry */
            border: none; border-radius: 4px; cursor: pointer; margin-top: 10px;
        }
         .retry-button:hover { background-color: #218838; }
    {% endraw %} {# End raw block #}
    </style>
</head>
<body>
    <h1>Arduino Device Control</h1>

    <!-- Flash Messages -->
    {% with messages = get_flashed_messages(with_categories=true) %}
      {% if messages %}
        <div style="margin-bottom: 20px;">
          {% for category, message in messages %}
            <p class="{{ category }}">{{ message }}</p> {# Jinja processed #}
          {% endfor %}
        </div>
      {% endif %}
    {% endwith %}


    {% if serial_status == 'connected' %}
        <form method="POST" action="/control">
            <div class="control-section">
                <h2>Light Control</h2>
                <button class="button light-button" type="submit" name="action" value="light_on">
                    Light ON
                </button>
                <button class="button light-button" type="submit" name="action" value="light_dim">
                    Light DIM
                </button>
            </div>

            <div class="control-section">
                <h2>Fan Control</h2>
                <button class="button fan-button" type="submit" name="action" value="fan_high">
                    Fan HIGH
                </button>
                 <button class="button fan-button" type="submit" name="action" value="fan_medium">
                    Fan MEDIUM
                </button>
                 <button class="button fan-button" type="submit" name="action" value="fan_low">
                    Fan LOW
                </button>
                <button class="button off-button" type="submit" name="action" value="fan_off">
                    Fan OFF
                </button>
            </div>
        </form>
        <p class="status">Serial Port: {{ port }} | Status: Connected</p> {# Jinja processed #}

    {% else %}
         <div class="control-section">
             <p class="error">Error: Cannot connect to Arduino{{ ' on ' + port if port else '' }}.</p> {# Jinja processed #}
             <p>Please check:</p>
             <ul>
                 <li>Is the Arduino plugged in and running the correct sketch?</li>
                 <li>Is the correct SERIAL_PORT ('{{ port or 'Not Set' }}') detected/set in the script?</li> {# Jinja processed #}
                 <li>Does the user running this script have permission for the serial port? (e.g., `sudo usermod -a -G dialout $USER` on Linux)</li>
                 <li>Is the Arduino IDE's Serial Monitor or another program using the port closed?</li>
             </ul>
             <form method="POST" action="/retry_serial">
                  <button type="submit" class="retry-button">Retry Connection</button>
             </form>
         </div>

    {% endif %}

</body>
</html>
"""

@app.route('/')
def index():
    """Renders the main control page."""
    status = 'connected' if ser and ser.is_open else 'disconnected'
    # No longer need to pass pins list for button generation
    return render_template_string(HTML_TEMPLATE,
                                  serial_status=status,
                                  port=SERIAL_PORT)

@app.route('/control', methods=['POST'])
def control_device(): # Renamed function for clarity
    """Handles the button clicks to send device-specific commands."""
    global ser
    if not ser or not ser.is_open:
        if not init_serial(): # Try to reconnect if disconnected
             flash("Serial port is not connected. Cannot send command.", "error")
             return redirect(url_for('index'))
        else:
             flash("Reconnected to serial port.", "message")


    # Get the action identifier from the button that was clicked
    action_id = request.form.get('action')

    # Validate the action and get the corresponding command string
    if action_id in COMMAND_MAP:
        command_str_with_newline = COMMAND_MAP[action_id]
        command_str_no_newline = command_str_with_newline.strip() # For display/logging
        # Encode the command to bytes for sending over serial
        command_bytes = command_str_with_newline.encode('ascii') # Use 'ascii' or 'utf-8'
    else:
         flash(f"Invalid action received: {action_id}", "error")
         print(f"Error: Invalid action ID received from form: {action_id}")
         return redirect(url_for('index'))

    # --- Send the command ---
    try:
        ser.write(command_bytes)
        # Optional: Short delay might sometimes help
        # time.sleep(0.05)

        # Optional: Read response from Arduino if implemented
        # try:
        #     response = ser.readline().decode('ascii').strip() # Adjust timeout/decode as needed
        #     print(f"Arduino response: {response}")
        #     if response:
        #          flash(f"Arduino: {response}", "message")
        # except serial.SerialTimeoutException:
        #      print("No response from Arduino within timeout.")
        # except Exception as read_e:
        #      print(f"Error reading Arduino response: {read_e}")

        # Generate user-friendly action description
        action_desc = action_id.replace('_', ' ').title()
        message = f"Sent command '{command_str_no_newline}' to perform action: {action_desc}"
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
        return redirect(url_for('index')) # Redirect to index to show disconnected state
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
            # Optional: Send a command to turn everything off on exit?
            # if "fan_off" in COMMAND_MAP:
            #     try:
            #         ser.write(COMMAND_MAP["fan_off"].encode('ascii'))
            #         time.sleep(0.1) # Give it a moment
            #     except Exception as send_e:
            #         print(f"Could not send final off command: {send_e}")
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
         print("Warning: SERIAL_PORT not set. Connection attempts may fail.")
    print(f"Action to Command Mapping: {COMMAND_MAP}")
    print(f"Flask server running on http://0.0.0.0:5000")
    print("Access the control page in your browser.")
    # Make accessible on your local network, use 127.0.0.1 for local only
    # debug=True is helpful for development (auto-reloads), but turn off for production
    app.run(host='0.0.0.0', port=5000, debug=False)