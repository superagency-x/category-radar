# Adding Categories

Category Radar is category-agnostic. To monitor an entirely new category (such as espresso machines or robot vacuums):

1. **Create Category YAML**:
   Create a new configuration file under `config/<category_id>.yaml`.

2. **Define Taxonomy**:
   Specify category-specific claims, features, price tiers, and target keywords.

3. **Specify Channels**:
   Map the category listing URLs on comparison sites across DE, AT, CH, PL, CZ, and HU.

4. **Execute**:
   Run the pipeline pointing to the new YAML:
   ```bash
   radar run --config config/espresso.yaml
   ```
