# Adding Green-on-Green to the OWL (Beta)

Welcome to the inaugural iteration of Green-on-Green in-crop weed detection using the OWL (OpenWeedLocator) system. As an early beta version, this implementation is subject to additional troubleshooting and iterative enhancement. The objective of this project is to provide a robust and scalable solution for precision agriculture by employing advanced edge AI technology for weed detection within crop fields. The system has been evaluated on various platforms, including the Raspberry Pi 4, LibreComputer, and Windows desktop environments. While promising, it still necessitates user feedback to identify and resolve potential issues. We encourage early adopters to report anomalies and propose enhancements to foster a more resilient and efficient deployment.

The Green-on-Green detection paradigm is designed for versatility across diverse agricultural settings. Utilizing sophisticated AI algorithms, this system differentiates weeds from crops within a homogeneous field environment, thereby facilitating targeted interventions. The overarching aim is to optimize herbicide utilization, lower operational costs, and ultimately enhance crop yield. The OWL platform serves as an accessible yet powerful tool for farmers seeking to modernize their weed management practices through reduced manual labor and increased automation.

## Stage 1: Hardware/Software - Hailo 8 Installation

To deploy the OpenWeedLocator system effectively with the Hailo 8 AI accelerator, the necessary software components must be installed on the Raspberry Pi. The Hailo 8 is a high-efficiency AI processor tailored for edge computing, making it suitable for executing complex AI models in situ. Begin the setup by executing the `install_hailo.sh` script as per the following instructions. This comprehensive guide will facilitate the correct configuration of your system, thereby preparing it for real-time weed detection with heightened computational efficiency.

### Step 1: Clone the Repository

Ensure that you have cloned the OpenWeedLocator repository and renamed it to `owl`. Navigate to the `models` directory within the repository on the Raspberry Pi, which will serve as the repository for all inference models, including those optimized for Hailo.

```sh
cd ~/owl/models
```

### Step 2: Install Hailo SDK

