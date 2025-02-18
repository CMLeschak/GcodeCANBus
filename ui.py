import os
import tkinter as tk
from tkinter import ttk, filedialog
import time
import can
import serial.tools.list_ports
from convert import process_tap_files
from send import parse_can_message, adjust_speeds_within_packet, can_send_messages
from ttkthemes import ThemedStyle
import threading

# Global variables
selected_port = None
connected = False
bus = None
message_fields = [""] * 6  # Initialize message_fields
current_field_index = 0
selected_axis = {"01": True, "02": False, "03": False, "04": False, "05": False, "06": False}

def toggle_axis(axis_id):
    selected_axis[axis_id] = not selected_axis[axis_id]
    update_message(f"Axis {axis_id} {'enabled' if selected_axis[axis_id] else 'disabled'}")

def create_gcode_tap_file():
    default_content = "F100\nG90 X 0.00 Y 0.00 Z 0.00 A 0.00 B 0.00 C 0.00"
    if not os.path.exists("./gcode.tap"):
        with open("gcode.tap", "w") as file:
            file.write(default_content)
    return default_content

def create_canbus_txt_file():
    if not os.path.exists("./canbus.txt"):
        with open("canbus.txt", "w") as file:
            pass  # Create an empty file

def read_gcode_tap_values():
    with open("gcode.tap", "r") as file:
        content = file.read()
    values = content.split()
    return {
        "X": values[3],
        "Y": values[5],
        "Z": values[7],
        "A": values[9],
        "B": values[11],
        "C": values[13]
    }
    
# def update_target_entry_boxes(values):
#     for label, value in values.items():
#         r_field = r_field_widgets[label.lower()]
#         r_field.config(state=tk.NORMAL)
#         r_field.delete('1.0', tk.END)
#         r_field.insert(tk.END, value)
#         # r_field.config(state=tk.DISABLED)
def update_target_entry_boxes(values):
    for label, value in values.items():
        r_field = r_field_widgets[label.lower()]
        r_field.config(state=tk.NORMAL)
        r_field.delete(0, tk.END)
        r_field.insert(0, value)
        # r_field.config(state=tk.DISABLED)  # Uncomment this if you want to disable editing
        
# Function to refresh available ports
def refresh_ports():
    ports = [port.device for port in serial.tools.list_ports.comports()]
    port_combobox['values'] = ports
    port_combobox.current(0)  # Select the first port by default

# Function to connect to a selected port
def connect():
    global selected_port, connected, bus
    port = port_combobox.get()

    if not port:
        update_message("Please select a port.")
        return

    try:
        bus = can.interface.Bus(interface="slcan", channel=port, bitrate=500000)
        connected = True
        selected_port = port
        connect_button.config(style='Green.TButton')  # Change button style to green upon successful connection
        update_message(f"Connected to port {port}.")
    except Exception as e:
        update_message(f"Error connecting: {str(e)}")

# Function to disconnect from the currently selected port
def disconnect():
    global connected, bus
    if connected:
        try:
            bus.shutdown()
            connected = False
            update_message(f"Disconnected from port {selected_port}.")
        except Exception as e:
            update_message(f"Error disconnecting: {str(e)}")
    else:
        update_message("Not connected to any port.")

# Function to send messages in a separate thread
def send_in_thread():
    global selected_port, connected, bus, current_field_index, message_fields
    global selected_axis
    index = 0
    
    if not connected:
        update_message("Not connected to any port.")
        return

    filename = send_file_entry.get()
    if not filename:
        update_message("Please select a file to send.")
        return

    try:
        with open(filename, "r") as file:
            for line in file:
                sent_message = line.strip()
                # print(f"axis: {sent_message[:2]}")  # Print the first two characters of the sent_message[:2]
                if selected_axis[sent_message[:2]]:
                    update_message(f"Sent: {sent_message}")
                    index = int(sent_message[:2])  # Convert the first two characters to an integer and store it in index variablesent_message[:2]
                    # Parse the message and send it
                    message = parse_can_message(sent_message)
                    can_send_messages(bus, [message])

                    # Extract 11th to 16th characters and convert from hex to decimal
                    hex_values = sent_message[10:16]
                    decimal_value = int(hex_values, 16) / 100  # Divide by 100
                    decimal_value_formatted = "{:.2f}".format(decimal_value)  # Format to two decimal places

                    # Append the decimal value to the current field 
                    message_fields[current_field_index] += f"{decimal_value_formatted}\n"
                    current_field_index = (current_field_index + 1) % 6
                    # current_field_index = int(sent_message[:2])
                    # message_fields[int(sent_message[:2])] += f"{decimal_value_formatted}\n"
                    # current_field_index = (current_field_index + 1) % 6

                    time.sleep(0.1)  # Sleep for a short duration to separate messages
                    
                    field = field_widgets[field_labels[index-1].lower()]
                    field.config(state=tk.NORMAL, height=1)  # Set height to 1 line
                    field.delete('1.0', tk.END)
                    field.insert(tk.END, decimal_value_formatted)
                    field.config(state=tk.DISABLED)
                    # Update the GUI to immediately show the changes
                    root.update_idletasks()
                    # # Display messages in each field immediately
                    # for i, field_content in enumerate(message_fields, start=1):
                    #     field = field_widgets[field_labels[i-1].lower()]
                    #     field.config(state=tk.NORMAL, height=1)  # Set height to 1 line
                    #     field.delete('1.0', tk.END)
                    #     field.insert(tk.END, field_content)
                    #     field.config(state=tk.DISABLED)
                    #     # Update the GUI to immediately show the changes
                    #     root.update_idletasks()

        update_message("All messages sent successfully.")
    except Exception as e:
        update_message(f"Error sending messages: {str(e)}")

