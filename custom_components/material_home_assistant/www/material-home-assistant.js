(async function () {
  const DOMAIN = "material_home_assistant";
  const API_ENDPOINT = "/api/material_home_assistant/get_url";
  const CACHE_NAME = `${DOMAIN}-resource-cache-v1`;
  const RESOURCE_KEY = "main_component.js";
  const logPrefix = `[${DOMAIN}]`;

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
    const cache = await caches.open(CACHE_NAME);
    const cachedResponse = await cache.match(RESOURCE_KEY);
    let alreadyLoaded = false;

    // --- 1. CARICAMENTO IMMEDIATO DALLA CACHE (Prestazioni) ---
    if (cachedResponse) {
      console.info(`${logPrefix} 🚀 Avvio rapido dalla cache locale`);
      const blob = await cachedResponse.blob();
      injectScript(URL.createObjectURL(blob));
      alreadyLoaded = true;
    }

    // --- 2. CONTROLLO AGGIORNAMENTI IN BACKGROUND ---
    try {
      const token = await getAuthToken();
      const apiResponse = await fetch(API_ENDPOINT, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });

      if (apiResponse.ok) {
        const data = await apiResponse.json();
        const componentResponse = await fetch(data.url);

        if (componentResponse.ok) {
          // Salva la nuova versione per il PROSSIMO avvio
          await cache.put(RESOURCE_KEY, componentResponse.clone());
          console.info(
            `${logPrefix} 📥 Nuova versione scaricata e pronta per il prossimo riavvio`,
          );

          // Se non avevamo nulla in cache, lo carichiamo ora
          if (!alreadyLoaded) {
            console.info(
              `${logPrefix} ✅ Primo caricamento da remoto completato`,
            );
            const blob = await componentResponse.blob();
            injectScript(URL.createObjectURL(blob));
          }
        }
      }
    } catch (e) {
      console.debug(`${logPrefix} Controllo aggiornamenti saltato (offline)`);
    }
  }

  function injectScript(url) {
    const script = document.createElement("script");
    script.type = "module";
    script.src = url;
    script.onload = () => URL.revokeObjectURL(url);
    document.head.appendChild(script);
  }

  loadResource();
})();
