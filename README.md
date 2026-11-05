# Wishlist

A pink wishlist with product photos, categories and daily price checks.

- `index.html` is the page (served by GitHub Pages).
- `items.json` is the list. Add an item by copying an existing block and changing the name, link, category and target price.
- `scripts/check_prices.py` reads the price and photo from each link.
- `.github/workflows/check-prices.yml` runs that script every day and when `items.json` changes.

## Phone alerts (optional)

1. Install the free ntfy app and subscribe to a topic name only you know.
2. In the repo go to Settings, Secrets and variables, Actions, and add a secret called `NTFY_TOPIC` with that topic name.

The daily check then sends a notification when an item reaches its target price or hits a new lowest price.

## Notes

- Some shops block automated visitors. An item whose price cannot be read shows a message on its card instead of a guess.
- Prices are read in pounds only.
