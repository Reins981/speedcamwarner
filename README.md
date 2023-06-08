# A simple speedcam warner based on OpenStreetMap (OSM)

This App is designed to run on Android. iOS is not supported.
The sources also include a ready to go buildozer.spec file for the arm64-v8a platform.
This can be adapted to your needs.

**Tested on android architecture:**
- arm64-v8a

**Preconditions:**
- Internet
- GPS

## Build process using a devkit environment

Are you tired of setting up your own devkit environment in order to build
android apps?
If so then this is the right place for you.
I have provided a devkit environment as Docker image to build your own android projects. 
No more struggles to set up the dependencies that go along with it. The devkit contains all the tools and libraries you need.

The devkit image is available under (https://hub.docker.com/repository/docker/reko8680/android/general)

You can also pull it from the repository

```
docker pull reko8680/android:devkit1
```

### Steps

1) Install docker and git
2) Clone the speedwarner master branch into your local working directory
```
git clone git@github.com:Reins981/speedcamwarner.git .
```
3) Run the script "run_docker.sh" with the following options:

```
# Start a devkit container with name "speedwarner" and build your app in debug mode
# Mount the project sources and the buildozer.spec file using the -m option, Syntax: "SOURCE_PATH:DESTINATION_PATH"
# NOTE: If no name is provided, the default devkit container name is "devkit_container"
./run_docker.sh --name speedwarner -m "$PWD:/home/docker/speedwarner" -c "buildozer -v android debug"


# Start a devkit container with name "speedwarner" and build your app in release mode
./run_docker.sh --name speedwarner -m "$PWD:/home/docker/speedwarner" -c "buildozer -v android release"

# Cleanup your android build directories
./run_docker.sh --name speedwarner -m "$PWD:/home/docker/speedwarner" -c "buildozer android clean"

# Stop and remove the devkit container with name "speedwarner"
./run_docker.sh -rm --name speedwarner
```

If the build was successfull, **the APK image will be
automatically available on your host machine in the $SOURCE_PATH/bin directory.**


## Build process on Google Colab:

On Google Colab most of the libraries needed are already installed.
Just execute the below commands to install buildozer relevant libraries.
Upload your sources and then run the build.

```
!pip install --upgrade buildozer
!pip install cython==0.29.33
!sudo apt-get update
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






