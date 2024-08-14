FROM nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04

# Prevents prompts from packages asking for user input during installation
ENV DEBIAN_FRONTEND=noninteractive
# Prefer binary wheels over source distributions for faster pip installations
ENV PIP_PREFER_BINARY=1
# Ensures output from python is printed immediately to the terminal without buffering
ENV PYTHONUNBUFFERED=1 

# Install Python, git and other necessary tools
RUN apt-get update && apt-get install -y \
  python3.10 \
  python3-pip \
  git \
  wget \
  libgl1-mesa-glx \
  libglib2.0-0

# Clean up to reduce image size
RUN apt-get autoremove -y && apt-get clean -y && rm -rf /var/lib/apt/lists/*

# Clone ComfyUI repository
RUN git clone https://github.com/comfyanonymous/ComfyUI.git /comfyui

# Change working directory to ComfyUI
WORKDIR /comfyui

# Install ComfyUI dependencies
RUN pip3 install --upgrade --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121 \
  && pip3 install --upgrade -r requirements.txt

# Install runpod
RUN pip3 install runpod requests requests-toolbelt

# Support for the network volume
ADD src/extra_model_paths.yaml ./

# Go back to the root
WORKDIR /

# Add the start and the handler
ADD src/start.sh src/rp_handler.py test_input.json ./
RUN chmod +x /start.sh

WORKDIR /comfyui

# clone custom nodes
RUN git clone https://github.com/cubiq/ComfyUI_essentials custom_nodes/ComfyUI_essentials
RUN pip3 install -r custom_nodes/ComfyUI_essentials/requirements.txt

RUN git clone https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite custom_nodes/ComfyUI-VideoHelperSuite
RUN pip3 install -r custom_nodes/ComfyUI-VideoHelperSuite/requirements.txt

RUN git clone https://github.com/kijai/ComfyUI-KJNodes custom_nodes/ComfyUI-KJNodes
RUN pip3 install -r custom_nodes/ComfyUI-KJNodes/requirements.txt

RUN git clone https://github.com/kijai/ComfyUI-LivePortraitKJ custom_nodes/ComfyUI-LivePortraitKJ
RUN pip3 install -r custom_nodes/ComfyUI-LivePortraitKJ/requirements.txt

RUN git clone https://github.com/chrisgoringe/cg-use-everywhere custom_nodes/cg-use-everywhere

RUN git clone https://github.com/Gourieff/comfyui-reactor-node custom_nodes/comfyui-reactor-node
# RUN pip3 install -r custom_nodes/comfyui-reactor-node/requirements.txt
WORKDIR /comfyui/custom_nodes/comfyui-reactor-node
RUN python3 install.py

WORKDIR /comfyui

# Start the container
CMD /start.sh