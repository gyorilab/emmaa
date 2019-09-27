FROM 292075781285.dkr.ecr.us-east-1.amazonaws.com/indra:latest

ARG BUILD_BRANCH

ENV DIRPATH /sw
WORKDIR $DIRPATH

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

# Install indralab_auth_tools
RUN git clone https://github.com/indralab/ui_util.git && \
    cd ui_util/indralab_auth_tools && \
    pip install .

# Clone and install EMMAA
RUN pip install git+https://github.com/indralab/indra_db.git && \
    git clone --recursive https://github.com/indralab/emmaa.git && \
    cd emmaa && \
    git checkout $BUILD_BRANCH && \
    echo $BUILD_BRANCH && \
    git branch && \
    pip install -e .

ENV EMMAAPATH /sw/emmaa
WORKDIR $EMMAAPATH
