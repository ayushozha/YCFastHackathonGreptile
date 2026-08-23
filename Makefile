.PHONY: install demo run fix replay cache test clean

install:
	pip install -r requirements.txt

# serves the arena on :8000 (static/index.html at /)
demo:
	uvicorn arena.api:app --reload --port 8000

# make run PR=https://github.com/<owner>/payments-svc/pull/42 ID=m1
run:
	python scripts/run_pr.py $(PR) --arena-id $(ID)

fix:
	python scripts/run_pr.py --arena-id $(ID) --fix-only

# A's M2 proof: whole loop in one process
full:
	python scripts/run_pr.py $(PR) --arena-id $(ID) --fix

cache:
	python scripts/make_cache.py $(ID)

test:
	pytest tests -q

clean:
	rm -rf runs/* .pytest_cache