Proceed by executing the installation script. This script will install the Hailo SDK and other requisite packages needed to utilize the Hailo 8 processor. The SDK comprises essential libraries and utilities for managing the Hailo hardware, compiling models, and conducting inference. For a comprehensive installation guide, consult the official Hailo [documentation](https://hailo.ai/developer-zone/), which provides detailed information on system prerequisites, compatible Raspberry Pi models, and troubleshooting methodologies.

During the installation process, you will be prompted to verify performance settings and connect the Hailo 8 hardware to the appropriate interface. It is imperative to ensure all hardware connections are secure before proceeding, as improper connections can result in installation or operational failures.

```sh
chmod +x install_hailo.sh && ./install_hailo.sh
```

Should errors arise during installation, attempt activating the appropriate virtual environment and manually install the SDK dependencies:

```sh
workon owl
pip install hailo_sdk
```

### Step 3: Validate Installation

The final step in this stage is to validate the installation to ensure that all components have been correctly set up. Open a Python terminal by executing the following command:

```sh
python
```

Next, verify the installation by importing the Hailo SDK. This verification step ensures that the installation was successful and that the necessary libraries are accessible:

```python
import hailo_sdk
```

If no errors are raised, you are prepared to progress to the next phase, which involves executing object detection models using the OWL platform. These models must be appropriately optimized for compatibility with the Hailo platform to ensure efficient real-time inference.

## Stage 2: Model Training/Deployment - Inference with the Hailo 8

Deploying weed recognition models on the Hailo 8 necessitates the generation of model files that are specifically tailored to the Hailo SDK. Such models are engineered to be lightweight and computationally efficient, rendering them ideal for edge applications like the Hailo 8. The Hailo 8 offers substantial computational throughput, enabling real-time inference even under challenging environmental conditions. Note that generic, non-optimized models will significantly underperform or fail entirely; hence, models must be explicitly optimized for Hailo deployment.

The following diagram illustrates the end-to-end workflow for model generation and deployment on Hailo. This workflow includes data collection, training, optimization, and eventual deployment on Hailo hardware, ensuring that models are optimized to achieve high efficiency during edge inference.



### Step 1: Download a Sample Model

To verify whether the installation has been successful, it is advisable to download a pre-compiled model from the [Hailo model repository](https://hailo.ai/models/). This model is configured to execute on Hailo hardware and can be utilized to ascertain whether the OWL setup is functioning as expected. This step is instrumental in isolating any issues related to either the OWL configuration or the Hailo 8 installation.

While still in the `models` directory, execute the following command to download the requisite model:

```sh
wget https://hailo.ai/models/sample_model.hef
```

Once the model is downloaded, navigate back to the `owl` directory and attempt to run `owl.py`, specifying `gog` (Green-on-Green) as the algorithm. If a specific model path is not provided, the system will automatically select the first model in the directory based on alphabetical order, simplifying the testing procedure when experimenting with multiple models.

**Note**: If the testing is performed indoors, the default camera settings may produce an underexposed or entirely black image. In such cases, adjust the camera exposure settings using the following parameters to achieve a properly lit image:

```sh
python owl.py --show-display --algorithm gog --exp-compensation 4 --exp-mode auto
```

If the execution is successful, a video stream should appear, highlighting detected objects (e.g., a 'potted plant') with a red bounding box. To detect alternative categories, modify the `filter_id=63` parameter to reflect a different COCO category. The full list of available COCO dataset categories can be found [here](https://tech.amikelive.com/node-718/what-object-categories-labels-are-in-coco-dataset/). This configurability allows for testing the system across various object types and environmental conditions to validate the versatility of detection capabilities.

Upon confirming the correct functionality of the system, proceed to train and deploy your weed recognition models. Training on custom datasets that reflect the specific weed species prevalent in your agricultural environment will yield a more targeted and effective weed management solution.

## Model Training Options

The following are several approaches for training a model compatible with the Hailo 8. The choice of method will depend on the user's familiarity with machine learning frameworks and the available tools.

### Option 1: Train a Model Using TensorFlow

EdjeElectronics provides a step-by-step guide for generating a TensorFlow model compatible with the Hailo 8. This option is particularly suitable for users with experience using TensorFlow as a training framework:
- [Google Colab Walkthrough](https://colab.research.google.com/github/EdjeElectronics/TensorFlow-Lite-Object-Detection-on-Android-and-Raspberry-Pi/blob/master/Train_TFLite2_Object_Detction_Model.ipynb)
- [Accompanying YouTube Video](https://www.youtube.com/watch?v=XZ7FYAMCc4M&ab_channel=EdjeElectronics)

The [official Hailo Colab tutorial](https://hailo.ai/developer-zone/tutorials/) also offers a detailed guide on training models using custom datasets. This tutorial covers the entire workflow—from environment setup to deployment on the Hailo 8—utilizing Hailo’s optimization tools to ensure models perform optimally on the hardware.

### Option 2: Train a YOLOv5/v8 Model and Export for Hailo

**Note**: This methodology is currently under refinement and may not yield consistent results. However, once stabilized, it is expected to become the preferred solution due to the simplicity and efficacy of training YOLO models. Track ongoing developments on the Ultralytics repository [here](https://github.com/ultralytics/ultralytics/issues/1185).

To train a YOLOv5 model using Weed-AI datasets, refer to the following Colab notebook: [Weed-AI Datasets](https://colab.research.google.com/github/Weed-AI/Weed-AI/blob/master/weed_ai_yolov5.ipynb). After training, export the model for deployment on Hailo using the following commands:

#### YOLOv5

```sh
!python export.py --weights path/to/your/weights/best.pt --include hailo
```

#### YOLOv8

```sh
!yolo export model=path/to/your/weights/best.pt format=hailo
```

For additional details, consult the documentation for [Ultralytics YOLOv5](https://github.com/ultralytics/yolov5) and [Ultralytics YOLOv8](https://github.com/ultralytics/ultralytics). YOLO models are celebrated for their versatility and efficiency, making them well-suited for agricultural applications requiring real-time detection. Once export stability is achieved, YOLO models are likely to become the benchmark for Hailo-based in-crop weed detection.

### Option 3: Train an ONNX YOLO Model for Hailo

Another option for training models compatible with Hailo involves using ONNX (Open Neural Network Exchange) with YOLO models. ONNX is a widely supported format that allows models to be trained in one framework and deployed across different hardware targets, making it an attractive option for edge deployments with the Hailo 8.

To train an ONNX YOLO model, follow these steps:

1. **Train a YOLO Model**
   Train a YOLO model using your preferred method, such as YOLOv5 or YOLOv8. Once the model is trained, export it to the ONNX format. For YOLOv5, execute the following command:

   ```sh
   !python export.py --weights path/to/your/weights/best.pt --include onnx
   ```

   For YOLOv8, use:

   ```sh
   !yolo export model=path/to/your/weights/best.pt format=onnx
   ```

2. **Convert the ONNX Model for Hailo**
   Once you have the ONNX model, use the Hailo Model Zoo tools to convert the ONNX file into a format compatible with Hailo hardware. The Hailo Model Zoo provides scripts that automate the conversion and optimization processes, ensuring the model is efficient for edge inference. Execute the following command to convert the ONNX model:

   ```sh
   hailomodelzoo-convert -i path/to/your/model.onnx -t hailo
   ```

3. **Deploy the Model**
   After conversion, the resulting `.hef` file is ready for deployment on the Hailo 8. Place the `.hef` file in the `models` directory within the OWL repository and execute the OWL script:

   ```sh
   cd ~/owl
   python owl.py --algorithm gog --model path/to/your/model.hef
   ```

The `GreenOnGreen` class in the OWL software will load the ONNX-converted Hailo model when specified with the appropriate parameters. This approach ensures that the trained YOLO models are efficiently executed on the Hailo 8 hardware, leveraging ONNX for portability and ease of use across different systems.

The ONNX format provides the added advantage of being a universal model representation, facilitating interoperability between various machine learning frameworks and hardware accelerators, thus ensuring flexibility in model development and deployment.

As an early-stage implementation, the Green-on-Green feature is continuously evolving. Ongoing work is focused on enhancing stability, computational performance, and usability. User feedback is invaluable for guiding these improvements, and contributions from early testers are highly appreciated.

## References

The following references have been instrumental in the development of this project. These resources provide a deeper understanding of AI model deployment on edge devices such as the Hailo 8 and cover various facets of model training, optimization, and hardware interfacing:

1. [PyImageSearch](https://pyimagesearch.com/2019/05/13/object-detection-and-image-classification-with-google-coral-usb-accelerator/)
2. [Hailo Guides](https://hailo.ai/developer-zone/)
3. [EdjeElectronics - TensorFlow Training](https://github.com/EdjeElectronics/TensorFlow-Lite-Object-Detection-on-Android-and-Raspberry-Pi)
4. [Ultralytics - YOLO Models](https://github.com/ultralytics/yolov5)
5. [Weed-AI - Dataset Repository](https://github.com/Weed-AI/Weed-AI)
6. [ONNX - Open Neural Network Exchange](https://onnx.ai)
