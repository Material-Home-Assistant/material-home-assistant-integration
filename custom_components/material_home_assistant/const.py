"""Costanti per l'integrazione Material Home Assistant."""

DOMAIN = "material_home_assistant"

# URL base del backend.
# NOTA: Se HA gira su Docker/VM, "localhost" non funzionerà.
# Usa l'IP della macchina dove gira il backend (es. http://192.168.1.10:8080)
#API_BASE_URL = "http://localhost:8080"
API_BASE_URL = "http://192.168.1.90:8080"

# Endpoint
API_ENDPOINT_HANDSHAKE = "/api/v1/license/handshake"

# Chiavi per il file di storage persistente (per secret_key)
STORAGE_VERSION = 1
STORAGE_KEY = f"{DOMAIN}_auth"

# Costanti di configurazione
CONF_EMAIL = "email"
CONF_TOKEN = "token"
CONF_SECRET_KEY = "secret_key"
CONF_STATUS = "status"
CONF_PLAN = "plan"
# Nuova costante per gestire l'URL nel flusso di configurazione
CONF_RESOURCE_URL = "resource_url"