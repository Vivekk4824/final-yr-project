# VendorMap final recommendation input validation

## Decision

The approved policy keeps K-Means at **K=2** and ranks a saved, valid pin with **85% six-factor MCDA and 15% proximity**, using `100 × exp(-distance_km / 3)`. The business GIS flag replaces only the Commercial component with available category evidence. The original MCDA score remains available in the API and UI. Radius limits the Top 3 and Expand Search temporarily lifts that limit. The preference form exposes the six inputs together. The legacy locality column and saved values remain available for compatibility.

Use both experiment flags for the demonstration or staging after selecting the intended environment. Keep the **existing 3× facility multiplier** and the default **3 km decay**. The production defaults keep both flags off for controlled rollout.

## Coverage and headline results

The audit ran **274 deterministic cases** against `manual-142-v2`. This comprises 144 matrix cases across six divisions, six categories and four priorities, 106 controlled and demonstration cases, and 24 separate facility-multiplier trials. The matrix uses reviewed west/east references selected deterministically within each division. The controlled cases hold the other inputs constant. Each scenario records the comparison inputs, all six effective weights, zone IDs, original MCDA, category-adjusted MCDA, personalized scores, distances and contribution changes in the [scenario CSV](final-recommendation-input-validation.csv).

| Metric | Approved 144-case matrix versus flags-off baseline |
| --- | ---: |
| Different Top 1 | **47 / 144 (32.6%)** |
| Different Top-3 membership | **90 / 144 (62.5%)** |
| Mean Top-3 overlap | 77.8% |
| Different first-ranked zone IDs across the matrix | **22** |
| Mean original MCDA loss per Top 3 | **1.47 points** |
| Mean original MCDA loss where Top-3 membership changed | 2.36 points |
| Mean selected category GIS relevance versus location-only, where category evidence applies | **+1.58 points on a 0–100 scale** |

Across all 250 approved cases and their specified controls, Top 1 changed in 66 (26.4%) and Top-3 membership changed in 117 (46.8%). The 144-case matrix isolates the policy comparison with a common flags-off baseline. Original loss compares selected zones with the score-maximizing baseline at the same requested category, division, priority and facilities. The CSV also records loss against the best original candidates inside the same radius, so the cost of narrowing eligibility can be examined independently.

## What each input did

| Input | Held fixed | Observed sensitivity |
| --- | --- | --- |
| Business category | Food control at the NW_F_004 pin, Nashik West, Balanced, Anywhere, facilities off | 4 of 5 category changes changed Top 1 and 5 of 5 changed Top-3 membership. Food, Clothing, Vegetables/Fruits and General Goods used mapped category-specific Commercial evidence. Flowers and Other used the baseline Commercial fallback. |
| Division | Food, Balanced, NW_F_004 pin, Anywhere, facilities off | Compared with Any, 5 of 6 divisions changed Top 1 and all 6 changed Top-3 membership. Every selected-division result stayed in that division. |
| Working location | Food, Nashik West, Balanced, Anywhere, facilities off | NW_F_004 made NW_F_007 first. Moving the pin to NW_F_025 made NW_F_025 first. The no-pin run also started with NW_F_025 but ordered the next two zones differently. |
| Distance | Food, Nashik West, Balanced, facilities off, same pin within each comparison | At NW_F_004, the 1 km and 3 km options changed membership. The 5 km and 10 km results matched Anywhere. At NW_F_009, the 1 km shortlist had two results and Expand Search restored three. Each shared zone kept the same underlying MCDA and personalized scores. |
| Main priority | Food, same division and location, facilities off | Across 18 non-Balanced comparisons with no pin, 4 changed Top 1 and 3 changed membership. With the matched division pins, 1 changed Top 1 and 3 changed membership. Proximity dampened Top-1 sensitivity in this sample. Each selected priority increased its intended effective weight. |
| Facility checkboxes | Food, Balanced, same division and pin, Anywhere | Compared with all off, the 24 enabled cases changed Top 1 once and Top-3 membership four times. Each individual checkbox and all-on changed membership once across six divisions. Switching on a checkbox aligned to an already elevated main priority left the weights and ranking identical in three targeted checks. |

