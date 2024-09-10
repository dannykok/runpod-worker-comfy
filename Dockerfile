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
# ADD src/extra_model_paths.yaml ./

# Go back to the root
WORKDIR /

# Add the start and the handler
ADD src/start.sh src/rp_handler.py test_input.json ./
RUN chmod +x /start.sh

WORKDIR /comfyui

# clone custom nodes
RUN git clone https://github.com/cubiq/ComfyUI_essentials custom_nodes/ComfyUI_essentials --recursive
RUN if [ -f custom_nodes/ComfyUI_essentials/requirements.txt ]; then pip3 install -r custom_nodes/ComfyUI_essentials/requirements.txt; fi

RUN git clone https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite custom_nodes/ComfyUI-VideoHelperSuite --recursive
RUN if [ -f custom_nodes/ComfyUI-VideoHelperSuite/requirements.txt ]; then pip3 install -r custom_nodes/ComfyUI-VideoHelperSuite/requirements.txt; fi

RUN git clone https://github.com/kijai/ComfyUI-KJNodes custom_nodes/ComfyUI-KJNodes --recursive
RUN if [ -f custom_nodes/ComfyUI-KJNodes/requirements.txt ]; then pip3 install -r custom_nodes/ComfyUI-KJNodes/requirements.txt; fi

RUN git clone https://github.com/kijai/ComfyUI-LivePortraitKJ custom_nodes/ComfyUI-LivePortraitKJ --recursive
RUN if [ -f custom_nodes/ComfyUI-LivePortraitKJ/requirements.txt ]; then pip3 install -r custom_nodes/ComfyUI-LivePortraitKJ/requirements.txt; fi

RUN git clone https://github.com/chrisgoringe/cg-use-everywhere custom_nodes/cg-use-everywhere --recursive
RUN if [ -f custom_nodes/cg-use-everywhere/requirements.txt ]; then pip3 install -r custom_nodes/cg-use-everywhere/requirements.txt; fi

RUN git clone https://github.com/Gourieff/comfyui-reactor-node custom_nodes/comfyui-reactor-node --recursive
RUN if [ -f custom_nodes/comfyui-reactor-node/requirements.txt ]; then pip3 install -r custom_nodes/comfyui-reactor-node/requirements.txt; fi

RUN git clone https://github.com/ltdrdata/ComfyUI-Inspire-Pack custom_nodes/ComfyUI-Inspire-Pack --recursive
RUN if [ -f custom_nodes/ComfyUI-Inspire-Pack/requirements.txt ]; then pip3 install -r custom_nodes/ComfyUI-Inspire-Pack/requirements.txt; fi

# RUN git clone https://github.com/yolain/ComfyUI-Easy-Use custom_nodes/ComfyUI-Easy-Use --recursive
# RUN if [ -f custom_nodes/ComfyUI-Easy-Use/requirements.txt ]; then pip3 install -r custom_nodes/ComfyUI-Easy-Use/requirements.txt; fi

RUN git clone https://github.com/rgthree/rgthree-comfy custom_nodes/rgthree-comfy --recursive
RUN if [ -f custom_nodes/rgthree-comfy/requirements.txt ]; then pip3 install -r custom_nodes/rgthree-comfy/requirements.txt; fi

RUN git clone https://github.com/sipherxyz/comfyui-art-venture custom_nodes/comfyui-art-venture --recursive
RUN if [ -f custom_nodes/comfyui-art-venture/requirements.txt ]; then pip3 install -r custom_nodes/comfyui-art-venture/requirements.txt; fi

RUN git clone https://github.com/ssitu/ComfyUI_UltimateSDUpscale custom_nodes/ComfyUI_UltimateSDUpscale --recursive
RUN if [ -f custom_nodes/ComfyUI_UltimateSDUpscale/requirements.txt ]; then pip3 install -r custom_nodes/ComfyUI_UltimateSDUpscale/requirements.txt; fi

RUN git clone https://github.com/pythongosssss/ComfyUI-Custom-Scripts custom_nodes/ComfyUI-Custom-Scripts --recursive
RUN if [ -f custom_nodes/ComfyUI-Custom-Scripts/requirements.txt ]; then pip3 install -r custom_nodes/ComfyUI-Custom-Scripts/requirements.txt; fi

RUN git clone https://github.com/aureagle/comfyui-saveasjpeg custom_nodes/comfyui-saveasjpeg --recursive
RUN if [ -f custom_nodes/comfyui-saveasjpeg/requirements.txt ]; then pip3 install -r custom_nodes/comfyui-saveasjpeg/requirements.txt; fi

RUN git clone https://github.com/PowerHouseMan/ComfyUI-AdvancedLivePortrait custom_nodes/ComfyUI-AdvancedLivePortrait --recursive
RUN if [ -f custom_nodes/ComfyUI-AdvancedLivePortrait/requirements.txt ]; then pip3 install -r custom_nodes/ComfyUI-AdvancedLivePortrait/requirements.txt; fi

# WORKDIR /comfyui

# removing the original models folder, preparing for the network volume linking
RUN rm -rf models

# Start the container
CMD /start.sh