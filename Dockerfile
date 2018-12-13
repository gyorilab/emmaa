FROM indra:latest

ARG BUILD_BRANCH

ENV DIRPATH /sw
WORKDIR $DIRPATH

# Install INDRA and dependencies
RUN git clone --recursive https://github.com/indralab/emmaa.git