For Food and Nashik West at NW_F_004, all four checkbox settings below changed the weighted scores while the three zone IDs stayed in the same order. Strict division is an eligibility constraint and the Preference criterion's weight is redistributed to the other criteria.

| Facility setting | Commercial | Accessibility | Facilities | Top 1 changed? |
| --- | ---: | ---: | ---: | --- |
| All off | 22.22% | 22.22% | 16.67% | No |
| Market | 36.76% | 18.07% | 13.55% | No |
| Transport | 18.07% | 36.76% | 13.55% | No |
| Parking | 18.86% | 18.86% | 29.29% | No |
| Market, Transport, Parking | 26.99% | 26.99% | 20.25% | No |

The 3.3× offline trial used the same 24 enabled facility profiles as the production 3× policy. It increased Top-1 changes from **1 to 2** while Top-3 membership changes stayed at **4**. It only swapped the first two zones in the Satpur Market case. Mean original suitability loss on the same approved 3× MCDA scale was **1.248 points** for both policies. This provided no suitability improvement, so the production policy retains 3×.

## Exact paired results

Each zone is shown as **zone ID (original MCDA / personalized score / straight-line km)**. The table displays six decimals. The CSV retains additional precision and lists the six factor contributions and actual GIS method for each ranked result. Score change is the change in the mean across the returned results. Factor drivers describe changes in the ranking margin between a new and departing leader or shortlist member. For unchanged memberships they describe score movements on the highlighted zone.

### Business and division

