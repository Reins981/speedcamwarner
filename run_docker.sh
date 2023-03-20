#!/bin/bash
set -e

DOCKER_IMAGE="reko8680/android:devkit1"

function setup_docker_run_options()
{

    DOCKER_RUN_OPTS=(

        -it # Start pseudo-TTY and interactive bash shell in container
    )

    if [ -n ${VOLUME} ]; then
        DOCKER_RUN_OPTS+=( -v "${VOLUME}" )
    fi
    
    if [ -n ${WORKDIR} ]; then
        DOCKER_RUN_OPTS+=( -w "${WORKDIR}" )
    fi
    DOCKER_RUN_OPTS+=( --name "${CONTAINER_NAME}" )
    DOCKER_RUN_OPTS+=( "${DOCKER_IMAGE}" )

}

function remove_container()
{
    if [ "${CONTAINER_EXISTS}" == 1 ]; then
    
        echo "Removing container ${CONTAINER_NAME}.."
        cmd="docker rm -f ${CONTAINER_NAME}"
        
        echo "eval command: ${cmd}"
        eval "${cmd}"
    else
        echo "Container ${CONTAINER_NAME} already removed"
    fi
}

function run_container()
{
    
    if [ "${CONTAINER_EXISTS}" == 1 ]; then
        
        remove_container
    fi

    echo "Run container ${CONTAINER_NAME} with command \"${COMMAND}\""
    
    if [ -n "${COMMAND}" ]; then
        cmd="docker run ${DOCKER_RUN_OPTS[*]} ${COMMAND}"
    else
        cmd="docker run ${DOCKER_RUN_OPTS[*]}"
    fi
    
    echo "eval command: ${cmd}"
    eval "${cmd}"
}

function check_container_status()
{
    CONTAINER_RUNS=0
    CONTAINER_EXISTS=0
    if docker ps -a | grep ${CONTAINER_NAME} > /dev/null; then
        echo "Docker container ${CONTAINER_NAME} already exists"
        CONTAINER_EXISTS=1
        
        if docker ps -a --filter status=running | grep ${CONTAINER_NAME} > /dev/null; then
            CONTAINER_RUNS=1
        fi
    fi
}

function cleanup()
{
	CLEANUP_PATH=${VOLUME%:*}/.buildozer
	echo "Removing ${CLEANUP_PATH}"
	rm -rf $CLEANUP_PATH
}


function usage()
{
    echo -e "\nScript for running the android devkit container:"
    echo -e "USAGE: $0 [OPTIONS][COMMAND][ARG..]\n"
    echo -e "   -h  | --help                Print usage" 
    echo -e "   -n  | --name                Container Name" 
    echo -e "   -rm | --remove_container    Remove the Container" 
    echo -e "   -c  | --command             Command to be executed in container" 
    echo -e "   -m | --mount                Mount a volume in the container"
    echo -e "\nRun a command in a new container with -c option. If no command defined terminal is started and waits for user input."
    echo -e "Example call: $0 -c \"ping 127.0.0.1 && echo test\""
    echo -e "\nMount a directory of the host filesystem in the container with the -m option. The directory must contain all your source files and the buildozer.spec file"
    echo -e "Example call: $0 -m \"/home/user/test_app:/workdir/test_app\"" 
}

REMOVE_CONTAINER=0
CONTAINER_NAME="devkit_container"
VOLUME=${PWD}:${PWD}
WORKDIR=${VOLUME##*:}
COMMAND=""

for ((i=1;i<=${#@}; i++)); do
    i_next=$((i+1))
    case ${!i} in 
        -h|--help)
            usage
            exit 0
            ;;
        -n|--name)
            CONTAINER_NAME=${!i_next}
            echo "Set the container name to \"${CONTAINER_NAME}\""
            ;;
        -rm|--remove_container)
            REMOVE_CONTAINER=1
            echo "Stop and remove the container with name \"${CONTAINER_NAME}\""
            ;;
        -m|--mount)
            VOLUME=${!i_next}
            echo "Mount the volume \"${VOLUME}\" in the container with name \"${CONTAINER_NAME}\""
            WORKDIR=${VOLUME##*:}
            ;;
        -c|--command)
            COMMAND=${!i_next}
            echo "Run the command \"${COMMAND}\" in the container with name \"${CONTAINER_NAME}\""
            ;;
        
    esac
done

echo "------ Show all docker containers --------"
docker ps -a
echo "------------------------------------------"

cleanup
setup_docker_run_options
check_container_status

if [ "${REMOVE_CONTAINER}" == 1 ]; then
    remove_container
else
    echo "Workdir in container is: \"$WORKDIR\""
    run_container
fi
exit 0
