#! /usr/bin/env bash
# Run model tests from s3. For use running on AWS batch. User has the option
# to specify a git branch. This is to avoid having to rebuild the Emmaa docker
# every time a change is made. Instead the docker will be able to update to
# whichever version of Emmaa was specified by branch. This script is extremely
# dangerous is only intended to be run in temporary environments. It will overwrite
# unstaged changed with a git reset --hard

usage()
{
    echo "usage: $0 [- b --branch <branch>] -m --model <model> -t --test <test>"
}

TEMP=`getopt -o hb:m:t: --long help,branch:,model:,test: -- "$@"`
eval set -- "$TEMP"

while true; do
    case "$1" in
	-b | --branch)
	    branch=$2; shift 2 ;;
	-m | --model)
	    model=$2; shift 2 ;;
	-t | --test)
	    test=$2; shift 2 ;;
	-- ) shift; break ;;
	* ) break ;;
    esac
done

if [[ -z $model ]]; then
    echo "option --model must be set"
    failed=true
fi

if [[ -z $test ]]; then
    echo "option --test must be set"
    failed=true
fi

if [[ $failed ]]; then
    usage
    exit 1
fi

# if branch has been given. update git and run
if [[ $branch ]]; then
    # First verify that the branch actually exists
    git rev-parse --verify $branch >/dev/null 2>/dev/null
    if [[ "$?" != 0 ]]; then
	echo "Error: Branch $branch could not be found"
	exit 1
    fi
    # If branch is remote, we will need to fetch latest
    remote=$(basename $branch)
    if [[ "$remote" != "$branch" ]] && [[ "$remote" != *"/"* ]]; then
	git fetch $remote
    fi
    git reset --hard $branch
fi

python scripts/run_model_test_from_s3.py --model $model --test $test
      




