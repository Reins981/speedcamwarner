#!/bin/bash
set -e

DOCKER_IMAGE="reko8680/android:devkit1"

DOCKER_CREATE_OPTS=(

    --it
    -v ${VOLUME}
    -w ${WORKDIR}

)

DOCKER_GENERAL_OPTS=(

    --name ${CONTAINER_NAME}

)

function stop_container()
{
    if [ $CONTAINER_RUNS == 1 ]; then
        echo "Stopping container ${CONTAINER_NAME}.."
        docker stop ${CONTAINER_NAME}
        CONTAINER_RUNS=0
    else
        echo "Container ${CONTAINER_NAME} is already stopped"
    fi
}

function start_container()
{
    if [$CONTAINER_RUNS == 0 ]; then
        echo "Starting container ${CONTAINER_NAME}.."
        docker start -a ${CONTAINER_NAME}
        $CONTAINER_RUNS=1
    else
        echo "Container ${CONTAINER_NAME} is already started"
    fi
}

function remove_container()
{
    if [$CONTAINER_EXISTS == 1 ]; then
    
        if [$CONTAINER_RUNS == 1 ]; then
            stop_container
        fi
        
        echo "Removing container ${CONTAINER_NAME}.."
        docker rm -f ${CONTAINER_NAME}
        $CONTAINER_EXISTS=0
    else
        echo "Container ${CONTAINER_NAME} already removed"
    fi
}

function create_container()
{
    if [$CONTAINER_EXISTS == 1 ]; then
        echo "Container ${CONTAINER_NAME} is already created"
    else
        echo "Creating container ${CONTAINER_NAME}"
        DOCKER_OPTS=${DOCKER_CREATE_OPTS[@]} + ( ${DOCKER_GENERAL_OPTS[@]} )
        docker create ${DOCKER_OPTS} ${CONTAINER_NAME} ${DOCKER_IMAGE}
    fi
}

function exec_container()
{
    
    if [$CONTAINER_EXISTS == 1 ]; then

        if [$CONTAINER_RUNS == 0 ]; then
            echo "Container ${CONTAINER_NAME} is not running"
            start_container
        fi

        echo "Executing ${COMMAND} in container ${CONTAINER_NAME}"
        if [ -n $COMMAND ]; then
            docker exec ${DOCKER_CREATE_OPTS[*]} $CONTAINER_NAME bash -c ${COMMAND}  
        else
            docker exec ${DOCKER_CREATE_OPTS[*]} $CONTAINER_NAME
        fi

    fi
}

function check_container_status()
{
    $CONTAINER_RUNS=0
    $CONTAINER_EXISTS=0

    exists=$(docker ps -a | grep ${CONTAINER_NAME})
    if [ -n $exists ]; then
        echo "Docker container ${CONTAINER_NAME} already exists"
        $CONTAINER_EXISTS=1
        
        status=$(docker ps -a --filter status=running | grep ${CONTAINER_NAME})
        if [ -n $status ]; then
            CONTAINER_RUNS=1
        fi
    fi
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
            usage 0
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
docker ps --all
echo "------------------------------------------"

check_container_status

if [ $REMOVE_CONTAINER == 1 ]; then
    remove_container
    exit 0
fi

echo "Workdir in container is: \"$WORKDIR\""
create_container
exec_container
exit 0
