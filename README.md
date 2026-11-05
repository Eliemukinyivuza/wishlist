# Wishlist

A pink wishlist with product photos, categories and daily price checks.

- `index.html` is the page (served by GitHub Pages).
- `items.json` is the list. Add an item by copying an existing block and changing the name, link, category and target price.
- `scripts/check_prices.py` reads the price and photo from each link.
- `.github/workflows/check-prices.yml` runs that script every day and when `items.json` changes.

## Email alerts

When an item reaches its target price or hits a new lowest price, the daily check opens an issue in this repo that mentions the owner. GitHub emails that to the address on the GitHub account. Check that email notifications are on under GitHub Settings, Notifications.

## Notes

- Some shops block automated visitors. An item whose price cannot be read shows a message on its card instead of a guess.
- Prices are read in pounds only.
