# 1. The product

## The problem in one paragraph

Our company (the *supplier*) sells wear-protection products to industrial plants: cement, power, steel, mining. When a part in a plant wears out, a technician calls the supplier, and a sales engineer goes back and forth to work out what's wrong and what to sell. That's slow, it depends on who picks up the phone, and it misses chances to recommend a product that would last longer.

## What Plant Advisor does

A technician photographs the worn part and answers a few questions. Within minutes they get a **preliminary diagnosis and three recommended products**. On our side, the request becomes a **ticket** that an engineer checks, discusses with an AI assistant if needed, approves, and turns into a quote.

## Who uses it

| Person | Where | What they do |
|---|---|---|
| **Plant technician** | Phone app | Takes photos, answers questions, sees the recommendation, calls or texts us, gets the quote |
| **Engineer** (our side) | Desktop console | Reviews each ticket, approves or corrects the diagnosis and products |
| **Salesperson** (our side) | Desktop console | Contacts the customer, sends the quote, updates the status. Can be the same person as the engineer |
| **Admin** (our side) | Desktop console | Approves product data and rules, invites plant users |

## The journey of one request

1. **Join.** The plant was set up in advance by us. A technician joins with an invite link or plant code, so they never type plant details.
2. **Capture.** The app guides three photos: overview, close-up, and one with a coin for scale. It rejects blurry or dark photos on the spot.
3. **Answer.** A few questions: what material hits the part, how hot it gets, wet or dry, and so on.
4. **Analyze.** The request joins a queue. A background worker runs a fixed seven-step analysis:
   1. Gathers the context: which part, what's installed, past requests.
   2. An AI model describes what it *sees* in the photos, using a fixed list of wear features (for example "grooves along the flow").
   3. Code (not AI) scores the likely wear causes from those features and the answers: abrasion, erosion, impact, corrosion, heat, sticking.
   4. Rules turn the diagnosis into requirements (for example "abrasion resistance at least 4 out of 5"). Only products that meet them are candidates. The AI ranks the candidates and must cite data-sheet values.
   5. Code double-checks the result: temperature limits, sizes offered, not repeating a product that already failed.
   6. A confidence score is calculated, and the AI writes a short explanation.
5. **Preliminary result.** The technician sees the diagnosis and top three products, marked *Preliminary*. If confidence is low or the checks failed, products are hidden and they see "an engineer is reviewing this."
6. **Ticket.** Our staff get an email with a link to the ticket: photos, diagnosis, products with citations, checks, confidence, and an AI chat that knows the ticket.
7. **Review.** An engineer approves or edits. The technician now sees it as *Confirmed*.
8. **Quote.** Sales sends a PDF quote and updates the status.
9. **Follow-up.** Weeks later, the app asks how long the new product lasted. Good outcomes strengthen future recommendations; fast failures flag a rule for review.

## Why it's built this way (the short version)

- **Accuracy over speed.** The AI does what it's good at (seeing and writing), while code does the deciding, so the same photo and answers always give the same result. See [decision 0002](03-decisions.md#0002-recommendations-from-rules-not-vector-search).
- **A human approves everything** before a quote goes out.
- **It learns only from reviewed work.** Nothing the AI says becomes "knowledge" until an engineer has approved it.
- **New product families don't need new code.** Each family's vocabulary, questions, weights and rules live in a *playbook* file.

## What the MVP includes, and what it doesn't

**In:** one supplier, one product family (wear protection: 9 wear plates and 2 welding wires), the phone app, the console, quotes as PDFs, the ticket chat, and a test harness that measures accuracy.

**Not yet:** spare parts, WhatsApp, other languages, connections to ERP or CRM systems, automatic pricing, a native app store app.
