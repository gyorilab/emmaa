FROM 292075781285.dkr.ecr.us-east-1.amazonaws.com/indra:latest

ARG BUILD_BRANCH
ARG INDRA_BRANCH

ENV DIRPATH /sw
WORKDIR $DIRPATH

# Update INDRA
RUN cd indra && \
    git fetch --all && \
    git checkout origin/$INDRA_BRANCH

# Install libpq5
RUN apt-get update && \
    apt-get install -y libpq5 libpq-dev

# Install psycopg2
RUN git clone https://github.com/psycopg/psycopg2.git && \
    cd psycopg2 && \
    python setup.py build && \
    python setup.py install

# Install pgcopy
RUN git clone https://github.com/pagreene/pgcopy.git && \
    cd pgcopy && \
    python setup.py install

# Install covid-19
RUN git clone https://github.com/indralab/covid-19.git

# Clone and install EMMAA
RUN pip install git+https://github.com/indralab/indra_db.git#egg=indra_db[misc] && \
    pip install git+https://github.com/sorgerlab/bioagents.git && \
    git clone https://github.com/indralab/indra_world.git && \
    pip install -U gilda && \
    git clone --recursive https://github.com/indralab/emmaa.git && \
    cd emmaa && \
    git checkout $BUILD_BRANCH && \
    echo $BUILD_BRANCH && \
    git branch && \
    pip install -e .

ENV BNGPATH /sw/BioNetGen-2.4.0
ENV EMMAAPATH /sw/emmaa
WORKDIR $EMMAAPATH
