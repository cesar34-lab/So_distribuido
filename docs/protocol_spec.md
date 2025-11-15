docs/protocol_spec.md
Especificación del Protocolo SOD — SOD/1.0

Versión: SOD/1.0
Propósito: definir los mensajes, formatos, timeouts y reglas de comportamiento entre nodos del Sistema Operativo Descentralizado (SOD). Usado por los agentes: Discover, Net, Scheduler-D, Store-D, Health, etc.

Índice

Resumen y convenciones

Modos de transporte y puertos lógicos

Encabezado binario mínimo (formato)

Mensajes y tipos (lista)

Formato JSON (para simulador) — schema base

Mensajes comunes (ejemplos JSON)

DSL de BUSCAR (query)

Score para scheduler distribuido

QoS, prioridades y colas

ACK / retransmisión / ARQ

Firma HMAC (simulador) y validación

Fragmentación (visión general)

Timeouts, TTLs y parámetros por defecto

Códigos de error

Flujos de control (BUSCAR→ENCONTRADO; PROPUESTA→ACEPTAR/RECHAZAR→ASIGNAR)

Versionado y compatibilidad

Ubicación en repo y notas de integración

Cambios y control de versiones

1 — Resumen y convenciones

Mensajes pueden viajar en dos modos: DIFUSIÓN (no fiable) y DIRECTO (fiable con ACKs).

Para el simulador usamos JSON legible; para integración con kernel/embedded definimos un encabezado binario (compacto).

Todos los mensajes llevan un msg_id (UUIDv4), src, dst, ts (timestamp epoch float), proto y type.

Tamaño máximo payload JSON por mensaje en el simulador: 16 KB. Para datos mayores usar STORE_PUT con chunking o fragmentación.

2 — Modos de transporte y puertos lógicos

Puertos lógicos por servicio (convención):

DISCOVER = 1001

SCHEDULER = 1002

STORE = 1003

HEALTH = 1004

NET_CTRL = 1005

Modos:

DIFUSIÓN (UDP-like, no fiable): HELLO, ESTADO (gossip), eventos de descubrimiento.

DIRECTO (confiable opcional): BUSCAR, PROPUESTA, ASIGNAR, STORE_GET/PUT, CHECKPOINT_* (usa ACK + retransmisión).

3 — Encabezado binario mínimo (integración)

Formato binario (orden big-endian donde corresponde) — para uso en kernel o en transporte binario eficiente:

[ magic (4) ]  = ASCII 'SOD1'
[ version (1) ] = uint8
[ type (1) ]    = uint8 (tipo)
[ flags (1) ]   = bitmask (reliable=0x01, signed=0x02, encrypted=0x04)
[ reserved (1) ]= uint8  (for future)
[ src_len (1) ] = uint8  (len of src NodeID)
[ dst_len (1) ] = uint8  (len of dst NodeID)
[ msg_id (16) ] = UUID v4 (raw 16 bytes)
[ payload_len (4) ] = uint32 BE
[ src (src_len) ]    = bytes utf-8
[ dst (dst_len) ]    = bytes utf-8
[ payload (payload_len) ] = payload bytes (JSON or binary piece)


flags determina si el payload incluye meta.signature o se cifra.

Si payload_len > MTU, NetAgent debe fragmentar y reensamblar (ver sección 12).

4 — Tipos de mensaje (enum)
Código	Nombre
0x01	HELLO
0x02	ESTADO
0x03	BUSCAR
0x04	ENCONTRADO
0x05	PROPUESTA
0x06	ACEPTAR
0x07	RECHAZAR
0x08	ASIGNAR
0x09	STORE_PUT
0x0A	STORE_GET
0x0B	STORE_PUT_ACK
0x0C	STORE_GET_RESP
0x0D	CHECKPOINT_PUSH
0x0E	CHECKPOINT_FETCH
0x0F	PING
0x10	ACK
0x11	NODE_DOWN
0x12	ERROR
5 — Formato JSON (simulador) — esquema base

Todos los mensajes JSON siguen esta plantilla:

