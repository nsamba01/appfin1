"""Validation statique de docker-compose.yml (équivalent de `docker compose config`).

Utile en CI ou lorsque le démon Docker n'est pas disponible : vérifie l'interpolation
des variables, les dépendances, réseaux, volumes, ports, la cohérence nginx et
l'absence de secret littéral dans le fichier.

Usage :
    python scripts/validate-compose.py          # depuis la racine du projet
    py -3 scripts\\validate-compose.py           # Windows (module PyYAML requis)

Sortie : code 0 si tout est valide, 1 sinon.
"""
from __future__ import annotations

import os
import re
import sys
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COMPOSE = os.path.join(ROOT, "docker-compose.yml")

VAR_RE = re.compile(
    r"\$(?:\$|(?P<braced>\{(?P<name>[A-Za-z_][A-Za-z0-9_]*)"
    r"(?:(?P<op>:?[-?+])(?P<arg>[^}]*))?\})|(?P<bare>[A-Za-z_][A-Za-z0-9_]*))"
)


class InterpolationError(RuntimeError):
    pass


def interpolate(text: str, env: dict[str, str]) -> str:
    out = []
    pos = 0
    for m in VAR_RE.finditer(text):
        out.append(text[pos:m.start()])
        pos = m.end()
        if m.group(0) == "$$":
            out.append("$")
            continue
        name = m.group("name") or m.group("bare")
        op = m.group("op")
        arg = m.group("arg")
        value = env.get(name)
        if op in (":-", "-"):
            unset = value is None or (op == ":-" and value == "")
            out.append(arg if unset else value)
        elif op in (":?", "?"):
            invalid = value is None or (op == ":?" and value == "")
            if invalid:
                raise InterpolationError(f"{name} : {arg}")
            out.append(value)
        elif op in (":+", "+"):
            unset = value is None or (op == ":+" and value == "")
            out.append("" if unset else arg)
        else:
            if value is None:
                raise InterpolationError(f"{name} n'est pas définie (aucune valeur par défaut)")
            out.append(value)
    out.append(text[pos:])
    return "".join(out)


def resolve(node, env):
    if isinstance(node, str):
        return interpolate(node, env)
    if isinstance(node, list):
        return [resolve(x, env) for x in node]
    if isinstance(node, dict):
        return {k: resolve(v, env) for k, v in node.items()}
    return node


def parse_env(path: str) -> dict[str, str]:
    env = {}
    with open(path, encoding="utf-8-sig") as fh:
        for raw in fh:
            line = raw.strip().lstrip("\ufeff")
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            env[key.strip()] = val.strip().strip('"').strip("'")
    return env


def gen_env_from_windows_script(script_path: str) -> dict[str, str]:
    """Reproduit les couples clé/valeur écrits par scripts/init-secrets.ps1."""
    src = open(script_path, encoding="utf-8-sig").read()
    keys = set(re.findall(r"^\s*'([A-Z][A-Z0-9_]+)=", src, re.M))
    keys |= set(re.findall(r'^\s*"([A-Z][A-Z0-9_]+)=', src, re.M))
    env = {}
    for k in keys:
        if k == "DJANGO_SECRET_KEY":
            env[k] = "a" * 64
        elif k == "FIELD_ENCRYPTION_KEY":
            env[k] = "A" * 43 + "="
        elif k == "POSTGRES_PASSWORD":
            env[k] = "P" * 43
        elif k.startswith("INITIAL_"):
            env[k] = "Initial#Passw0rd"
        elif k == "POSTGRES_DB":
            env[k] = "finbank"
        elif k == "POSTGRES_USER":
            env[k] = "finbank"
        elif k == "NGINX_HTTP_PORT":
            env[k] = "8080"
        elif k in {"BACKUP_INTERVAL_SECONDS", "BACKUP_RETENTION_DAYS", "ECOBANK_HTTP_TIMEOUT",
                   "BANK_SYNC_INTERVAL_MINUTES", "JWT_ACCESS_MINUTES", "JWT_REFRESH_MINUTES",
                   "SESSION_COOKIE_AGE", "MAX_LOGIN_ATTEMPTS", "LOGIN_LOCKOUT_MINUTES"}:
            env[k] = "30"
        elif k in {"DJANGO_DEBUG", "DJANGO_SECURE_COOKIES", "DJANGO_SECURE_SSL_REDIRECT",
                   "BANK_SYNC_WORKER_ENABLED"}:
            env[k] = "False"
        elif k == "DJANGO_ALLOWED_HOSTS":
            env[k] = "localhost,127.0.0.1"
        elif k in {"DJANGO_CSRF_TRUSTED_ORIGINS", "CORS_ALLOWED_ORIGINS"}:
            env[k] = "http://localhost:8080"
        elif k == "THROTTLE_LOGIN":
            env[k] = "20/min"
        # Les autres variables gardent leur valeur par défaut Compose (:-).
    return env


