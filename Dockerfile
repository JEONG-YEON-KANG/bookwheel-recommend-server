FROM python:3.9

RUN apt-get update && apt-get install -y \
    build-essential \
    gfortran \
    libopenblas-dev \
    liblapack-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# pip 최신화
RUN pip install --upgrade pip

# 버전 충돌 방지를 위해 numpy/setuptools/scipy 설치
RUN pip install "numpy<2.0" "setuptools<70" wheel scipy

# LightFM 수동 설치 (원본 버그 패치 버전)
RUN git clone https://github.com/lyst/lightfm.git /tmp/lightfm
RUN sed -i "s/__builtins__.__LIGHTFM_SETUP__ = True/__builtins__['__LIGHTFM_SETUP__'] = True/" /tmp/lightfm/setup.py
RUN pip install /tmp/lightfm
RUN rm -rf /tmp/lightfm

# 파이썬 패키지 설치
COPY requirements.txt .
RUN pip install -r requirements.txt

# 소스 복사
COPY . .

# 실행 스크립트 권한
RUN chmod +x start.sh
CMD ["./start.sh"]
