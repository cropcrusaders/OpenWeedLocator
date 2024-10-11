#!/usr/bin/env python
from hailo_platform import create_hef, configure_net_group
from hailo_sdk_client import Client
from pathlib import Path
import cv2
import numpy as np


class GreenOnGreen:
    def __init__(self, model_path='models', label_file='models/labels.txt', inference_size=(640, 640)):
        # Set default model path if none provided
        if model_path is None:
            print('[WARNING] No model directory or path provided with --model-path flag. '
                  'Attempting to load from default...')
            model_path = 'models'
        self.model_path = Path(model_path)

        # If the model path is a directory, try to find a .hef file
        if self.model_path.is_dir():
            model_files = list(self.model_path.glob('*.hef'))
            if not model_files:
                raise FileNotFoundError('No .hef model files found. Please provide a directory or .hef file.')
            else:
                # Allow user to select the appropriate model if multiple models are found
                if len(model_files) > 1:
                    print('[INFO] Multiple models found:')
                    for idx, model_file in enumerate(model_files):
                        print(f'{idx + 1}: {model_file.name}')
                    selected_idx = int(input('Enter the number of the model you want to use: ')) - 1
                    self.model_path = model_files[selected_idx]
                else:
                    self.model_path = model_files[0]
                print(f'[INFO] Using {self.model_path.stem} model...')

        # If the model path is a .hef file, use it
        elif self.model_path.suffix == '.hef':
            print(f'[INFO] Using {self.model_path.stem} model...')

        # If the model path is unsupported, try to use the default
        else:
            print(f'[WARNING] Specified model path {model_path} is unsupported, attempting to use default...')

            model_files = Path('models').glob('*.hef')
            try:
                self.model_path = next(model_files)
                print(f'[INFO] Using {self.model_path.stem} model...')

            except StopIteration:
                raise FileNotFoundError('[ERROR] No model files found.')

        # Read labels from the label file
        self.labels = self.read_label_file(label_file)
        # Create Hailo client and configure the network group
        self.client = Client()
        self.hef = create_hef(self.model_path.as_posix())
        self.net_group = self.client.configure(self.hef)
        # Set the inference input size
        self.inference_size = inference_size
        self.objects = None
        self.weed_centers = []
        self.boxes = []

    def read_label_file(self, label_file):
        # Read the labels from the given label file
        labels = {}
        with open(label_file, 'r') as f:
            for line in f.readlines():
                pair = line.strip().split(maxsplit=1)
                labels[int(pair[0])] = pair[1].strip() if len(pair) > 1 else pair[0]
        return labels

    def inference(self, image, confidence=0.5, filter_id=0):
        # Convert the input image to RGB
        cv2_im_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        # Maintain aspect ratio by adding padding to resize to inference size
        h, w, _ = cv2_im_rgb.shape
        scale = min(self.inference_size[0] / w, self.inference_size[1] / h)
        new_w, new_h = int(w * scale), int(h * scale)
        resized_image = cv2.resize(cv2_im_rgb, (new_w, new_h))
        padded_image = np.full((self.inference_size[1], self.inference_size[0], 3), 128, dtype=np.uint8)
        padded_image[(self.inference_size[1] - new_h) // 2:(self.inference_size[1] - new_h) // 2 + new_h,
                     (self.inference_size[0] - new_w) // 2:(self.inference_size[0] - new_w) // 2 + new_w] = resized_image
        # Prepare input data for inference
        input_data = padded_image.tobytes()
        # Run inference on the input data
        output = self.client.infer(self.net_group, input_data)
        # Parse the output to get detected objects
        self.objects = self.parse_output(output, confidence)
        self.filter_id = filter_id

        # Filter detected objects by ID before further processing
        filtered_objects = [obj for obj in self.objects if obj['id'] == self.filter_id]

        # Get the original image dimensions
        height, width, _ = image.shape
        # Calculate scaling factors to map bounding boxes back to the original image size
        scale_x, scale_y = width / new_w, height / new_h
        self.weed_centers.clear()
        self.boxes.clear()

        # Iterate over filtered objects
        for det_object in filtered_objects:
            # Scale the bounding box coordinates to the original image size
            bbox = det_object['bbox']
            startX = int((bbox['xmin'] - (self.inference_size[0] - new_w) // 2) * scale_x / scale)
            startY = int((bbox['ymin'] - (self.inference_size[1] - new_h) // 2) * scale_y / scale)
            endX = int((bbox['xmax'] - (self.inference_size[0] - new_w) // 2) * scale_x / scale)
            endY = int((bbox['ymax'] - (self.inference_size[1] - new_h) // 2) * scale_y / scale)
            boxW = endX - startX
            boxH = endY - startY

            # Save the bounding box
            self.boxes.append([startX, startY, boxW, boxH])
            # Compute the center of the bounding box
            centerX = int(startX + (boxW / 2))
            centerY = int(startY + (boxH / 2))
            self.weed_centers.append([centerX, centerY])

            # Draw the bounding box and label on the image
            percent = int(100 * det_object['score'])
            label = f'{percent}% {self.labels.get(det_object["id"], det_object["id"])}'
            cv2.rectangle(image, (startX, startY), (endX, endY), (0, 0, 255), 2)
            cv2.putText(image, label, (startX, startY + 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 0, 0), 2)
        return None, self.boxes, self.weed_centers, image

    def parse_output(self, output, confidence):
        # Filter detected objects based on confidence threshold
        objects = []
        for detection in output:
            if detection['score'] >= confidence:
                objects.append(detection)
        return objects
