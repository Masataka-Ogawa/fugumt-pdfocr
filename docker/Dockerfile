From nvcr.io/nvidia/cuda:11.0.3-devel-ubuntu20.04

LABEL maintainer "staka@vole.jp"

RUN apt-get update && apt-get -y upgrade
ENV TZ=Asia/Tokyo 
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone
RUN apt-get install -y tzdata

RUN apt-get install -y language-pack-ja-base language-pack-ja
RUN locale-gen en_US.UTF-8  
ENV LANG en_US.UTF-8  
ENV LANGUAGE en_US:en  
ENV LC_ALL en_US.UTF-8

RUN apt-get install -y git curl cmake build-essential python3-pip libpq-dev python-dev python3-setuptools libatlas-* libopenblas-*
RUN mkdir /app
WORKDIR /app
RUN git clone https://github.com/marian-nmt/marian
WORKDIR /app/marian/
RUN mkdir -p build
WORKDIR /app/marian/build
RUN cmake ../ -DUSE_SENTENCEPIECE=on -DCOMPILE_SERVER=on
RUN make -j4
RUN pip3 install --upgrade pip

RUN pip3 install bottle websocket_client h5py

RUN apt-get install -y mecab libmecab-dev mecab-ipadic-utf8 
RUN pip3 install mecab-python3 unidic-lite

RUN pip3 install pdfminer
RUN pip3 install spacy
RUN python3 -m spacy download en_core_web_sm
RUN chmod -R 755 /app/marian/build

RUN pip install torch==1.8.2+cu111 torchvision==0.9.2+cu111 torchaudio==0.8.2 -f https://download.pytorch.org/whl/lts/1.8/torch_lts.html
RUN pip install detectron2 -f https://dl.fbaipublicfiles.com/detectron2/wheels/cu111/torch1.8/index.html
RUN pip install -U layoutparser
RUN pip install -U layoutparser[layoutmodels]
RUN pip install -U layoutparser[ocr]
RUN pip install  pdf2image pdf2img
RUN apt-get install -y tesseract-ocr libtesseract-dev libleptonica-dev pkg-config tesseract-ocr-eng tesseract-ocr-osd tesseract-ocr-deu tesseract-ocr-fra tesseract-ocr-spa  poppler-utils
RUN pip install pyocr
RUN pip install --upgrade  numpy scipy setuptools bottle websocket_client h5py mecab-python3 unidic-lite  tf-sentencepiece tensorflow_hub tensorflow tensorflow_text nltk bert-for-tf2 allennlp allennlp-models psutil timeout-decorator pdfminer 
RUN pip install --upgrade google-cloud-storage
RUN groupadd -g 1000 ec2-user && \
    useradd -m -s /bin/bash -u 1000 -g 1000 ec2-user 
RUN pip install pysbd fasttext
RUN apt-get update && apt-get upgrade -y
RUN apt-get install -y libgl1-mesa-dev