{
  "proto": "SOD/1.0",
  "type": "ESTADO",
  "src": "nodeA",
  "dst": "*",
  "msg_id": "uuidv4-string",
  "ts": 1700000000.123,
  "meta": {
     "signed": true,
     "signature": "...base64...",
     "node_pub": "..."   // optional
  },
  "payload": { ... }
}


dst puede ser "*" para difusión.

meta.signature opcional hasta que se integre seguridad con claves reales.

6 — Mensajes comunes — ejemplos JSON
HELLO (difusión)
{
  "proto":"SOD/1.0",
  "type":"HELLO",
  "src":"nodeA",
  "dst":"*",
  "msg_id":"6f1b9b3a-...",
  "ts":1700000000.123,
  "payload":{
    "node_id":"nodeA",
    "services":["DISCOVER","NET","STORE"],
    "boot_ts":1700000000
  }
}

ESTADO (gossip / periodic)
{
  "proto":"SOD/1.0",
  "type":"ESTADO",
  "src":"nodeA",
  "dst":"*",
  "msg_id":"...",
  "ts":1700000001.456,
  "payload":{
    "cpu_load":0.27,
    "ram_free_mb":120,
    "battery_pct":0.92,
    "rtt_ms":15,
    "tags":["gpu:false","arch:arm"],
    "reputation":0.85
  }
}

BUSCAR
{
  "proto":"SOD/1.0",
  "type":"BUSCAR",
  "src":"nodeClient",
  "dst":"nodeB",
  "msg_id":"...",
  "ts":1700000100.0,
  "payload":{
    "query": { "cpu_mips_min":700, "ram_mb_min":512, "tags":["gpu:true"] },
    "k":5,
    "ttl":3
  }
}

ENCONTRADO
{
  "proto":"SOD/1.0",
  "type":"ENCONTRADO",
  "src":"nodeB",
  "dst":"nodeClient",
  "msg_id":"...",
  "ts":1700000100.7,
  "payload":{
    "candidates":[
      { "node_id":"nodeX", "cpu_load":0.2, "ram_free_mb":800, "rtt_ms":10, "reputation":0.9, "tags":["gpu:true"] }
    ]
  }
}

PROPUESTA
{
  "proto":"SOD/1.0",
  "type":"PROPUESTA",
  "src":"nodeClient",
  "dst":"nodeX",
  "msg_id":"...",
  "payload":{
    "task_id":"task123",
    "task_hash":"sha256:abcd...",
    "score":0.82,
    "deadline":1700001200,
    "resources": { "cpu_mips":500, "ram_mb":256 }
  }
}

ACEPTAR / RECHAZAR
{
  "proto":"SOD/1.0",
  "type":"ACEPTAR",
  "src":"nodeX",
  "dst":"nodeClient",
  "msg_id":"...",
  "payload":{"task_id":"task123", "node_id":"nodeX"}
}

ASIGNAR
{
  "proto":"SOD/1.0",
  "type":"ASIGNAR",
  "src":"nodeClient",
  "dst":"nodeX",
  "msg_id":"...",
  "payload":{"task_id":"task123", "checkpoint_hash":"sha256:..." }
}

STORE_PUT / STORE_GET (checkpoint / blobs)

STORE_PUT payload: { "hash":"sha256:...", "chunk_index":0, "total_chunks":N, "data": "<base64 chunk>" } (o enviar data por stream / chunking).

STORE_GET payload: { "hash":"sha256:..." }

STORE_GET_RESP payload: { "hash":"sha256:...", "found": true, "data":"<base64>" }

7 — DSL de BUSCAR (consulta)

Campo payload.query admite:

cpu_mips_min (int)

ram_mb_min (int)

battery_min_pct (float 0..1)

tags puede ser:

lista ["gpu:true","arch:arm"] (AND por default) o

objeto { "gpu": true, "arch": ["arm","arm64"] } (más expresivo)

Los campos _min y _max son aceptados.

k número de candidatos deseados (int).

ttl profundidad de forwarding (int).

Interpretación: Discover/Net filtran por capacidad y devuelven hasta k candidatos ordenados por un score (sección 8).

8 — Score (fórmula para ranking por Scheduler-D)

Se propone:

