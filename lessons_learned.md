# Lessons Learned: GitLab CI/CD & Dependency-Track (Local Environment)

Questa è una sintesi dei problemi riscontrati durante il setup dell'ambiente locale e le relative soluzioni.

## 1. Connettività Git (SSH)
*   **Problema**: Errore "Connection refused" durante il `git push`.
*   **Causa**: GitLab in Docker espone la porta SSH 22 internamente, ma nel `docker-compose.yml` era mappata sulla **2222** dell'host.
*   **Soluzione**: Usare il formato URL esteso: `git remote add origin ssh://git@localhost:2222/root/app-java.git`.

## 2. Registrazione Runner (GitLab v16+)
*   **Problema**: Il Runner non partiva o i job rimanevano "stuck".
*   **Causa**: Le nuove versioni di GitLab usano "Authentication Tokens" invece dei vecchi "Registration Tokens". Inoltre, i job senza tag vengono ignorati per default.
*   **Lezione**: Quando si crea un runner nell'area Admin, è fondamentale spuntare **"Run untagged jobs"** se il file `.gitlab-ci.yml` non specifica tag.

## 3. Networking nei Job Containers (Sibling Containers)
*   **Problema**: Errore `lookup gitlab: no such host` durante l'upload degli artifact o il clone.
*   **Causa**: Il Runner lancia dei container "fratelli" (non figli). Questi container temporanei non ereditano i file `/etc/hosts` o il DNS del runner.
*   **Soluzione**: Configurare `extra_hosts` nel file `config.toml` del runner per mappare esplicitamente `gitlab` sull'IP interno della rete Docker.

## 4. Il Loop di "localhost"
*   **Problema**: Il job fallisce cercando di clonare da `http://localhost`.
*   **Causa**: GitLab vede se stesso su `localhost` e passa questo indirizzo al Runner. Ma per il runner (e per i suoi job), `localhost` è il container stesso.
*   **Soluzione**: Usare l'opzione `clone_url = "http://gitlab"` nel `config.toml` del runner per forzare l'uso della rete interna Docker.

## 5. Comunicazione con l'Host (Mac)
*   **Problema**: Il comando `curl` verso Dependency-Track falliva puntando a `localhost:8081`.
*   **Causa**: Dependency-Track gira sul Mac (porta 8081), ma il job gira in un container.
*   **Soluzione**: Usare **`host.docker.internal`** invece di `localhost` per permettere al container di raggiungere i servizi esposti sul computer host.

## 6. Permessi Dependency-Track
*   **Problema**: Errore `The principal does not have permission to create project`.
*   **Causa**: La API Key non ha il permesso di creare progetti "al volo".
*   **Soluzione**: Nel pannello Administration di Dependency-Track, assegnare al team i permessi **`BOM_UPLOAD`** e **`PROJECT_CREATION_UPLOAD`**.

## 7. Analisi delle Vulnerabilità e API Keys
*   **Problema**: I componenti vengono rilevati ma non appaiono vulnerabilità.
*   **Causa**: La scansione NVD e Sonatype OSS Index richiedono API Key per funzionare correttamente e senza limitazioni (rate limiting).
*   **Soluzione**: 
    1. Ottenere una API Key dal [NIST NVD](https://nvd.nist.gov/developers/request-an-api-key).
    2. Ottenere credenziali per [OSS Index (Sonatype)](https://ossindex.sonatype.org/).
    3. Inserirle in **Administration > Analyzers > Vulnerability Analyzers** su Dependency-Track.
