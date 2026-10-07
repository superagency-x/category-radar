# Understanding Metrics

## Visibility Share
Quantifies the brand's presence on the digital shelf, discounted logarithmically by rank:

$$\text{Weight} = \frac{1}{\log_2(\text{rank} + 1)}$$

Rank 1 contributes 1.0, Rank 3 contributes 0.5, Rank 15 contributes 0.25.

## Price Index
Measures brand price positioning relative to market median:

$$\text{Price Index} = \frac{\text{Brand Median Price}}{\text{Market Median Price}} \times 100$$

A score of 100 represents the market midpoint. >100 represents a premium brand; <100 represents budget positioning.

## Feature Lift
Evaluates whether a product feature is rewarded by shelf rank:

$$\text{Lift} = \frac{\% \text{ of Top 20 with Feature}}{\% \text{ of All Listings with Feature}}$$

A lift $> 1.0$ indicates that the market actively prioritizes this feature.

## Herfindahl-Hirschman Index (HHI)
Measures market concentration on visibility shares from 0 to 10,000:
- $< 1,500$: Highly competitive / fragmented.
- $1,500 - 2,500$: Moderately concentrated.
- $> 2,500$: Highly concentrated.

## Cross-Elasticity & Brand Velocity
- **Elasticity**: Relates percentage price change to rank movement.
- **Brand Velocity**: Identifies new entrants, declining brands, and rising stars across consecutive snapshots.
