FROM ghcr.io/proger/kaldi:master

RUN python3 -m pip install --upgrade pip
RUN python3 -m pip install hatch
RUN hatch run make
