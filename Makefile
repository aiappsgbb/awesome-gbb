# awesome-gbb static site Makefile.
# Targets:
#   build     — generate docs/ from skills/ + plugins/
#   serve     — serve docs/ locally on http://localhost:8000
#   validate  — build + assert every root-relative link resolves
#   clean     — remove docs/ entirely

.PHONY: build serve clean validate

build:
	python3 scripts/build-site.py --out docs/

serve:
	python3 -m http.server --directory docs 8000

clean:
	rm -rf docs/

validate:
	python3 scripts/build-site.py --out docs/ --validate
