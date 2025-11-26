# agents/store_d/store.py (Modificaciones sugeridas)

# ... (importaciones existentes) ...
import os
import json
import hashlib
import time
import asyncio
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
import uuid # Para generar msg_id en mensajes de red

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
        self.net_agent = net_agent # <--- Nuevo parámetro
        self.storage_dir = Path(storage_dir)
        self.meta_file_path = Path(meta_file)
        self.r_copies = r_copies
        self.gc_ttl = gc_ttl

        # Crear directorio de almacenamiento local si no existe
        self.storage_dir.mkdir(exist_ok=True)

        # Cargar o inicializar metadatos
        self.metadata: Dict[str, Any] = self._load_metadata()

        # --- Registrar este agente como handler en NetAgent ---
        self.net_agent.add_handler(self.handle_message)

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
            with open(file_path, 'rb') as f:
                return f.read()

        # 2. Buscar remotamente
        print(f"[Store-D] No encontrado localmente: {obj_hash}. Buscando en la red...")
        # Usar nodos conocidos de NetAgent
        candidate_nodes = [n for n in self.net_agent.get_known_nodes() if n != self.node_id]

        if not candidate_nodes:
            print(f"[Store-D] No hay nodos conocidos para buscar {obj_hash}")
            return None

        for node_id in candidate_nodes:
            if node_id == self.node_id:
                continue # Ya verificamos localmente

            print(f"[Store-D] Intentando obtener {obj_hash} de {node_id}")
            # Enviar mensaje STORE_GET usando send_to_node_id
            request_msg_payload = {
                "hash": obj_hash
            }

            try:
                # Enviar el mensaje a través de NetAgent usando node_id
                msg_id_sent = await self.net_agent.send_to_node_id(
                    node_id, "STORE_GET", request_msg_payload, reliable=False, qos='DATA'
                )
                if not msg_id_sent:
                    print(f"[Store-D] Fallo al enviar STORE_GET a {node_id}")
                    continue

                # Aquí necesitamos un mecanismo para esperar la respuesta específica.
                # Usaremos una cola o diccionario para asociar la solicitud con la respuesta futura.
                # Crear un asyncio.Event para esta solicitud
                response_event = asyncio.Event()
                response_data = None
                # Registrar la solicitud pendiente
                if not hasattr(self, '_pending_get_requests'):
                    self._pending_get_requests = {}
                self._pending_get_requests[msg_id_sent] = {'event': response_event, 'data': None, 'node_id': node_id}

                # Esperar la respuesta con timeout
                try:
                    await asyncio.wait_for(response_event.wait(), timeout=5.0)
                    # La respuesta debería haber sido manejada por handle_message y haber liberado el evento
                    stored_response = self._pending_get_requests.pop(msg_id_sent, None)
                    if stored_response and stored_response['data']:
                        data_bytes = stored_response['data']
                        print(f"[Store-D] Obtenido {obj_hash} de {node_id}")

                        # Guardar localmente
                        local_file_path = self.storage_dir / obj_hash
                        with open(local_file_path, 'wb') as f:
                            f.write(data_bytes)

                        # Actualizar metadatos localmente
                        if obj_hash not in self.metadata:
                            self.metadata[obj_hash] = {
                                "replicas": [node_id],
                                "refcount": 1,
                                "timestamp": int(time.time())
                            }
                        else:
                            self.metadata[obj_hash]["refcount"] += 1
                            if node_id not in self.metadata[obj_hash]["replicas"]:
                                self.metadata[obj_hash]["replicas"].append(node_id)

                        self._save_metadata()
                        return data_bytes
                    else:
                        print(f"[Store-D] No se recibió datos válidos para {msg_id_sent} de {node_id}")
                except asyncio.TimeoutError:
                    print(f"[Store-D] Timeout esperando respuesta de {node_id} para {obj_hash} (msg_id: {msg_id_sent})")
                    self._pending_get_requests.pop(msg_id_sent, None) # Limpiar entrada
                    continue # Intentar con el siguiente nodo
            except Exception as e:
                print(f"[Store-D] Error obteniendo {obj_hash} de {node_id}: {e}")
                # Limpiar entrada si es necesario
                self._pending_get_requests.pop(msg_id_sent, None) # Asumiendo msg_id_sent existe aquí
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
            # Supongamos que NetAgent puede resolver node_id -> addr internamente
            # replicate_msg = {
            #     "magic": "SOD1",
            #     "type": "STORE_PUT",
            #     "src": self.node_id,
            #     "dst": node_id, # <-- Requiere resolución en NetAgent
            #     "msg_id": f"rep_{obj_hash}_{node_id}_{int(time.time())}",
            #     "timestamp": int(time.time()),
            #     "payload": {
            #         "hash": obj_hash,
            #         "data": data_bytes.hex(), # Enviar como string hexadecimal
            #         "replica": True
            #     }
            # }
            # await self.net_agent.send_to_node_id(node_id, replicate_msg["type"], replicate_msg["payload"], reliable=True)
            # Por ahora, simulamos que no se puede enviar sin el mapeo.
            print(f"[Store-D] No se puede replicar a {node_id} sin mapeo de dirección. (Pendiente implementar en NetAgent)")

    async def _ensure_replication(self, obj_hash: str):
        """
        Verifica si el número de réplicas es menor a R y, si es así, intenta replicar.
        Debe ser llamado asincrónicamente.
        """
        current_replicas = set(self.list_replicas(obj_hash))
        if len(current_replicas) < self.r_copies:
            print(f"[Store-D] Iniciando replicación para {obj_hash} (actual: {len(current_replicas)}, objetivo: {self.r_copies})")
            # Usar nodos conocidos de NetAgent
            all_known_nodes = self.net_agent.get_known_nodes()
            candidate_nodes = [n for n in all_known_nodes if n not in current_replicas and n != self.node_id]
            nodes_to_replicate_to = candidate_nodes[:self.r_copies - len(current_replicas)]
            if nodes_to_replicate_to:
                await self.replicate(obj_hash, nodes_to_replicate_to)
            else:
                print(f"[Store-D] No se encontraron nodos candidatos para replicar {obj_hash}.")

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
    async def handle_message(self, msg: Dict[str, Any], addr: Tuple[str, int]):
        """
        Maneja mensajes entrantes dirigidos al Store-D.
        Debe ser llamado por el agente de red.
        """
        msg_type = msg.get("type")
        src = msg.get("src")
        original_msg_id = msg.get("msg_id") # <-- Obtener el msg_id ORIGINAL del mensaje recibido (STORE_GET)
        payload = msg.get("payload", {})

        # Añadir src a nodos conocidos de NetAgent
        if src and src != self.node_id:
            self.net_agent.add_known_node(src)

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
                response_msg_payload = {
                    "hash": obj_hash,
                    "data": data_bytes.hex(), # Enviar como string hexadecimal
                    "request_id": original_msg_id # <-- INCLUIR EL MSG_ID ORIGINAL
                }
                print(f"[Store-D] Enviando STORE_FOUND para {obj_hash} a {src}, respuesta a {original_msg_id}")
                # Enviar respuesta - Requiere que NetAgent maneje dst como node_id
                try:
                    await self.net_agent.send_to_node_id(src, "STORE_FOUND", response_msg_payload, reliable=False, qos='DATA')
                    print(f"[Store-D] (Real) Enviado STORE_FOUND a {src}")
                except Exception as e_send:
                    print(f"[Store-D] Error al enviar STORE_FOUND a {src}: {e_send}")
            else:
                response_msg_payload = {
                    "hash": obj_hash,
                    "request_id": original_msg_id # <-- INCLUIR EL MSG_ID ORIGINAL
                }
                print(f"[Store-D] Enviando STORE_NOT_FOUND para {obj_hash} a {src}, respuesta a {original_msg_id}")
                try:
                    await self.net_agent.send_to_node_id(src, "STORE_NOT_FOUND", response_msg_payload, reliable=False, qos='DATA')
                    print(f"[Store-D] (Real) Enviado STORE_NOT_FOUND a {src}")
                except Exception as e_send:
                    print(f"[Store-D] Error al enviar STORE_NOT_FOUND a {src}: {e_send}")

        elif msg_type == "STORE_FOUND":
            # Este es el mensaje de respuesta a un STORE_GET
            obj_hash = payload.get("hash")
            data_hex = payload.get("data")
            request_id = payload.get("request_id") # <-- Asumimos que se incluye
            if obj_hash and data_hex and request_id:
                try:
                    data_bytes = bytes.fromhex(data_hex)
                    received_hash = self._calculate_hash(data_bytes)
                    if received_hash == obj_hash:
                        # Buscar la solicitud pendiente asociada a este request_id
                        if request_id in self._pending_get_requests:
                            pending_req = self._pending_get_requests[request_id]
                            pending_req['data'] = data_bytes
                            pending_req['event'].set() # Liberar el evento de espera
                            print(f"[Store-D] Recibida respuesta para solicitud {request_id} de {src}.")
                        else:
                            print(f"[Store-D] STORE_FOUND recibido para solicitud desconocida {request_id} de {src}.")
                    else:
                        print(f"[Store-D] Error en STORE_FOUND: Hash recibido {received_hash} no coincide con {obj_hash}.")
                except Exception as e_parse:
                    print(f"[Store-D] Error al procesar STORE_FOUND: {e_parse}")
            else:
                print(f"[Store-D] STORE_FOUND recibido sin hash, data o request_id válidos.")

        elif msg_type == "STORE_NOT_FOUND":
            # Este es el mensaje de respuesta a un STORE_GET
            obj_hash = payload.get("hash")
            request_id = payload.get("request_id") # <-- Asumimos que se incluye
            if obj_hash and request_id:
                # Buscar la solicitud pendiente
                if request_id in self._pending_get_requests:
                    pending_req = self._pending_get_requests[request_id]
                    # No hay data, pero marcamos que la respuesta fue recibida (y fue negativa)
                    pending_req['event'].set() # Liberar el evento de espera
                    print(f"[Store-D] Recibido STORE_NOT_FOUND para solicitud {request_id} de {src}.")
                else:
                    print(f"[Store-D] STORE_NOT_FOUND recibido para solicitud desconocida {request_id} de {src}.")
            else:
                print(f"[Store-D] STORE_NOT_FOUND recibido sin hash o request_id válidos.")

        else:
            print(f"[Store-D] Mensaje desconocido recibido: {msg_type}")

# ... (resto del archivo) ...