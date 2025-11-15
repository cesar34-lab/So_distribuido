# agents/security/security.py

import hmac
import hashlib
import json
from typing import Dict, Any, Optional
import base64

class SecurityModule:
    def __init__(self, node_id: str, keys_config_path: str = "configs/node_keys.json"):
        """
        Inicializa el módulo de seguridad.

        Args:
            node_id (str): ID del nodo actual.
            keys_config_path (str): Ruta al archivo JSON con las claves por nodo.
        """
        self.node_id = node_id
        self.node_keys = self._load_keys(keys_config_path)
        self.own_key = bytes.fromhex(self.node_keys.get(node_id, ""))

    def _load_keys(self, path: str) -> Dict[str, str]:
        """Carga las claves simétricas desde el archivo JSON."""
        try:
            with open(path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"[SecurityModule] ADVERTENCIA: Archivo de claves {path} no encontrado. Se usarán claves vacías.")
            return {}
        except json.JSONDecodeError as e:
            print(f"[SecurityModule] ERROR: Error al leer JSON de claves {path}: {e}")
            return {}

    def sign_message(self, msg: Dict[str, Any], dst_node_id: Optional[str] = None) -> str:
        """
        Genera un HMAC para un mensaje.

        Args:
            msg (Dict[str, Any]): El mensaje a firmar (sin el HMAC).
            dst_node_id (str, optional): ID del nodo destino (opcional, para claves por par).

        Returns:
            str: El HMAC en formato hexadecimal.
        """
        if not self.own_key:
            print(f"[SecurityModule] ADVERTENCIA: No se encontró clave para firmar mensaje desde {self.node_id}.")
            return ""

        # Crear una copia del mensaje sin HMAC para calcular el hash
        # Asumimos que el HMAC se añade DESPUÉS de calcularlo
        msg_to_sign = msg.copy()
        # msg_to_sign.pop('hmac', None) # Si el HMAC ya estuviera en el payload, lo quitaríamos

        # Serializar el mensaje (payload y otros campos relevantes) como bytes
        # La serialización debe ser determinista (mismo orden de claves)
        # Incluimos src, dst, type, payload, msg_id, timestamp para mayor seguridad
        message_str = json.dumps(msg_to_sign, sort_keys=True, separators=(',', ':'))
        message_bytes = message_str.encode('utf-8')

        # Calcular HMAC usando SHA256
        # La clave es la del nodo emisor (self.own_key)
        calculated_hmac = hmac.new(self.own_key, message_bytes, hashlib.sha256)

        # Devolver el HMAC en formato hexadecimal
        return calculated_hmac.hexdigest()

    def verify_message(self, msg: Dict[str, Any], src_node_id: str) -> bool:
        """
        Verifica la integridad y autenticidad de un mensaje firmado.

        Args:
            msg (Dict[str, Any]): El mensaje recibido, incluyendo el HMAC.
            src_node_id (str): ID del nodo que envió el mensaje.

        Returns:
            bool: True si el HMAC es válido, False en caso contrario.
        """
        stored_hmac = msg.get("hmac", "")
        if not stored_hmac:
            print(f"[SecurityModule] ERROR: Mensaje recibido de {src_node_id} no tiene HMAC.")
            return False

        # Obtener la clave del nodo emisor
        sender_key_hex = self.node_keys.get(src_node_id)
        if not sender_key_hex:
            print(f"[SecurityModule] ERROR: No se encontró clave para verificar mensaje de {src_node_id}.")
            return False
        sender_key = bytes.fromhex(sender_key_hex)

        # Crear una copia del mensaje sin el HMAC para calcular el hash
        msg_to_verify = msg.copy()
        msg_to_verify.pop('hmac', None) # Remover el HMAC del mensaje original

        # Serializar el mensaje (sin HMAC) como bytes, con el mismo método que sign_message
        message_str = json.dumps(msg_to_verify, sort_keys=True, separators=(',', ':'))
        message_bytes = message_str.encode('utf-8')

        # Calcular HMAC usando la clave del emisor
        calculated_hmac = hmac.new(sender_key, message_bytes, hashlib.sha256)

        # Comparar el HMAC calculado con el almacenado
        # Usar hmac.compare_digest para prevenir ataques de temporización
        return hmac.compare_digest(calculated_hmac.hexdigest(), stored_hmac)
