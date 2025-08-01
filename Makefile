RUN = poetry run

all: test
test: pytest doctest mypy codespell
test-full: test all-nb

pytest:
	$(RUN) pytest

mypy:
	$(RUN) mypy src tests

codespell:
	$(RUN) tox -e codespell

DOCTEST_DIR = src
doctest:
	$(RUN) pytest --doctest-modules src


# TODO: have a more elegant way of testing a subset using pytest.mark
pytest-core:
	$(RUN) pytest tests/test_datamodel.py && \
	$(RUN) typedlogic --help

# mdkocs
serve: mkd-serve
mkd-%:
	$(RUN) mkdocs $*

# find all nb files; exclude checkpoint files
NB_FILES = $(shell find docs -type f -name "*.ipynb" -not -path "*/.ipynb_checkpoints/*")
all-nb: $(patsubst docs/%.ipynb,tmp/docs/%.ipynb,$(NB_FILES))

# run notebook with papermill and diff with nbdime
tmp/docs/%.ipynb: docs/%.ipynb
	mkdir -p $(dir $@) && \
	$(RUN) papermill --cwd $(dir $<) $< $@.tmp.ipynb && mv $@.tmp.ipynb $@ && $(RUN) nbdime diff -D -M -A -S $< $@


%-doctest: %
	$(RUN) python -m doctest --option ELLIPSIS --option NORMALIZE_WHITESPACE $<

