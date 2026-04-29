---
name: Trial length policy — open decision (default option 2, A/B test option 3)
description: Marketing doc §14 lists trial-length options; this captures the framing, the SaaS conversion data, and the recommended path (default to $0/14-day auto-extend, A/B-test $19/30-day paid against it).
type: project
originSessionId: 1081317d-f863-470f-ab07-65ddc614e856
---
## Open decision

Trial length is currently $0/7-day. Marketing doc §14 says don't change immediately — watch trial-conversion data 60+ days first. But three options to evaluate are pre-staged:

## The trade space

| Trial design | Top-of-funnel | Trial→paid conversion | Quiet-week problem |
|---|---|---|---|
| **$0/7d (current)** | High (CC required helps) | Low — many never see a signal in a quiet week | **Unsolved** |
| **$0/14d w/ auto-extend if quiet** *(marketing-doc recommended first move)* | ≈ current | Higher (everyone sees ≥1 signal before deciding) | **Solved** |
| **$19/30d paid** *(Erik's option)* | Lower (CC + commitment to actual charge) | Highest (paid SaaS trials run 40-60% vs 5-15% for free) | Largely solved |
| $0/30d no-credit-card | Highest | Lowest (tire-kicker magnet) | Solved but trial-abuse risk |

## Empirical SaaS pattern

- **Free trials**: typical conversion 5-15%
- **Paid trials**: typical conversion 40-60%
- Reason: $19 isn't about revenue, it's about *qualifying intent*. Anyone who paid $19 has crossed the "I am a customer" threshold internally; the leap from $19 → $129 is psychologically smaller than free → $129.

## Recommended path (when ready to act)

**Default new signups → $0/14d auto-extend** (marketing doc's recommended first move).

**A/B-test 50% → $19/30d paid** against the default. Specifically:
- Random assignment at signup
- Track for 60 days: trial→paid conversion AND signups within first 60 days
- Compare net paid subscribers, not trial signups
- Pick the winner; memorialize in marketing doc + here

## Considerations that could shift the choice

- **If clean-data 8-date avg is STRONG (Scenario A from project_marketing_strategy_doc.md tensions)**: more attractive product = wider leeway on trial design = default ($0/14d) is fine.
- **If clean-data numbers are SOLID-BUT-NOT-STELLAR (Scenario B/C)**: $19 paid trial becomes MORE important. You want only-genuinely-interested users early so word-of-mouth comes from people who actually understood the value, not freeloaders who churned.
- **If numbers are WORSE (Scenario D)**: trial design isn't the problem — the product is. Don't optimize trial length until the strategy story is fixed.

## Engineering cost (when chosen)

- $0/14d auto-extend: ~3-4 hours. Modify trial logic to check signal-fired-during-trial; extend by 7 days if not.
- $19/30d paid: ~2-3 hours + Stripe config. New SKU, billing logic for the upgrade path ($19 trial → $129 ongoing).
- A/B harness: ~2 hours to build random assignment + tracking.

## What's currently in code

- 7-day free trial, CC required (Stripe Checkout)
- Cancel via Stripe Customer Portal
- `send_winback_email` exists for trial-exit-without-conversion (currently fires on simple time delay)
- `send_onboarding_email` step 5 (Day 8) is the existing "win-back" with COMEBACK20 promo code

## Don't act before launch + 60 days

Marketing doc §14 explicitly says: *"Don't change immediately. Watch trial-conversion data for 60+ days first, then revisit."* Decision is queued for that revisit point — not a launch-blocking item.
