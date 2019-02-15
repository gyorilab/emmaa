#!/usr/bin/env bash
#------------------------------------------------------------------------------
# update_git_and_run
# This updates the current git repo and executes the given command
# This script is extremely dangerous. It is designed to be run in temporary
# environments. Do not use if you don't know what you're doing.
#------------------------------------------------------------------------------

echo $#
echo $@



# if [ "$#" -ne 2 ]; then
#     echo "Usage: $0 <branch> <command>"
#     exit 1
# fi

branch=$1
IFS='//'; remote=($branch); unset IFS;

echo $branch
echo $remote
echo $command
git fetch $remote
git reset --hard $branch
command=$2
$command
