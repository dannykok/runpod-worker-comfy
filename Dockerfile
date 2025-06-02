FROM nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04

# Prevents prompts from packages asking for user input during installation
ENV DEBIAN_FRONTEND=noninteractive
# Prefer binary wheels over source distributions for faster pip installations
ENV PIP_PREFER_BINARY=1
# Ensures output from python is printed immediately to the terminal without buffering
ENV PYTHONUNBUFFERED=1 

# Install Python, git and other necessary tools, then clean up
RUN apt-get update && apt-get install -y \
  python3.10 \
  python3-pip \
  git \
  wget \
  libgl1-mesa-glx \
  libglib2.0-0 && \
  apt-get autoremove -y && apt-get clean -y && \
  rm -rf /var/lib/apt/lists/*

WORKDIR /comfyui

# Clone ComfyUI repository and custom nodes in a single run to reduce layers
RUN git clone https://github.com/teamalpha-ai/ComfyUI.git /comfyui && \
  git clone https://github.com/cubiq/ComfyUI_essentials custom_nodes/ComfyUI_essentials --recursive && \
  git clone https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite custom_nodes/ComfyUI-VideoHelperSuite --recursive && \
  git clone https://github.com/kijai/ComfyUI-KJNodes custom_nodes/ComfyUI-KJNodes --recursive && \
  git clone https://github.com/kijai/ComfyUI-LivePortraitKJ custom_nodes/ComfyUI-LivePortraitKJ --recursive && \
  git clone https://github.com/chrisgoringe/cg-use-everywhere custom_nodes/cg-use-everywhere --recursive && \
  git clone https://github.com/ltdrdata/ComfyUI-Inspire-Pack custom_nodes/ComfyUI-Inspire-Pack --recursive && \
  git clone https://github.com/rgthree/rgthree-comfy custom_nodes/rgthree-comfy --recursive && \
  git clone https://github.com/sipherxyz/comfyui-art-venture custom_nodes/comfyui-art-venture --recursive && \
  git clone https://github.com/ssitu/ComfyUI_UltimateSDUpscale custom_nodes/ComfyUI_UltimateSDUpscale --recursive && \
  git clone https://github.com/pythongosssss/ComfyUI-Custom-Scripts custom_nodes/ComfyUI-Custom-Scripts --recursive && \
  git clone https://github.com/aureagle/comfyui-saveasjpeg custom_nodes/comfyui-saveasjpeg --recursive && \
  git clone https://github.com/PowerHouseMan/ComfyUI-AdvancedLivePortrait custom_nodes/ComfyUI-AdvancedLivePortrait --recursive && \
  git clone https://github.com/chrisgoringe/cg-training-tools custom_nodes/cg-training-tools --recursive && \
  git clone https://github.com/Fannovel16/comfyui_controlnet_aux custom_nodes/comfyui_controlnet_aux && \
  git clone https://github.com/ltdrdata/ComfyUI-Impact-Pack custom_nodes/ComfyUI-Impact-Pack && \
  git clone https://github.com/ltdrdata/ComfyUI-Impact-Subpack custom_nodes/ComfyUI-Impact-Subpack && \
  git clone https://github.com/welltop-cn/ComfyUI-TeaCache custom_nodes/ComfyUI-TeaCache --recursive && \
  git clone https://github.com/huchenlei/ComfyUI-IC-Light-Native custom_nodes/ComfyUI-IC-Light-Native --recursive && \
  git clone https://github.com/chflame163/ComfyUI_LayerStyle_Advance custom_nodes/ComfyUI_LayerStyle_Advance --recursive && \
  git clone https://github.com/sipie800/ComfyUI-PuLID-Flux-Enhanced custom_nodes/ComfyUI-PuLID-Flux-Enhanced --recursive && \
  git clone https://github.com/WASasquatch/was-node-suite-comfyui custom_nodes/was-node-suite-comfyui --recursive && \
  git clone https://github.com/yolain/ComfyUI-Easy-Use custom_nodes/ComfyUI-Easy-Use --recursive && \
  git clone https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes custom_nodes/ComfyUI_Comfyroll_CustomNodes --recursive && \
  git clone https://github.com/city96/ComfyUI-GGUF custom_nodes/ComfyUI-GGUF --recursive

# Install dependencies
RUN for req in custom_nodes/*/requirements.txt; do \
  if [ -f "$req" ]; then \
  pip3 install --no-cache-dir -r "$req"; \
  fi; \
  done && \
  pip3 install --upgrade --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121 && \
  pip3 install --upgrade -r requirements.txt

# removing the original models folder, preparing for the network volume linking
RUN rm -rf models

# Support for the network volume
# ADD src/extra_model_paths.yaml ./
WORKDIR /

COPY requirements.txt .
RUN pip3 install -r requirements.txt

# temporary fix numpy version
RUN pip3 install numpy==2.1.3

# COPY src files
COPY src src
COPY start.sh .
COPY test_input.json .
RUN chmod +x /start.sh

# Start the container
WORKDIR /
CMD ["sh", "-c", "./start.sh"]
