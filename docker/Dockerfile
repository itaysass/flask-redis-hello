FROM python:3.9-slim

WORKDIR /app

# Copy requirements from repo root (context) into image
# (source path is relative to build context, not to the Dockerfile location)
COPY docker/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy your application code from app/ folder
COPY app/ .

EXPOSE 5000
CMD ["python", "app.py"]
