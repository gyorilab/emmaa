FROM 292075781285.dkr.ecr.us-east-1.amazonaws.com/indra:latest

ARG BUILD_BRANCH

ENV DIRPATH /sw
WORKDIR $DIRPATH

# Get EMMAA repo.
RUN pip install https://github.com/indralab/indra_db.git \
    git clone --recursive https://github.com/indralab/emmaa.git && \
    cd emmaa && \
    git checkout $BUILD_BRANCH && \
    echo $BUILD_BRANCH && \
    git branch && \
    pip install -e .

ENV EMMAAPATH /sw/emmaa
WORKDIR $EMMAAPATH
