# Wishlist 🎀

A pink wishlist with product photos, daily price checks, a weekly deal scout and a phone button for adding things.

- `index.html` is the page (served by GitHub Pages).
- `items.json` is the list. The robots keep it up to date; you can also edit it by hand.
- `scripts/check_prices.py` reads the price and photo from each link, every day.
- `scripts/add_item.py` adds a new item from a link sent by the phone button.
- `scripts/scout.py` looks for each item at other UK shops once a week.
- `scripts/notify.sh` turns alerts into an issue that mentions you, which GitHub emails to you.

## Adding things from your phone

An Apple Shortcut in the Share menu opens an issue titled **Add to wishlist** with this in it:

```
url: https://www.shop.com/the-product
target: 60
for: Me
```

Only the `url` line is needed. The **Add to wishlist** workflow fills in the name, photo, shop, size and price, saves it, then closes the issue with a reply saying what was added. Issues from anyone other than you are ignored.

The Shortcut needs a fine-grained GitHub token that can only reach this repo, with **Issues: Read and write** and nothing else.

## Deal scout

Every Sunday the scout searches Google Shopping (through SerpApi) for each item. If the same item and size is at least £1 cheaper at another UK shop, the card shows "💸 £45 at Boots" and you get an email. It ignores gift sets, testers, samples, refills and other versions of a perfume (Intense, Elixir, Royal and so on) unless your item is one.

It needs a free SerpApi key saved as the repository secret `SERPAPI_KEY` (Settings, Secrets and variables, Actions). Without it the scout does nothing. To run it straight away: Actions, Deal scout, Run workflow.

## Email alerts

When an item reaches its target price, hits a new lowest price, or is cheaper elsewhere, the robots open an issue that mentions you. GitHub emails that to the address on your GitHub account. Check that email notifications are on under GitHub Settings, Notifications.

## Notes

- Some shops block automated visitors. An item whose price cannot be read shows a message on its card instead of a guess.
- Prices are read in pounds only.
