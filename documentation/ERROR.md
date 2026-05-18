# Log degli Errori di Analisi — Motore Euristico (v1.0)

> Questi casi documentano i falsi positivi prodotti dalla versione 1.0 del motore,
> che simulava l'analisi AI tramite regex e keyword hardcoded invece di usare un
> LLM reale. Sono stati la motivazione principale per il passaggio ad AWS Bedrock
> (v2.0) e poi all'architettura completamente automatizzata con `vex-engine` (v3.0).
> Il motore attuale non presenta questi errori di contesto.

---

ALIAS:GHSA-9wx4-h78v-vm56
Descritption: Requests is a HTTP library. Prior to 2.32.0, when making requests through a Requests `Session`, if the first request is made with `verify=False` to disable cert verification, all subsequent requests to the same host will continue to ignore cert verification regardless of changes to the value of `verify`. This behavior will continue for the lifecycle of the connection in the connection pool. This vulnerability is fixed in 2.32.0.

Audit Trail:CycloneDX VEX - 17 Feb 2026 at 12:55:51
Details: Vulnerability CVE-2024-35195 analyzed by Antigravity AI (python) on 2026-02-17. Reachable: AI audit confirmed that 'verify' is used with dynamic data in ./cvedemo/cvedemo/vuln_demo.py:20. The data flow appears to originate from an external or untrusted source. Context: `img.verify()`

Code: 
with Image.open(img_file) as img:
                    # Un hacker potrebbe inviare un file "SGI" o "PCX" corrotto
                    # che causa un crash o un overflow durante il caricamento dei pixel.
                    img.verify() 
                    img.thumbnail((100, 100))
                    img.save(f"thumb_{img_file.name}")

Osservazioni: come vedi hai confuso il contesto perchè la libreria di riferimento è Requests ed è verc che il parametro è quello del verify ma tu invece lo hai confuso con img.verify() come vedi è sbagliato sia il riferimento specifico che il contesto di riferimento


ALIAS:CVE-2022-28347
Description: A SQL injection issue was discovered in `QuerySet.explain()` in Django 2.2 before 2.2.28, 3.2 before 3.2.13, and 4.0 before 4.0.4. This occurs by passing a crafted dictionary (with dictionary expansion) as the `**options` argument, and placing the injection payload in an option name.

Audit: CycloneDX VEX - 17 Feb 2026 at 12:55:50
Details: Vulnerability GHSA-w24h-v9qh-8gxj analyzed by Antigravity AI (python) on 2026-02-17. Reachable: AI audit confirmed that 'load' is used with dynamic data in ./cvedemo/cvedemo/vuln_demo.py:39. The data flow appears to originate from an external or untrusted source. Context: `print("Processing with unsafe load (DANGER)...")`

Code:
print("Processing with unsafe load (DANGER)...")
    return yaml.load(data, Loader=yaml.FullLoader)

Osservazioni: qui il riferimento è proprio sbagliato perchè non vedo ne QuerySet ne options ma soprattutto non vedo riferimenti a logiche di SQL

