# libs/ml/distributed.py

import numpy as np
from typing import List, Dict, Any
from Libs.ml.base import BaseEstimator
class GradientAggregator:
    """
    Agregador simple de gradientes para entrenamiento distribuido.
    Este objeto podría vivir en el nodo que coordina (por ejemplo, el que llama a submit_task).
    Recibe gradientes parciales de nodos ejecutores y los promedia.
    """
    def __init__(self):
        self.partial_gradients = {}
        self.counts = {}

    def add_gradients(self, task_id: str, model_weights_keys: List[str], gradients: List[np.ndarray]):
        """
        Añade gradientes parciales de una tarea específica.
        """
        if task_id not in self.partial_gradients:
            self.partial_gradients[task_id] = {}
            self.counts[task_id] = 0

        for key, grad in zip(model_weights_keys, gradients):
            if key not in self.partial_gradients[task_id]:
                self.partial_gradients[task_id][key] = grad
            else:
                self.partial_gradients[task_id][key] += grad

        self.counts[task_id] += 1

    def get_average_gradients(self, task_id: str) -> Dict[str, np.ndarray]:
        """
        Obtiene los gradientes promediados para una tarea.
        """
        if task_id not in self.partial_gradients or self.counts[task_id] == 0:
            return {}
        avg_grads = {}
        for key, grad_sum in self.partial_gradients[task_id].items():
            avg_grads[key] = grad_sum / self.counts[task_id]
        return avg_grads

    def reset_task(self, task_id: str):
        """
        Reinicia los acumuladores para una tarea.
        """
        if task_id in self.partial_gradients:
            del self.partial_gradients[task_id]
            del self.counts[task_id]

#class DistributedTrainer:
#    def __init__(self, model_class, model_params, scheduler_agent, store_agent):
#        self.model_class = model_class
#        self.model_params = model_params
#        self.scheduler_agent = scheduler_agent
#        self.store_agent = store_agent
#        self.aggregator = GradientAggregator()
#    def fit(self, X, y, n_nodes: int = 2):
#        # Dividir datos
#        # Enviar tareas de entrenamiento parcial a n_nodes
#        # Recibir gradientes
#        # Agregar gradientes
#        # Actualizar modelo global
#        pass