results: list[tuple[bool, str, str]] = []


def check(ok: bool, label: str, detail: str = "") -> None:
    results.append((bool(ok), label, detail))


def main() -> int:
    raw = yaml.safe_load(open(COMPOSE, encoding="utf-8"))

    # --- 1. Sans .env : messages d'erreur actionnables -------------------
    try:
        resolve(raw, {})
        check(False, "Compose refuse de démarrer sans .env", "aucune erreur levée !")
    except InterpolationError as exc:
        msg = str(exc)
        check("scripts/init-secrets" in msg,
              "Sans .env, l'erreur indique la commande à lancer",
              msg.splitlines()[0][:120])

    # --- 2. Avec le .env généré par le script Windows --------------------
    env = gen_env_from_windows_script(os.path.join(ROOT, "scripts", "init-secrets.ps1"))
    try:
        cfg = resolve(raw, env)
        check(True, "Le .env produit par init-secrets.ps1 suffit à Compose",
              f"{len(env)} variables fournies")
    except InterpolationError as exc:
        check(False, "Le .env produit par init-secrets.ps1 suffit à Compose", str(exc))
        return 1

    services = cfg["services"]
    names = set(services)
    check(True, "Services déclarés", ", ".join(services))

    # --- 3. Images / contextes de build ----------------------------------
    for name, svc in services.items():
        if "image" in svc:
            check(True, f"[{name}] image", svc["image"])
        ctx = svc.get("build")
        if ctx:
            ctx = ctx if isinstance(ctx, dict) else {"context": ctx}
            ctx_dir = os.path.normpath(os.path.join(ROOT, ctx.get("context", ".")))
            dockerfile = os.path.join(ctx_dir, ctx.get("dockerfile", "Dockerfile"))
            check(os.path.isdir(ctx_dir) and os.path.isfile(dockerfile),
                  f"[{name}] contexte + Dockerfile",
                  f"{os.path.relpath(ctx_dir, ROOT)}/{os.path.basename(dockerfile)}")

    # --- 4. env_file, réseaux, volumes, dépendances ----------------------
    declared_networks = set(cfg.get("networks", {}))
    declared_volumes = set(cfg.get("volumes", {}))
    for name, svc in services.items():
        if "env_file" in svc:
            for entry in svc["env_file"] if isinstance(svc["env_file"], list) else [svc["env_file"]]:
                path = entry if isinstance(entry, str) else entry.get("path")
                check(os.path.isfile(os.path.join(ROOT, path)),
                      f"[{name}] env_file présent après génération", path)
        for net in svc.get("networks", []):
            check(net in declared_networks, f"[{name}] réseau déclaré", net)
        for vol in svc.get("volumes", []):
            src = vol.split(":")[0]
            if src.startswith(".") or src.startswith("/"):
                check(os.path.exists(os.path.join(ROOT, src)),
                      f"[{name}] chemin monté existant", src)
            else:
                check(src in declared_volumes, f"[{name}] volume nommé déclaré", src)
        for dep, cond in (svc.get("depends_on") or {}).items():
            check(dep in names, f"[{name}] dépendance existe", dep)
            if isinstance(cond, dict):
                check(cond.get("condition") in {"service_started", "service_healthy", "service_completed_successfully"},
                      f"[{name}] condition depends_on valide", f"{dep}: {cond.get('condition')}")
                if cond.get("condition") == "service_healthy":
                    check("healthcheck" in services[dep] or "healthcheck" in services[dep].get("build", {}) or dep == "frontend",
                          f"[{name}] {dep} possède un healthcheck", "requis par service_healthy")

    # --- 5. Ports ---------------------------------------------------------
    published = []
    for name, svc in services.items():
        for port in svc.get("ports", []):
            host = str(port).split(":")[0]
            published.append((host, name))
    check(len(published) == 1, "Un seul service publie un port (surface d'exposition minimale)",
          f"{published}")
    check(all("db" != name for _, name in published), "PostgreSQL n'est jamais publié", f"{published}")

    # --- 6. Cohérence nginx <-> compose -----------------------------------
    conf_dir = os.path.join(ROOT, "nginx", "conf.d")
    confs = [f for f in os.listdir(conf_dir) if f.endswith(".conf")]
    text = "\n".join(open(os.path.join(conf_dir, f), encoding="utf-8").read() for f in confs)
    upstreams = re.findall(r"server\s+([a-z0-9_-]+):(\d+)", text)
    for host, port in upstreams:
        check(host in names, f"nginx : upstream '{host}' est un service Compose", f"{host}:{port}")
    check("location = /healthz" in text, "nginx expose /healthz (healthcheck du conteneur)")

    # --- 7. Configs nginx montées existent --------------------------------
    nginx_svc = services["nginx"]
    for vol in nginx_svc["volumes"]:
        src = vol.split(":")[0]
        if src.startswith(".") or src.startswith("/"):
            check(os.path.exists(os.path.join(ROOT, src)), "nginx : configuration montée", src)
        else:
            check(src in declared_volumes, "nginx : volume nommé déclaré", src)

    # --- 8. Sécurité des conteneurs ---------------------------------------
    backend_dockerfile = open(os.path.join(ROOT, "backend", "Dockerfile"), encoding="utf-8").read()
    check("USER app" in backend_dockerfile, "Backend : utilisateur non-root dans l'image")
    check("HEALTHCHECK" in backend_dockerfile, "Backend : HEALTHCHECK défini dans l'image")
    # On inspecte la version NON résolue : un secret ne doit jamais être littéral.
    for name, svc in raw["services"].items():
        envmap = svc.get("environment") or {}
        leaked = [k for k, v in envmap.items()
                  if re.search(r"PASSWORD|SECRET|KEY", k) and "$" not in str(v)]
        check(not leaked, f"[{name}] aucun secret en clair dans compose", str(leaked))

    # --- 9. Healthchecks --------------------------------------------------
    for name in ("db", "backend", "nginx"):
        check("healthcheck" in services[name], f"[{name}] healthcheck défini")

    # --- 10. Les scripts référencés existent ------------------------------
    for script in ("entrypoint.sh", "wait_for_db", "bootstrap_users"):
        if script.endswith(".sh"):
            check(os.path.isfile(os.path.join(ROOT, "backend", script)), "Script d'entrée présent", script)
        else:
            path = os.path.join(ROOT, "backend", "apps", "core", "management", "commands", f"{script}.py")
            check(os.path.isfile(path), "Commande de gestion présente", f"{script}.py")

    # --- Rapport ----------------------------------------------------------
    failures = [r for r in results if not r[0]]
    print(f"\n{len(results) - len(failures)}/{len(results)} vérifications OK\n")
    for ok, label, detail in results:
        mark = "OK  " if ok else "ECHEC"
        print(f"[{mark}] {label}" + (f" — {detail}" if detail else ""))
    print()
    if failures:
        print(f"{len(failures)} PROBLÈME(S) DÉTECTÉ(S)")
        return 1
    print("docker-compose.yml : structure valide (équivalent de `docker compose config`)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
