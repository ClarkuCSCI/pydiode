FROM --platform=linux/amd64 python:3.11
MAINTAINER PeStory@clarku.edu

# Add source code
ADD src /root/pydiode/src
ADD pyproject.toml /root/pydiode/pyproject.toml
ADD README.md /root/pydiode/README.md

# Install Python dependencies
RUN pip install pyinstaller

# Install fpm, for generating .deb packages
RUN apt update && apt install -y ruby && gem install fpm

# Install pydiode
WORKDIR /root/pydiode
RUN pip install .
