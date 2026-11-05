.PHONY: readme-hero

# Rebuilds the README hero and the GitHub social card. See scripts/readme/.
readme-hero:
	uv run scripts/readme/build_readme_hero.py
