FROM python:3.13-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY ailedger ailedger
COPY static static
RUN useradd -m app
USER app
EXPOSE 8080
CMD ["uvicorn", "ailedger.app:app", "--host", "0.0.0.0", "--port", "8080"]
