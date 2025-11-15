# libs/ml/base.py

import pickle
import numpy as np # Añadido numpy para el cálculo de score
from abc import ABC, abstractmethod
from typing import Any, Optional

class BaseEstimator(ABC):
    """
    Clase base abstracta para todos los estimadores de ML.
    Define la interfaz común para fit, predict, save, load.
    """
    def __init__(self):
        self.is_fitted = False

    @abstractmethod
    def fit(self, X, y, **kwargs):
        """
        Ajusta el modelo a los datos de entrenamiento.
        """
        pass

    @abstractmethod
    def predict(self, X):
        """
        Predice etiquetas para los datos de entrada X.
        """
        pass

    def score(self, X, y):
        """
        Calcula la precisión del modelo.
        Para clasificación: devuelve la proporción de predicciones correctas.
        Para regresión: devuelve el coeficiente de determinación R².
        """
        predictions = self.predict(X)

        # Asegurar que y y predictions tengan la misma forma
        y = np.asarray(y)
        predictions = np.asarray(predictions)

        # Verificar si es un problema de clasificación o regresión
        # Clasificación si y tiene etiquetas enteras o es 1D con pocos valores únicos
        # Regresión si y es numérico continuo o tiene muchos valores únicos
        # Para simplificar, asumimos que si y es entero o tiene forma (n,) o (n, 1) y no es 0/1, podría ser regresión
        # Si es 0/1 binario o tiene pocos valores enteros, es clasificación
        # Caso más robusto para regresión: verificar si y es numérico y no es claramente categórico
        # Caso más robusto para clasificación: verificar si y es entero y tiene pocos valores únicos

        # Estrategia simplificada: Si y es 1D o tiene shape (n, 1) y no parece ser 0/1 binario para clasificación,
        # asumimos regresión. Si es 0/1 o tiene pocos valores enteros, asumimos clasificación.
        # La distinción puede ser compleja. Usaremos un enfoque heurístico o dejaremos que el usuario especifique el tipo si es necesario.
        # Por ahora, intentaremos inferirlo.
        y_flat = y.flatten() if y.ndim > 1 else y
        # Si y tiene pocos valores únicos (menos de 5) y son enteros, probablemente sea clasificación
        unique_vals = np.unique(y_flat)
        is_classification_heuristic = len(unique_vals) < 5 and np.issubdtype(y.dtype, np.integer)

        if is_classification_heuristic:
            # Clasificación
            if len(y.shape) > 1 and y.shape[1] > 1: # Clasificación multiclase one-hot
                correct_predictions = (predictions.argmax(axis=1) == y.argmax(axis=1))
            else: # Clasificación binaria o multiclase con etiquetas
                # Asegurar que predictions sean enteros (clases)
                if predictions.ndim > 1 and predictions.shape[1] > 1: # Salida one-hot o probabilidades
                    predicted_classes = predictions.argmax(axis=1)
                else: # Salida de clase directa
                    predicted_classes = (predictions >= 0.5).astype(int).flatten() # Asumiendo 0/1 o probabilidad

                # Asegurar que y sea 1D si es clasificación binaria con una sola columna
                if y.ndim > 1 and y.shape[1] == 1:
                    y_reshaped = y.flatten()
                else:
                    y_reshape = y_flat

                correct_predictions = (predicted_classes == y_reshape)
            return correct_predictions.mean()
        else:
            # Regresión: Calcula R²
            # Asegurar que predictions y y tengan la misma forma para el cálculo
            if predictions.shape != y.shape:
                # Intentar reshape si es posible
                try:
                    predictions = predictions.reshape(y.shape)
                except ValueError:
                    print(f"[BaseEstimator.score] Error: Forma de predicciones {predictions.shape} no coincide con la de y {y.shape}")
                    return float('nan') # O lanzar una excepción

            ss_res = ((y - predictions) ** 2).sum()
            # ss_tot: varianza de y
            # y.mean() calcula la media global si y es 2D. Para R², necesitamos la media por columna si y es 2D (múltiples salidas)
            # Para simplificar, asumimos una sola salida (y.shape[1] == 1) o y 1D.
            # Si y es 2D con múltiples salidas, R² se calcula por cada salida y luego se promedia o se usa una versión multivariante.
            # Por ahora, asumimos una sola salida.
            if y.ndim == 2 and y.shape[1] == 1:
                y_mean = y.mean(axis=0, keepdims=True) # Shape (1, 1)
            else:
                y_mean = y.mean() # Escalar o shape (1,) si y es 1D

            ss_tot = ((y - y_mean) ** 2).sum()
            # print(f"ss_res: {ss_res}, ss_tot: {ss_tot}") # Descomentar para debug
            if ss_tot == 0:
                # Si la varianza de y es 0, el modelo no puede mejorar, R² es 1.0 si predice perfecto, NaN si no.
                # Si ss_res también es 0, predicen perfecto.
                # Si ss_res > 0, predicen mal, R² no está definido claramente, pero tiende a -inf.
                # Por convención, si ss_tot es 0 y ss_res es 0, R² = 1.0. Si ss_tot es 0 y ss_res > 0, R² = -inf o NaN.
                # Para evitar problemas, devolvemos 1.0 si predicen exacto, NaN si no.
                if ss_res == 0:
                    return 1.0
                else:
                    return float('nan') # o -float('inf')
            else:
                r2 = 1 - (ss_res / ss_tot)
                return r2


    def save(self, store_d_agent) -> Optional[str]:
        """
        Serializa el modelo y lo almacena en Store-D.

        Args:
            store_d_agent: Instancia del agente Store-D para almacenar los bytes.

        Returns:
            str: Hash del modelo almacenado, o None si falla.
        """
        try:
            model_bytes = pickle.dumps(self)
            obj_hash = store_d_agent.put(model_bytes)
            print(f"[ML BaseEstimator] Modelo almacenado con hash: {obj_hash}")
            return obj_hash
        except Exception as e:
            print(f"[ML BaseEstimator] Error al guardar modelo: {e}")
            return None

    @classmethod
    def load(cls, store_d_agent, obj_hash: str):
        """
        Carga un modelo desde Store-D.

        Args:
            store_d_agent: Instancia del agente Store-D para recuperar los bytes.
            obj_hash (str): Hash del modelo a cargar.

        Returns:
            BaseEstimator: Instancia del modelo cargado.
        """
        try:
            model_bytes = store_d_agent.get(obj_hash)
            if model_bytes is not None:
                model = pickle.loads(model_bytes)
                print(f"[ML BaseEstimator] Modelo cargado desde hash: {obj_hash}")
                return model
            else:
                print(f"[ML BaseEstimator] Error: No se pudo recuperar el modelo con hash {obj_hash}.")
                return None
        except Exception as e:
            print(f"[ML BaseEstimator] Error al cargar modelo: {e}")
            return None
