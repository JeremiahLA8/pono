#!/usr/bin/env python3
"""build_deal_package.py — assemble the shareable STR Deal Analyzer package + zip.

Pulls the engine scripts from scripts/ and the assets from references/str-deal-analyzer/ (so the
bundle never drifts from the canonical source), copies the package-only files from
references/str-deal-analyzer/package/, generates a working config.py with EMPTY keys, runs the
smoke test, and zips the result.

NEVER includes secrets — *secret*.json, token_drive.json, credentials.json are excluded by
construction (only the explicit ENGINE files are copied).

Usage:
    python3 scripts/build_deal_package.py                     # -> ~/Downloads/str-deal-analyzer.zip
    python3 scripts/build_deal_package.py --out /some/dir     # build dir + zip there
"""
import argparse, os, shutil, subprocess, sys, zipfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(REPO, "scripts")
REFS = os.path.join(REPO, "references", "str-deal-analyzer")
PKGSRC = os.path.join(REFS, "package")

# Canonical engine scripts (copied flat so their `from fill_deal_analyzer import ...` imports work).
ENGINE = [
    "fill_deal_analyzer.py", "deal_scenarios.py", "deal_probabilistic.py",
    "airroi_lookup.py", "listing_hasdata.py", "permit_costs.py", "renovation_budget.py",
]
# Package-only files (live in references/str-deal-analyzer/package/).
PKG_FILES = ["analyze.py", "config.example.py", "requirements.txt", "README.md", "CHANGELOG.md"]
# Assets copied into assets/.
ASSETS = {
    "template.xlsx": "template.xlsx",
    "condition-rubric.md": "condition-rubric.md",
    "examples-3880-wyllie-8c.spec.json": "example.spec.json",  # renamed for clarity
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.expanduser("~/Downloads"))
    ap.add_argument("--name", default="str-deal-analyzer")
    args = ap.parse_args()

    root = os.path.join(args.out, args.name)
    if os.path.exists(root):
        shutil.rmtree(root)
    os.makedirs(os.path.join(root, "assets", "permit-costs"))
    os.makedirs(os.path.join(root, "docs"))
    os.makedirs(os.path.join(root, "tests"))

    for f in ENGINE:
        shutil.copy2(os.path.join(SCRIPTS, f), os.path.join(root, f))
    for f in PKG_FILES:
        shutil.copy2(os.path.join(PKGSRC, f), os.path.join(root, f))
    shutil.copy2(os.path.join(PKGSRC, "tests", "test_smoke.py"), os.path.join(root, "tests", "test_smoke.py"))

    for src, dst in ASSETS.items():
        shutil.copy2(os.path.join(REFS, src), os.path.join(root, "assets", dst))
    for f in os.listdir(os.path.join(REFS, "permit-costs")):
        shutil.copy2(os.path.join(REFS, "permit-costs", f), os.path.join(root, "assets", "permit-costs", f))
    # the methodology doc is the references README
    shutil.copy2(os.path.join(REFS, "README.md"), os.path.join(root, "docs", "METHODOLOGY.md"))

    # working config.py with EMPTY keys (so the math runs out of the box; keys added by the user)
    shutil.copy2(os.path.join(PKGSRC, "config.example.py"), os.path.join(root, "config.py"))

    # sanity: assert no secret files slipped in
    leaked = [p for d, _, fs in os.walk(root) for p in fs
              if "secret" in p.lower() or p in ("token_drive.json", "credentials.json")]
    if leaked:
        sys.exit(f"ABORT: secret-looking files in bundle: {leaked}")

    # smoke test the assembled package
    print("Running smoke test on the assembled package...")
    r = subprocess.run([sys.executable, os.path.join(root, "tests", "test_smoke.py")],
                       capture_output=True, text=True)
    print(r.stdout[-600:]);
    if r.returncode != 0:
        print(r.stderr[-600:]); sys.exit("smoke test FAILED — package not zipped")

    # zip it
    zip_path = os.path.join(args.out, f"{args.name}.zip")
    if os.path.exists(zip_path):
        os.remove(zip_path)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for dirpath, _, files in os.walk(root):
            for fn in files:
                fp = os.path.join(dirpath, fn)
                z.write(fp, os.path.relpath(fp, args.out))
    n = len(zipfile.ZipFile(zip_path).namelist())
    print(f"\nPackage: {root}")
    print(f"Zip:     {zip_path}  ({n} files, {os.path.getsize(zip_path)//1024} KB)")


if __name__ == "__main__":
    main()
