# agents/store_d/store.py

import os
import json
import hashlib
import time
import asyncio
from pathlib import Path
from typing import Optional, List, Dict, Any

# Asumimos que NetAgent está disponible para enviar/recibir mensajes
# y que el protocolo está definido en algún lugar común.
# Este es un ejemplo de cómo podría integrarse.

class StoreD:
    def __init__(self, node_id: str, net_agent, storage_dir: str = "store_local", meta_file: str = "store_meta.json", r_copies: int = 3, gc_ttl: int = 3600):
        """
        Inicializa el Store-D.

        Args:
            node_id (str): Identificador único del nodo.
            net_agent: Instancia del agente de red para comunicación.
            storage_dir (str): Directorio local para almacenar datos.
            meta_file (str): Nombre del archivo JSON para metadatos.
            r_copies (int): Número objetivo de réplicas por objeto.
            gc_ttl (int): Tiempo en segundos antes de que un objeto sin referencias sea candidato a GC.
        """
        self.node_id = node_id
        self.net_agent = net_agent
        self.storage_dir = Path(storage_dir)
        self.meta_file_path = Path(meta_file)
        self.r_copies = r_copies
        self.gc_ttl = gc_ttl

        # Crear directorio de almacenamiento local si no existe
        self.storage_dir.mkdir(exist_ok=True)

        # Cargar o inicializar metadatos
        self.metadata: Dict[str, Any] = self._load_metadata()

    def _load_metadata(self) -> Dict[str, Any]:
        """Carga los metadatos desde el archivo JSON."""
        if self.meta_file_path.exists():
            try:
                with open(self.meta_file_path, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                print(f"Advertencia: Error al cargar {self.meta_file_path}, creando uno nuevo. Error: {e}")
                return {}
        return {}

    def _save_metadata(self):
        """Guarda los metadatos en el archivo JSON."""
        try:
            with open(self.meta_file_path, 'w') as f:
                json.dump(self.metadata, f, indent=2)
        except IOError as e:
            print(f"Error al guardar metadatos en {self.meta_file_path}: {e}")

    def _calculate_hash(self, data: bytes) -> str:
        """Calcula el hash SHA256 del dato."""
        return hashlib.sha256(data).hexdigest()

    def put(self, data: bytes) -> str:
        """
        Almacena un objeto y devuelve su hash.

        Args:
            data (bytes): El objeto a almacenar.

        Returns:
            str: El hash SHA256 del objeto.
        """
        obj_hash = self._calculate_hash(data)
        file_path = self.storage_dir / obj_hash

        # Guardar archivo localmente
        with open(file_path, 'wb') as f:
            f.write(data)

        # Actualizar metadatos
        if obj_hash not in self.metadata:
            self.metadata[obj_hash] = {
                "replicas": [self.node_id],
                "refcount": 1,
                "timestamp": int(time.time())
            }
        else:
            # Si ya existía, incrementar refcount (ej: si se llama put de nuevo con los mismos datos)
            self.metadata[obj_hash]["refcount"] += 1

        self._save_metadata()

        # Disparar replicación asincrónica si es necesario
        asyncio.create_task(self._ensure_replication(obj_hash))

        return obj_hash

    def list_replicas(self, obj_hash: str) -> List[str]:
        """
        Lista los nodos que tienen una réplica del objeto.

        Args:
            obj_hash (str): Hash del objeto.

        Returns:
            List[str]: Lista de IDs de nodos.
        """
        return self.metadata.get(obj_hash, {}).get("replicas", [])

    async def get(self, obj_hash: str) -> Optional[bytes]:
        """
        Recupera un objeto por su hash. Primero busca localmente, luego en la red.

        Args:
            obj_hash (str): Hash del objeto a recuperar.

        Returns:
            Optional[bytes]: El objeto si se encuentra, None en caso contrario.
        """
        file_path = self.storage_dir / obj_hash

        # 1. Buscar localmente
        if file_path.exists():
            print(f"[Store-D] Encontrado localmente: {obj_hash}")
            # NO incrementamos refcount aquí. Solo lo hacemos si lo obtenemos de otro nodo.
            # Si es un 'get' que se usa para *leer* localmente, no debería afectar refcount.
            # El refcount se incrementa cuando se *usa* el objeto en una operación como una tarea.
            # Para simplificar el test, asumiremos que get() no incrementa refcount local.
            # Si se quisiera que get() incrementara refcount local, habría que descomentar la línea de abajo.
            # if obj_hash in self.metadata:
            #     self.metadata[obj_hash]["refcount"] += 1
            #     self._save_metadata()
            with open(file_path, 'rb') as f:
                return f.read()

        # 2. Buscar remotamente
        print(f"[Store-D] No encontrado localmente: {obj_hash}. Buscando en la red...")
        # Primero, intentar con nodos conocidos que reportaron tenerlo
        candidate_nodes = self.list_replicas(obj_hash)

        # Si no hay nodos conocidos con el hash en metadatos, debemos buscarlo activamente.
        # En un sistema real, usaríamos una DHT o un mensaje tipo STORE_FIND.
        # Por ahora, en el simulador, asumiremos que si no está en metadatos, debemos preguntar a otros nodos.
        # Para pruebas, el MockNetAgent puede simular que ciertos hashes están disponibles en otros nodos.
        # Usaremos una lógica simple: si no está en metadatos, preguntaremos a todos los nodos conocidos.
        # Para simplificar, usaremos los nodos conocidos por el NetAgent.
        if not candidate_nodes:
            # Obtener nodos conocidos del agente de red (esto debe integrarse con DiscoverAgent en la realidad)
            all_known_nodes = getattr(self.net_agent, 'known_nodes', set())
            candidate_nodes = [n for n in all_known_nodes if n != self.node_id]
            print(f"[Store-D] Hash {obj_hash} no está en metadatos. Buscando entre nodos conocidos: {candidate_nodes}")

        if not candidate_nodes:
            print(f"[Store-D] No hay nodos conocidos para buscar {obj_hash}")
            return None

        for node_id in candidate_nodes:
            if node_id == self.node_id:
                continue # Ya verificamos localmente

            print(f"[Store-D] Intentando obtener {obj_hash} de {node_id}")
            # Enviar mensaje STORE_GET
            request_msg = {
                "magic": "SOD1",
                "type": "STORE_GET",
                "src": self.node_id,
                "dst": node_id,
                "msg_id": f"get_{obj_hash}_{int(time.time())}",
                "timestamp": int(time.time()),
                "payload": {"hash": obj_hash}
            }

            try:
                # Enviar el mensaje y esperar respuesta (esto requiere que NetAgent maneje el envío y recepción de respuestas)
                # Supongamos que net_agent.send_request espera una respuesta específica
                response = await self.net_agent.send_request(request_msg, timeout=5.0)
                if response and response.get("type") == "STORE_FOUND" and response.get("payload", {}).get("hash") == obj_hash:
                    data_bytes = bytes.fromhex(response["payload"]["data"]) # Asumiendo que los datos se envían como hex
                    print(f"[Store-D] Obtenido {obj_hash} de {node_id}")

                    # Guardar localmente
                    local_file_path = self.storage_dir / obj_hash
                    with open(local_file_path, 'wb') as f:
                        f.write(data_bytes)

                    # Actualizar metadatos localmente
                    if obj_hash not in self.metadata:
                        self.metadata[obj_hash] = {
                            "replicas": [node_id], # Nodo de origen
                            "refcount": 1, # Almacenado localmente por primera vez, refcount es 1
                            "timestamp": int(time.time())
                        }
                    else:
                        # Si ya existía en metadatos (por ejemplo, por replicación o descubrimiento), solo incrementamos refcount
                        # y agregamos el nodo de origen si no estaba
                        self.metadata[obj_hash]["refcount"] += 1
                        if node_id not in self.metadata[obj_hash]["replicas"]:
                            self.metadata[obj_hash]["replicas"].append(node_id)

                    self._save_metadata()
                    return data_bytes
                elif response and response.get("type") == "STORE_NOT_FOUND":
                     print(f"[Store-D] Nodo {node_id} no tiene {obj_hash}")
                     # Opcional: Actualizar metadatos locales si el nodo reporta que ya no lo tiene
                     # Si el nodo era el único en la lista de réplicas locales, podría borrarlo de metadatos locales
                     if obj_hash in self.metadata and node_id in self.metadata[obj_hash]["replicas"]:
                         self.metadata[obj_hash]["replicas"].remove(node_id)
                         if not self.metadata[obj_hash]["replicas"]:
                             # Si no quedan réplicas conocidas en la lista local, podría marcarlo de alguna manera
                             # o dejarlo si refcount > 0. Para GC, solo borramos si refcount=0 y TTL.
                             # Por ahora, no borramos metadatos si refcount > 0.
                             # Si refcount es 0 y no hay réplicas, es un candidato a GC si se vuelve a intentar get.
                             # Para simplificar, no borramos la entrada de metadatos aquí.
                             pass
            except asyncio.TimeoutError:
                print(f"[Store-D] Timeout esperando respuesta de {node_id} para {obj_hash}")
                continue # Intentar con el siguiente nodo
            except Exception as e:
                print(f"[Store-D] Error obteniendo {obj_hash} de {node_id}: {e}")
                continue # Intentar con el siguiente nodo

        print(f"[Store-D] No se pudo obtener {obj_hash} de ningún nodo conocido.")
        return None


    async def replicate(self, obj_hash: str, target_nodes: List[str]):
        """
        Replica un objeto a una lista de nodos destino.

        Args:
            obj_hash (str): Hash del objeto a replicar.
            target_nodes (List[str]): Lista de IDs de nodos destino.
        """
        file_path = self.storage_dir / obj_hash
        if not file_path.exists():
            print(f"[Store-D] No se puede replicar {obj_hash}, no encontrado localmente.")
            return

        with open(file_path, 'rb') as f:
            data_bytes = f.read()

        for node_id in target_nodes:
            if node_id == self.node_id:
                continue # No replicar a sí mismo

            print(f"[Store-D] Replicando {obj_hash} a {node_id}")
            replicate_msg = {
                "magic": "SOD1",
                "type": "STORE_PUT",
                "src": self.node_id,
                "dst": node_id,
                "msg_id": f"rep_{obj_hash}_{node_id}_{int(time.time())}",
                "timestamp": int(time.time()),
                "payload": {
                    "hash": obj_hash,
                    "data": data_bytes.hex(), # Enviar como string hexadecimal
                    "replica": True
                }
            }

            try:
                # Enviar el mensaje de replicación
                # Asumimos que NetAgent puede manejar el envío fiable o no
                await self.net_agent.send(replicate_msg, reliable=True) # Opcional: usar canal fiable para replicación
                print(f"[Store-D] {obj_hash} replicado exitosamente a {node_id}")
                # Actualizar lista local de réplicas
                if obj_hash in self.metadata and node_id not in self.metadata[obj_hash]["replicas"]:
                    self.metadata[obj_hash]["replicas"].append(node_id)
                    self._save_metadata()
            except Exception as e:
                print(f"[Store-D] Error replicando {obj_hash} a {node_id}: {e}")


    async def _ensure_replication(self, obj_hash: str):
        """
        Verifica si el número de réplicas es menor a R y, si es así, intenta replicar.
        Debe ser llamado asincrónicamente.
        """
        current_replicas = set(self.list_replicas(obj_hash))
        if len(current_replicas) < self.r_copies:
            print(f"[Store-D] Iniciando replicación para {obj_hash} (actual: {len(current_replicas)}, objetivo: {self.r_copies})")
            # Aquí necesitas una forma de obtener nodos candidatos para replicar
            # Por ejemplo, usar Discover para obtener nodos disponibles
            # Supongamos que tenemos un método en Discover o en el propio NetAgent
            # Por ahora, un stub que obtiene nodos de ejemplo
            # candidate_nodes = await self.discover_agent.get_available_nodes(exclude=[self.node_id])
            # Por simplicidad, usamos un stub que devuelve una lista fija o vacía
            candidate_nodes = await self._get_candidate_nodes_for_replication(exclude=[self.node_id] + list(current_replicas))
            nodes_to_replicate_to = [n for n in candidate_nodes if n not in current_replicas][:self.r_copies - len(current_replicas)]
            if nodes_to_replicate_to:
                await self.replicate(obj_hash, nodes_to_replicate_to)
            else:
                print(f"[Store-D] No se encontraron nodos candidatos para replicar {obj_hash}.")


    async def _get_candidate_nodes_for_replication(self, exclude: List[str]) -> List[str]:
        """
        Stub: Obtener nodos candidatos para replicación.
        En la implementación real, esto debería consultar a Discover o usar otra lógica.
        """
        # Este es un stub. En la práctica, usarías DiscoverAgent o un servicio de nodos conocidos.
        # Por ejemplo, podría llamar a DiscoverAgent.get_neighbors() o una función similar
        # y aplicar filtros (salud, reputación, carga).
        # Por ahora, devolvemos una lista vacía o una simulación.
        # Supongamos que NetAgent o Discover puede proveer esta info.
        # return await self.discover_agent.get_nodes_suitable_for_replication(exclude=exclude)
        # Para el simulador, devolvemos una lista simulada de nodos vecinos.
        # En un entorno real, esto debería integrarse con DiscoverAgent.
        all_known_nodes = getattr(self.net_agent, 'known_nodes', set()) # Suponiendo que NetAgent mantenga una lista
        available_nodes = list(all_known_nodes - set(exclude))
        #print(f"[Store-D] Candidatos para replicación (excluyendo {exclude}): {available_nodes}")
        return available_nodes


    def garbage_collect(self):
        """
        Realiza recolección de basura: borra archivos locales si refcount es 0 y han pasado GC_TTL segundos.
        """
        current_time = int(time.time())
        hashes_to_remove = []
        files_to_remove = []

        for obj_hash, info in self.metadata.items():
            if info["refcount"] == 0 and (current_time - info["timestamp"]) > self.gc_ttl:
                hashes_to_remove.append(obj_hash)
                files_to_remove.append(self.storage_dir / obj_hash)
                print(f"[Store-D] Programado para GC: {obj_hash}")

        for file_path in files_to_remove:
            try:
                file_path.unlink() # Borra el archivo
                print(f"[Store-D] Archivo borrado: {file_path}")
            except OSError as e:
                print(f"[Store-D] Error borrando archivo {file_path}: {e}")

        for obj_hash in hashes_to_remove:
            del self.metadata[obj_hash] # Borra la entrada de metadatos
            print(f"[Store-D] Metadato borrado: {obj_hash}")

        if hashes_to_remove:
            self._save_metadata()

    # --- Manejo de Mensajes de Red ---
    # Este método debe ser llamado por NetAgent cuando recibe un mensaje dirigido a Store-D
    async def handle_message(self, msg: Dict[str, Any]):
        """
        Maneja mensajes entrantes dirigidos al Store-D.
        Debe ser llamado por el agente de red.
        """
        msg_type = msg.get("type")
        src = msg.get("src")
        payload = msg.get("payload", {})

        if msg_type == "STORE_PUT":
            obj_hash = payload.get("hash")
            data_hex = payload.get("data")
            is_replica = payload.get("replica", False)

            if obj_hash and data_hex:
                data_bytes = bytes.fromhex(data_hex)
                received_hash = self._calculate_hash(data_bytes)
                if received_hash == obj_hash:
                    # Guardar localmente
                    file_path = self.storage_dir / obj_hash
                    with open(file_path, 'wb') as f:
                        f.write(data_bytes)

                    # Actualizar metadatos
                    if obj_hash not in self.metadata:
                        self.metadata[obj_hash] = {
                            "replicas": [src] if is_replica else [self.node_id],
                            "refcount": 0, # No incrementa refcount por replicación
                            "timestamp": int(time.time())
                        }
                    else:
                        if src not in self.metadata[obj_hash]["replicas"]:
                            self.metadata[obj_hash]["replicas"].append(src)
                        # No se incrementa refcount si es replica, solo si es un PUT inicial
                        # Si es un PUT inicial (no replica), incrementamos refcount
                        if not is_replica:
                            self.metadata[obj_hash]["refcount"] += 1

                    self._save_metadata()
                    print(f"[Store-D] Almacenado objeto {obj_hash} recibido de {src} (replica={is_replica}).")
                else:
                    print(f"[Store-D] Error: Hash recibido {received_hash} no coincide con el calculado {obj_hash}.")

        elif msg_type == "STORE_GET":
            obj_hash = payload.get("hash")
            file_path = self.storage_dir / obj_hash

            if file_path.exists():
                with open(file_path, 'rb') as f:
                    data_bytes = f.read()
                response_msg = {
                    "magic": "SOD1",
                    "type": "STORE_FOUND",
                    "src": self.node_id,
                    "dst": src,
                    "msg_id": f"found_{obj_hash}_{int(time.time())}",
                    "timestamp": int(time.time()),
                    "payload": {
                        "hash": obj_hash,
                        "data": data_bytes.hex() # Enviar como string hexadecimal
                    }
                }
                print(f"[Store-D] Enviando STORE_FOUND para {obj_hash} a {src}")
            else:
                response_msg = {
                    "magic": "SOD1",
                    "type": "STORE_NOT_FOUND",
                    "src": self.node_id,
                    "dst": src,
                    "msg_id": f"not_found_{obj_hash}_{int(time.time())}",
                    "timestamp": int(time.time()),
                    "payload": {"hash": obj_hash}
                }
                print(f"[Store-D] Enviando STORE_NOT_FOUND para {obj_hash} a {src}")

            # Enviar respuesta
            await self.net_agent.send(response_msg, reliable=False) # No es crítico, usar canal no fiable

        else:
            print(f"[Store-D] Mensaje desconocido recibido: {msg_type}")
