import pytest
import numpy as np
from libs.ml.svm import SVM
from libs.ml.base import BaseEstimator

# Mock Store-D para pruebas de serialización
class MockStoreAgent:
    def __init__(self):
        self.storage = {}
        self.next_id = 0

    def put(self,  bytes) -> str:
        obj_hash = f"hash_{self.next_id}"
        self.storage[obj_hash] = data
        self.next_id += 1
        return obj_hash

    def get(self, obj_hash: str) -> bytes:
        return self.storage.get(obj_hash)


def test_svm_fit_predict():
    """Prueba fit y predict de SVM."""
    model = SVM(lr=1.0, epochs=100, lambda_reg=0.1)

    # Datos linealmente separables: y = 1 si x1 > 0, else y = -1
    X = np.array([[1, 0], [2, 1], [-1, 0], [-2, -1]])
    y = np.array([1, 1, -1, -1])

    model.fit(X, y)

    predictions = model.predict(X)
    # Verificar que las predicciones coincidan con las etiquetas verdaderas (1 o -1)
    assert np.array_equal(predictions, y)


def test_svm_save_load():
    """Prueba save y load de SVM con Store-D."""
    mock_store = MockStoreAgent()

    model = SVM(lr=1.0, epochs=50, lambda_reg=0.1)
    X = np.array([[1, 0], [-1, 0]])
    y = np.array([1, -1])
    model.fit(X, y)

    # Guardar
    hash_saved = model.save(mock_store)
    assert hash_saved is not None

    # Cargar
    loaded_model = SVM.load(mock_store, hash_saved)
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


def test_svm_score():
    """Prueba el score de SVM (precisión para clasificación)."""
    model = SVM(lr=1.0, epochs=100, lambda_reg=0.1)

    # Datos linealmente separables
    X = np.array([[3, 1], [1, 3], [-3, -1], [-1, -3]])
    y = np.array([1, 1, -1, -1])

    model.fit(X, y)

    score = model.score(X, y)
    # El score debería ser 1.0 para un ajuste perfecto en estos datos
    assert score == 1.0


# Correr con: pytest tests/test_ml_svm.py -v -s