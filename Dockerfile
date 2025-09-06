FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Europe/Madrid

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc libffi-dev \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Instala dependencias
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia el resto del proyecto
COPY . .

EXPOSE 8000
CMD ["python", "main.py"]