| Input changed | Previous Top 3 | New Top 3 | Score change | Top-1 changed? | Why? |
| --- | --- | --- | --- | --- | --- |
| Business · Food (S145) | `NW_F_007` (63.194867 / 64.424823 / 0.913030)<br>`NW_F_025` (72.061265 / 60.633265 / 4.349245)<br>`NW_F_008` (47.865020 / 50.964213 / 1.068381) | `NW_F_007` (63.194867 / 64.424823 / 0.913030)<br>`NW_F_025` (72.061265 / 60.633265 / 4.349245)<br>`NW_F_008` (47.865020 / 50.964213 / 1.068381) | Rank +0.000000 / original +0.000000 | No | The control and tested input produce the same ranking and factor contributions. |
| Business · Clothing (S146) | `NW_F_007` (63.194867 / 64.424823 / 0.913030)<br>`NW_F_025` (72.061265 / 60.633265 / 4.349245)<br>`NW_F_008` (47.865020 / 50.964213 / 1.068381) | `NW_F_025` (76.699222 / 66.075075 / 4.349245)<br>`NW_F_007` (68.996095 / 62.057667 / 0.913030)<br>`NW_F_003` (61.064634 / 59.551028 / 2.352809) | Rank +3.887156 / original +7.879600 | Yes | NW_F_025 versus NW_F_007 score-change drivers · commercial +8.798 pts, business -0.989 pts |
| Business · Vegetables/Fruits (S147) | `NW_F_007` (63.194867 / 64.424823 / 0.913030)<br>`NW_F_025` (72.061265 / 60.633265 / 4.349245)<br>`NW_F_008` (47.865020 / 50.964213 / 1.068381) | `NW_F_025` (66.397376 / 59.087065 / 4.349245)<br>`NW_F_017` (54.300663 / 54.059900 / 4.136985)<br>`NW_F_007` (59.847979 / 52.196195 / 0.913030) | Rank -3.559714 / original -0.858378 | Yes | NW_F_025 versus NW_F_007 score-change drivers · commercial +12.652 pts, business -1.969 pts |
| Business · Flowers (S148) | `NW_F_007` (63.194867 / 64.424823 / 0.913030)<br>`NW_F_025` (72.061265 / 60.633265 / 4.349245)<br>`NW_F_008` (47.865020 / 50.964213 / 1.068381) | `NW_F_007` (69.130716 / 69.825223 / 0.913030)<br>`NW_F_025` (77.790885 / 69.641692 / 4.349245)<br>`NW_F_003` (59.989207 / 57.837619 / 2.352809) | Rank +7.094078 / original +7.929885 | No | NW_F_003 versus NW_F_008 score-change drivers · business +4.249 pts, commercial +3.194 pts |
| Business · General Goods (S149) | `NW_F_007` (63.194867 / 64.424823 / 0.913030)<br>`NW_F_025` (72.061265 / 60.633265 / 4.349245)<br>`NW_F_008` (47.865020 / 50.964213 / 1.068381) | `NW_F_025` (76.610776 / 64.616309 / 4.349245)<br>`NW_F_007` (64.317345 / 57.484851 / 0.913030)<br>`NW_F_005` (49.460971 / 55.542979 / 0.315825) | Rank +0.540613 / original +2.422647 | Yes | NW_F_025 versus NW_F_007 score-change drivers · commercial +8.010 pts, business +2.913 pts |
| Business · Other (S150) | `NW_F_007` (63.194867 / 64.424823 / 0.913030)<br>`NW_F_025` (72.061265 / 60.633265 / 4.349245)<br>`NW_F_008` (47.865020 / 50.964213 / 1.068381) | `NW_F_025` (71.035683 / 63.899770 / 4.349245)<br>`NW_F_007` (58.339698 / 60.652858 / 0.913030)<br>`NW_F_005` (44.934040 / 51.695088 / 0.315825) | Rank +0.075138 / original -2.937243 | Yes | NW_F_025 versus NW_F_007 score-change drivers · commercial +3.783 pts, business +3.255 pts |
| Division · Any (S151) | `NW_F_007` (61.875381 / 63.338752 / 0.913030)<br>`NW_F_025` (69.855138 / 59.171883 / 4.349245)<br>`NR_F_034` (66.253210 / 52.682510 / 11.398805) | `NW_F_007` (61.875381 / 63.338752 / 0.913030)<br>`NW_F_025` (69.855138 / 59.171883 / 4.349245)<br>`NR_F_034` (66.253210 / 52.682510 / 11.398805) | Rank +0.000000 / original +0.000000 | No | The control and tested input produce the same ranking and factor contributions. |
| Division · Nashik East (S152) | `NW_F_007` (61.875381 / 63.338752 / 0.913030)<br>`NW_F_025` (69.855138 / 59.171883 / 4.349245)<br>`NR_F_034` (66.253210 / 52.682510 / 11.398805) | `NE_F_008` (53.323228 / 48.511679 / 4.646972)<br>`NE_F_011` (49.391617 / 44.876108 / 4.937026)<br>`NE_F_002` (41.322484 / 35.870260 / 5.316878) | Rank -15.311700 / original -17.982133 | Yes | Strict division eligibility changed the candidate set. |
| Division · Nashik Road (S153) | `NW_F_007` (61.875381 / 63.338752 / 0.913030)<br>`NW_F_025` (69.855138 / 59.171883 / 4.349245)<br>`NR_F_034` (66.253210 / 52.682510 / 11.398805) | `NR_F_034` (68.059123 / 53.776600 / 11.398805)<br>`NR_F_020` (61.690394 / 48.377432 / 11.274083)<br>`NR_F_017` (51.012813 / 42.051266 / 10.934594) | Rank -10.329282 / original -5.740466 | Yes | Strict division eligibility changed the candidate set. |
| Division · Nashik West (S154) | `NW_F_007` (61.875381 / 63.338752 / 0.913030)<br>`NW_F_025` (69.855138 / 59.171883 / 4.349245)<br>`NR_F_034` (66.253210 / 52.682510 / 11.398805) | `NW_F_007` (63.194867 / 64.424823 / 0.913030)<br>`NW_F_025` (72.061265 / 60.633265 / 4.349245)<br>`NW_F_008` (47.865020 / 50.964213 / 1.068381) | Rank +0.276385 / original -4.954192 | No | Strict division eligibility changed the candidate set. |
| Division · New Nashik (S155) | `NW_F_007` (61.875381 / 63.338752 / 0.913030)<br>`NW_F_025` (69.855138 / 59.171883 / 4.349245)<br>`NR_F_034` (66.253210 / 52.682510 / 11.398805) | `NN_F_011` (52.400138 / 44.495375 / 6.609565)<br>`NN_F_004` (37.599430 / 33.387191 / 4.701842)<br>`NN_F_006` (37.578332 / 32.616314 / 4.899764) | Rank -21.564755 / original -23.468610 | Yes | Strict division eligibility changed the candidate set. |
| Division · Panchavati (S156) | `NW_F_007` (61.875381 / 63.338752 / 0.913030)<br>`NW_F_025` (69.855138 / 59.171883 / 4.349245)<br>`NR_F_034` (66.253210 / 52.682510 / 11.398805) | `PAN_F_028` (61.424756 / 53.323842 / 4.820991)<br>`PAN_F_031` (62.566959 / 51.410889 / 4.574922)<br>`PAN_F_027` (48.491521 / 43.352065 / 4.795007) | Rank -9.035449 / original -8.500164 | Yes | Strict division eligibility changed the candidate set. |
| Division · Satpur (S157) | `NW_F_007` (61.875381 / 63.338752 / 0.913030)<br>`NW_F_025` (69.855138 / 59.171883 / 4.349245)<br>`NR_F_034` (66.253210 / 52.682510 / 11.398805) | `SAT_F_010` (48.778641 / 46.466224 / 3.406494)<br>`SAT_F_022` (52.515713 / 45.736912 / 4.606731)<br>`SAT_F_016` (38.655256 / 43.825739 / 0.990148) | Rank -13.054757 / original -19.344707 | Yes | Strict division eligibility changed the candidate set. |

