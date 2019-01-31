FROM 292075781285.dkr.ecr.us-east-1.amazonaws.com/indra:latest

ARG BUILD_BRANCH

ENV DIRPATH /sw
WORKDIR $DIRPATH

# Get EMMAA repo.
RUN git clone --recursive https://github.com/indralab/emmaa.git && \
    cd emmaa && \
    git checkout $BUILD_BRANCH && \
    echo $BUILD_BRANCH && \
    git branch && \
