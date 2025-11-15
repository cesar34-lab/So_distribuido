import pytest
import numpy as np
from libs.ml.tree import DecisionTree
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


def test_tree_fit_predict():
    """Prueba fit y predict de DecisionTree."""
    model = DecisionTree(max_depth=3, min_samples_split=2, criterion="gini")

    # Datos simples: clasificación con una regla clara
    # y = 1 si x1 > 0, else y = 0
    X = np.array([[1, 2], [1, 3], [-1, -2], [-1, -1]])
    y = np.array([1, 1, 0, 0])

    model.fit(X, y)

    predictions = model.predict(X)
    # Verificar que las predicciones coincidan con las etiquetas verdaderas
    assert np.array_equal(predictions, y)


def test_tree_save_load():
    """Prueba save y load de DecisionTree con Store-D."""
    mock_store = MockStoreAgent()

    model = DecisionTree(max_depth=2, min_samples_split=2, criterion="gini")
    X = np.array([[1, 1], [0, 0]])
    y = np.array([1, 0])
    model.fit(X, y)

    # Guardar
    hash_saved = model.save(mock_store)
    assert hash_saved is not None

    # Cargar
    loaded_model = DecisionTree.load(mock_store, hash_saved)
    assert loaded_model is not None
    assert loaded_model.is_fitted
    # No comparamos directamente el árbol (estructura dict) porque puede haber variaciones
    # equivalentes en la división. Verificamos que esté ajustado y predecir funcione.

    # Verificar predicción del modelo cargado
    X_test = np.array([[0.5, 0.5]])
    pred_original = model.predict(X_test)
    pred_cargado = loaded_model.predict(X_test)
    assert np.array_equal(pred_original, pred_cargado)


def test_tree_score():
    """Prueba el score de DecisionTree (precisión para clasificación)."""
    model = DecisionTree(max_depth=3, min_samples_split=2, criterion="gini")

    # Datos simples
    X = np.array([[2, 2], [2, 1], [1, 2], [0, 0], [0, 1], [1, 0]])
    y = np.array([1, 1, 1, 0, 0, 0])

    model.fit(X, y)

    score = model.score(X, y)
    # El score debería ser 1.0 para un ajuste perfecto en estos datos
    assert score == 1.0


# Correr con: pytest tests/test_ml_tree.py -v -s