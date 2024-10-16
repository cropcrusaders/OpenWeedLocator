#!/usr/bin/env python
from utils.button_inputs import BasicController
from utils.image_sampler import ImageRecorder
from utils.blur_algorithms import fft_blur
from utils.greenonbrown import GreenOnBrown
from utils.relay_control import RelayController, StatusIndicator
from utils.frame_reader import FrameReader
from utils.canbus import MultiNodeCanBusController

from multiprocessing import Value, Process
from configparser import ConfigParser
from pathlib import Path
from datetime import datetime
from imutils.video import FPS
from utils.video import VideoStream
from time import strftime

import argparse
import imutils
import time
import sys
import cv2
import os


def nothing(x):
    pass


class Owl:
    def __init__(self, show_display=False,
                 focus=False,
                 input_file_or_directory=None,
                 config_file='config/DAY_SENSITIVITY_2.ini'):

        # start by reading the config file
        self._config_path = Path(__file__).parent / config_file
        self.config = ConfigParser()
        self.config.read(self._config_path)

        # is the source a directory/file
        self.input_file_or_directory = input_file_or_directory

        # visualise the detections with video feed
        self.show_display = show_display

        # WARNING: option disable detection for data collection
        self.disable_detection = False

        # initialise controller buttons and async management
        self.enable_controller = self.config.getboolean('Controller', 'enable_controller')
        self.switch_purpose = self.config.get('Controller', 'switch_purpose')
        self.switch_pin = self.config.getint('Controller', 'switch_pin')

        if self.enable_controller:
            # Shared values for controller states
            self.detection_state = Value('b', False)
            self.sample_state = Value('b', False)
            self.stop_flag = Value('b', False)
            # Initialize the controller
            self.basic_controller = BasicController(detection_state=self.detection_state,
                                                    sample_state=self.sample_state,
                                                    stop_flag=self.stop_flag,
                                                    switch_board_pin=f'BOARD{self.switch_pin}',
                                                    switch_purpose=self.switch_purpose)

            # Start the controller in a separate process
            self.basic_controller_process = Process(target=self.basic_controller.run)
            self.basic_controller_process.start()

        self.relay_vis = None

        # If focus is enabled, force display to show the output
        self.focus = focus
        if self.focus:
            self.show_display = True

        # Camera resolution and exposure compensation
        self.resolution = (self.config.getint('Camera', 'resolution_width'),
                           self.config.getint('Camera', 'resolution_height'))
        self.exp_compensation = self.config.getint('Camera', 'exp_compensation')

        # Threshold parameters for different algorithms
        self.exgMin = self.config.getint('GreenOnBrown', 'exgMin')
        self.exgMax = self.config.getint('GreenOnBrown', 'exgMax')
        self.hueMin = self.config.getint('GreenOnBrown', 'hueMin')
        self.hueMax = self.config.getint('GreenOnBrown', 'hueMax')
        self.saturationMin = self.config.getint('GreenOnBrown', 'saturationMin')
        self.saturationMax = self.config.getint('GreenOnBrown', 'saturationMax')
        self.brightnessMin = self.config.getint('GreenOnBrown', 'brightnessMin')
        self.brightnessMax = self.config.getint('GreenOnBrown', 'brightnessMax')

        self.threshold_dict = {}
        # Time spent on each image when looping over a directory
        self.image_loop_time = self.config.getint('Visualisation', 'image_loop_time')

        # Setup the track bars if show_display is True
        if self.show_display:
            # Create trackbars for the threshold calculation
            self.window_name = "Adjust Detection Thresholds"
            cv2.namedWindow("Adjust Detection Thresholds", cv2.WINDOW_AUTOSIZE)
            cv2.createTrackbar("ExG-Min", self.window_name, self.exgMin, 255, nothing)
            cv2.createTrackbar("ExG-Max", self.window_name, self.exgMax, 255, nothing)
            cv2.createTrackbar("Hue-Min", self.window_name, self.hueMin, 179, nothing)
            cv2.createTrackbar("Hue-Max", self.window_name, self.hueMax, 179, nothing)
            cv2.createTrackbar("Sat-Min", self.window_name, self.saturationMin, 255, nothing)
            cv2.createTrackbar("Sat-Max", self.window_name, self.saturationMax, 255, nothing)
            cv2.createTrackbar("Bright-Min", self.window_name, self.brightnessMin, 255, nothing)
            cv2.createTrackbar("Bright-Max", self.window_name, self.brightnessMax, 255, nothing)

        # Relay Dict maps the reference relay number to a boardpin on the embedded device
        self.relay_dict = {}

        # Use the [Relays] section to build the dictionary
        for key, value in self.config['Relays'].items():
            self.relay_dict[int(key)] = int(value)

        # Instantiate the relay controller - successful start should beep the buzzer
        self.relay_controller = RelayController(relay_dict=self.relay_dict)

        # Instantiate the logger
        self.logger = self.relay_controller.logger

        # Check that the resolution is not too high to avoid performance issues
        total_pixels = self.resolution[0] * self.resolution[1]
        if total_pixels > (832 * 640):
            # Adjust resolution if it's too high
            self.resolution = (416, 320)
            self.logger.log_line(f"[WARNING] Resolution {self.config.getint('Camera', 'resolution_width')}, "
                                 f"{self.config.getint('Camera', 'resolution_height')} selected is dangerously high. ",
                                 verbose=True)

        # Determine if the source is a directory/file
        if self.input_file_or_directory is None or len(self.input_file_or_directory) == 0:
            self.input_file_or_directory = self.config.get('System', 'input_file_or_directory', fallback=None)

        if len(self.config.get('System', 'input_file_or_directory', fallback='')) > 0 and input_file_or_directory is not None:
            print('[WARNING] two paths to image/videos provided. Defaulting to the command line flag.')

        if self.input_file_or_directory:
            # Use FrameReader if input is a directory or file
            self.cam = FrameReader(path=self.input_file_or_directory,
                                   resolution=self.resolution,
                                   loop_time=self.image_loop_time)
            self.frame_width, self.frame_height = self.cam.resolution

            self.logger.log_line(f'[INFO] Using {self.cam.input_type} from {self.input_file_or_directory}...', verbose=True)

        # If no video, start the camera with the provided parameters
        else:
            try:
                self.cam = VideoStream(resolution=self.resolution,
                                       exp_compensation=self.exp_compensation)
                self.cam.start()

                self.frame_width = self.cam.frame_width
                self.frame_height = self.cam.frame_height

            except ModuleNotFoundError as e:
                missing_module = str(e).split("'")[-2]
                error_message = f"Missing required module: {missing_module}. Please install it and try again."
                raise ModuleNotFoundError(error_message) from None

            except Exception as e:
                error_detail = f"[CRITICAL ERROR] Stopped OWL at start: {e}"
                self.logger.log_line(error_detail, verbose=True)
                if self.config.getboolean('System', 'enable_audible_errors', fallback=True):
                    self.relay_controller.relay.beep(duration=1, repeats=1)
                time.sleep(2)
                sys.exit(1)

        time.sleep(1.0)

        ### Data collection only ###
        self.sample_images = self.config.getboolean('DataCollection', 'sample_images', fallback=False)

        if self.sample_images:
            # Setup data collection parameters
            self.sample_method = self.config.get('DataCollection', 'sample_method', fallback='whole')
            self.disable_detection = self.config.getboolean('DataCollection', 'disable_detection', fallback=False)
            self.sample_frequency = self.config.getint('DataCollection', 'sample_frequency', fallback=60)
            self.enable_device_save = self.config.getboolean('DataCollection', 'enable_device_save', fallback=True)
            self.save_directory = self.config.get('DataCollection', 'save_directory', fallback='data')
            self.camera_name = self.config.get('DataCollection', 'camera_name', fallback='camera')

            # Initialize indicators and image recorder
            self.indicators = StatusIndicator(save_directory=self.save_directory)
            self.save_subdirectory = self.indicators.setup_directories(enable_device_save=self.enable_device_save)
            self.indicators.start_storage_indicator()

            self.image_recorder = ImageRecorder(save_directory=self.save_subdirectory, mode=self.sample_method)

        ############################

        # Sensitivity and weed size to be added in the future
        self.sensitivity = None
        self.lane_coords = {}

        # Set the total number of relays being controlled
        self.relay_num = self.config.getint('System', 'relay_num', fallback=4)

        # Activation region limit - once weed crosses this line, relay is activated
        self.yAct = int(0.01 * self.frame_height)
        self.lane_width = self.frame_width / self.relay_num

        # Calculate lane coordinates for relay activation
        for i in range(self.relay_num):
            laneX = int(i * self.lane_width)
            self.lane_coords[i] = laneX

        # Set up CAN bus integration
        self.enable_can_bus = self.config.getboolean('CANBus', 'enable_can_bus', fallback=False)
        if self.enable_can_bus:
            self.can_bus_controller = MultiNodeCanBusController(controller_id=1, 
                                                                can_interface=self.config.get('CANBus', 'can_interface', fallback='can0'),
                                                                bitrate=self.config.getint('CANBus', 'bitrate', fallback=500000))
            self.can_bus_controller.start()

            # Load available configuration files
            self.available_configs = [f'config/config_{i}.ini' for i in range(1, 21)]

            # Start receiving CAN messages to handle configuration changes
            self.can_bus_controller.can_bus.receive_messages(callback=self.handle_can_message)

    def handle_can_message(self, message):
        # Handle CAN message to change configuration
        try:
            config_index = int(message.data[0])
            self.change_config(config_index)
        except (ValueError, IndexError) as e:
            self.logger.log_line(f"[ERROR] Failed to change configuration from CAN message: {e}", verbose=True)

    def change_config(self, config_index):
        # Change the configuration file
        if 1 <= config_index <= 20:
            new_config_file = self.available_configs[config_index - 1]
            self._config_path = Path(__file__).parent / new_config_file
            self.config.read(self._config_path)
            self.logger.log_line(f"[INFO] Configuration changed to {new_config_file}", verbose=True)
        else:
            self.logger.log_line(f"[ERROR] Invalid configuration index: {config_index}. Must be between 1 and 20.", verbose=True)

    def hoot(self):
        # Read algorithm and logging preferences from the config
        algorithm = self.config.get('System', 'algorithm', fallback='gob')
        log_fps = self.config.getboolean('DataCollection', 'log_fps', fallback=False)
        if self.enable_controller:
            # Update detection and sampling state from the controller
            self.disable_detection = not self.detection_state.value
            self.sample_images = self.sample_state.value

        # Track FPS and frame count
        frame_count = 0

        if log_fps:
            fps = FPS().start()

        try:
            # Initialize the appropriate weed detection algorithm
            if algorithm == 'gog':
                from utils.greenongreen import GreenOnGreen
                model_path = self.config.get('GreenOnGreen', 'model_path', fallback='models/gog_model.tflite')
                confidence = self.config.getfloat('GreenOnGreen', 'confidence', fallback=0.5)

                weed_detector = GreenOnGreen(model_path=model_path)

            else:
                # Parameters for GreenOnBrown algorithm
                min_detection_area = self.config.getint('GreenOnBrown', 'min_detection_area', fallback=500)
                invert_hue = self.config.getboolean('GreenOnBrown', 'invert_hue', fallback=False)

                weed_detector = GreenOnBrown(algorithm=algorithm)

        except (ModuleNotFoundError, IndexError, FileNotFoundError, ValueError) as e:
            self._handle_exceptions(e, algorithm)

        except Exception as e:
            self.logger.log_line(
                f"\n[ALGORITHM ERROR] Unrecognised error while starting algorithm: {algorithm}.\nError message: {e}", verbose=True)
            self.stop()

        if self.show_display:
            # Setup relay visualization if display is enabled
            self.relay_vis = self.relay_controller.relay_vis
            self.relay_vis.setup()
            self.relay_controller.vis = True

        try:
            actuation_duration = self.config.getfloat('System', 'actuation_duration', fallback=0.5)
            delay = self.config.getfloat('System', 'delay', fallback=0.1)

            while True:
                if self.enable_controller:
                    # Update detection and sampling state from the controller
                    self.disable_detection = not self.detection_state.value
                    self.sample_images = self.sample_state.value

                # Read the next frame from the camera or video
                frame = self.cam.read()

                if self.focus:
                    # Convert to grayscale and calculate blurriness if focus is enabled
                    grey = cv2.cvtColor(frame.copy(), cv2.COLOR_BGR2GRAY)
                    blurriness = fft_blur(grey, size=30)

                if frame is None:
                    # Stop if no frame is returned
                    if log_fps:
                        fps.stop()
                        print(f"[INFO] Stopped. Approximate FPS: {fps.fps():.2f}")
                        self.stop()
                        break
                    else:
                        print("[INFO] Frame is None. Stopped.")
                        self.stop()
                        break

                # Retrieve the trackbar positions for thresholds
                if self.show_display:
                    self.exgMin = cv2.getTrackbarPos("ExG-Min", self.window_name)
                    self.exgMax = cv2.getTrackbarPos("ExG-Max", self.window_name)
                    self.hueMin = cv2.getTrackbarPos("Hue-Min", self.window_name)
                    self.hueMax = cv2.getTrackbarPos("Hue-Max", self.window_name)
                    self.saturationMin = cv2.getTrackbarPos("Sat-Min", self.window_name)
                    self.saturationMax = cv2.getTrackbarPos("Sat-Max", self.window_name)
                    self.brightnessMin = cv2.getTrackbarPos("Bright-Min", self.window_name)
                    self.brightnessMax = cv2.getTrackbarPos("Bright-Max", self.window_name)

                else:
                    # Update threshold values if display is not enabled
                    self.update(exgMin=self.exgMin, exgMax=self.exgMax)

                # Perform weed detection if detection is enabled
                if not self.disable_detection:
                    if algorithm == 'gog':
                        cnts, boxes, weed_centres, image_out = weed_detector.inference(frame,
                                                                                       confidence=confidence,
                                                                                       filter_id=63)
                    else:
                        cnts, boxes, weed_centres, image_out = weed_detector.inference(frame,
                                                                                       exgMin=self.exgMin,
                                                                                       exgMax=self.exgMax,
                                                                                       hueMin=self.hueMin,
                                                                                       hueMax=self.hueMax,
                                                                                       saturationMin=self.saturationMin,
                                                                                       saturationMax=self.saturationMax,
                                                                                       brightnessMin=self.brightnessMin,
                                                                                       brightnessMax=self.brightnessMax,
                                                                                       show_display=self.show_display,
                                                                                       algorithm=algorithm,
                                                                                       min_detection_area=min_detection_area,
                                                                                       invert_hue=invert_hue,
                                                                                       label='WEED')

                    # Precompute the integer lane coordinates for reuse
                    lane_coords_int = {k: int(v) for k, v in self.lane_coords.items()}

                    if len(weed_centres) > 0 and self.enable_controller:
                        # Trigger the detection indicator
                        self.basic_controller.weed_detect_indicator()

                    # Loop over the detected weed centres
                    for centre in weed_centres:
                        if centre[1] > self.yAct:
                            actuation_time = time.time()
                            centre_x = centre[0]

                            # Determine the appropriate lane and activate the corresponding relay
                            for i in range(self.relay_num):
                                lane_start = lane_coords_int[i]
                                lane_end = lane_start + self.lane_width

                                if lane_start <= centre_x < lane_end:
                                    self.relay_controller.receive(relay=i, delay=delay,
                                                                  time_stamp=actuation_time,
                                                                  duration=actuation_duration)

                ##### IMAGE SAMPLER #####
                # Record sample images if required
                if self.sample_images:
                    # Record every sample_frequency frames
                    if frame_count % self.sample_frequency == 0:
                        self.indicators.image_write_indicator()

                        if self.sample_method == 'whole':
                            self.image_recorder.add_frame(frame=frame, frame_id=frame_count, boxes=None, centres=None)

                        elif self.sample_method != 'whole' and not self.disable_detection:
                            self.image_recorder.add_frame(frame=frame, frame_id=frame_count, boxes=boxes,
                                                          centres=weed_centres)
                        else:
                            self.image_recorder.add_frame(frame=frame, frame_id=frame_count, boxes=None, centres=None)

                    if self.indicators.DRIVE_FULL:
                        # Stop sampling if storage is full
                        self.sample_images = False
                        self.image_recorder.stop()

                frame_count = frame_count + 1 if frame_count < 900 else 1

                if log_fps and frame_count % 900 == 0:
                    fps.stop()
                    self.logger.log_line(f"[INFO] Approximate FPS: {fps.fps():.2f}", verbose=True)
                    fps = FPS().start()

                # Update the framerate counter
                if log_fps:
                    fps.update()

                # Display the output if enabled
                if self.show_display:
                    if self.disable_detection:
                        image_out = frame.copy()

                    cv2.putText(image_out, f'OWL-gorithm: {algorithm}', (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.75,
                                (80, 80, 255), 1)
                    cv2.putText(image_out, f'Press "S" to save {algorithm} thresholds to file.',
                                (20, int(image_out.shape[1] * 0.72)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (80, 80, 255), 1)
                    if self.focus:
                        cv2.putText(image_out, f'Blurriness: {blurriness:.2f}', (20, 70), cv2.FONT_HERSHEY_SIMPLEX, 1,
                                    (80, 80, 255), 1)

                    cv2.imshow("Detection Output", imutils.resize(image_out, width=600))

                k = cv2.waitKey(1) & 0xFF
                if k == ord('s'):
                    self.save_parameters()
                    self.logger.log_line("[INFO] Parameters saved.", verbose=True)

                if k == 27:
                    if log_fps:
                        fps.stop()
                        self.logger.log_line(f"[INFO] Approximate FPS: {fps.fps():.2f}", verbose=True)
                    if self.show_display:
                        self.relay_controller.relay_vis.close()

                    self.logger.log_line("[INFO] Stopped.", verbose=True)
                    self.stop()
                    break

        except KeyboardInterrupt:
            # Handle keyboard interrupt gracefully
            if log_fps:
                fps.stop()
                self.logger.log_line(f"[INFO] Approximate FPS: {fps.fps():.2f}", verbose=True)
            if self.show_display:
                self.relay_controller.relay_vis.close()
            self.logger.log_line("[INFO] Stopped.", verbose=True)
            self.stop()

        except Exception as e:
            # Handle other exceptions
            self.logger.log_line(f"[CRITICAL ERROR] STOPPED: {e}", verbose=True)
            self.stop()

    def stop(self):
        # Stop all relay actions and clean up resources
        self.relay_controller.running = False
        self.relay_controller.relay.all_off()
        if self.config.getboolean('System', 'enable_audible_errors', fallback=True):
            self.relay_controller.relay.beep(duration=0.1)
            self.relay_controller.relay.beep(duration=0.1)

        self.cam.stop()

        if self.enable_controller:
            self.basic_controller.stop()
            self.basic_controller_process.join()

        if self.sample_images:
            self.indicators.stop()
            self.image_recorder.stop()

        if self.show_display:
            cv2.destroyAllWindows()

        if self.enable_can_bus:
            self.can_bus_controller.stop()

        sys.exit()

    def update(self, exgMin=30, exgMax=180):
        # Update the ExG threshold values
        self.exgMin = exgMin
        self.exgMax = exgMax

    def update_delay(self, delay=0):
        # Update delay value (could be linked to GPS speed in the future)
        return delay

    def save_parameters(self):
        # Save current parameters to a new configuration file with a timestamp
        timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        new_config_filename = f"{timestamp}_{self._config_path.name}"
        new_config_path = self._config_path.parent / new_config_filename

        # Update the 'GreenOnBrown' section with current attribute values
        if 'GreenOnBrown' not in self.config.sections():
            self.config.add_section('GreenOnBrown')

        self.config.set('GreenOnBrown', 'exgMin', str(self.exgMin))
        self.config.set('GreenOnBrown', 'exgMax', str(self.exgMax))
        self.config.set('GreenOnBrown', 'hueMin', str(self.hueMin))
        self.config.set('GreenOnBrown', 'hueMax', str(self.hueMax))
        self.config.set('GreenOnBrown', 'saturationMin', str(self.saturationMin))
        self.config.set('GreenOnBrown', 'saturationMax', str(self.saturationMax))
        self.config.set('GreenOnBrown', 'brightnessMin', str(self.brightnessMin))
        self.config.set('GreenOnBrown', 'brightnessMax', str(self.brightnessMax))

        # Write the updated configuration to the new file with a timestamped filename
        with open(new_config_path, 'w') as configfile:
            self.config.write(configfile)

        print(f"[INFO] Configuration saved to {new_config_path}")

    def _handle_exceptions(self, e, algorithm):
        # Handle exceptions cleanly and log error details
        error_type = type(e).__name__
        error_message = str(e)

        if isinstance(e, ModuleNotFoundError):
            detailed_message = f"\nIs pycoral correctly installed? Visit: https://coral.ai/docs/accelerator/get-started/#requirements"

        elif isinstance(e, (IndexError, FileNotFoundError)):
            detailed_message = "\nAre there model files in the 'models' directory?"

        elif isinstance(e, ValueError) and 'delegate' in error_message:
            detailed_message = (
                "\nThis is due to an unrecognised Google Coral device. Please make sure it is connected correctly.\n"
                "If the error persists, try unplugging it and plugging it again or restarting the\n"
                "Raspberry Pi. For more information visit:\nhttps://github.com/tensorflow/tensorflow/issues/32743")

        else:
            detailed_message = ""

        full_message = f"\n[{error_type}] while starting algorithm: {algorithm}.\nError message: {error_message}{detailed_message}"

        self.logger.log_line(full_message, verbose=True)
        if self.config.getboolean('System', 'enable_audible_errors', fallback=True):
            self.relay_controller.relay.beep(duration=0.25, repeats=4)
        sys.exit()


# Entry point of the script
if __name__ == "__main__":
    # Command line arguments for changing settings
    ap = argparse.ArgumentParser()
    ap.add_argument('--show-display', action='store_true', default=False, help='show display windows')
    ap.add_argument('--focus', action='store_true', default=False, help='add FFT blur to output frame')
    ap.add_argument('--input', type=str, default=None, help='path to image directory, single image or video file')
    ap.add_argument('--config-index', type=int, default=None, help='index of configuration file to use (1-20)')

    args = ap.parse_args()

    # Initialize the Owl instance with the provided arguments
    owl = Owl(config_file='config/DAY_SENSITIVITY_2.ini',
              show_display=args.show_display,
              focus=args.focus,
              input_file_or_directory=args.input)

    # Change configuration if specified
    if args.config_index is not None:
        owl.change_config(args.config_index)

    # Start the detection process
    owl.hoot()
