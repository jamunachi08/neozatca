#!/usr/bin/env python3
"""Structural guards for the NeoZatca app. Run from the repo root: python3 scripts/verify_tree.py"""
import ast, glob, json, os, re, sys, tomllib

APP = "neozatca"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
errors = []

def err(msg): errors.append(msg)

# 1. pyproject: Frappe Cloud requires [tool.bench.frappe-dependencies]
py = tomllib.load(open("pyproject.toml", "rb"))
deps = py.get("tool", {}).get("bench", {}).get("frappe-dependencies", {})
if "frappe" not in deps: err("pyproject.toml: [tool.bench.frappe-dependencies] frappe missing")
for app_dep in ("frappe", "erpnext"):
    spec = deps.get(app_dep, "")
    if ">=15" not in spec.replace(" ", "") or "<" not in spec:
        err(f"pyproject.toml: {app_dep} range must start at 15 and keep a tested upper bound (got {spec!r})")
if not os.path.exists(f"{APP}/public/images/neozatca-logo.svg"): err("apps-screen logo missing")
if py["project"]["name"] != APP: err("pyproject.toml: project.name != app name")

# 2. Package basics
for f in (f"{APP}/__init__.py", f"{APP}/hooks.py", f"{APP}/modules.txt", f"{APP}/patches.txt"):
    if not os.path.exists(f): err(f"missing {f}")
if not re.search(r'__version__\s*=\s*"[\d.]+"', open(f"{APP}/__init__.py").read()): err("__version__ missing")
modules = [m.strip() for m in open(f"{APP}/modules.txt") if m.strip()]
scrub = lambda s: s.strip().lower().replace(" ", "_").replace("-", "_")
for m in modules:
    if not os.path.isdir(os.path.join(APP, scrub(m))): err(f"module folder missing for '{m}'")

# 3. DocType / Report / Page JSON consistency
for f in glob.glob(f"{APP}/*/*/*/*.json"):
    kind_dir = f.split(os.sep)[2]
    if kind_dir not in ("doctype", "report", "page", "workspace", "number_card", "dashboard_chart", "print_format"): continue
    d = json.load(open(f))
    folder = os.path.basename(os.path.dirname(f))
    if os.path.splitext(os.path.basename(f))[0] != folder: continue
    if d.get("module") and d["module"] not in modules: err(f"{f}: module '{d['module']}' not in modules.txt")
    if kind_dir == "doctype":
        if scrub(d["name"]) != folder: err(f"{f}: name '{d['name']}' does not scrub to folder '{folder}'")
        ctrl = f[:-5] + ".py"
        if os.path.exists(ctrl):
            cls = d["name"].replace(" ", "").replace("-", "")
            if f"class {cls}(" not in open(ctrl).read(): err(f"{ctrl}: class {cls} not found")

# 4. Every dotted path in hooks.py / patches.txt must resolve
def resolves(dotted):
    parts = dotted.split(".")
    for i in range(len(parts), 0, -1):
        base = os.path.join(*parts[:i])
        for cand in (base + ".py", os.path.join(base, "__init__.py")):
            if os.path.exists(cand):
                rest = parts[i:]
                if not rest: return True
                src = ast.parse(open(cand).read())
                names = {n.name for n in ast.walk(src) if isinstance(n, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef))}
                names |= {a.asname or a.name for n in ast.walk(src) if isinstance(n, ast.ImportFrom) for a in n.names}
                return rest[0] in names
    return False
hooks_src = "\n".join(l for l in open(f"{APP}/hooks.py") if not l.lstrip().startswith("#"))
for dotted in set(re.findall(rf'["\']({APP}(?:\.\w+)+)["\']', hooks_src)):
    if not resolves(dotted): err(f"hooks.py: cannot resolve {dotted}")
for line in open(f"{APP}/patches.txt"):
    line = line.split("#")[0].strip()
    if line.startswith(APP + ".") and not resolves(line.split()[0] + ".execute"): err(f"patches.txt: {line} has no execute()")

# 5. Brand guard: no legacy upstream identifiers outside LICENSE
legacy = re.compile(r"optima|systematic", re.I)
for r, ds, fs in os.walk("."):
    ds[:] = [d for d in ds if d not in (".git", "node_modules", "__pycache__")]
    for f in fs:
        p = os.path.join(r, f)
        if p in ("./LICENSE", "./scripts/verify_tree.py"): continue
        try: txt = open(p, encoding="utf-8").read()
        except (UnicodeDecodeError, IsADirectoryError): continue
        for m in legacy.finditer(txt):
            word = re.match(r"\w+", txt[m.start():]).group().lower()
            if word.startswith(("optimal", "optimiz", "optimis")): continue
            err(f"{p}: legacy brand string '{m.group()}'"); break

# 6. Python syntax
for p in glob.glob(f"{APP}/**/*.py", recursive=True):
    try: ast.parse(open(p).read())
    except SyntaxError as e: err(f"{p}: {e}")

# 7. Frappe Cloud: no Node build at deploy time — the onboarding SPA ships pre-built
pkg = json.load(open("package.json"))
for script in ("build", "postinstall", "install", "preinstall"):
    if script in pkg.get("scripts", {}):
        err(f"package.json: '{script}' script would run a Node build on Frappe Cloud; ship the SPA pre-built")
if not os.path.exists(f"{APP}/public/zatca-onboarding/zatca_onboarding.js"):
    err("pre-built onboarding bundle missing: run `yarn build:onboarding` inside a bench and commit the output")
for line in open(".gitignore"):
    if "public/zatca-onboarding" in line:
        err(".gitignore excludes the pre-built onboarding bundle")

if errors:
    print("verify_tree: FAILED"); [print("  -", e) for e in errors]; sys.exit(1)
print("verify_tree: OK")