### Working location and distance

| Input changed | Previous Top 3 | New Top 3 | Score change | Top-1 changed? | Why? |
| --- | --- | --- | --- | --- | --- |
| Location · No pin (S158) | `NW_F_025` (72.061265 / 67.192736 / —)<br>`NW_F_007` (63.194867 / 62.777305 / —)<br>`NW_F_017` (58.339878 / 53.785957 / —) | `NW_F_025` (72.061265 / 67.192736 / —)<br>`NW_F_007` (63.194867 / 62.777305 / —)<br>`NW_F_017` (58.339878 / 53.785957 / —) | Rank +0.000000 / original +0.000000 | No | The control and tested input produce the same ranking and factor contributions. |
| Location · NW_F_004 (S159) | `NW_F_025` (72.061265 / 67.192736 / —)<br>`NW_F_007` (63.194867 / 62.777305 / —)<br>`NW_F_017` (58.339878 / 53.785957 / —) | `NW_F_007` (63.194867 / 64.424823 / 0.913030)<br>`NW_F_025` (72.061265 / 60.633265 / 4.349245)<br>`NW_F_008` (47.865020 / 50.964213 / 1.068381) | Rank -2.577899 / original -3.491619 | Yes | NW_F_007 versus NW_F_025 score-change drivers · proximity +7.545 pts, facilities +0.377 pts, commercial +0.115 pts |
| Location · NW_F_025 (S160) | `NW_F_025` (72.061265 / 67.192736 / —)<br>`NW_F_007` (63.194867 / 62.777305 / —)<br>`NW_F_017` (58.339878 / 53.785957 / —) | `NW_F_025` (72.061265 / 72.113825 / 0.000000)<br>`NW_F_017` (58.339878 / 58.367467 / 0.511320)<br>`NW_F_007` (63.194867 / 57.735342 / 3.696683) | Rank +1.486879 / original +0.000000 | No | NW_F_025 score-change drivers · proximity +15.000 pts, business -2.624 pts, access -2.430 pts |
| Move saved pin from NW_F_004 to NW_F_025 (S159 → S160) | `NW_F_007` (63.194867 / 64.424823 / 0.913030)<br>`NW_F_025` (72.061265 / 60.633265 / 4.349245)<br>`NW_F_008` (47.865020 / 50.964213 / 1.068381) | `NW_F_025` (72.061265 / 72.113825 / 0.000000)<br>`NW_F_017` (58.339878 / 58.367467 / 0.511320)<br>`NW_F_007` (63.194867 / 57.735342 / 3.696683) | Rank +4.064778 / original +3.491619 | Yes | Only the pin changed. The 15% proximity term reordered zones. |
| Distance · Anywhere at NW_F_004 (S161) | `NW_F_007` (63.194867 / 64.424823 / 0.913030)<br>`NW_F_025` (72.061265 / 60.633265 / 4.349245)<br>`NW_F_008` (47.865020 / 50.964213 / 1.068381) | `NW_F_007` (63.194867 / 64.424823 / 0.913030)<br>`NW_F_025` (72.061265 / 60.633265 / 4.349245)<br>`NW_F_008` (47.865020 / 50.964213 / 1.068381) | Rank +0.000000 / original +0.000000 | No | The control and tested input produce the same ranking and factor contributions. |
| Distance · 1 km at NW_F_004 (S162) | `NW_F_007` (63.194867 / 64.424823 / 0.913030)<br>`NW_F_025` (72.061265 / 60.633265 / 4.349245)<br>`NW_F_008` (47.865020 / 50.964213 / 1.068381) | `NW_F_007` (63.194867 / 64.424823 / 0.913030)<br>`NW_F_005` (42.720917 / 49.813933 / 0.315825)<br>`NW_F_004` (29.961602 / 40.467362 / 0.000000) | Rank -7.105394 / original -15.747922 | No | The radius changed shortlist membership while leaving common scores intact. |
| Distance · 3 km at NW_F_004 (S163) | `NW_F_007` (63.194867 / 64.424823 / 0.913030)<br>`NW_F_025` (72.061265 / 60.633265 / 4.349245)<br>`NW_F_008` (47.865020 / 50.964213 / 1.068381) | `NW_F_007` (63.194867 / 64.424823 / 0.913030)<br>`NW_F_008` (47.865020 / 50.964213 / 1.068381)<br>`NW_F_003` (54.990102 / 50.167724 / 2.352809) | Rank -3.488514 / original -5.690387 | No | The radius changed shortlist membership while leaving common scores intact. |
| Distance · 5 km at NW_F_004 (S164) | `NW_F_007` (63.194867 / 64.424823 / 0.913030)<br>`NW_F_025` (72.061265 / 60.633265 / 4.349245)<br>`NW_F_008` (47.865020 / 50.964213 / 1.068381) | `NW_F_007` (63.194867 / 64.424823 / 0.913030)<br>`NW_F_025` (72.061265 / 60.633265 / 4.349245)<br>`NW_F_008` (47.865020 / 50.964213 / 1.068381) | Rank +0.000000 / original +0.000000 | No | The control and tested input produce the same ranking and factor contributions. |
| Distance · 10 km at NW_F_004 (S165) | `NW_F_007` (63.194867 / 64.424823 / 0.913030)<br>`NW_F_025` (72.061265 / 60.633265 / 4.349245)<br>`NW_F_008` (47.865020 / 50.964213 / 1.068381) | `NW_F_007` (63.194867 / 64.424823 / 0.913030)<br>`NW_F_025` (72.061265 / 60.633265 / 4.349245)<br>`NW_F_008` (47.865020 / 50.964213 / 1.068381) | Rank +0.000000 / original +0.000000 | No | The control and tested input produce the same ranking and factor contributions. |
| Distance · Anywhere at NW_F_009 (S166) | `NW_F_025` (72.061265 / 61.643863 / 3.591960)<br>`NW_F_007` (63.194867 / 60.480089 / 2.235689)<br>`NW_F_003` (54.990102 / 53.594829 / 1.135331) | `NW_F_025` (72.061265 / 61.643863 / 3.591960)<br>`NW_F_007` (63.194867 / 60.480089 / 2.235689)<br>`NW_F_003` (54.990102 / 53.594829 / 1.135331) | Rank +0.000000 / original +0.000000 | No | The control and tested input produce the same ranking and factor contributions. |
| Distance · 1 km at NW_F_009 (S167) | `NW_F_025` (72.061265 / 61.643863 / 3.591960)<br>`NW_F_007` (63.194867 / 60.480089 / 2.235689)<br>`NW_F_003` (54.990102 / 53.594829 / 1.135331) | `NW_F_009` (43.536359 / 50.489853 / 0.000000)<br>`NW_F_018` (24.062294 / 30.187644 / 0.980139) | Rank -18.234178 / original -29.616085 | Yes | The radius changed shortlist membership while leaving common scores intact. |
| Expand Search · NW_F_009 from 1 km (S168) | `NW_F_009` (43.536359 / 50.489853 / 0.000000)<br>`NW_F_018` (24.062294 / 30.187644 / 0.980139) | `NW_F_025` (72.061265 / 61.643863 / 3.591960)<br>`NW_F_007` (63.194867 / 60.480089 / 2.235689)<br>`NW_F_003` (54.990102 / 53.594829 / 1.135331) | Rank +18.234178 / original +29.616085 | Yes | The radius changed shortlist membership while leaving common scores intact. |

