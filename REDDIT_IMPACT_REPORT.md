# Reddit Integration — Full-Cycle Impact Report
_Generated 2026-07-16 20:01 UTC_

## 1. Headline result (A/B)

**Reddit priorities HELP** (n=89, same provider both arms — isolates the Reddit effect)

| Arm | Spearman rho | AUC (flop vs monopoly) |
|---|---|---|
| With Reddit priorities | 0.359 | 0.752 |
| Without priorities | 0.311 | 0.728 |
| **Delta** | **+0.048** | **+0.024** |

## 2. What Reddit data was collected

Source: Arctic Shift archive API. Total: **1090 high-signal comments** across **10 categories** (score>=5, 10-400 words, deduped, buying-intent threads only).

| Category | Comments kept |
|---|---|
| health_fitness_apps | 237 |
| education_apps | 196 |
| kitchen_appliances | 136 |
| finance_apps | 121 |
| wireless_headphones | 103 |
| bluetooth_speakers | 96 |
| power_banks | 85 |
| productivity_apps | 51 |
| smartwatches | 47 |
| smartphones | 18 |

## 3. What changed in the category profiles

Reddit affects **Stage F (profiles)** and **Stage G (bridging prompt)** only — training (aspect extraction, labels, features, XGBoost models) is untouched, so the models themselves did not change.

### consumer_priorities added per category

**bluetooth_speakers** — _NEW_
> Here are the priorities for consumers in the "bluetooth_speakers" category based on the Reddit discussions:
* Sound quality is a top priority, with many users discussing the importance of clear and balanced sound
* Value for money is also important, with users seeking affordable options that deliver good sound quality
* Brand reputation and product quality are considered, with some users expressing skepticism about certain brands and their business decisions
* Room placement and acoustics are also discussed, with users sharing tips on how to optimize speaker placement for the best sound
* Dura

**education_apps** — _NEW_
> Here are 3-6 short bullet points summarizing what consumers in the "education_apps" category prioritize when choosing a product, based on the Reddit discussions:

* Effective and engaging learning methods, with some users preferring interactive approaches and others valuing traditional textbook-style learning
* Authenticity and quality of content, with users expressing frustration with "AI slop" and low-quality resources
* Personalization and flexibility, with users seeking learning experiences that cater to their individual needs and goals
* Community and support, with some users valuing the 

**finance_apps** — _NEW_
> Here are 3-6 short bullet points summarizing what consumers in the "finance_apps" category prioritize when choosing a product, based on the Reddit discussions:

* Affordability and cost-effectiveness, with a focus on avoiding unnecessary expenses and saving money
* Long-term financial planning and stability, including investing, saving for retirement, and building an emergency fund
* Avoiding debt and high-interest rates, with a preference for paying off loans and credit cards quickly
* Transparency and simplicity in financial products and services, with a desire to understand and manage finan

**health_fitness_apps** — _NEW_
> Here are 3-6 short bullet points summarizing what consumers in the "health_fitness_apps" category prioritize when choosing a product, based on the Reddit discussions:

* Sustainable and long-term weight loss methods over quick fixes
* Healthy relationships with food and exercise, rather than restrictive dieting or overexercising
* Progress tracking and accountability, such as calorie counting and exercise monitoring
* Mental health and self-care, including building confidence and self-acceptance
* Flexibility and adaptability in fitness routines, such as incorporating rest days and cheat meals

**kitchen_appliances** — _NEW_
> Here are the priorities for consumers in the "kitchen_appliances" category based on the Reddit discussions:
* Quality and durability of the product
* Good customer service and support
* Trust in the brand and its manufacturing process
* Value for money and affordability
* Ease of use and maintenance of the product 
* Reliability and performance of the product

**power_banks** — _NEW_
> Here are the top priorities for consumers in the "power_banks" category based on the Reddit discussions:
* Safety: avoiding fire hazards, explosion risks, and damage to devices
* Quality: looking for well-made products from reputable brands, with proper certifications and labeling
* Compatibility: ensuring the power bank and cables are compatible with their devices and meet their power needs
* Authenticity: being wary of counterfeit or misleading products, especially those with fake certifications or logos
* Performance: considering the power bank's capacity, discharge rate, and charging speed

**productivity_apps** — _NEW_
> Here are the top priorities for consumers in the "productivity_apps" category based on the Reddit discussions:

* Simplicity and ease of use: Many users prefer simple tools that don't overwhelm them with features or complexity.
* Small, achievable goals: Breaking down tasks into tiny, manageable steps helps build momentum and consistency.
* Flexibility and adaptability: Users value apps that allow them to adjust their goals and habits as needed, without feeling guilty or stuck.
* Minimalism and clutter reduction: Many users prioritize decluttering their digital and physical spaces to reduce st

**smartphones** — _NEW_
> Here are the priorities for consumers in the "smartphones" category based on the Reddit discussions:
* Value for money, with many users considering mid-range or budget options as viable alternatives to flagship devices
* Performance and features, such as battery life, camera quality, and processing power
* Ecosystem and compatibility, with some users prioritizing seamless integration with other devices and services
* Freedom and customization, with some Android users valuing the ability to personalize and control their device
* Brand loyalty and familiarity, with some users sticking with a par

**smartwatches** — _NEW_
> Here are the priorities for consumers in the "smartwatches" category based on the Reddit discussions:
* Accuracy and reliability of health and fitness tracking features
* Battery life and performance
* Durability and build quality
* Compatibility with other devices and apps
* Price and value for money
* Customization options and ease of use

**wireless_headphones** — _NEW_
> Here are the priorities of consumers in the "wireless_headphones" category based on the Reddit discussions:
* Sound quality is a top priority, with many users seeking headphones with accurate and detailed sound reproduction.
* Build quality and durability are also important, with users looking for headphones that can withstand regular use and potential accidents.
* Reliability and customer service are crucial, as users want to be able to get help when their headphones break or experience issues.
* Comfort and fit are significant factors, with users seeking headphones that are comfortable to we

### Sanity check — non-Reddit profile stats unchanged

All price/label/aspect stats identical before vs after — only `consumer_priorities` was added.

## 4. Live spec review + prediction (post-Reddit)

**Product:** AeroPods Pro X @ $79.99 (wireless_headphones)

- **Design viability:** 50-60/100 (aspects-only)
- **Market percentile:** 25.8th vs 90 real products
- **Confidence:** 85%, ungrounded aspects: 2
- **Top risk:** ease_of_use (-2.71)

**Spec coach summary:** The draft provides a strong foundation of technical specifications but lacks critical details regarding long-term reliability, repairability, and support processes that address common consumer pain points.

- Covered: utility, ease_of_use, design_appeal, after_sales, build_quality
- Missing: repairability

## 5. Observations across the cycle

- Arctic Shift required a custom User-Agent (default python UA -> 403) and pacing (429 rate limits); collector retries/caches per category so the sweep is resumable.
- Gemini free-tier daily quota was exhausted during the run; Stage F and the A/B fell through to Groq. The A/B uses the **same provider for both arms**, so the delta remains a clean measure of the Reddit effect.
- Reddit priorities enter only at bridging; if the A/B delta is ~0, that is an honest negative finding (the review-derived category stats may already capture what consumers prioritise).