Score = w1*(1 - normalized_cpu) + w2*reputation + w3*normalized_ram + w4*(1 - normalized_rtt) + tag_bonus


normalized_cpu = min(cpu_load, 1.0) (cpu_load en [0,1])

normalized_ram = min(ram_free_mb / required_ram, 1.0)

normalized_rtt = min(rtt_ms / 200, 1.0) (cap 200ms)

Pesos sugeridos: w1=0.35, w2=0.25, w3=0.25, w4=0.15

tag_bonus = 0.2 si cumple tags críticos, 0 si no.

Nota: valores y pesos son configurables por deploy.

9 — QoS, prioridades y colas

Tres colas en NetAgent por prioridad:

CTRL (más alto): mensajes como PROPUESTA, ASIGNAR, STORE_* críticos.

DISCOVER: HELLO, ESTADO, BUSCAR, ENCONTRADO.

DATA (más bajo): payloads grandes, transferencias no críticas.

NetAgent consume siempre CTRL > DISCOVER > DATA.

10 — ACK / retransmisión / ARQ

Mensajes directos con reliable=true requieren ACK: enviar → esperar ACK (msg_id) dentro de ACK_TIMEOUT.

Reintentar RETRANSMIT_MAX veces con backoff_with_jitter(base=ACK_TIMEOUT, attempt=i).

Si no se recibe ACK tras RETRANSMIT_MAX, devolver ERROR con ERR_TIMEOUT.

ACK format (JSON):

{ "proto":"SOD/1.0", "type":"ACK", "src":"nodeB", "dst":"nodeA", "msg_id":"uuid-of-original" }

11 — Firma HMAC (simulador)

Para evitar falsificaciones en simulador, se usa HMAC-SHA256 con clave simétrica por nodo (archivo de configuración o KVS del simulador).

meta.signature = base64(HMAC(key, msg_id + '.' + compact_payload_json))

Verificación: remite a verify_message_hmac(key, msg_id, payload, signature) — comprobar hmac.compare_digest.

Mensajes críticos que deben firmarse: PROPUESTA, ASIGNAR, CHECKPOINT_PUSH, STORE_PUT (al menos metadata).

Campo meta.signed booleano presente.

Nota: en producción usar firma asimétrica (RSA/ECDSA) y PKI; HMAC es solución temporal para Fase 2.

12 — Fragmentación (visión general)

Si payload_len > MTU, NetAgent fragmenta en fragment_count piezas: cada fragmento incluye header con frag_index y frag_total.

Reensamblado en destino: esperar todos frag_total o timeout FRAGMENT_TIMEOUT → si faltan, informar ERR_TIMEOUT.

Alternativa para blobs grandes: usar STORE_PUT en chunks de tamaño seguro (ej. 4 KB) y enviar solo hashes por mensaje de control.

13 — Timeouts, TTLs y parámetros por defecto

Parámetros recomendados (configurables):

HELLO_INTERVAL = 2.0 s

ESTADO_INTERVAL = 5.0 s

BUSCAR_RESPONSE_TIMEOUT = 1.5 s

PROPUESTA_RESPONSE_TIMEOUT = 2.0 s

ACK_TIMEOUT = 0.8 s

RETRANSMIT_MAX = 3

NODE_DEAD_TIMEOUT = 3 * HELLO_INTERVAL

CACHE_TTL_BUSCAR = 15 s

RESOURCE_ENTRY_TTL = NODE_DEAD_TIMEOUT

FRAGMENT_TIMEOUT = 5 s

BACKOFF_BASE = 0.2 s (para retransmisión exponencial)

14 — Códigos de error

Mensaje ERROR payload contiene { "code": <int>, "message":"..." }.

Code	Const	Significado
1	ERR_TIMEOUT	Timeout en operación / no ACK
2	ERR_BUSY	Nodo saturado / rechazó por sobrecarga
3	ERR_UNAUTHORIZED	Firma inválida / no autorizado
4	ERR_NOT_FOUND	Objeto no encontrado en Store
5	ERR_INVALID	Mensaje inválido / formato incorrecto
15 — Flujos de control críticos
15.1 — BUSCAR → ENCONTRADO → PROPUESTA (cliente) → ACEPTAR/RECHAZAR (candidato) → ASIGNAR

