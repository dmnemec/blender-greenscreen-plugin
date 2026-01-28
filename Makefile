ADDON_NAME = greenscreen_data_prep
ZIP_FILE = $(ADDON_NAME).zip

.PHONY: all clean zip

all: zip

zip:
	@echo "Packaging $(ADDON_NAME)..."
	@rm -rf $(ADDON_NAME)
	@mkdir $(ADDON_NAME)
	@cp __init__.py $(ADDON_NAME)/
	@zip -r $(ZIP_FILE) $(ADDON_NAME)
	@echo "Cleaning up temporary files..."
	@rm -rf $(ADDON_NAME)
	@echo "Created $(ZIP_FILE)"

clean:
	@rm -f $(ZIP_FILE)
	@find . -name "__pycache__" -type d -exec rm -rf {} +