import pytest
import tempfile
import json
import os
from agents.security.security import SecurityModule

# --- Setup para pruebas ---

@pytest.fixture
def temp_keys_file():
    """Crea un archivo temporal de claves para pruebas."""
    keys_data = {
        "nodeA": "a1b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef123456",
        "nodeB": "f0e0d0c0b0a09876543210abcdefabcdefabcdefabcdefabcdefabcdefabcd"
    }
    temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json')
    json.dump(keys_data, temp_file)
    temp_file.close()
    yield temp_file.name
    os.unlink(temp_file.name)

# --- Tests ---

def test_sign_and_verify_valid(temp_keys_file):
    """Prueba que un mensaje firmado por un nodo sea verificado correctamente por otro."""
    # Nodo A firma un mensaje
    sec_mod_a = SecurityModule(node_id="nodeA", keys_config_path=temp_keys_file)
    msg_to_sign = {
        "magic": "SOD1",
        "type": "PROPUESTA",
        "src": "nodeA",
        "dst": "nodeC",
        "msg_id": "prop_abc_123",
        "timestamp": 1234567890,
        "payload": {"task_id": "task_001", "score": 0.85}
    }
    calculated_hmac = sec_mod_a.sign_message(msg_to_sign)
    assert calculated_hmac != ""

    # Agregar HMAC al mensaje
    signed_msg = msg_to_sign.copy()
    signed_msg["hmac"] = calculated_hmac

    # Nodo B (con las mismas claves) verifica el mensaje de A
    sec_mod_b = SecurityModule(node_id="nodeB", keys_config_path=temp_keys_file)
    is_valid = sec_mod_b.verify_message(signed_msg, src_node_id="nodeA")
    assert is_valid


def test_verify_invalid_modified_payload(temp_keys_file):
    """Prueba que un mensaje con payload modificado sea rechazado."""
    sec_mod_a = SecurityModule(node_id="nodeA", keys_config_path=temp_keys_file)
    msg_to_sign = {
        "magic": "SOD1",
        "type": "ASIGNAR",
        "src": "nodeA",
        "dst": "nodeB",
        "msg_id": "assign_xyz_789",
        "timestamp": 1234567891,
        "payload": {"task_id": "task_002", "binary": "abc123"}
    }
    calculated_hmac = sec_mod_a.sign_message(msg_to_sign)

    signed_msg = msg_to_sign.copy()
    signed_msg["hmac"] = calculated_hmac

    # Modificar el payload
    signed_msg["payload"]["binary"] = "modified_payload"

    sec_mod_b = SecurityModule(node_id="nodeB", keys_config_path=temp_keys_file)
    is_valid = sec_mod_b.verify_message(signed_msg, src_node_id="nodeA")
    assert not is_valid


def test_verify_invalid_wrong_node_key(temp_keys_file):
    """Prueba que un mensaje firmado con la clave incorrecta sea rechazado."""
    sec_mod_a = SecurityModule(node_id="nodeA", keys_config_path=temp_keys_file)
    msg_to_sign = {
        "magic": "SOD1",
        "type": "CHECKPOINT_PUSH",
        "src": "nodeA",
        "dst": "nodeC",
        "msg_id": "chkpt_123",
        "timestamp": 1234567892,
        "payload": {"task_id": "task_003", "hash": "def456"}
    }
    # Simular que el mensaje fue firmado con la clave de nodeB en lugar de nodeA
    # Esto no es trivial hacerlo directamente con la API actual sin manipular internamente.
    # Una forma es firmar con A, luego cambiar el src_node_id en la verificación.
    calculated_hmac_by_a = sec_mod_a.sign_message(msg_to_sign)

    signed_msg_by_a = msg_to_sign.copy()
    signed_msg_by_a["hmac"] = calculated_hmac_by_a
    # Cambiar el src para que parezca que vino de nodeB (pero la firma es de A)
    signed_msg_by_a["src"] = "nodeB"

    sec_mod_b = SecurityModule(node_id="nodeB", keys_config_path=temp_keys_file)
    # Verificar como si viniera de nodeB, debería fallar porque la firma no coincide con la clave de B
    is_valid = sec_mod_b.verify_message(signed_msg_by_a, src_node_id="nodeB")
    # La verificación falla porque:
    # 1. Se toma la clave de nodeB
    # 2. Se calcula el HMAC del mensaje (sin el HMAC original) usando la clave de nodeB
    # 3. Se compara con el HMAC que fue calculado con la clave de nodeA
    # 4. Son diferentes -> False
    assert not is_valid

    # Otra prueba: mensaje firmado por A, verificado como si viniera de A (debe pasar)
    signed_msg_by_a_correct_src = msg_to_sign.copy()
    signed_msg_by_a_correct_src["hmac"] = calculated_hmac_by_a
    signed_msg_by_a_correct_src["src"] = "nodeA" # src correcto
    is_valid_correct = sec_mod_b.verify_message(signed_msg_by_a_correct_src, src_node_id="nodeA")
    assert is_valid_correct


def test_verify_no_hmac(temp_keys_file):
    """Prueba que un mensaje sin HMAC sea rechazado."""
    sec_mod_b = SecurityModule(node_id="nodeB", keys_config_path=temp_keys_file)
    msg_without_hmac = {
        "magic": "SOD1",
        "type": "ASIGNAR",
        "src": "nodeA",
        "dst": "nodeB",
        "msg_id": "assign_no_hmac",
        "timestamp": 1234567893,
        "payload": {"task_id": "task_004"}
    }
    is_valid = sec_mod_b.verify_message(msg_without_hmac, src_node_id="nodeA")
    assert not is_valid


def test_verify_no_key_for_sender(temp_keys_file):
    """Prueba que un mensaje de un nodo sin clave conocida sea rechazado."""
    sec_mod_b = SecurityModule(node_id="nodeB", keys_config_path=temp_keys_file)
    msg_with_hmac = {
        "magic": "SOD1",
        "type": "ASIGNAR",
        "src": "nodeUnknown",
        "dst": "nodeB",
        "msg_id": "assign_unknown",
        "timestamp": 1234567894,
        "payload": {"task_id": "task_005"},
        "hmac": "dummy_hmac_that_will_fail_anyway"
    }
    is_valid = sec_mod_b.verify_message(msg_with_hmac, src_node_id="nodeUnknown")
    assert not is_valid


# Correr con: pytest tests/test_security.py -v -s
# Asegúrate de tener asyncio_mode = "auto" en pytest.ini o pyproject.toml si se usan async