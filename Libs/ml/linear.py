# libs/ml/linear.py

import numpy as np
from .base import BaseEstimator

class LinearRegression(BaseEstimator):
    """
    Regresión Lineal implementada desde cero.
    """
    def __init__(self, lr: float = 0.01, epochs: int = 1000, fit_intercept: bool = True):
        super().__init__()
        self.lr = lr
        self.epochs = epochs
        self.fit_intercept = fit_intercept
        self.weights = None
        self.bias = 0.0

    def fit(self, X, y):
        """
        Ajusta el modelo usando Gradiente Descendente.
        """
        n_samples, n_features = X.shape

        # Inicializar pesos y bias
        self.weights = np.zeros(n_features)
        if self.fit_intercept:
            self.bias = 0.0

        # Gradiente Descendente
        for i in range(self.epochs):
            # Calcular predicción DENTRO del bucle de entrenamiento usando los pesos actuales
            # NO llames a self.predict aquí, porque is_fitted aún es False
            y_pred_internal = np.dot(X, self.weights) + self.bias # <-- Cálculo directo

            # Calcular gradientes
            dw = (1 / n_samples) * np.dot(X.T, (y_pred_internal - y))
            db = (1 / n_samples) * np.sum(y_pred_internal - y)

            # Actualizar pesos
            self.weights -= self.lr * dw
            if self.fit_intercept:
                self.bias -= self.lr * db

        # Marcar el modelo como ajustado DESPUÉS del entrenamiento
        self.is_fitted = True

    def predict(self, X):
        """
        Predice valores de salida para X.
        """
        if not self.is_fitted:
            raise ValueError("El modelo no ha sido ajustado aún.")
        # Aquí sí puedes usar los pesos ya ajustados
        return np.dot(X, self.weights) + self.bias

    # score ya está implementado en BaseEstimator