# Function to initiate sending messages
def send():
    threading.Thread(target=send_in_thread).start()

# Function to clear messages
def clear_messages():
    messages_text.config(state=tk.NORMAL)
    messages_text.delete('1.0', tk.END)
    messages_text.config(state=tk.DISABLED)

# Function to stop
def stop():
    # Placeholder for stopping logic
    pass

# Function to convert
def convert():
    input_filename = convert_file_entry.get()
    if not input_filename:
        update_message("Please select a file to convert.")
        return

    output_filename = os.path.splitext("canbus")[0] + ".txt"
    try:
        process_tap_files()
        update_message(f"File converted successfully: {output_filename}")
    except Exception as e:
        update_message(f"Error converting file: {str(e)}")

# Function to handle file selection for conversion
def browse_convert_file():
    filename = filedialog.askopenfilename(filetypes=[("G-code files", "*.tap")])
    convert_file_entry.delete(0, tk.END)
    convert_file_entry.insert(0, filename)

# Function to handle file selection for sending
def browse_send_file():
    filename = filedialog.askopenfilename(filetypes=[("Text files", "*.txt")])
    send_file_entry.delete(0, tk.END)
    send_file_entry.insert(0, filename)

# Function to update messages
def update_message(message):
    messages_text.config(state=tk.NORMAL)
    messages_text.insert(tk.END, message + "\n")
    messages_text.config(state=tk.DISABLED)

def update_tap_file(axis, new_value):
    tap_file_path = "gcode.tap"  # Update this with the correct path to your .tap file
    try:
        with open(tap_file_path, "r") as file:
            content = file.read()
        
        # Find the position of the axis in the string
        axis_pos = content.find(f"{axis.upper()} ")
        if axis_pos != -1:
            end_pos = content.find(" ", axis_pos + 2)
            if end_pos == -1:
                end_pos = len(content)
            
            # Replace the value
            new_content = f"{content[:axis_pos + 2]}{new_value:.2f}{content[end_pos:]}"
            
            # Write the updated content back to the file
            with open(tap_file_path, "w") as file:
                file.write(new_content)
            
            update_message(f"Updated {axis.upper()} value to {new_value:.2f} in {tap_file_path}")
            convert()
        else:
            update_message(f"Axis {axis.upper()} not found in the .tap file")
    except Exception as e:
        update_message(f"Error updating .tap file: {str(e)}")
    
# def on_enter_pressed(event, axis):
#     value = event.widget.get("1.0", "end-1c").strip()
#     if value:
#         try:
#             new_value = float(value)
#             update_tap_file(axis, new_value)
#         except ValueError:
#             update_message(f"Invalid input for {axis.upper()}. Please enter a number.")
#     # event.widget.delete("1.0", "end")
def on_enter_pressed(event, axis):
    value = event.widget.get().strip()
    if value:
        try:
            new_value = float(value)
            update_tap_file(axis, new_value)
        except ValueError:
            update_message(f"Invalid input for {axis.upper()}. Please enter a number.")
    # event.widget.delete(0, tk.END)  # Uncomment this if you want to clear the entry after pressing Enter

# GUI setup
root = tk.Tk()
root.title("Arctos CAN controller")

# Create files if they don't exist
create_gcode_tap_file()
create_canbus_txt_file()
# Read initial values from gcode.tap
initial_values = read_gcode_tap_values()

# Create a themed style object
style = ThemedStyle(root)
style.set_theme("breeze")  # Set the theme to 'arc'

# Refresh button
refresh_button = ttk.Button(root, text="Refresh Ports", command=refresh_ports)
refresh_button.grid(row=0, column=0, padx=5, pady=5, sticky="ew")

# Port selection dropdown
port_combobox = ttk.Combobox(root, width=25)
port_combobox.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

# Connect button
connect_button = ttk.Button(root, text="Connect", command=connect, style='Green.TButton')
connect_button.grid(row=0, column=2, padx=5, pady=5, sticky="ew")

