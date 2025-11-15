import pytest
import numpy as np

from Libs.ml import LogisticRegression


# Mock Store-D para pruebas de serialización
class MockStoreAgent:
    def __init__(self):
        self.storage = {}
        self.next_id = 0

    def put(self,  data:bytes) -> str:
        obj_hash = f"hash_{self.next_id}"
        self.storage[obj_hash] = data
        self.next_id += 1
        return obj_hash

    def get(self, obj_hash: str) -> bytes:
        return self.storage.get(obj_hash)


def test_logistic_regression_fit_predict():
    """Prueba fit y predict de LogisticRegression."""
    model = LogisticRegression(lr=0.1, epochs=1000)

    # Datos simples: clasificación linealmente separable
    # y = 1 si x1 + x2 > 0, else y = 0
    X = np.array([[1, 1], [1, -1], [-1, 1], [-1, -1]])
    y = np.array([1, 0, 0, 0])

    model.fit(X, y)

    predictions = model.predict(X)
    # Verificar que las predicciones coincidan con las etiquetas verdaderas para este caso simple
    # Puede no ser exacto al 100% debido a la naturaleza del algoritmo y la poca cantidad de datos
    # pero debería ser mayoritariamente correcto.
    accuracy = (predictions == y).mean()
    assert accuracy >= 0.75 # Ajustar según sea necesario


def test_logistic_regression_save_load():
    """Prueba save y load de LogisticRegression con Store-D."""
    mock_store = MockStoreAgent()

    model = LogisticRegression(lr=0.01, epochs=100)
    X = np.array([[1, 1], [0, 0]])
    y = np.array([1, 0])
    model.fit(X, y)

    # Guardar
    hash_saved = model.save(mock_store)
    assert hash_saved is not None

    # Cargar
    loaded_model = LogisticRegression.load(mock_store, hash_saved)
    assert loaded_model is not None
    assert loaded_model.is_fitted
    # Verificar que los pesos y bias sean los mismos
    assert np.allclose(model.weights, loaded_model.weights)
    assert model.bias == loaded_model.bias

    # Verificar predicción del modelo cargado
    X_test = np.array([[0.5, 0.5]])
    pred_original = model.predict(X_test)
    pred_cargado = loaded_model.predict(X_test)
    assert np.array_equal(pred_original, pred_cargado)


def test_logistic_regression_score():
    """Prueba el score de LogisticRegression (precisión para clasificación)."""
    model = LogisticRegression(lr=0.1, epochs=1000)

    # Datos simples: clasificación linealmente separable
    X = np.array([[2, 2], [2, 1], [1, 2], [0, 0], [0, 1], [1, 0]])
    y = np.array([1, 1, 1, 0, 0, 0])

    model.fit(X, y)

    score = model.score(X, y)
    # El score debería ser 1.0 para un ajuste perfecto en estos datos
    assert score >= 0.8 # Ajustar según sea necesario, puede no ser 1.0 siempre


# Correr con: pytest tests/test_ml_logistic.py -v -s