Cliente envía BUSCAR(query,k) (reliable/directo) a nodo Discover local o vecino.

Discover responde con ENCONTRADO(candidates[]) (directo).

Cliente calcula score y envía PROPUESTA a top-m candidatos (reliable).

Candidato responde ACEPTAR o RECHAZAR (o no responde → timeout).

Cliente recibe ACEPTARs y selecciona ganador → envía ASIGNAR(task_id, checkpoint_hash?) (reliable).

Cliente monitorea ejecución via HEALTH/heartbeats y Store-D para checkpoint fetch.

15.2 — Checkpoint push/pull

Ejecuter local hace CHECKPOINT_PUSH para Store-D (reliable, chunked).

Scheduler puede pedir CHECKPOINT_FETCH a Store-D para restaurar en nuevo nodo.

16 — Versionado y compatibilidad

Campo proto determina versión. Si un nodo recibe proto > su versión soportada → enviar ERROR con ERR_INVALID y desconectar.

Cambios incompatibles deben incrementar versión SOD/2.0.

17 — Ubicación en repo y notas de integración

docs/protocol_spec.md — este archivo (colocarlo en docs/).

Código utilitario (serialización / firma / validación): agents/protocols.py.

NetAgent debe implementar: envío JSON (difusión/directo), retransmisión, fragmentación básica (si aplica), y prioridad de colas.

DiscoverAgent y SchedulerD deben adherirse estrictamente al formato BUSCAR/ENCONTRADO/PROPUESTA/ASIGNAR.

libs/sod_api debe exponer helpers para crear mensajes y firmarlos (usar las utilidades HMAC para el simulador).

18 — Cambios y control de versiones

Commit / Pull requests que cambien este documento deben:

Incrementar PROTOCOL_VERSION si hay cambios incompatibles.

Incluir ejemplos actualizados y tests en tests/test_protocols.py.

Añadir migración de parsers en agents/protocols.py.

Anexos — Utilidades rápidas (mini-reference)
Backoff con jitter (ejemplo)
def backoff_with_jitter(base, attempt, jitter_factor=0.1):
    backoff = base * (2 ** attempt)
    jitter = backoff * jitter_factor
    return backoff + random.uniform(-jitter, jitter)

Firma HMAC (pseudocódigo)

signature = base64( HMAC_SHA256( key, msg_id + '.' + compact(payload_json) ) )

Últimos pasos recomendados (inmediatos)

Copiar este archivo a docs/protocol_spec.md en el repo.

Añadir agents/protocols.py (módulo utilitario con funciones de sign/verify, builder/parsers JSON). (Si no lo tienes, pide que lo genere ahora.)

Implementar tests tests/test_protocols.py (ya preparado).

Implementar NetAgent y DiscoverAgent que usen HELLO/ESTADO y la firma HMAC.

Mantener protocol_spec.md como fuente de verdad: cualquier cambio requiere actualización del doc y tests.

Historial de versiones (registro)

SOD/1.0 — inicial: mensajes JSON y encabezado binario, HMAC simulado, ARQ básico, fragmentación conceptual.
## Mensajes del Agente Store-D

### `STORE_PUT`

- **Tipo:** `STORE_PUT`
- **Descripción:** Solicita almacenar un objeto en un nodo.
- **Origen:** Nodo que posee el objeto o está replicando.
- **Destino:** Nodo destino.
- **Payload:**
  - `hash` (string): Hash SHA256 del objeto.
  - `data` (string): Contenido del objeto codificado en hexadecimal.
  - `replica` (bool): `true` si el mensaje es una réplica, `false` si es un `put` inicial.
- **Ejemplo:**
  ```json
  {
    "magic": "SOD1",
    "type": "STORE_PUT",
    "src": "nodeA",
    "dst": "nodeB",
    "msg_id": "rep_abc123_nodeB_1690000000",
    "timestamp": 1690000000,
    "payload": {
      "hash": "abc123...",
      "data": "48656c6c6f20576f726c64",
      "replica": true
    }
  }