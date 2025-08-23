FROM python:3.9-slim

WORKDIR /app

# Copy requirements first (better caching)
COPY ../requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY ../app.py ./

EXPOSE 5000
CMD ["python", "app.py"]
