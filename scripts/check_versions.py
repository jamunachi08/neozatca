#!/usr/bin/env python3
"""Static compatibility audit of NeoZatca against several Frappe/ERPNext lines.

    python3 scripts/check_versions.py                 # version-15, version-16, develop
    python3 scripts/check_versions.py version-17      # any branch names

Shallow-clones each frappe/erpnext branch into .version-cache/ (reused next time) and checks:
imports, hook targets, custom-field/property-setter targets, fieldtypes, workspace keys,
background-job/realtime APIs, desk JS APIs and third-party Python packages.
Run it before lifting the upper bound in [tool.bench.frappe-dependencies].
"""
import subprocess
import ast, os, re, json, glob, sys, tomllib
APPROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__))); APP=f"{APPROOT}/neozatca"
CACHE=os.path.join(APPROOT, ".version-cache")
BRANCHES=sys.argv[1:] or ["version-15","version-16","develop"]
def fetch(repo, branch):
    dest=os.path.join(CACHE, f"{repo}-{branch}")
    if not os.path.isdir(dest):
        os.makedirs(CACHE, exist_ok=True)
        subprocess.run(["git","clone","-q","--depth","1","-b",branch,f"https://github.com/frappe/{repo}.git",dest],check=True)
    return dest
PAIRS={b:(fetch("frappe",b),fetch("erpnext",b)) for b in BRANCHES}

def modfile(roots, mod):
    top=mod.split(".")[0]; base=roots.get(top)
    if not base: return None
    p=os.path.join(base,*mod.split("."))
    for c in (p+".py", os.path.join(p,"__init__.py")):
        if os.path.exists(c): return c
def defined(roots, path, name, seen=None):
    seen=seen or set()
    if path in seen: return False
    seen.add(path)
    t=ast.parse(open(path).read())
    for n in ast.walk(t):
        if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)) and n.name==name: return True
        if isinstance(n,ast.Assign) and any(isinstance(x,ast.Name) and x.id==name for x in n.targets): return True
        if isinstance(n,ast.AnnAssign) and isinstance(n.target,ast.Name) and n.target.id==name: return True
        if isinstance(n,(ast.ImportFrom,ast.Import)) and any((a.asname or a.name.split(".")[0])==name for a in n.names if a.name!="*"): return True
    for n in ast.walk(t):  # star imports
        if isinstance(n,ast.ImportFrom) and any(a.name=="*" for a in n.names) and n.module:
            mf=modfile(roots,n.module)
            if mf and defined(roots,mf,name,seen): return True
    d=os.path.dirname(path)
    return path.endswith("__init__.py") and (os.path.exists(os.path.join(d,name+".py")) or os.path.isdir(os.path.join(d,name)))

def pyfiles():
    for r,_,fs in os.walk(APP):
        if "/tests" in r or "node_modules" in r: continue
        for f in fs:
            if f.endswith(".py") and not f.startswith("test_"): yield os.path.join(r,f)

def doctype_json(roots, dt):
    s=dt.lower().replace(" ","_").replace("-","_")
    for base in roots.values():
        hits=glob.glob(f"{base}/*/*/doctype/{s}/{s}.json")+glob.glob(f"{base}/*/doctype/{s}/{s}.json")
        if hits: return json.load(open(hits[0]))

