import pytest
import numpy as np

from Libs.ml import LinearRegression


#from libs.ml.linear import LinearRegression
#from libs.ml.base import BaseEstimator

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


def test_linear_regression_fit_predict():
    """Prueba fit y predict de LinearRegression."""
    model = LinearRegression(lr=0.1, epochs=1000)

    # Datos simples: y = 2*x + 1
    X = np.array([[1], [2], [3], [4], [5]])
    y = 2 * X.flatten() + 1

    model.fit(X, y)

    predictions = model.predict(X)
    # Verificar que las predicciones sean razonablemente cercanas
    assert np.allclose(predictions, y, rtol=0.1)


def test_linear_regression_save_load():
    """Prueba save y load de LinearRegression con Store-D."""
    mock_store = MockStoreAgent()

    model = LinearRegression(lr=0.01, epochs=100)
    X = np.array([[1], [2]])
    y = np.array([3, 5])
    model.fit(X, y)

    # Guardar
    hash_saved = model.save(mock_store)
    assert hash_saved is not None

    # Cargar
    loaded_model = LinearRegression.load(mock_store, hash_saved)
    assert loaded_model is not None
    assert loaded_model.is_fitted
    # Verificar que los pesos sean los mismos
    assert np.allclose(model.weights, loaded_model.weights)
    assert model.bias == loaded_model.bias

    # Verificar predicción del modelo cargado
    X_test = np.array([[6]])
    pred_original = model.predict(X_test)
    pred_cargado = loaded_model.predict(X_test)
    assert np.allclose(pred_original, pred_cargado)


def test_base_estimator_score():
    """Prueba el score de BaseEstimator (en este caso, R2 para regresión)."""
    model = LinearRegression(lr=0.1, epochs=1000)

    # Datos simples: y = 2*x + 1
    X = np.array([[1], [2], [3], [4], [5]])
    y_true = 2 * X.flatten() + 1
    # Añadir algo de ruido para que no sea un ajuste perfecto
    y_noisy = y_true + np.random.normal(0, 0.1, size=y_true.shape)

    model.fit(X, y_noisy)

    score = model.score(X, y_noisy)
    # El score R2 debería ser alto (> 0.9) para un ajuste bueno
    assert score > 0.9

# Correr con: pytest tests/test_ml_linear.py -v -s