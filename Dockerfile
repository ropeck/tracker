FROM python:3.11-slim

# Always use this python
RUN ln -sf /usr/local/bin/python /usr/bin/python3 && \
    ln -sf /usr/local/bin/pip /usr/bin/pip3

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["uvicorn", "scripts.logger:app", "--proxy-headers", "--forwarded-allow-ips=\"*\"", "--host", "0.0.0.0", "--port", "8000"]
