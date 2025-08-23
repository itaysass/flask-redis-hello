from flask import Flask
import logging
import os

app = Flask(__name__)

# Make sure /logs directory exists
os.makedirs('logs', exist_ok=True)

# Set up logging to file
logging.basicConfig(filename='logs/app.log', level=logging.INFO)

@app.route('/')
def index():
    logging.info("Homepage was accessed.")
    return "Hello, World! By Itay"

# Liveness probe
@app.route('/health')
def health():
    return "OK", 200

# Readiness probe
@app.route('/ready')
def ready():
    return "Ready", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
