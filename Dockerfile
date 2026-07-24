FROM python:3.14-slim

# Install uv
RUN pip install uv

# 작업 디렉토리 설정
WORKDIR /app

# 의존성 파일 및 소스 코드 복사
COPY pyproject.toml server.py /app/

# 의존성 설치 (빌드 컨텍스트에 uv.lock이 없으면 여기서 생성)
RUN uv sync

# 포트
ENV PORT=8000

# 애플리케이션 실행
CMD ["uv", "run", "server.py"]
