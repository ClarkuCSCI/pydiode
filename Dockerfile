FROM --platform=linux/amd64 python:3.11-bullseye
MAINTAINER PeStory@clarku.edu

# Add source code
ADD src /root/pydiode/src
ADD pyproject.toml /root/pydiode/pyproject.toml
ADD README.md /root/pydiode/README.md

# Install Python dependencies
RUN pip install pyinstaller

# Install:
# - fpm, for generating .deb packages
# - gpg, for decrypting files
RUN apt update && apt install -y ruby && gem install fpm && apt install -y gpg

# Increase the default height of the file dialogue
RUN sed -i 's/-height 120/-height 500/' /usr/share/tcltk/tk8.6/iconlist.tcl

# Install pydiode
WORKDIR /root/pydiode
RUN pip install .
