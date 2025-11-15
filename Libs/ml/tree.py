# libs/ml/tree.py

import numpy as np
from .base import BaseEstimator

class DecisionTree(BaseEstimator):
    """
    Árbol de Decisión usando el algoritmo CART.
    """
    def __init__(self, max_depth: int = 5, min_samples_split: int = 2, criterion: str = "gini"):
        super().__init__()
        self.max_depth = max_depth
        self.min_samples_split = min_samples_split
        self.criterion = criterion # "gini" o "entropy"
        self.tree = None

    def _gini(self, y):
        """Calcula el índice de Gini para un conjunto de etiquetas."""
        classes, counts = np.unique(y, return_counts=True)
        probabilities = counts / len(y)
        gini = 1 - np.sum(probabilities ** 2)
        return gini

    def _entropy(self, y):
        """Calcula la entropía para un conjunto de etiquetas."""
        classes, counts = np.unique(y, return_counts=True)
        probabilities = counts / len(y)
        # Evitar log(0)
        probabilities = probabilities[probabilities > 0]
        entropy = -np.sum(probabilities * np.log2(probabilities))
        return entropy

    def _best_split(self, X, y):
        """Encuentra la mejor división basada en el criterio."""
        best_gain = -1
        best_feature = None
        best_threshold = None
        current_impurity = self._gini(y) if self.criterion == "gini" else self._entropy(y)

        for feature in range(X.shape[1]):
            thresholds = np.unique(X[:, feature])
            for threshold in thresholds:
                left_mask = X[:, feature] <= threshold
                right_mask = ~left_mask

                if np.sum(left_mask) == 0 or np.sum(right_mask) == 0:
                    continue

                n_left, n_right = np.sum(left_mask), np.sum(right_mask)
                left_impurity = self._gini(y[left_mask]) if self.criterion == "gini" else self._entropy(y[left_mask])
                right_impurity = self._gini(y[right_mask]) if self.criterion == "gini" else self._entropy(y[right_mask])

                weighted_impurity = (n_left / len(y)) * left_impurity + (n_right / len(y)) * right_impurity
                gain = current_impurity - weighted_impurity

                if gain > best_gain:
                    best_gain = gain
                    best_feature = feature
                    best_threshold = threshold

        return best_feature, best_threshold

    def _build_tree(self, X, y, depth=0):
        """Construye el árbol recursivamente."""
        n_samples, n_features = X.shape
        n_classes = len(np.unique(y))

        # Condiciones de parada
        if (depth >= self.max_depth or
            n_samples < self.min_samples_split or
            n_classes == 1):

            leaf_value = self._most_common_label(y)
            return leaf_value

        best_feature, best_threshold = self._best_split(X, y)

        if best_feature is None: # No se encontró división válida
            leaf_value = self._most_common_label(y)
            return leaf_value

        # Dividir el dataset
        left_mask = X[:, best_feature] <= best_threshold
        right_mask = ~left_mask

        # Construir sub-árboles
        left_subtree = self._build_tree(X[left_mask], y[left_mask], depth + 1)
        right_subtree = self._build_tree(X[right_mask], y[right_mask], depth + 1)

        return {"feature": best_feature, "threshold": best_threshold, "left": left_subtree, "right": right_subtree}

    def _most_common_label(self, y):
        """Encuentra la etiqueta más común."""
        values, counts = np.unique(y, return_counts=True)
        return values[np.argmax(counts)]

    def fit(self, X, y):
        """
        Ajusta el modelo construyendo el árbol.
        """
        self.tree = self._build_tree(X, y)
        self.is_fitted = True # <-- Marcar como ajustado al final

    def _traverse_tree(self, x, tree):
        """Recorre el árbol para predecir un solo ejemplo."""
        if not isinstance(tree, dict): # Es una hoja
            return tree

        if x[tree["feature"]] <= tree["threshold"]:
            return self._traverse_tree(x, tree["left"])
        else:
            return self._traverse_tree(x, tree["right"])

    def predict(self, X):
        """
        Predice clases para X.
        """
        if not self.is_fitted:
            raise ValueError("El modelo no ha sido ajustado aún.")
        # Aquí sí puedes usar el árbol ya construido
        return np.array([self._traverse_tree(x, self.tree) for x in X])

    # score ya está implementado en BaseEstimator
