#!/bin/bash
set -e



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

REMOVE=0
CONTAINER_NAME="devkit_container"
VOLUME=${PWD}
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
            REMOVE=1
            echo "Remove the container with name \"${CONTAINER_NAME}\""
            ;;
        -m|--mount)
            VOLUME=${!i_next}
            echo "Mount the volume \"${VOLUME}\" in the container with name \"${CONTAINER_NAME}\""
            ;;
        -c|--command)
            COMMAND=${!i_next}
            echo "Run the command \"${COMMAND}\" in the container with name \"${CONTAINER_NAME}\""
            ;;
        
    esac
done


