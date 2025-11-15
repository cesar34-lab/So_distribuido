# libs/ml/logistic.py

import numpy as np
from .base import BaseEstimator

class LogisticRegression(BaseEstimator):
    """
    Regresión Logística implementada desde cero.
    """
    def __init__(self, lr: float = 0.01, epochs: int = 1000, fit_intercept: bool = True, l2_reg: float = 0.0):
        super().__init__()
        self.lr = lr
        self.epochs = epochs
        self.fit_intercept = fit_intercept
        self.l2_reg = l2_reg # Regularización L2
        self.weights = None
        self.bias = 0.0

    def _sigmoid(self, z):
        # Clip z para evitar overflow en exp
        z = np.clip(z, -500, 500)
        return 1 / (1 + np.exp(-z))

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
            z_internal = np.dot(X, self.weights) + self.bias
            predictions_internal = self._sigmoid(z_internal) # <-- Cálculo directo

            # Calcular gradientes con regularización L2
            dw = (1 / n_samples) * np.dot(X.T, (predictions_internal - y)) + self.l2_reg * self.weights
            db = (1 / n_samples) * np.sum(predictions_internal - y)

            # Actualizar pesos
            self.weights -= self.lr * dw
            if self.fit_intercept:
                self.bias -= self.lr * db

        self.is_fitted = True

    def predict(self, X):
        """
        Predice clases (0 o 1) para X.
        """
        if not self.is_fitted:
            raise ValueError("El modelo no ha sido ajustado aún.")
        # Aquí sí puedes usar los pesos ya ajustados
        z = np.dot(X, self.weights) + self.bias
        predictions = self._sigmoid(z)
        return (predictions >= 0.5).astype(int)

    def predict_proba(self, X):
        """
        Predice probabilidades para X.
        """
        if not self.is_fitted:
            raise ValueError("El modelo no ha sido ajustado aún.")
        z = np.dot(X, self.weights) + self.bias
        predictions = self._sigmoid(z)
        return np.column_stack((1 - predictions, predictions))

    # score ya está implementado en BaseEstimator
