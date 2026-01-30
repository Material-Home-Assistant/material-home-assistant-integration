/**
 * MATERIAL HOME ASSISTANT - LOADER INTELLIGENTE
 * * Questo script gestisce il caricamento dinamico del componente protetto.
 * 1. Tenta di ottenere l'URL dell'ultima versione dal backend HA.
 * 2. Scarica il componente e lo salva nella Cache API del browser (non su disco HA).
 * 3. Se internet è assente, recupera istantaneamente l'ultima versione funzionante dalla cache.
 */

(async function () {
  const DOMAIN = "material_home_assistant";
  const API_ENDPOINT = "/api/material_home_assistant/get_url";
  const CACHE_NAME = `${DOMAIN}-resource-cache-v1`;
  const RESOURCE_KEY = "main_component.js";

  const logPrefix = `[${DOMAIN}]`;

  console.info(
    `%c ${logPrefix} 🚀 Loader avviato`,
    "color:#2196f3;font-weight:bold;",
  );

  function getAuthToken() {
    // Cerca l'oggetto hass nel documento
    const main = document.querySelector("home-assistant");
    if (main && main.auth && main.auth.accessToken) {
      return main.auth.accessToken;
    }
    // Fallback per alcune versioni/configurazioni
    if (window.hassConnection) {
      return window.hassConnection.then((conn) => conn.auth.accessToken);
    }
    return null;
  }

  async function loadResource() {
    let componentBlobUrl = null;
    const startTime = performance.now();

    console.debug(`${logPrefix} Configurazione`, {
      API_ENDPOINT,
      CACHE_NAME,
      RESOURCE_KEY,
    });

    try {
      /* ===========================
       * STEP 1 - FETCH BACKEND
       * =========================== */
      console.info(`${logPrefix} 🔐 STEP 1: Richiesta URL al backend`);

      const token = await getAuthToken();

      const headers = {
        "Content-Type": "application/json",
      };

      // Se abbiamo trovato il token, lo aggiungiamo come Bearer Auth
      if (token) {
        headers["Authorization"] = `Bearer ${token}`;
      }

      const apiResponse = await fetch(API_ENDPOINT, {
        method: "GET",
        headers: headers,
      });

      if (apiResponse.status === 401) {
        throw new Error("Accesso negato: Token non valido o mancante");
      }

      console.debug(`${logPrefix} Backend response`, {
        ok: apiResponse.ok,
        status: apiResponse.status,
      });

      if (!apiResponse.ok) {
        throw new Error(`Backend error (${apiResponse.status})`);
      }

      const data = await apiResponse.json();
      const remoteUrl = data?.url;

      if (!remoteUrl) {
        throw new Error("URL remoto mancante nella risposta API");
      }

      console.info(`${logPrefix} 🌍 URL remoto ricevuto, url: ${remoteUrl}`);
      console.debug(`${logPrefix} remoteUrl`, remoteUrl);

      /* ===========================
       * STEP 2 - FETCH CDN
       * =========================== */
      console.info(`${logPrefix} 📥 STEP 2: Download componente remoto`);

      const componentResponse = await fetch(remoteUrl);

      console.debug(`${logPrefix} CDN response`, {
        ok: componentResponse.ok,
        status: componentResponse.status,
      });

      if (!componentResponse.ok) {
        throw new Error(`CDN download error (${componentResponse.status})`);
      }

      /* ===========================
       * STEP 2a - CACHE UPDATE
       * =========================== */
      console.info(`${logPrefix} 💾 Aggiornamento cache browser`);

      const cache = await caches.open(CACHE_NAME);
      await cache.put(RESOURCE_KEY, componentResponse.clone());

      console.debug(`${logPrefix} Cache aggiornata`, {
        cache: CACHE_NAME,
        key: RESOURCE_KEY,
      });

      /* ===========================
       * STEP 2b - BLOB CREATION
       * =========================== */
      const blob = await componentResponse.blob();
      componentBlobUrl = URL.createObjectURL(blob);

      console.info(
        `%c ${logPrefix} ✅ Caricato da remoto e sincronizzato in cache`,
        "color:#4caf50;",
      );
    } catch (error) {
      /* ===========================
       * STEP 3 - FALLBACK CACHE
       * =========================== */
      console.warn(
        `${logPrefix} ⚠️ Modalità OFFLINE / FALLBACK`,
        error.message,
      );

      try {
        const cache = await caches.open(CACHE_NAME);
        const cachedResponse = await cache.match(RESOURCE_KEY);

        console.debug(`${logPrefix} Cache lookup`, {
          found: !!cachedResponse,
        });

        if (!cachedResponse) {
          throw new Error("Nessuna risorsa in cache");
        }

        const blob = await cachedResponse.blob();
        componentBlobUrl = URL.createObjectURL(blob);

        console.info(
          `%c ${logPrefix} 📦 Caricato dalla cache locale`,
          "color:#ff9800;",
        );
      } catch (cacheError) {
        console.error(
          `%c ${logPrefix} ❌ ERRORE CRITICO`,
          "color:#f44336;font-weight:bold;",
          cacheError.message,
        );
      }
    }

    /* ===========================
     * STEP 4 - SCRIPT INJECTION
     * =========================== */
    if (componentBlobUrl) {
      console.info(`${logPrefix} 🧩 STEP 4: Iniezione script nel DOM`);

      const script = document.createElement("script");
      script.type = "module";
      script.src = componentBlobUrl;

      script.onload = () => {
        console.info(`${logPrefix} ✅ Script caricato correttamente`);
        URL.revokeObjectURL(componentBlobUrl);

        console.debug(`${logPrefix} Blob URL revocato`);
        console.info(
          `${logPrefix} ⏱️ Tempo totale:`,
          `${(performance.now() - startTime).toFixed(2)}ms`,
        );
      };

      script.onerror = (e) => {
        console.error(`${logPrefix} ❌ Errore caricamento script`, e);
      };

      document.head.appendChild(script);
    } else {
      console.error(
        `${logPrefix} ❌ Impossibile iniettare lo script (URL nullo)`,
      );
    }
  }

  loadResource();
})();