# Disconnect button
disconnect_button = ttk.Button(root, text="Disconnect", command=disconnect)
disconnect_button.grid(row=0, column=3, padx=5, pady=5, sticky="ew")

# Send button (widest)
send_button = ttk.Button(root, text="Send", command=send, width=15)
send_button.grid(row=1, column=0, columnspan=2, padx=5, pady=5, sticky="ew")

# Convert button
convert_button = ttk.Button(root, text="Convert", command=convert)
convert_button.grid(row=1, column=2, padx=5, pady=5, sticky="ew")

# Stop button
stop_button = ttk.Button(root, text="Stop", command=stop)
stop_button.grid(row=1, column=3, padx=5, pady=5, sticky="ew")

# File selection for conversion
convert_file_label = ttk.Label(root, text="Select File to Convert:")
convert_file_label.grid(row=2, column=0, padx=5, pady=5, sticky="e")

convert_file_entry = ttk.Entry(root, width=30)
convert_file_entry.grid(row=2, column=1, padx=5, pady=5, sticky="ew")
convert_file_entry.insert(0, r"./gcode.tap")

convert_browse_button = ttk.Button(root, text="Browse", command=browse_convert_file)
convert_browse_button.grid(row=2, column=2, padx=5, pady=5, sticky="ew")

# File selection for sending
send_file_label = ttk.Label(root, text="Select File to Send:")
send_file_label.grid(row=3, column=0, padx=5, pady=5, sticky="e")

send_file_entry = ttk.Entry(root, width=30)
send_file_entry.grid(row=3, column=1, padx=5, pady=5, sticky="ew")
send_file_entry.insert(0, r"./canbus.txt")

send_browse_button = ttk.Button(root, text="Browse", command=browse_send_file)
send_browse_button.grid(row=3, column=2, padx=5, pady=5, sticky="ew")

# Clear messages button (aligned with message display)
clear_button = ttk.Button(root, text="Clear Messages", command=clear_messages)
clear_button.grid(row=4, column=3, padx=5, pady=5, sticky="ew")

# Messages display
messages_label = ttk.Label(root, text="Messages:")
messages_label.grid(row=4, column=0, columnspan=3, padx=5, pady=(10, 0), sticky="w")

messages_text = tk.Text(root, height=8, width=50, state=tk.DISABLED)
messages_text.grid(row=5, column=0, columnspan=4, padx=5, pady=(0, 10), sticky="ew")

# Modify the labels for message fields
field_labels = ['X', 'Y', 'Z', 'A', 'B', 'C']

# Messages display fields
field_widgets = {}  # Dictionary to store references to text widgets
r_field_widgets = {}

for i in range(6):
    # Create a frame for each label and text widget pair
    frame = ttk.Frame(root)
    frame.grid(row=i+6, column=0, columnspan=2, padx=5, pady=5, sticky="ew")
    r_frame = ttk.Frame(root)
    r_frame.grid(row=i+6, column=2, columnspan=2, padx=5, pady=5, sticky="ew")

    field_label = ttk.Label(frame, text=f"{field_labels[i]}:")
    field_label.grid(row=0, column=0, padx=5, pady=5, sticky="e")
    r_field_label = ttk.Label(r_frame, text=f"Target {field_labels[i]}:")
    r_field_label.grid(row=0, column=3, padx=5, pady=5, sticky="e")

    field = tk.Text(frame, height=1, width=30, state=tk.DISABLED)
    field.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

    r_field = ttk.Entry(r_frame, width=30)#, state=tk.ENABLED)
    r_field.grid(row=0, column=4, padx=5, pady=5, sticky="ew")
    r_field.bind("<Return>", lambda event, axis=field_labels[i].lower(): on_enter_pressed(event, axis))

    # Store reference to the text widget in the dictionary
    field_widgets[field_labels[i].lower()] = field
    r_field_widgets[field_labels[i].lower()] = r_field
    
# Create a frame for checkboxes
checkbox_frame = ttk.Frame(root)
checkbox_frame.grid(row=12, column=0, columnspan=4, padx=5, pady=5, sticky="ew")

# Create "Enable Axis" label
enable_axis_label = ttk.Label(checkbox_frame, text="Enable Axis:")
enable_axis_label.grid(row=0, column=0, padx=5, pady=5, sticky="w")

# Create checkboxes for each axis
checkbox_vars = {}
for i, label in enumerate(field_labels):
    axis_id = f"{i+1:02d}"  # Convert to two-digit string
    var = tk.BooleanVar(value=selected_axis[axis_id])
    checkbox_vars[axis_id] = var
    checkbox = ttk.Checkbutton(
        checkbox_frame, 
        text=label, 
        variable=var, 
        command=lambda id=axis_id: toggle_axis(id)
    )
    checkbox.grid(row=0, column=i+1, padx=5, pady=5)

# Update target entry boxes with initial values
update_target_entry_boxes(initial_values)

root.mainloop()

