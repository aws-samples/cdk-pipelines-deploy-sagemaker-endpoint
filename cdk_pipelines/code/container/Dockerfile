FROM public.ecr.aws/a1c1q3b9/python:3.7

RUN apt-get -y update && apt-get install -y \
         nginx \
         ca-certificates \
         policycoreutils \
         ffmpeg \
         libsm6 \
         libxext6 \
    && rm -rf /var/lib/apt/lists/*

ENV PATH="/usr/sbin/:${PATH}"

COPY requirements.txt /requirements.txt

RUN pip install --upgrade pip
RUN pip install --no-cache -r /requirements.txt && \
    rm /requirements.txt


# sm vars
ENV SAGEMAKER_MODEL_SERVER_TIMEOUT="300"
ENV MODEL_SERVER_TIMEOUT="300"
ENV PYTHONUNBUFFERED=TRUE
ENV PYTHONDONTWRITEBYTECODE=TRUE
ENV MODEL_SERVER_WORKERS="4"
ENV PATH="/opt/program:${PATH}"

# Set up the program in the image
COPY inference/src /opt/program

# set permissions of entrypoint
RUN chmod +x /opt/program/serve

WORKDIR /opt/program