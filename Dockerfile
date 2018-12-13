FROM 292075781285.dkr.ecr.us-east-1.amazonaws.com/indra:latest

ARG BUILD_BRANCH

ENV DIRPATH /sw
WORKDIR $DIRPATH

# Install INDRA and dependencies
RUN git clone --recursive https://github.com/indralab/emmaa.git