### Priority, facilities and the Satpur combination

| Input changed | Previous Top 3 | New Top 3 | Score change | Top-1 changed? | Why? |
| --- | --- | --- | --- | --- | --- |
| Priority · Balanced · No pin (S185) | `NW_F_025` (72.061265 / 67.192736 / —)<br>`NW_F_007` (63.194867 / 62.777305 / —)<br>`NW_F_017` (58.339878 / 53.785957 / —) | `NW_F_025` (72.061265 / 67.192736 / —)<br>`NW_F_007` (63.194867 / 62.777305 / —)<br>`NW_F_017` (58.339878 / 53.785957 / —) | Rank +0.000000 / original +0.000000 | No | The control and tested input produce the same ranking and factor contributions. |
| Priority · Commercial · No pin (S186) | `NW_F_025` (72.061265 / 67.192736 / —)<br>`NW_F_007` (63.194867 / 62.777305 / —)<br>`NW_F_017` (58.339878 / 53.785957 / —) | `NW_F_025` (74.090713 / 66.037165 / —)<br>`NW_F_007` (62.493855 / 61.803121 / —)<br>`NW_F_022` (58.512498 / 51.659539 / —) | Rank -1.418724 / original +0.500352 | No | NW_F_022 versus NW_F_017 score-change drivers · commercial +6.365 pts, historical +2.077 pts, business +0.738 pts |
| Priority · Accessibility · No pin (S187) | `NW_F_025` (72.061265 / 67.192736 / —)<br>`NW_F_007` (63.194867 / 62.777305 / —)<br>`NW_F_017` (58.339878 / 53.785957 / —) | `NW_F_025` (72.220561 / 68.262038 / —)<br>`NW_F_007` (64.874161 / 64.534647 / —)<br>`NW_F_017` (59.867949 / 56.165228 / —) | Rank +1.735305 / original +1.122220 | No | NW_F_025 score-change drivers · access +10.600 pts, business -3.270 pts, commercial -2.534 pts |
| Priority · Facilities · No pin (S188) | `NW_F_025` (72.061265 / 67.192736 / —)<br>`NW_F_007` (63.194867 / 62.777305 / —)<br>`NW_F_017` (58.339878 / 53.785957 / —) | `NW_F_025` (69.665618 / 65.534745 / —)<br>`NW_F_007` (59.855647 / 59.501352 / —)<br>`NW_F_017` (55.164334 / 51.300401 / —) | Rank -2.473166 / original -2.970137 | No | NW_F_025 score-change drivers · facilities +7.102 pts, business -2.651 pts, access -2.455 pts |
| Priority · Balanced · NW_F_004 (S189) | `NW_F_007` (63.194867 / 64.424823 / 0.913030)<br>`NW_F_025` (72.061265 / 60.633265 / 4.349245)<br>`NW_F_008` (47.865020 / 50.964213 / 1.068381) | `NW_F_007` (63.194867 / 64.424823 / 0.913030)<br>`NW_F_025` (72.061265 / 60.633265 / 4.349245)<br>`NW_F_008` (47.865020 / 50.964213 / 1.068381) | Rank +0.000000 / original +0.000000 | No | The control and tested input produce the same ranking and factor contributions. |
| Priority · Commercial · NW_F_004 (S190) | `NW_F_007` (63.194867 / 64.424823 / 0.913030)<br>`NW_F_025` (72.061265 / 60.633265 / 4.349245)<br>`NW_F_008` (47.865020 / 50.964213 / 1.068381) | `NW_F_007` (62.493855 / 63.596767 / 0.913030)<br>`NW_F_025` (74.090713 / 59.651030 / 4.349245)<br>`NW_F_008` (49.050246 / 51.823274 / 1.068381) | Rank -0.317077 / original +0.837887 | No | NW_F_007 score-change drivers · commercial +7.113 pts, business -2.682 pts, access -2.548 pts |
| Priority · Accessibility · NW_F_004 (S191) | `NW_F_007` (63.194867 / 64.424823 / 0.913030)<br>`NW_F_025` (72.061265 / 60.633265 / 4.349245)<br>`NW_F_008` (47.865020 / 50.964213 / 1.068381) | `NW_F_007` (64.874161 / 65.918564 / 0.913030)<br>`NW_F_025` (72.220561 / 61.542172 / 4.349245)<br>`NW_F_008` (51.872480 / 54.412948 / 1.068381) | Rank +1.950461 / original +1.948684 | No | NW_F_007 score-change drivers · access +8.919 pts, business -2.682 pts, commercial -2.032 pts |
| Priority · Facilities · NW_F_004 (S192) | `NW_F_007` (63.194867 / 64.424823 / 0.913030)<br>`NW_F_025` (72.061265 / 60.633265 / 4.349245)<br>`NW_F_008` (47.865020 / 50.964213 / 1.068381) | `NW_F_007` (59.855647 / 61.640263 / 0.913030)<br>`NW_F_025` (69.665618 / 59.223973 / 4.349245)<br>`NW_F_008` (46.548437 / 49.879482 / 1.068381) | Rank -1.759527 / original -2.350483 | No | NW_F_007 score-change drivers · facilities +4.417 pts, business -2.174 pts, access -2.066 pts |
| Facilities · All off (S238) | `NW_F_007` (63.194867 / 64.424823 / 0.913030)<br>`NW_F_025` (72.061265 / 60.633265 / 4.349245)<br>`NW_F_008` (47.865020 / 50.964213 / 1.068381) | `NW_F_007` (63.194867 / 64.424823 / 0.913030)<br>`NW_F_025` (72.061265 / 60.633265 / 4.349245)<br>`NW_F_008` (47.865020 / 50.964213 / 1.068381) | Rank +0.000000 / original +0.000000 | No | The control and tested input produce the same ranking and factor contributions. |
| Facilities · Market (S239) | `NW_F_007` (63.194867 / 64.424823 / 0.913030)<br>`NW_F_025` (72.061265 / 60.633265 / 4.349245)<br>`NW_F_008` (47.865020 / 50.964213 / 1.068381) | `NW_F_007` (62.493855 / 63.596767 / 0.913030)<br>`NW_F_025` (74.090713 / 59.651030 / 4.349245)<br>`NW_F_008` (49.050246 / 51.823274 / 1.068381) | Rank -0.317077 / original +0.837887 | No | NW_F_007 score-change drivers · commercial +7.113 pts, business -2.682 pts, access -2.548 pts |
| Facilities · Transport (S241) | `NW_F_007` (63.194867 / 64.424823 / 0.913030)<br>`NW_F_025` (72.061265 / 60.633265 / 4.349245)<br>`NW_F_008` (47.865020 / 50.964213 / 1.068381) | `NW_F_007` (64.874161 / 65.918564 / 0.913030)<br>`NW_F_025` (72.220561 / 61.542172 / 4.349245)<br>`NW_F_008` (51.872480 / 54.412948 / 1.068381) | Rank +1.950461 / original +1.948684 | No | NW_F_007 score-change drivers · access +8.919 pts, business -2.682 pts, commercial -2.032 pts |
| Facilities · Parking (S243) | `NW_F_007` (63.194867 / 64.424823 / 0.913030)<br>`NW_F_025` (72.061265 / 60.633265 / 4.349245)<br>`NW_F_008` (47.865020 / 50.964213 / 1.068381) | `NW_F_007` (59.855647 / 61.640263 / 0.913030)<br>`NW_F_025` (69.665618 / 59.223973 / 4.349245)<br>`NW_F_008` (46.548437 / 49.879482 / 1.068381) | Rank -1.759527 / original -2.350483 | No | NW_F_007 score-change drivers · facilities +4.417 pts, business -2.174 pts, access -2.066 pts |
| Facilities · Market, Transport, Parking (S245) | `NW_F_007` (63.194867 / 64.424823 / 0.913030)<br>`NW_F_025` (72.061265 / 60.633265 / 4.349245)<br>`NW_F_008` (47.865020 / 50.964213 / 1.068381) | `NW_F_007` (61.808937 / 63.170571 / 0.913030)<br>`NW_F_025` (72.043024 / 59.729179 / 4.349245)<br>`NW_F_008` (50.474073 / 53.133206 / 1.068381) | Rank +0.003552 / original +0.401627 | No | NW_F_007 score-change drivers · business -4.842 pts, access +2.928 pts, historical -2.927 pts |
| Vegetables/Fruits · Satpur · Facilities + Parking · SAT_F_020 (S274) | `SAT_F_004` (44.706124 / 44.706124 / —)<br>`SAT_F_022` (41.984806 / 41.984806 / —)<br>`SAT_F_011` (40.332849 / 40.332849 / —) | `SAT_F_013` (36.785963 / 46.025515 / 0.048907)<br>`SAT_F_004` (44.706124 / 43.784932 / 3.071753)<br>`SAT_F_011` (40.332849 / 39.840525 / 2.285863) | Rank +0.875731 / original -1.732948 | Yes | SAT_F_013 versus SAT_F_004 score-change drivers · proximity +9.370 pts, business +1.150 pts, access -0.509 pts |

