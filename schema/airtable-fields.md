# Airtable Base Structure

## PROPERTIES Table
- Property Name (Single Line)
- Address (Single Line)
- Waste Score (Number 0-100)
- Est. Penalty (Currency)
- Tier (Formula)
- Assigned Crew (Link to CREWS)
- Stripe Link (URL)
- Status (Single Select: Hot / Warm / Nurture / Client)

## CREWS Table
- Name
- Lead
- Phone
- Channel (Telegram / ClickSend)
- Tribe Score (Number)

## AUDITS Table
- Waste Score
- Penalty
- Route Overlap %
- Crew Idle Mins
- Fuel Burn Score

Full schema + deployment checklist coming in next commit.