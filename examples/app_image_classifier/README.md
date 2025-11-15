# Aplicación: Clasificación de Imágenes Distribuida

## Descripción
Esta aplicación demuestra un esquema de **aprendizaje federado**. Divide un dataset de imágenes sintéticas en 3 partes y envía cada parte a un nodo diferente para que entrenen un modelo MLP local. Luego, recoge los modelos entrenados y los promedia para obtener un modelo global.

## Requisitos
- Sistema Operativo Descentralizado (SOD) en modo simulador.
- Archivos `libs/ml/mlp.py` y `libs/sod_api/client.py` implementados.

## Cómo Ejecutar
1.  Asegúrate de que los agentes `Scheduler-D`, `Store-D` y `Net` estén corriendo en 3 nodos simulados.
2.  Abre una terminal en la carpeta raíz del proyecto.
3.  Activa tu entorno virtual:
    ```bash
    .venv\Scripts\activate
    ```
4.  Ejecuta la aplicación:
    ```bash
    python examples/app_image_classifier/main.py
    ```
5.  Observa cómo:
    - El dataset se divide y se guarda en `Store-D`.
    - Tres tareas se envían y se asignan a nodos diferentes.
    - Los modelos se entrenan en paralelo.
    - El cliente recupera los modelos y los promedia.
    - Se muestra la precisión final.

## Resultado Esperado
- Precisión del modelo final mayor a 0.85.
- Todos los nodos deben haber recibido y ejecutado una tarea.
- El modelo final es mejor que cualquiera de los modelos locales (porque aprende de toda la información).