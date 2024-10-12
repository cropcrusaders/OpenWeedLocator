# Custom CAN Bus Messaging System for Raspberry Pi Network

import can
import threading
import time
import logging

from utils.canbus import CanBusController, MultiNodeCanBusController


class CanBusController:
    def __init__(self, can_interface='can0', bitrate=500000):
        self.can_interface = can_interface
        self.bitrate = bitrate
        self.bus = None
        self.running = True
        self.setup_can_bus()

    def setup_can_bus(self):
        try:
            # Set up the CAN bus interface
            self.bus = can.interface.Bus(channel=self.can_interface, bustype='socketcan', bitrate=self.bitrate)
            logging.info(f"CAN Bus setup on interface {self.can_interface} with bitrate {self.bitrate}bps.")
        except OSError as e:
            logging.error(f"Failed to initialize CAN Bus: {e}")

    def send_message(self, arbitration_id, data, retries=3, delay=1.0):
        for attempt in range(retries):
            try:
                # Create and send CAN message
                message = can.Message(arbitration_id=arbitration_id, data=data, is_extended_id=False)
                self.bus.send(message)
                logging.info(f"Message sent with ID: {arbitration_id}, Data: {data}")
                return
            except can.CanError as e:
                logging.error(f"Error sending message (attempt {attempt + 1} of {retries}): {e}")
                time.sleep(delay)
        logging.error(f"Failed to send message with ID: {arbitration_id} after {retries} attempts.")

    def receive_messages(self, callback):
        def receive_loop():
            # Start a loop to receive CAN messages
            while self.running:
                try:
                    message = self.bus.recv(timeout=1.0)
                    if message:
                        logging.info(f"Message received: ID {message.arbitration_id}, Data {message.data}")
                        callback(message)
                except can.CanError as e:
                    logging.error(f"Error receiving message: {e}")

        # Start the receiving loop in a separate thread with proper cleanup handling
        receive_thread = threading.Thread(target=receive_loop)
        receive_thread.start()
        self.receive_thread = receive_thread

    def stop_receiving(self):
        # Gracefully stop the receiving loop
        if hasattr(self, 'receive_thread') and self.receive_thread.is_alive():
            logging.info("Stopping CAN message receiving thread...")
            self.running = False
            self.receive_thread.join()


class MultiNodeCanBusController:
    def __init__(self, controller_id, can_interface='can0', bitrate=500000):
        self.controller_id = controller_id
        self.can_bus = CanBusController(can_interface=can_interface, bitrate=bitrate)
        self.nodes_settings = {}

    def update_node_settings(self, node_id, settings):
        # Update node settings and send to corresponding Raspberry Pi
        self.nodes_settings[node_id] = settings
        arbitration_id = 0x100 + node_id
        data = self.settings_to_can_data(settings)
        self.can_bus.send_message(arbitration_id, data)

    def settings_to_can_data(self, settings):
        # Convert settings dictionary to CAN message data
        data = bytearray()
        for key, value in settings.items():
            key_encoded = key.encode()[:1]  # Use first character of setting as key
            value_encoded = value.to_bytes((value.bit_length() + 7) // 8 or 1, 'big')
            data.extend(len(key_encoded).to_bytes(1, 'big'))  # Add key length
            data.extend(key_encoded)
            data.extend(len(value_encoded).to_bytes(1, 'big'))  # Add value length
            data.extend(value_encoded)
        return data

    def receive_message_callback(self, message):
        # Handle received CAN message and update relevant settings
        node_id = message.arbitration_id - 0x100
        data = message.data
        settings = self.can_data_to_settings(data)
        self.nodes_settings[node_id] = settings
        logging.info(f"Updated settings for node {node_id}: {settings}")

    def can_data_to_settings(self, data):
        # Convert CAN message data to settings dictionary
        settings = {}
        i = 0
        while i < len(data):
            key_length = data[i]
            i += 1
            key = data[i:i + key_length].decode()
            i += key_length
            value_length = data[i]
            i += 1
            value = int.from_bytes(data[i:i + value_length], 'big')
            i += value_length
            settings[key] = value
        return settings

    def start(self):
        # Start receiving messages
        self.can_bus.receive_messages(callback=self.receive_message_callback)

    def stop(self):
        # Stop receiving messages
        self.can_bus.stop_receiving()
