# Configuration

Category definitions are authored in YAML under `config/` (for example, `config/airfryer.yaml`).
All configuration files are validated against the type-safe Pydantic schema in `category_radar.config_schema`.

## Configuration Structure

```yaml
category:
  id: airfryer
  name: Air fryers
  base_currency: EUR

crawl:
  delay_seconds: 4.0
  timeout_seconds: 30.0
  max_retries: 2
  respect_robots_txt: true
  fetcher: auto

markets:
  DE: { name: Germany, currency: EUR, language: de }
  AT: { name: Austria, currency: EUR, language: de }
  CH: { name: Switzerland, currency: CHF, language: de }
  PL: { name: Poland, currency: PLN, language: pl }
  CZ: { name: Czechia, currency: CZK, language: cs }
  HU: { name: Hungary, currency: HUF, language: hu }

channels:
  geizhals_de:
    market: DE
    adapter: geizhals
    type: price_comparison
    start_url: https://geizhals.de/?cat=hfritt
    max_pages: 1
```

## Claims & Needs Taxonomy

Claims and consumer needs are matched against titles and descriptions using validated multilingual regex patterns:

```yaml
claims:
  dual_zone:
    label: Dual zone / 2 baskets
    pattern: "(dual[- ]?zone|2[- ]?zone|doppelkorb|2 korb|zwei kammer|podwójny kosz)"
```
