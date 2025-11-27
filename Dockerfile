# Dockerfile.nodo
# Imagen ligera para un nodo de producción

FROM python:3.11-slim

WORKDIR /app

# Copiar solo lo necesario
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código
COPY . .

# El script de entrada será el run_node.py
CMD ["python", "run_node.py", "--id", "${NODE_ID}", "--port", "${NODE_PORT}", "--peers", "${NODE_PEERS}"]op", "-b"]