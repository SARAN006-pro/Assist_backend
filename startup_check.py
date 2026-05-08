#!/usr/bin/env python3
"""
startup_check.py
=================
Run this BEFORE uvicorn to self-diagnose Railway deployment failures.

Usage (add to Procfile):
  web: python startup_check.py && uvicorn app.main:app --host 0.0.0.0 --port $PORT ...

If anything is wrong, it prints the EXACT problem and exits with code 1.
Railway will show this in build/deploy logs.
"""

import os
import sys


def check(label, fn):
    try:
        result = fn()
        print(f"  ✅ {label}" + (f": {result}" if result else ""))
        return True
    except Exception as e:
        print(f"  ❌ {label}: {type(e).__name__}: {e}")
        return False


def main():
    print()
    print("=" * 60)
    print("  ARIA STARTUP SELF-CHECK")
    print("=" * 60)
    failures = []

    # ── 1. Python version ──────────────────────────────────────────
    print("\n[1] Python Environment")
    v = sys.version_info
    version_str = f"Python {v.major}.{v.minor}.{v.micro}"
    if v.major < 3 or v.minor < 10:
        print(f"  ❌ Python version too old: {version_str} (need 3.10+)")
        failures.append("Python version")
    else:
        print(f"  ✅ {version_str}")

    # ── 2. PORT env var ────────────────────────────────────────────
    print("\n[2] Railway PORT binding")
    port = os.environ.get("PORT")
    if port:
        print(f"  ✅ PORT={port} (Railway-assigned)")
    else:
        print("  ⚠️  PORT not set — will default to 8000 (OK for local, not Railway)")

    # ── 3. Critical packages ───────────────────────────────────────
    print("\n[3] Required packages")
    packages = [
        ("fastapi", "fastapi"),
        ("uvicorn", "uvicorn"),
        ("pydantic", "pydantic"),
        ("starlette", "starlette"),
    ]
    for name, import_name in packages:
        ok = check(name, lambda n=import_name: __import__(n).__version__)
        if not ok:
            failures.append(f"package:{name}")

    # ── 4. Optional packages (warn, don't fail) ────────────────────
    print("\n[4] Optional packages")
    optional = ["redis", "openai", "anthropic", "httpx"]
    for pkg in optional:
        try:
            mod = __import__(pkg)
            ver = getattr(mod, "__version__", "?")
            print(f"  ✅ {pkg}: {ver}")
        except ImportError:
            print(f"  ⚠️  {pkg}: not installed (OK if not used)")

    # ── 5. App module import ───────────────────────────────────────
    print("\n[5] App module import")
    sys.path.insert(0, os.getcwd())

    ok = check("from app.main import app", lambda: __import__("app.main", fromlist=["app"]).app.title)
    if not ok:
        failures.append("app.main import")
        # Try to give more specific error
        for sub in ["app.core.config", "app.core.middleware", "app.routers.health",
                    "app.routers.chat", "app.routers.websocket", "app.services.redis_service",
                    "app.models.schemas"]:
            check(f"  submodule: {sub}", lambda s=sub: __import__(s, fromlist=["x"]) and "ok")

    # ── 6. __init__.py files ───────────────────────────────────────
    print("\n[6] Package __init__.py files")
    init_paths = [
        "app/__init__.py",
        "app/core/__init__.py",
        "app/routers/__init__.py",
        "app/services/__init__.py",
        "app/models/__init__.py",
    ]
    for path in init_paths:
        if os.path.exists(path):
            print(f"  ✅ {path}")
        else:
            print(f"  ❌ {path} MISSING — Python cannot import this package")
            failures.append(f"missing:{path}")

    # ── 7. Environment variables ───────────────────────────────────
    print("\n[7] Environment variables")
    env_checks = [
        ("OPENAI_API_KEY", False),
        ("ANTHROPIC_API_KEY", False),
        ("GEMINI_API_KEY", False),
        ("SECRET_KEY", False),
        ("REDIS_URL", False),
    ]
    has_ai_key = any(os.environ.get(k) for k, _ in env_checks[:3])
    for key, required in env_checks:
        val = os.environ.get(key, "")
        if val:
            masked = val[:8] + "..." if len(val) > 8 else "***"
            print(f"  ✅ {key}={masked}")
        else:
            print(f"  {'❌' if required else '⚠️ '} {key} not set")
    if not has_ai_key:
        print("  ⚠️  No AI API key set — chat will return echo responses")

    # ── 8. File structure ──────────────────────────────────────────
    print("\n[8] Critical files")
    critical_files = ["Procfile", "requirements.txt", "app/main.py",
                      "app/routers/health.py", "app/core/config.py"]
    for f in critical_files:
        if os.path.exists(f):
            print(f"  ✅ {f}")
        else:
            print(f"  ❌ {f} MISSING")
            failures.append(f"missing:{f}")

    # ── Summary ───────────────────────────────────────────────────
    print()
    print("=" * 60)
    if failures:
        print(f"  ❌ STARTUP CHECK FAILED — {len(failures)} issue(s):")
        for f in failures:
            print(f"     • {f}")
        print()
        print("  Fix these issues then redeploy.")
        print("=" * 60)
        sys.exit(1)
    else:
        print("  ✅ ALL CHECKS PASSED — starting uvicorn")
        print("=" * 60)
        print()
        sys.exit(0)


if __name__ == "__main__":
    main()