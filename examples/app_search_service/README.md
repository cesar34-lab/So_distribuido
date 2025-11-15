# Aplicación: Servicio de Búsqueda Distribuida

## Descripción
Esta aplicación simula un servicio de búsqueda por etiquetas, como un motor de búsqueda para documentos. Cada nodo indexa un conjunto de documentos y los almacena en el sistema de archivos distribuido. Cuando se realiza una búsqueda, se consulta a todos los nodos para encontrar qué documentos contienen una palabra clave específica.

## Requisitos
- Sistema Operativo Descentralizado (SOD) en modo simulador.
- Carpeta `sample_docs/` con archivos de texto.
- Archivos `libs/ml/mlp.py` y `libs/sod_api/client.py` implementados.

## Cómo Ejecutar
1.  Asegúrate de que los agentes `Scheduler-D`, `Store-D` y `Discover` estén corriendo en 3 nodos simulados.
2.  Añade algunos archivos de texto en la carpeta `sample_docs/` (ej: `doc1.txt`, `doc2.txt`).
3.  Abre una terminal en la carpeta raíz del proyecto.
4.  Activa tu entorno virtual:
    ```bash
    .venv\Scripts\activate
    ```
5.  Ejecuta el indexador (una vez):
    ```bash
    python examples/app_search_service/document_indexer.py
    ```
6.  Ejecuta la búsqueda:
    ```bash
    python examples/app_search_service/main.py
    ```
7.  Observa cómo:
    - El indexador carga los documentos y los guarda en `Store-D`.
    - La búsqueda envía una tarea que recupera los documentos que contienen la palabra clave.
    - Los resultados se muestran en la terminal.

## Resultado Esperado
- Los documentos que contienen la palabra clave buscada son recuperados.
- La aplicación es capaz de encontrar documentos incluso si están en nodos diferentes.