# libs/ml/mlp.py

import numpy as np
from .base import BaseEstimator

class MLP(BaseEstimator):
    """
    Perceptrón Multicapa (MLP) Feedforward con Backpropagation.
    """
    def __init__(self, layers: list, lr: float = 0.01, epochs: int = 1000, batch_size: int = 32):
        super().__init__()
        self.layers = layers # Ej: [n_inputs, n_hidden1, n_hidden2, n_outputs]
        self.lr = lr
        self.epochs = epochs
        self.batch_size = batch_size
        self.weights = []
        self.biases = []

    def _sigmoid(self, z):
        z = np.clip(z, -500, 500)
        return 1 / (1 + np.exp(-z))

    def _sigmoid_derivative(self, z):
        s = self._sigmoid(z)
        return s * (1 - s)

    def fit(self, X, y):
        """
        Ajusta el modelo usando Backpropagation y mini-batches.
        """
        n_samples, n_inputs = X.shape
        n_outputs = y.shape[1] if len(y.shape) > 1 else 1

        # Inicializar pesos y biases
        self.weights = []
        self.biases = []
        for i in range(len(self.layers) - 1):
            w = np.random.randn(self.layers[i], self.layers[i+1]) * np.sqrt(2.0 / self.layers[i])
            b = np.zeros((1, self.layers[i+1]))
            self.weights.append(w)
            self.biases.append(b)

        for epoch in range(self.epochs):
            # Barajar datos
            indices = np.random.permutation(n_samples)
            X_shuffled = X[indices]
            y_shuffled = y[indices]

            # Mini-batches
            for start_idx in range(0, n_samples, self.batch_size):
                end_idx = min(start_idx + self.batch_size, n_samples)
                X_batch = X_shuffled[start_idx:end_idx]
                y_batch = y_shuffled[start_idx:end_idx]

                # Forward pass DENTRO del entrenamiento, sin llamar a self.predict
                activations = [X_batch]
                zs = []
                for i in range(len(self.weights)):
                    z = np.dot(activations[-1], self.weights[i]) + self.biases[i]
                    zs.append(z)
                    a = self._sigmoid(z)
                    activations.append(a)

                # Calcular error en la salida DENTRO del entrenamiento
                delta = activations[-1] - y_batch # Derivada del error cuadrático medio

                # Backward pass DENTRO del entrenamiento
                deltas = [delta]

                # Calcular deltas para capas ocultas DENTRO del entrenamiento
                for i in range(len(self.weights) - 2, -1, -1):
                    delta_hidden = np.dot(deltas[-1], self.weights[i+1].T) * self._sigmoid_derivative(zs[i])
                    deltas.append(delta_hidden)

                deltas.reverse() # Ahora deltas[i] corresponde a la capa i

                # Actualizar pesos y biases DENTRO del entrenamiento
                for i in range(len(self.weights)):
                    self.weights[i] -= self.lr * np.dot(activations[i].T, deltas[i]) / len(X_batch)
                    self.biases[i] -= self.lr * np.sum(deltas[i], axis=0, keepdims=True) / len(X_batch)

        self.is_fitted = True # <-- Marcar como ajustado al final

    def predict(self, X):
        """
        Predice valores para X.
        """
        if not self.is_fitted:
            raise ValueError("El modelo no ha sido ajustado aún.")
        # Aquí sí puedes usar los pesos ya ajustados
        a = X
        for i in range(len(self.weights)):
            z = np.dot(a, self.weights[i]) + self.biases[i]
            a = self._sigmoid(z)
        return a # Devuelve la salida final (puede ser probabilidades o valores directos)

    # score ya está implementado en BaseEstimator (ajustar para regresión o clasificación)
