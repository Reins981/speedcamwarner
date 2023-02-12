# A simple speedcam warner based on OpenStreetMap (OSM)

This App is designed to run on Android. iOS is not supported.

**Preconditions:**
- Internet
- GPS

## Build process using a devkit environment

Are you tired of setting up your own devkit environment in order to build
android apps?
If so then this is the right place for you.
I have provided a devkit environment as Docker image to build your own android projects. 
No more struggles to set up the dependencies that go along with it. The devkit contains all the tools and libraries you need.

### Steps

1) Install docker
2) Clone the speedwarner master branch into your local working directory
```
git clone git@github.com:Reins981/speedcamwarner.git .
```
3) Run the script "run_docker.sh" with the following options:

```
# Start a devkit container with name "speedwarner" and build your app in debug mode
# NOTE: If no name is provided, the default devkit container name is "devkit_container"
./run_docker.sh --name speedwarner -m ".:/home/docker/speedwarner" -c "buildozer -v android debug"


# Start a devkit container with name "speedwarner" and build your app in release mode
./run_docker.sh --name speedwarner -m ".:/home/docker/speedwarner" -c "buildozer -v android release"

# Cleanup your android build directories
./run_docker.sh -c "android clean"

# Stop and remove the devkit container with name "speedwarner"
./run_docker.sh --rm --name speedwarner
```

If the build was successfull, **the APK image will be
automatically available in your host machine under $PWD/bin**


## Build process on Google Colab:

On Google Colab most of the libraries needed are already installed.
Just execute the below commands to install the buildozer relevant libraries.
Upload your sources and then run the build.

```
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
```

Build in debug or release mode:
```
!buildozer -v android debug
!buildozer android clean
```






