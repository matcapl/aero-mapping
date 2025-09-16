.PHONY: test-providers
test-providers:
	@echo "== Running six geocoder connectivity tests =="
	@chmod +x tests/test_six_geocoders.sh
	@./tests/test_six_geocoders.sh

.PHONY: test-full docs-serve

test-full:
	./scripts/test-full-pipeline.sh

docs-serve:
	python -m http.server 8080 --directory docs/

docker-init-db:
	docker-compose exec db psql -U a -d suppliers -c "$(shell cat scripts/init_schema.sql)"

