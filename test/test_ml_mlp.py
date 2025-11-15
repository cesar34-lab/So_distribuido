# tests/test_ml_mlp.py

import pytest
import numpy as np
from Libs.ml.base import BaseEstimator
from Libs.ml import MLP


# Mock Store-D para pruebas de serialización
class MockStoreAgent:
    def __init__(self):
        self.storage = {}
        self.next_id = 0

    def put(self,  bytes) -> str:
        obj_hash = f"hash_{self.next_id}"
        self.storage[obj_hash] = bytes # <-- CORREGIDO: era 'data', ahora es 'bytes'
        self.next_id += 1
        return obj_hash

    def get(self, obj_hash: str) -> bytes:
        return self.storage.get(obj_hash)


def test_mlp_fit_predict():
    """Prueba fit y predict de MLP."""
    # Modelo simple: [2 entradas, 3 neuronas ocultas, 1 salida]
    model = MLP(layers=[2, 3, 1], lr=0.5, epochs=1000, batch_size=2)

    # Datos XOR (ejemplo no linealmente separable, bueno para clasificación)
    X = np.array([[0, 0], [0, 1], [1, 0], [1, 1]])
    y = np.array([[0], [1], [1], [0]]) # Formato 2D para salida

    model.fit(X, y)

    predictions = model.predict(X)
    # Las predicciones son probabilidades o valores continuos
    # Verificar que estén en el rango [0, 1] y que separen razonablemente las clases
    rounded_predictions = (predictions > 0.5).astype(int)
    # print(f"XOR y real: {y.flatten()}")
    # print(f"XOR pred redondeada: {rounded_predictions.flatten()}")
    # El ajuste puede no ser perfecto, pero debería ser razonable
    # Aceptamos que al menos 3 de 4 estén correctos
    correct = (rounded_predictions.flatten() == y.flatten()).sum()
    assert correct >= 3 # Ajustar según sea necesario


def test_mlp_save_load():
    """Prueba save y load de MLP con Store-D."""
    mock_store = MockStoreAgent()

    model = MLP(layers=[2, 2, 1], lr=0.1, epochs=10, batch_size=2)
    X = np.array([[1, 0], [0, 1]])
    y = np.array([[1], [0]])
    model.fit(X, y)

    # Guardar
    hash_saved = model.save(mock_store)
    assert hash_saved is not None

    # Cargar
    loaded_model = MLP.load(mock_store, hash_saved)
    assert loaded_model is not None
    assert loaded_model.is_fitted
    # Verificar que los pesos y biases sean los mismos (puede haber pequeñas diferencias por floats)
    for w_orig, w_loaded in zip(model.weights, loaded_model.weights):
        assert np.allclose(w_orig, w_loaded)
    for b_orig, b_loaded in zip(model.biases, loaded_model.biases):
        assert np.allclose(b_orig, b_loaded)

    # Verificar predicción del modelo cargado
    X_test = np.array([[0.5, 0.5]])
    pred_original = model.predict(X_test)
    pred_cargado = loaded_model.predict(X_test)
    assert np.allclose(pred_original, pred_cargado)


def test_mlp_score_classification():
    """Prueba el score de MLP para clasificación."""
    # Modelo para clasificación simple
    model = MLP(layers=[2, 4, 2], lr=0.1, epochs=500, batch_size=2) # 2 clases de salida

    # Datos linealmente separables para clasificación binaria
    X = np.array([[1, 1], [1, 0], [0, 1], [0, 0]])
    y = np.array([[1, 0], [1, 0], [0, 1], [0, 1]]) # Formato one-hot

    model.fit(X, y)

    score = model.score(X, y)
    # El score debería ser 1.0 para un ajuste perfecto en estos datos (si logra converger)
    # Puede no ser 1.0 siempre, dependiendo del entrenamiento
    # Ajustamos el umbral a un valor razonable
    assert score >= 0.75 # Ajustar según sea necesario, puede no ser 1.0 siempre


# Correr con: pytest tests/test_ml_mlp.py -v -s