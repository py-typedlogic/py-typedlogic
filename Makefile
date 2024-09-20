RUN = poetry run

test: pytest doctest mypy

pytest:
	$(RUN) pytest

mypy:
	$(RUN) mypy src tests

DOCTEST_DIR = src
doctest:
	find $(DOCTEST_DIR) -type f \( -name "*.rst" -o -name "*.md" -o -name "*.py" \) -print0 | xargs -0 $(RUN) python -m doctest --option ELLIPSIS --option NORMALIZE_WHITESPACE

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