report={}
for ver,(fr,er) in PAIRS.items():
    roots={"frappe":fr,"erpnext":er}; issues=[]
    # 1 imports
    for p in pyfiles():
        for n in ast.walk(ast.parse(open(p).read())):
            if isinstance(n,ast.ImportFrom) and n.module and n.module.split(".")[0] in roots:
                mf=modfile(roots,n.module)
                if not mf: issues.append(f"module missing {n.module} ({os.path.relpath(p,APP)})"); continue
                for a in n.names:
                    if a.name!="*" and not defined(roots,mf,a.name): issues.append(f"{n.module}.{a.name} missing ({os.path.relpath(p,APP)})")
    # 2 dotted hook targets in frappe/erpnext
    hooks=open(f"{APP}/hooks.py").read()
    for dotted in set(re.findall(r'["\']((?:frappe|erpnext)(?:\.\w+)+)["\']',hooks)):
        parts=dotted.split("."); ok=False
        for i in range(len(parts),0,-1):
            mf=modfile(roots,".".join(parts[:i]))
            if mf:
                ok = i==len(parts) or defined(roots,mf,parts[i]); break
        if not ok: issues.append(f"hooks target missing: {dotted}")
    # 3 doc_events / custom fields / property setters target doctypes + fields
    sys.path.insert(0,APPROOT)
    src=open(f"{APP}/setup/customizations.py").read()
    for dt in set(re.findall(r'^\s{8}"([A-Z][\w ]+)":\s*\[',src,re.M)):
        if not doctype_json(roots,dt): issues.append(f"custom field target doctype missing: {dt}")
    for m in re.finditer(r'"doctype":\s*"([^"]+)",\s*"fieldname":\s*"([^"]+)"',src):
        d=doctype_json(roots,m.group(1))
        if d and m.group(2) not in {f["fieldname"] for f in d["fields"]}:
            issues.append(f"property setter field missing: {m.group(1)}.{m.group(2)}")
    for dt in set(re.findall(r'^\t"([A-Z][\w ]+)":\s*\{',hooks,re.M)):
        if not doctype_json(roots,dt) and not glob.glob(f"{APP}/*/doctype/{dt.lower().replace(' ','_')}"):
            issues.append(f"doc_events doctype missing: {dt}")
    # 4 fieldtypes valid
    docfield=json.load(open(f"{fr}/frappe/core/doctype/docfield/docfield.json"))
    valid=set(next(f for f in docfield["fields"] if f["fieldname"]=="fieldtype")["options"].split("\n"))
    for j in glob.glob(f"{APP}/*/doctype/*/*.json"):
        d=json.load(open(j))
        for f in d.get("fields",[]):
            if f.get("fieldtype") and f["fieldtype"] not in valid: issues.append(f"invalid fieldtype {f['fieldtype']} in {os.path.basename(j)}")
    # 5 workspace / shortcut keys
    ws=json.load(open(f"{APP}/neozatca/workspace/zatca/zatca.json"))
    wsf={f["fieldname"] for f in json.load(open(f"{fr}/frappe/desk/doctype/workspace/workspace.json"))["fields"]}
    for k in ("content","shortcuts","links","number_cards","charts","label","title","module","public"):
        if k in ws and k not in wsf: issues.append(f"workspace key not in Workspace doctype: {k}")
    scf={f["fieldname"] for f in json.load(open(f"{fr}/frappe/desk/doctype/workspace_shortcut/workspace_shortcut.json"))["fields"]}
    for s in ws["shortcuts"]:
        for k in s:
            if k not in scf and k not in ("doctype","name"): issues.append(f"shortcut key unknown: {k}")
    # 6 runtime APIs (python)
    bgj=open(f"{fr}/frappe/utils/background_jobs.py").read()
    for kw in ("deduplicate","job_id","enqueue_after_commit","timeout","queue"):
        if not re.search(rf"def enqueue\([^)]*\b{kw}\b",bgj,re.S): issues.append(f"enqueue kwarg missing: {kw}")
    rt=open(glob.glob(f"{fr}/frappe/realtime*.py")[0] if glob.glob(f"{fr}/frappe/realtime.py") else f"{fr}/frappe/realtime/__init__.py").read()
    for kw in ("user","after_commit","doctype","docname"):
        if not re.search(rf"def publish_realtime\([^)]*\b{kw}\b",rt,re.S): issues.append(f"publish_realtime kwarg missing: {kw}")
    dbsrc="".join(open(p).read() for p in glob.glob(f"{fr}/frappe/database/database.py"))
    for m in ("get_single_value","set_single_value","has_column","get_value","set_value","exists","sql"):
        if f"def {m}(" not in dbsrc: issues.append(f"frappe.db.{m} missing")
    init=open(f"{fr}/frappe/__init__.py").read()
    for m in ("only_for","get_cached_value","enqueue","has_permission","log_error","get_roles","publish_realtime"):
        if not re.search(rf"(def {m}\(|\b{m},|import .*\b{m}\b)",init): issues.append(f"frappe.{m} missing")
    # 7 JS desk APIs
    js=""
    for p in glob.glob(f"{fr}/frappe/public/js/**/*.js",recursive=True): js+=open(p,errors="ignore").read()
    for api in ("set_headline_alert","show_progress","hide_progress","get_day_diff","comment_when","with_doc","make_app_page",
                "add_inner_button","set_secondary_action","add_custom_button","set_df_property","escape_html","str_to_user","get_today"):
        if api not in js: issues.append(f"JS API missing: {api}")
    # 8 third-party python modules available
    deps=set()
    for root in (fr,er):
        t=tomllib.load(open(f"{root}/pyproject.toml","rb"))
        deps|={re.split(r"[<>=~!\[; ]",x)[0].lower().replace("-","_") for x in t["project"].get("dependencies",[])}
    ours={re.split(r"[<>=~!\[; ]",x)[0].lower().replace("-","_") for x in tomllib.load(open(f"{APPROOT}/pyproject.toml","rb"))["project"]["dependencies"]}
    alias={"pyqrcode":"pyqrcode","qrcode":"qrcode","cryptography":"cryptography","asn1":"asn1","pikepdf":"pikepdf","requests":"requests","lxml":"lxml","PIL":"pillow","png":"pypng","dateutil":"python_dateutil","bs4":"beautifulsoup4","signxml":"signxml","OpenSSL":"pyopenssl","click":"click","jinja2":"jinja2","pytz":"pytz","xmltodict":"xmltodict","num2words":"num2words","babel":"babel"}
    stdlib=set(sys.stdlib_module_names)
    for p in pyfiles():
        for n in ast.walk(ast.parse(open(p).read())):
            mods=[]
            if isinstance(n,ast.Import): mods=[a.name.split(".")[0] for a in n.names]
            if isinstance(n,ast.ImportFrom) and n.module and n.level==0: mods=[n.module.split(".")[0]]
            for m in mods:
                if m in stdlib or m in ("frappe","erpnext","neozatca"): continue
                pkg=alias.get(m,m.lower())
                if pkg not in deps and pkg not in ours: issues.append(f"python package not guaranteed: {m} ({os.path.relpath(p,APP)})")
    report[ver]=sorted(set(issues))
# Known, intentional findings (not failures)
EXPECTED = (
    "doc_events doctype missing: Salary Slip",                 # lives in HRMS; hook is inert without it
    "module missing frappe.utils.number_format",               # v15: guarded by ImportError fallback
    "python package not guaranteed: weasyprint",               # v17+: pdfa3 falls back to frappe get_pdf
)
failed = False
for v,iss in report.items():
    real=[i for i in iss if not i.startswith(EXPECTED)]
    print(f"== {v}: {len(real)} issue(s)" + (f" (+{len(iss)-len(real)} expected)" if len(iss)!=len(real) else ""))
    for i in real: print("   ",i)
    failed = failed or bool(real)
sys.exit(1 if failed else 0)
