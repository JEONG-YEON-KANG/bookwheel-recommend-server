.PHONY: db-up db-down install run

# 'make db-up'
# 로컬 DB를 백그라운드로 실행
db-up:
	docker compose up -d

# 'make db-down'
# 로컬 DB를 중지하고 삭제
db-down:
	docker compose down

# 'make install'
# 의존성 패키지 설치
install:
	pip install -r requirements.txt

# 'make run'
# FASTAPI 서버를 개발모드로 실행
run:
	uvicorn app.main:app --reload