## Six combinations with different first-ranked zones

Each example uses Anywhere. For a direct personalization demonstration, start with the two Nashik West profiles and change only the pin. Then change the business from Food to Clothing at NW_F_004, which also changes Top 1 while keeping location fixed.

| Scenario | Profile and pin | Top 1 | Original MCDA | Personalized |
| --- | --- | --- | ---: | ---: |
| S159 | Food · Nashik West · Balanced · NW_F_004 | NW_F_007 | 63.194867 | 64.424823 |
| S160 | Food · Nashik West · Balanced · NW_F_025 | NW_F_025 | 72.061265 | 72.113825 |
| S152 | Food · Nashik East · Balanced · NW_F_004 | NE_F_008 | 53.323228 | 48.511679 |
| S155 | Food · New Nashik · Balanced · NW_F_004 | NN_F_011 | 52.400138 | 44.495375 |
| S153 | Food · Nashik Road · Balanced · NW_F_004 | NR_F_034 | 68.059123 | 53.776600 |
| S274 | Vegetables/Fruits · Satpur · Facilities · SAT_F_020 · Parking | SAT_F_013 | 36.785963 | 46.025515 |

## Eligibility and release checks

- **166 versus 165.** The official catalog lists 166 FREE zones. NE_F_003 is OPEN with null official and available capacity and is classified `CAPACITY_UNKNOWN`. The remaining 165 eligible FREE zones were preserved in citywide exploration. Of those, 20 are unscorable and 23 lack a reviewed distance reference, including 3 scoreable zones. Each of the four category GIS columns had 20 missing entries. Availability and scoreability are evaluated separately.
- **Score and account isolation.** Repeated API requests returned identical ranked records. The authenticated checks exercised two separate vendors, ownership enforcement, fresh preference reads, strict division, Anywhere and expansion. Missing coordinates or GIS remain explicit, and unscorable zones have null suitability.
- **Regression coverage.** 49 recommendation, authentication, migration and API checks passed with SQLite and disposable PostgreSQL 17. Another 51 slot, GIS, application and allocation tests passed. The frontend passed 63 standard checks plus 10 explorer and deployment checks. The production build passed.
- **Browser workflow.** Headless Edge passed the six-input form, touch pin selection at 320 and 390 px, immediate refresh, preference persistence after reload, Expand Search, English, Marathi, Hindi, and unscorable explorer entries.
- **Data scope.** The audit copied the operational snapshot through a read-only SQLite connection. API and workflow tests used disposable databases. The available local snapshot contained 10 pilot slot rows, so verification of the 115-slot inventory requires the operational environment that contains it. The recommendation changes have no slot, allocation or application write path.

## Reproduce and run the demo

Generate the CSV and JSON summary from the repository root. The evaluator uses the bundled operational database read-only and derives winners from the active model and actual GIS reference points.

```powershell
.venv/Scripts/python.exe extra/validation/12_validate_recommendation_inputs.py
```

Launch the backend using the intended demonstration database and the normal startup procedure. The preference schema uses the existing additive migration. Set these independently configurable demo flags in the backend process:

```powershell
$env:BUSINESS_AWARE_MCDA_EXPERIMENT = 'true'
$env:LOCATION_RANKING_EXPERIMENT = 'true'
$env:LOCATION_PROXIMITY_WEIGHT = '0.15'
$env:LOCATION_PROXIMITY_DECAY_KM = '3'
```

Use the existing FastAPI and Vite startup commands in the [README](../../../README.md). The demo environment's current capacity can change which eligible zones are returned.
