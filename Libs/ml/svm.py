# libs/ml/svm.py

import numpy as np
from .base import BaseEstimator

class SVM(BaseEstimator):
    """
    Support Vector Machine usando el algoritmo Pegasos (Primal Estimated sub-GrAdient SOlver for SVM).
    """
    def __init__(self, lr: float = 1.0, epochs: int = 1000, lambda_reg: float = 1.0):
        super().__init__()
        self.lr = lr
        self.epochs = epochs
        self.lambda_reg = lambda_reg # Parámetro de regularización
        self.weights = None
        self.bias = 0.0

    def fit(self, X, y):
        """
        Ajusta el modelo SVM usando Pegasos.
        """
        n_samples, n_features = X.shape
        # Asegurar que y sea -1 o 1
        y = np.where(y <= 0, -1, 1)

        # Inicializar pesos
        self.weights = np.zeros(n_features)
        t = 1 # Contador de iteración para tasa de aprendizaje adaptativa

        for epoch in range(self.epochs):
            for i in range(n_samples):
                # Calcular la tasa de aprendizaje adaptativa
                lr_t = 1.0 / (self.lambda_reg * t)

                # Calcular el margen DENTRO del bucle de entrenamiento
                margin_internal = y[i] * (np.dot(X[i], self.weights) - self.bias) # <-- Cálculo directo

                if margin_internal >= 1:
                    # Actualización cuando está bien clasificado
                    self.weights -= lr_t * (2 * self.lambda_reg * self.weights)
                else:
                    # Actualización cuando está mal clasificado o en el margen
                    self.weights -= lr_t * (2 * self.lambda_reg * self.weights - np.dot(X[i], y[i]))
                    self.bias -= lr_t * y[i]

                t += 1 # Incrementar contador para próxima tasa

        self.is_fitted = True

    def predict(self, X):
        """
        Predice clases (-1 o 1) para X.
        """
        if not self.is_fitted:
            raise ValueError("El modelo no ha sido ajustado aún.")
        # Aquí sí puedes usar los pesos ya ajustados
        approx = np.dot(X, self.weights) - self.bias
        return np.sign(approx)

    # score ya está implementado en BaseEstimator (ajustar para clasificación binaria)
