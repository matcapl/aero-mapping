.PHONY: test-providers
test-providers:
	@echo "== Running six geocoder connectivity tests =="
	@chmod +x tests/test_six_geocoders.sh
	@./tests/test_six_geocoders.sh
