# A simple speedcam warner based on OpenStreetMap OSM. 
This App is designed to run on Android. 
Preconditions:
- Internet
- GPS

# Build process on Google Colab:

!pip install buildozer
!pip install cython==0.29.19
!sudo apt-get install -y \
    python3-pip \
    build-essential \
    git \
    python3 \
    python3-dev \
    ffmpeg \
    libsdl2-dev \
    libsdl2-image-dev \
    libsdl2-mixer-dev \
    libsdl2-ttf-dev \
    libportmidi-dev \
    libswscale-dev \
    libavformat-dev \
    libavcodec-dev \
    zlib1g-dev
!sudo apt-get install -y \
    libgstreamer1.0 \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good
!sudo apt-get install build-essential libsqlite3-dev sqlite3 bzip2 libbz2-dev
!sudo apt-get install libffi-dev
!buildozer -v android debug
!buildozer android clean






