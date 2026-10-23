"""Banking intent routing — messages a retail-bank customer sends to a chatbot.

Ten intents, ~120 rows each. Hard rows mention vocabulary from a
neighbouring intent (ATMs, transfers, exchange rates, lost cards …) while
the requested action still clearly belongs to exactly one label under the
boundary rules written into ``LABELS``.
"""

from __future__ import annotations

import random

from ._common import FIRST_NAMES, MONTHS, WEEKDAYS, amount, digits, full_name, label_items, merge

SLUG = "intent_routing"
NAME = "Banking Intent Routing"
DESCRIPTION = (
    "1,200 synthetic messages a retail-bank customer sends to a chatbot, each labeled with one of "
    "10 intents: balance, transfers, lost/stolen cards, disputes, loans, personal-info updates, "
    "new accounts, exchange rates, ATM problems and card activation."
)
LANGUAGE = "en"
TASK = "Which banking intent does this customer message express?"

LABELS = [
    {
        "name": "check_balance",
        "description": (
            "The customer asks how much money is in, available on or currently due on a checking, "
            "savings or credit-card account (current, available or pending balance). Loan and mortgage "
            "balances are loan_inquiry; a balance that is wrong because of an ATM deposit or withdrawal "
            "is atm_issue; contesting a charge is dispute_transaction."
        ),
    },
    {
        "name": "transfer_money",
        "description": (
            "The customer wants to send money to another person or move it between their own accounts: "
            "P2P payments, wires, international transfers, adding a payee, and setting up, changing or "
            "cancelling scheduled or recurring transfers. Only asking what conversion rate or fee would "
            "apply is exchange_rate; paying toward a loan or mortgage is loan_inquiry."
        ),
    },
    {
        "name": "card_lost_stolen",
        "description": (
            "The customer reports a card as lost, misplaced or stolen, or asks to block, freeze, lock or "
            "cancel a card because it is missing or stolen (including requesting a replacement for it). "
            "A card kept by an ATM is atm_issue; contesting specific charges once the loss is already "
            "reported is dispute_transaction; activating the replacement is card_activation."
        ),
    },
    {
        "name": "dispute_transaction",
        "description": (
            "The customer contests a specific charge or debit: unrecognised, fraudulent, duplicated, "
            "wrong amount, a cancelled subscription still billed, or a refund that never arrived — "
            "including chargebacks and contesting a fee already posted. Cash an ATM failed to dispense "
            "is atm_issue; reporting the card itself lost or stolen is card_lost_stolen."
        ),
    },
    {
        "name": "loan_inquiry",
        "description": (
            "The customer asks about borrowing: personal, auto, student or business loans, mortgages "
            "and home-equity credit — rates, eligibility, applications, pre-approval, payments, "
            "remaining balance or payoff, early repayment, deferral or refinancing. 'Rate' questions "
            "about currency conversion are exchange_rate."
        ),
    },
    {
        "name": "update_personal_info",
        "description": (
            "The customer wants to change or correct personal details on file: postal or mailing "
            "address, phone number, email address, or legal or preferred name. This label applies "
            "even when the reason involves another topic (e.g. missed transfer codes or a card mailed "
            "to an old address), as long as the request is the update itself."
        ),
    },
    {
        "name": "open_account",
        "description": (
            "The customer wants to open a new deposit account — checking, savings, joint, student, "
            "child or business — or asks about the requirements, documents, minimum deposit, features "
            "or fees of opening one. Taking out a loan is loan_inquiry, not opening an account."
        ),
    },
    {
        "name": "exchange_rate",
        "description": (
            "The customer asks about currency conversion: exchange rates, how much an amount is worth "
            "in another currency, or the fees and markups for paying, withdrawing or converting in a "
            "foreign currency (including foreign ATM withdrawal fees). Actually sending money abroad "
            "is transfer_money; contesting a fee already charged is dispute_transaction."
        ),
    },
    {
        "name": "atm_issue",
        "description": (
            "The customer has a problem with an ATM or ATM transaction — card retained or stuck, cash "
            "not dispensed or short (even if the account was debited), ATM errors or out-of-service "
            "machines, ATM deposits not credited — or wants to find an ATM. Fees for withdrawing cash "
            "abroad are exchange_rate; a card lost elsewhere is card_lost_stolen."
        ),
    },
    {
        "name": "card_activation",
        "description": (
            "The customer wants to activate a newly received, renewed or replacement card, set the PIN "
            "for that new card, or asks whether a new card is not working because it still needs "
            "activating. Reporting a card lost or stolen is card_lost_stolen."
        ),
    },
]

# ── Slot generators ─────────────────────────────────────────────────────

_ASCII_LAST = [
    "Smith", "Silva", "Johnson", "Patel", "Wang", "Khan", "Garcia", "Mueller", "Rossi", "Kim",
    "Nguyen", "Brown", "Costa", "Ivanova", "Okafor", "Lopez", "Bennett", "Haddad", "Novak", "Reyes",
]


def _ordinal(n: int) -> str:
    if 10 <= n % 100 <= 20:
        return f"{n}th"
    return str(n) + {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")


def _past(rng: random.Random) -> str:
    """A past time reference that reads naturally after a verb ("charged ...")."""
    style = rng.randint(0, 4)
    if style == 0:
        return rng.choice(["yesterday", "this morning", "last night", "earlier today", "over the weekend", "last week"])
    if style == 1:
        return f"last {rng.choice(WEEKDAYS)}"
    if style == 2:
        return f"on {rng.choice(MONTHS)} {rng.randint(1, 28)}"
    if style == 3:
        return f"{rng.choice(['two', 'three', 'four', 'five', 'six'])} days ago"
    return f"on the {_ordinal(rng.randint(1, 28))}"


def _future(rng: random.Random) -> str:
    """A future date that reads naturally after "for" ("scheduled for ...")."""
    style = rng.randint(0, 3)
    if style == 0:
        return rng.choice(["tomorrow", "payday", "the end of the month", "next week"])
    if style == 1:
        return f"next {rng.choice(WEEKDAYS)}"
    if style == 2:
        return f"{rng.choice(MONTHS)} {rng.randint(1, 28)}"
    return f"the {_ordinal(rng.randint(1, 28))}"


def _atm_amount(rng: random.Random) -> str:
    return f"${rng.randrange(20, 820, 20)}"


def _atm_short(rng: random.Random) -> str:
    requested = rng.randrange(60, 820, 20)
    got = rng.randrange(20, requested, 20)
    return f"${got} of the ${requested}"


def _round_money(rng: random.Random, choices: list[int]) -> str:
    return f"${rng.choice(choices):,}"


def _cash(rng: random.Random) -> str:
    return f"${rng.randrange(40, 2000, 10):,}"


def _short(rng: random.Random) -> str:
    return f"${rng.randrange(20, 300, 10)}"


def _overcharge_checkout(rng: random.Random) -> str:
    low = rng.uniform(8, 600)
    high = low + rng.choice([5, 10, 15, 20, 25, 40, 50, 100]) + rng.choice([0, 0.5, 0.99])
    return f"${high:,.2f} but the price at checkout was ${low:,.2f}"


def _overcharge_receipt(rng: random.Random) -> str:
    low = rng.uniform(8, 600)
    high = low * rng.choice([2, 10]) if rng.random() < 0.3 else low + rng.randint(3, 90)
    return f"the receipt says ${low:,.2f} but my account shows ${high:,.2f}"


def _fx_usd(rng: random.Random) -> str:
    if rng.random() < 0.5:
        return _round_money(rng, [50, 100, 200, 250, 300, 500, 750, 1000, 1500, 2000, 2500, 5000, 10000])
    return amount(rng, 20, 3000)


def _fee(rng: random.Random) -> str:
    return f"${rng.randint(1, 9)}.{rng.randint(0, 99):02d}"


def _foreign_amount(rng: random.Random) -> str:
    value = rng.choice([50, 80, 100, 120, 150, 200, 250, 300, 400, 500, 750, 1000, 1200, 1500, 2000, 3000, 5000])
    cur = rng.choice(["euros", "British pounds", "Canadian dollars", "Swiss francs", "Australian dollars"])
    if rng.random() < 0.25:
        value, cur = value * 100, rng.choice(["yen", "pesos", "rupees", "won", "baht"])
    return f"{value:,} {cur}"


_LOAN_KINDS = [
    ("personal loan", 3, 50, [2, 3, 4, 5]),
    ("car loan", 8, 70, [3, 4, 5, 6]),
    ("mortgage", 150, 900, [15, 20, 30]),
    ("home equity loan", 20, 150, [5, 10, 15]),
    ("small business loan", 15, 250, [3, 5, 7, 10]),
    ("home improvement loan", 5, 60, [3, 5, 7]),
    ("debt consolidation loan", 5, 40, [3, 4, 5]),
]


def _loan_request(rng: random.Random) -> str:
    kind, lo, hi, _ = rng.choice(_LOAN_KINDS)
    return f"a ${rng.randint(lo, hi) * 1000:,} {kind}"


def _loan_request_term(rng: random.Random) -> str:
    kind, lo, hi, terms = rng.choice(_LOAN_KINDS)
    return f"a ${rng.randint(lo, hi) * 1000:,} {kind} over {rng.choice(terms)} years"


def _biz_loan(rng: random.Random) -> str:
    return f"a ${rng.randint(10, 250) * 1000:,} small business loan"


def _house_price(rng: random.Random) -> str:
    return f"${rng.randint(180, 950) * 1000:,}"


def _down_payment(rng: random.Random) -> str:
    return f"${rng.randint(10, 150) * 1000:,}"


_STREETS = [
    "Maple", "Oak", "Cedar", "Elm", "Pine", "Willow", "Birch", "Lakeview", "Hillcrest", "Sunset",
    "Highland", "Park", "River", "Chestnut", "Juniper", "Harbor", "Meadow", "Spruce", "Ash", "Magnolia",
]


def _address(rng: random.Random) -> str:
    street = f"{rng.randint(1, 9899)} {rng.choice(_STREETS)} {rng.choice(['Street', 'Avenue', 'Road', 'Lane', 'Drive', 'Court', 'Blvd'])}"
    if rng.random() < 0.35:
        street += f", Apt {rng.randint(1, 40)}{rng.choice(['', 'A', 'B', 'C'])}"
    if rng.random() < 0.4:
        street += f", {rng.choice(['Springfield', 'Riverton', 'Fairview', 'Oakdale', 'Clearwater', 'Brookside', 'Millbrook'])}"
    return street


def _phone(rng: random.Random) -> str:
    a, b, c = rng.randint(201, 989), rng.randint(200, 999), rng.randint(0, 9999)
    style = rng.randint(0, 2)
    if style == 0:
        return f"({a}) {b}-{c:04d}"
    if style == 1:
        return f"{a}-{b}-{c:04d}"
    return f"{a}{b}{c:04d}"


def _email(rng: random.Random) -> str:
    first = rng.choice(FIRST_NAMES).lower()
    last = rng.choice(_ASCII_LAST).lower()
    domain = rng.choice(["mailbox.com", "inboxly.net", "postmail.org", "fastmail.test", "webmail.co"])
    style = rng.randint(0, 2)
    if style == 0:
        return f"{first}.{last}@{domain}"
    if style == 1:
        return f"{first}{rng.randint(1, 99)}@{domain}"
    return f"{first[0]}{last}{rng.randint(70, 99)}@{domain}"


def _expiry(rng: random.Random) -> str:
    return f"{rng.randint(1, 12):02d}/{rng.randint(27, 31)}"


SLOTS = {
    "amount": lambda r: amount(r, 15, 1500),
    "amount2": lambda r: amount(r, 15, 1500),
    "small_amt": lambda r: amount(r, 5, 180),
    "rent": lambda r: f"${r.randrange(650, 3300, 25):,}",
    "charge": lambda r: amount(r, 4, 950),
    "overcharge_checkout": _overcharge_checkout,
    "overcharge_receipt": _overcharge_receipt,
    "cash_amt": _cash,
    "short_amt": _short,
    "fx_usd": _fx_usd,
    "min_dep": lambda r: _round_money(r, [10, 20, 25, 50, 100, 200]),
    "monthly": lambda r: _round_money(r, [50, 75, 100, 150, 200, 250, 300, 400, 500, 750, 1000]),
    "deposit_round": lambda r: _round_money(r, [500, 1000, 2000, 2500, 5000, 10000, 25000]),
    "fee_amt": _fee,
    "atm_amt": _atm_amount,
    "atm_short": _atm_short,
    "foreign_amount": _foreign_amount,
    "loan_request": _loan_request,
    "loan_request_term": _loan_request_term,
    "biz_loan": _biz_loan,
    "house_price": _house_price,
    "down": _down_payment,
    "last4": digits(4),
    "acctnum": digits(10),
    "routing": digits(9),
    "txn": lambda r: f"TXN-{r.randint(100000, 999999)}",
    "past": _past,
    "future": _future,
    "address": _address,
    "phone": _phone,
    "email": _email,
    "email2": _email,
    "exp": _expiry,
    "first": FIRST_NAMES,
    "fullname": full_name,
    "last": _ASCII_LAST,
    "last2": _ASCII_LAST,
    "ordinal": lambda r: _ordinal(r.randint(1, 28)),
    "age": lambda r: str(r.randint(6, 17)),
    "acct": [
        "checking", "savings", "checking account", "savings account", "joint account", "business account",
        "everyday checking", "high-yield savings", "main account", "student checking", "emergency savings",
        "holiday savings", "personal checking", "rainy-day savings", "kids' savings", "money market account",
        "college fund", "travel savings", "joint checking", "business checking", "premier checking",
        "everyday account", "household account",
    ],
    "acct_chk": [
        "checking", "checking account", "everyday checking", "student checking", "personal checking", "joint checking",
        "business checking", "premier checking", "main account", "household account",
    ],
    "acct_pair": [
        "checking and savings", "savings and joint account", "business and personal checking",
        "checking and credit card", "joint and personal savings", "everyday checking and holiday savings",
        "savings and money market account", "two checking accounts", "personal and joint checking",
        "business checking and business savings", "checking and college fund",
        "checking and rewards credit card",
    ],
    "acct_move": [
        "from my checking to my savings", "from savings to checking", "from my business account to my personal checking",
        "from our joint account to my savings", "out of my emergency savings into checking",
        "from checking into my holiday savings", "from my high-yield savings to checking",
    ],
    "cc": [
        "credit card", "rewards credit card", "cashback credit card", "travel credit card",
        "card ending in {last4}", "credit card ending {last4}",
    ],
    "card": [
        "debit card", "credit card", "card", "rewards credit card", "travel card", "contactless debit card",
        "cashback credit card", "business debit card", "platinum debit card", "student debit card",
        "premium credit card", "joint account debit card", "gold credit card", "secured credit card",
        "corporate card", "airline miles credit card", "teen debit card",
    ],
    "first_card": [
        "first debit card", "first credit card", "first business debit card", "first student debit card",
        "very first credit card", "first rewards card", "first teen debit card", "first secured credit card",
        "first card since opening my account",
    ],
    "payee": [
        "{first}", "{first}", "{fullname}", "my mom", "my dad", "my sister", "my brother", "my landlord",
        "my roommate", "my cousin {first}", "my friend {first}", "my son", "my daughter", "my babysitter",
        "my coworker {first}", "my grandmother",
    ],
    "friend": [
        "{first}", "{fullname}", "my friend {first}", "my roommate", "my sister", "my brother",
        "my coworker {first}", "my neighbor {first}",
    ],
    "split_reason": [
        "dinner", "the concert tickets", "groceries", "the Airbnb", "gas money", "the birthday gift",
        "the cab ride", "last weekend's trip", "the electricity bill", "the pizza", "my half of the hotel",
        "the parking", "the movie tickets", "the wedding gift",
    ],
    "p2p": ["QuickPay", "PayLink", "SendIt", "the app's instant pay"],
    "other_bank": [
        "Northwind Bank", "Harborview Credit Union", "Maple Ridge Bank", "Bluestone Bank", "Crescent Federal",
        "Pinecrest Savings", "Silverline Bank", "Redcliff Bank", "Granite State Bank",
        "Evergreen Credit Union", "Lighthouse Bank", "Prairie National", "Copperfield Bank", "Summit Federal",
    ],
    "freq": [
        "every week", "every month", "every two weeks", "every Friday", "every payday",
        "on the 1st of every month", "on the 15th of each month",
    ],
    "kid": [
        "son", "daughter", "kid", "teenager", "stepson", "niece", "stepdaughter", "nephew", "grandson",
        "granddaughter", "youngest", "oldest",
    ],
    "partner": [
        "wife", "husband", "partner", "girlfriend", "boyfriend", "mom", "dad", "business partner", "fiancée",
        "sister", "brother", "son", "daughter", "grandma", "roommate",
    ],
    "lost_where": [
        "at the gym", "on the bus", "at a bar", "at the airport", "on the subway", "at the supermarket",
        "in a taxi", "at a concert", "at work", "downtown", "at the beach", "at a restaurant", "at the mall",
        "on the train", "at the park", "at the library", "at the hospital", "at my kid's school", "at a hotel",
        "at the farmers market", "on a flight", "at the cinema", "at a coffee shop", "at a gas station",
    ],
    "lost_when": [
        "this morning", "last night", "yesterday", "an hour ago", "over the weekend", "earlier today",
        "on my way home", "while I was at work", "at lunch", "on Saturday", "two days ago",
        "during my commute", "this afternoon", "sometime yesterday", "on Friday night",
    ],
    "missing_since": ["yesterday", "last night", "Friday", "the weekend", "this morning", "Tuesday", "lunchtime"],
    "merchant": [
        "Brightmart", "QuickFuel", "StreamPlus", "Lumen Electronics", "Cafe Aurora", "ZipRide", "ShopNest",
        "PixelPlay Games", "Greenleaf Grocers", "FlyHigh Airlines", "Urban Threads", "Nimbus Cloud Storage",
        "Harbor Hotel", "FitZone Gym", "MegaBuy Online", "TasteBox Meals", "GadgetHub", "Bookworm Online",
        "PetPals Store", "SneakerVault", "Sunrise Pharmacy", "MetroParking",
    ],
    "shop": [
        "ShopNest", "MegaBuy Online", "Urban Threads", "Lumen Electronics", "PixelPlay Games",
        "HomeHaven Decor", "GadgetHub", "Bookworm Online", "PetPals Store", "KitchenCraft", "SneakerVault",
        "Toyland Direct",
    ],
    "subscription": [
        "StreamPlus", "Nimbus Cloud Storage", "FitZone Gym", "TasteBox Meals", "NewsDaily", "TuneBox Music",
        "CloudVault", "FitStream", "LingoLearn", "BoxOfBooks",
    ],
    "booking_merchant": [
        "Harbor Hotel", "ZipRide", "FlyHigh Airlines", "Seaside Inn", "RoadRunner Car Rental",
        "Skyway Airlines", "Lakeside Resort", "CityCab",
    ],
    "restaurant": ["Cafe Aurora", "Trattoria Sole", "Blue Lotus", "La Brasa Grill", "The Copper Pot", "Sakura House"],
    "few": ["two", "three", "four", "a few", "several", "five"],
    "qty": ["two", "three", "four", "five"],
    "loan": [
        "personal loan", "car loan", "vehicle loan", "mortgage", "home equity loan", "student loan",
        "small business loan", "home improvement loan", "debt consolidation loan", "used car loan",
        "new car loan", "motorcycle loan", "boat loan", "land loan", "construction loan",
        "home equity line of credit", "bridge loan", "solar panel loan", "medical loan", "tuition loan",
        "jumbo mortgage", "second mortgage", "fixed-rate mortgage",
    ],
    "loan_term": [
        "15-year fixed mortgage", "30-year fixed mortgage", "5/1 adjustable-rate mortgage",
        "3-year personal loan", "5-year car loan", "60-month auto loan", "7-year home improvement loan",
        "10-year small business loan", "20-year fixed mortgage", "10-year fixed mortgage",
        "4-year personal loan", "72-month auto loan", "48-month used car loan", "7/1 adjustable-rate mortgage",
        "15-year home equity loan",
    ],
    "loan_plural": [
        "home equity lines of credit", "debt consolidation loans", "green energy loans", "boat loans",
        "personal loans for people with fair credit", "loans for used cars", "jumbo mortgages",
        "motorcycle loans", "construction loans", "tuition loans", "loans for solar panels",
        "credit-builder loans", "bridge loans",
    ],
    "refi": [
        "mortgage", "car loan", "student loans", "home loan", "auto loan", "second mortgage",
        "home equity loan", "personal loan", "motorcycle loan",
    ],
    "newacct": [
        "checking account", "savings account", "joint checking account", "joint savings account",
        "business checking account", "student checking account", "kids' savings account",
        "high-yield savings account", "money market account", "basic checking account",
        "premium checking account", "teen checking account", "certificate of deposit",
        "senior checking account", "second savings account", "rewards checking account",
        "custodial savings account", "health savings account",
    ],
    "business": [
        "bakery", "consulting business", "new LLC", "food truck", "small online store", "landscaping company",
        "photography studio", "dental practice", "coffee shop", "nonprofit", "hair salon", "plumbing business",
        "tutoring service", "small farm", "craft brewery",
    ],
    "purpose": [
        "bills", "my side business", "household expenses", "travel", "rent", "my freelance income",
        "groceries", "my kids' allowance", "subscriptions", "holiday shopping", "my wedding budget",
        "car expenses",
    ],
    "feature": [
        "no monthly fees", "free overdraft protection", "the best cashback", "paper checks",
        "early direct deposit", "no minimum balance", "interest on my balance", "free ATM withdrawals",
        "a debit card with cashback", "no foreign transaction fees", "mobile check deposit",
        "joint access for my partner",
    ],
    "goal": [
        "Vacation fund", "House deposit", "Emergency fund", "Wedding", "New car", "Rainy day", "Car repairs",
        "Christmas gifts", "Kids' college", "Home renovation", "Travel 2027", "Tax money",
    ],
    "university": [
        "Lakeside University", "Westbrook College", "Northfield State", "Crestview University",
        "Riverside Community College", "Hillcrest Institute", "Southgate University", "Pine Valley College",
    ],
    "currency": [
        "euros", "British pounds", "Japanese yen", "Mexican pesos", "Canadian dollars", "Swiss francs",
        "Australian dollars", "Indian rupees", "Brazilian reais", "South Korean won", "Thai baht",
        "Turkish lira", "Polish zloty", "Danish kroner", "Norwegian kroner", "Singapore dollars",
        "Hong Kong dollars", "New Zealand dollars", "South African rand", "Chinese yuan", "Czech koruna",
        "Hungarian forint", "Moroccan dirhams", "Philippine pesos", "Colombian pesos",
    ],
    "currency_sg": [
        "euro", "British pound", "Japanese yen", "Mexican peso", "Canadian dollar", "Swiss franc",
        "Australian dollar", "Indian rupee", "Brazilian real", "Thai baht", "Turkish lira", "Danish krone",
        "Norwegian krone", "Singapore dollar", "Hong Kong dollar", "New Zealand dollar", "South African rand",
        "Chinese yuan", "Czech koruna", "Hungarian forint", "Moroccan dirham", "Philippine peso",
    ],
    "code": [
        "EUR", "GBP", "JPY", "MXN", "CAD", "CHF", "AUD", "INR", "BRL", "SEK", "NZD", "NOK", "SGD", "HKD",
        "ZAR", "CNY", "KRW", "THB", "PLN", "CZK",
    ],
    "country": [
        "Japan", "Spain", "Mexico", "Canada", "the UK", "Italy", "Thailand", "Brazil", "India", "Germany",
        "France", "Portugal", "Turkey", "Australia", "Greece", "Morocco", "Vietnam", "Colombia", "South Korea",
        "Switzerland", "Norway", "Ireland", "Egypt", "Peru", "Iceland",
    ],
    "timeframe": ["week", "month", "weekend", "Monday", "spring"],
    "atm_loc": [
        "on Main Street", "at the mall", "at the {street} branch", "outside the grocery store",
        "at the train station", "at the airport", "near my office", "at the gas station on {street} Road",
        "on {street} Avenue", "downtown", "in the hospital lobby", "by the university library",
    ],
    "street": _STREETS,
    "landmark": [
        "the central train station", "Union Square", "the airport", "my hotel", "Riverside Mall",
        "the university campus", "City Hall", "the stadium", "the convention center", "Lakeside Hospital",
        "the bus terminal", "{street} Street",
    ],
    "city": [
        "Chicago", "Denver", "Austin", "Boston", "Seattle", "Miami", "Phoenix", "Portland", "Atlanta",
        "Nashville", "Dallas", "San Diego", "Minneapolis", "Detroit", "Charlotte", "Sacramento", "Pittsburgh",
        "Raleigh",
    ],
    "later": ["tonight", "this afternoon", "later today", "this weekend", "tomorrow"],
    "period": ["week", "rest of the month", "weekend", "next two weeks"],
    "bal_tail": [
        "", "", "", "I'm at the store right now.", "Need to know before I pay for groceries.",
        "Just want to see if my paycheck cleared.", "Planning my budget for the week.", "I haven't checked in a while.",
        "I'm about to book a trip and want to be sure.",
    ],
    "lost_tail": [
        "", "", "", "I last had it {lost_where}.", "The last four digits are {last4}.", "I've checked everywhere.",
        "It went missing {lost_when}.", "I really need it blocked fast.",
    ],
    "loan_tail": [
        "", "", "", "My credit score is around {score}.", "I make about {income} a year.",
        "I've been a customer since {year}.", "I'm comparing a few banks right now.", "I'd like to apply this month.",
    ],
    "loan_acct_tail": ["", "", "", "The account ends in {last4}.", "It's the one I took out in {year}.", "Loan number {loannum}."],
    "open_tail": [
        "", "", "", "I'm new to the area.", "I'd prefer to do it online.", "I'm already a customer.",
        "I can visit a branch this week if needed.",
    ],
    "fx_tail": [
        "", "", "", "I'm traveling next month.", "Just comparing options before my trip.", "I need to budget for a vacation.",
        "I'm buying something from an overseas seller.", "Planning a semester abroad.",
    ],
    "act_tail": [
        "", "", "", "It came in the mail {past}.", "The last four digits are {last4}.", "I want to use it this weekend.",
        "The letter says to activate it within 30 days.",
    ],
    "score": lambda r: str(r.randrange(600, 830, 5)),
    "income": lambda r: f"${r.randrange(28, 260) * 1000:,}",
    "year": lambda r: str(r.randint(2004, 2025)),
    "loannum": digits(8),
    "move_when": ["next month", "in two weeks", "at the end of {month}", "this summer", "next week", "in {month}"],
    "month": MONTHS,
    "start_when": ["in the fall", "in January", "next semester", "this spring", "in September"],
    "contact_field": [
        "phone number", "email address", "home address", "mailing address", "last name", "mobile number",
        "work phone number", "email", "billing address", "legal name", "home phone number",
    ],
}

PREFIXES = [
    "Hi,", "Hello,", "Hey,", "Hi there,", "Good morning,", "Good afternoon,", "Hello, quick question:",
    "Hey bot,", "Hi, I need some help.", "Excuse me,", "Hiya,", "Hello again,", "Evening,",
]
SUFFIXES = [
    "Thanks.", "Thank you!", "Thanks in advance.", "Appreciate it.", "Please help.", "Cheers.", "Thx",
    "Thank you so much.", "Let me know.", "Thanks a lot!",
]
URGENT_SUFFIXES = SUFFIXES + ["This is urgent.", "Please hurry.", "ASAP please."]

# ── Templates ───────────────────────────────────────────────────────────

TEMPLATES = {
    "check_balance": [
        "What's my {acct} balance? {bal_tail}",
        "How much money do I have in my {acct} right now? {bal_tail}",
        "Can you tell me the current balance on my {acct} ending in {last4}?",
        "balance on my {acct} pls",
        "I need to know how much is available in my {acct} before I go shopping {later}.",
        "What's the available balance on the account ending {last4}? {bal_tail}",
        "How much is left in my {acct} after the purchases I made {past}?",
        "Show me the balances for my {acct_pair}.",
        "Do I have at least {amount} in my {acct}?",
        "Did my paycheck land yet? What's my {acct} balance showing?",
        "What's the current balance on my {cc}?",
        "Quick question, what's sitting in my {acct} at the moment? {bal_tail}",
        "Could you check my {acct} balance? I want to make sure there's enough in there before payday.",
        "What's my available balance vs my current balance on the {acct}? A few things are still pending.",
        "Am I in the negative on my {acct_chk}? {bal_tail}",
        "Give me my {acct_pair} balances.",
        "How much money is in the account ending in {last4}? {bal_tail}",
        "I'd like to see my {acct} balance as of today. {bal_tail}",
        "Did the {amount} deposit I made {past} clear? What does my {acct} balance say now?",
        "I'm trying to budget for the {period}. How much do I have left in my {acct}?",
        "Can I get the balance on my {kid}'s savings account? I'm a joint holder.",
        "What's the statement balance on my {cc} this month?",
        "how much $ do i have in my {acct}",
        "Is there enough in my {acct} to cover a {amount} purchase {later}? What's the balance?",
    ],
    "transfer_money": [
        "Send {amount} to {payee}.",
        "I want to transfer {amount} from my savings to my checking.",
        "Move {amount} from checking into savings please.",
        "Can you wire {amount} to {payee}'s account at {other_bank}?",
        "Schedule a transfer of {amount} to {payee} for {future}.",
        "Set up a recurring transfer of {amount} into my savings {freq}.",
        "How do I send money to someone who banks with {other_bank}?",
        "Pay {friend} back {small_amt} for {split_reason}.",
        "I need to send {rent} to my landlord for rent.",
        "Transfer {amount} to account number {acctnum}, routing number {routing}.",
        "Can I move {amount} from my personal account into our joint account?",
        "Please move {amount} {acct_move}.",
        "I'd like to make an international transfer of {amount} to {payee} in {country}.",
        "Send {friend} {small_amt} through {p2p}.",
        "Can you set up a standing order of {amount} to {payee} on the {ordinal} of each month?",
        "I want to send {amount} to my {kid} at college, today if possible.",
        "Change my scheduled transfer to {payee} from {amount} to {amount2}.",
        "Cancel the transfer to {payee} that I scheduled for {future}.",
        "What's the quickest way to get {amount} to {payee} today?",
        "Add {fullname} as a new payee so I can send them money.",
        "I need to pay a contractor a {amount} deposit by bank transfer, how do I do that?",
        "transfer {small_amt} to {friend} now",
        "Can I transfer {amount} to my own account at {other_bank}?",
    ],
    "card_lost_stolen": [
        "I lost my {card} {lost_where}.",
        "My {card} was stolen {lost_when}.",
        "Please block my {card}, I can't find it anywhere. {lost_tail}",
        "Someone stole my wallet {lost_where} and my {card} was in it. Freeze it now.",
        "How do I report a lost {card}? {lost_tail}",
        "I think I left my {card} {lost_where}. Can you freeze it?",
        "My purse was stolen {lost_where}, I need to cancel my {card} ending in {last4}.",
        "Card ending {last4} is missing, please deactivate it.",
        "lost my card {lost_where}, what do i do",
        "My {card} got stolen {lost_when} and I need a replacement sent out.",
        "Can you put a hold on my {card}? It's been missing since {missing_since}.",
        "I dropped my {card} somewhere {lost_where} and can't find it. Lock it please.",
        "My bag got stolen {lost_where} and my {card} was inside.",
        "I need to report my {card} as stolen. {lost_tail}",
        "Help, my card is gone. I think someone pickpocketed me {lost_where}.",
        "Can you temporarily freeze my {card}? I misplaced it {lost_when} and I'm still looking.",
        "My {partner} lost the card on our joint account {lost_where}, can we block it?",
        "I can't find my {card} since I got back from {country}. Please cancel it and send a new one.",
        "Is there a way to block my card from the app? It was stolen {lost_when}.",
        "Report stolen card ending in {last4}.",
        "I've lost my {card} and I'm worried someone will use it. What should I do? {lost_tail}",
    ],
    "dispute_transaction": [
        "There's a charge of {charge} from {merchant} on my statement that I don't recognize.",
        "I want to dispute a {charge} transaction from {merchant} that posted {past}.",
        "I was charged twice by {merchant} for the same purchase.",
        "Someone used my card details for a {charge} purchase at {merchant} and it wasn't me.",
        "How do I file a chargeback for an order from {shop} that never arrived?",
        "{merchant} charged me {overcharge_checkout}.",
        "There's a transaction on my account I didn't make: {charge} at {merchant}.",
        "I canceled my {subscription} subscription but they still charged me {charge}.",
        "I need to contest a charge on my {cc}.",
        "What's this {charge} charge from {merchant}? I've never shopped there.",
        "Please reverse the {charge} charge from {merchant}, it's fraudulent.",
        "I returned my order to {shop} weeks ago and never got the refund. I want to dispute it.",
        "My statement shows a payment to {merchant} that I never authorized.",
        "There are {few} small charges from {merchant} I didn't make. Can you investigate?",
        "I was overcharged at {merchant}: {overcharge_receipt}.",
        "Can you open a dispute for transaction {txn}?",
        "unknown charge {past} for {charge}, not mine",
        "An online seller took {charge} and never delivered anything. Can I get my money back through a dispute?",
        "{booking_merchant} charged me a {charge} cancellation fee even though I cancelled on time. I want to dispute it.",
        "Why was I charged {charge} by {merchant}? I don't have an account with them, please flag it as fraud.",
        "I was billed {charge} by {subscription} after I cancelled the free trial. How do I get that reversed?",
        "I was charged for {qty} items at {merchant} but only bought one. Please correct it.",
    ],
    "loan_inquiry": [
        "What are your current rates for a {loan_term}? {loan_tail}",
        "Am I eligible for a {loan}? {loan_tail}",
        "How much could I borrow with a {loan}? {loan_tail}",
        "I'd like to apply for {loan_request}.",
        "What APR would I get on a {loan_term} with good credit?",
        "How do I make an extra payment on my {loan}? {loan_acct_tail}",
        "What's the payoff amount on my {loan}? {loan_acct_tail}",
        "Can I refinance my {refi} with you? {loan_tail}",
        "What documents do I need to apply for a {loan}? {loan_tail}",
        "What's the status of my {loan} application?",
        "When is my next {loan} payment due? {loan_acct_tail}",
        "Can I defer my {loan} payment this month? Money is tight.",
        "What credit score do I need to qualify for a {loan}? {loan_tail}",
        "Do you offer {loan_plural}? {loan_tail}",
        "I want to pay off my {loan} early. Are there any prepayment penalties?",
        "How long would it take to repay {loan_request} at your current rates?",
        "Is the rate on my {loan} fixed or variable? {loan_acct_tail}",
        "We're first-time buyers looking at a {house_price} house. What mortgage options do you have?",
        "Can I get pre-approved for {loan_request}?",
        "Is there any way to lower the monthly payment on my {loan}? {loan_acct_tail}",
        "I'm self-employed, can I still qualify for a {loan}? {loan_tail}",
        "What would the monthly payment be on {loan_request_term}?",
    ],
    "update_personal_info": [
        "I need to change my address to {address}.",
        "Please update my phone number to {phone}.",
        "How do I change the email address on my {acct}?",
        "I got married and need to update my last name to {last}.",
        "I moved. New address is {address}.",
        "Can you update my email to {email}?",
        "My mobile number changed, the new one is {phone}.",
        "I want to change my mailing address to {address} but keep my home address the same.",
        "Update my contact details: email {email}, phone {phone}.",
        "How do I update my legal name after a divorce? It's going back to {last}.",
        "My name is misspelled on my account, it should be {fullname}.",
        "I'm moving to {city} {move_when}. How do I change my address with you?",
        "Please replace my old work email with my personal one, {email}.",
        "Can I change my {contact_field} online or do I have to visit a branch?",
        "I need the address my statements are mailed to changed to {address}.",
        "Please change the phone number on file. I don't have the old one anymore, the new one is {phone}.",
        "My {kid}'s account still has our old address, can you update it to {address}?",
        "I'd like to go by {first} in the app instead of my full legal name. Can you change my preferred name?",
        "What documents do you need to process a name change from {last} to {last2}?",
        "Change my email on file from {email} to {email2}.",
        "new phone number: {phone}. please update my profile",
    ],
    "open_account": [
        "I want to open a {newacct}. {open_tail}",
        "How do I open a {newacct}? {open_tail}",
        "Can I open a joint account with my {partner}? {open_tail}",
        "What do I need to open a business checking account for my {business}?",
        "Can I open a {newacct} online or do I have to come into a branch? {open_tail}",
        "Is there a minimum deposit to open a {newacct}? {open_tail}",
        "I'd like to open a second checking account just for {purpose}.",
        "Can I open a savings account for my {age}-year-old?",
        "I just moved here from {country}. Can I open a bank account with my foreign passport?",
        "What documents are required to open a {newacct}? {open_tail}",
        "Sign me up for a {newacct}, please. {open_tail}",
        "Do you have student checking accounts? I'm starting at {university} {start_when}.",
        "We're starting a {business} and need a business account. How do we get one?",
        "How long does it take to open a {newacct}? {open_tail}",
        "Can I open a {newacct} with just {min_dep}?",
        "I already bank with you. Can I add a {newacct} to my profile?",
        "My {partner} and I want a shared account for household expenses. How do we set one up?",
        "Which checking account should I open if I want {feature}?",
        "Open a new savings account and call it '{goal}'.",
        "Can a non-resident open an account with you? I live in {country}.",
        "Can a {age}-year-old open a checking account without a parent?",
    ],
    "exchange_rate": [
        "What's the exchange rate for {currency} today? {fx_tail}",
        "How much is {fx_usd} in {currency}?",
        "What rate do you give for converting dollars to {currency}? {fx_tail}",
        "Do you charge a fee for card purchases made in {currency}? {fx_tail}",
        "What's the foreign transaction fee on your {card}? {fx_tail}",
        "How many {currency} would I get for {fx_usd}?",
        "Is the {currency_sg} rate better at the branch or in the app?",
        "What fees apply if I use my {card} in {country}?",
        "What's the USD to {code} rate right now? {fx_tail}",
        "Can you tell me your buy and sell rates for {currency}? {fx_tail}",
        "I'm going to {country} next {timeframe}. What's the current rate for the local currency?",
        "Do you add a markup on top of the exchange rate when I pay in {currency}? {fx_tail}",
        "How much will {foreign_amount} cost me in dollars?",
        "What exchange rate did you use for my card purchase in {country} {past}?",
        "Is there a currency conversion fee on online purchases from shops in {country}?",
        "convert {fx_usd} to {currency}",
        "What's today's rate for buying {currency} cash at your branch? {fx_tail}",
        "How does your {currency_sg} rate compare to the mid-market rate?",
        "Will I pay a conversion fee if a merchant charges me in {currency} on my debit card?",
        "{code} to USD rate?",
        "How much is {foreign_amount} worth in US dollars at your current rate?",
    ],
    "atm_issue": [
        "The ATM {atm_loc} swallowed my card.",
        "I tried to withdraw {atm_amt} but the ATM {atm_loc} didn't give me any cash.",
        "Where's the nearest ATM to {landmark}?",
        "The ATM {atm_loc} gave me less cash than I asked for.",
        "The ATM {atm_loc} is showing an error and won't let me withdraw.",
        "The machine {atm_loc} kept my card after I typed my PIN, what now?",
        "Is there one of your ATMs near {landmark}?",
        "I deposited a check at the ATM {past} and it's still not showing up.",
        "My card got stuck in the ATM {atm_loc}.",
        "Find me an ATM that's open 24 hours near {landmark}.",
        "The ATM screen froze halfway through my withdrawal {atm_loc}.",
        "Which ATMs in {city} are in your network?",
        "The ATM {atm_loc} is out of service. Is there another one close by?",
        "I deposited {cash_amt} in cash at the ATM {atm_loc} but only part of it was credited.",
        "atm {atm_loc} ate my card",
        "The ATM {atm_loc} keeps rejecting cards, mine and my friend's too.",
        "How do I get my card back from the ATM that kept it {past}?",
        "Is there an ATM inside {landmark}?",
        "The ATM {atm_loc} only gave me {atm_short} I requested.",
        "The ATM {atm_loc} printed a receipt for {atm_amt} but no cash came out.",
        "Is there an ATM near {landmark} that takes cash deposits?",
    ],
    "card_activation": [
        "How do I activate my new {card}? {act_tail}",
        "My replacement {card} arrived {past}, I need to activate it.",
        "Activate card ending in {last4}.",
        "I got a new {card} in the mail {past}, what's the activation process?",
        "Can I activate my new {card} in the app? {act_tail}",
        "How do I set a PIN for my new {card}? {act_tail}",
        "My new {card} isn't working. Do I need to activate it first? {act_tail}",
        "The activation code you texted me isn't working for my new card ending {last4}.",
        "I need help activating the {card} I just received. {act_tail}",
        "Where do I enter the activation number from the sticker on my new {card}? {act_tail}",
        "Can you activate my new card for me? The last four digits are {last4}.",
        "I'd like to choose a PIN for the {card} that just arrived.",
        "Is my new {card} active yet? I called the number on the sticker {past}.",
        "My renewed card came with an expiry of {exp}. How do I switch it on?",
        "Do I have to activate my new {card} before the old one expires?",
        "The {card} that came in the mail says to activate it by phone. Can I do it here instead?",
        "Please activate my new {card}, it just arrived.",
        "I just got my {first_card} from you. How do I start using it?",
        "What number do I call to activate a new {card}? {act_tail}",
        "I'm trying to activate card {last4} but it says the details don't match.",
    ],
}

HARD = {
    "check_balance": [
        "Before I send {amount} to {payee}, how much is actually in my {acct}? Don't send anything yet, just the balance.",
        "I didn't want to wait in line at the ATM just to check, so what's my {acct} balance?",
        "I just activated my new {card}. How much money is in the account it's linked to?",
        "Not looking to open a new account, I only want the balance of my existing {acct}.",
        "After the transfer I made {past}, what's my {acct} balance now?",
        "I'm thinking about applying for a loan at some point, but for now just tell me my {acct} balance.",
        "My card was blocked after I reported it lost, but can you still tell me the balance on my {acct}?",
        "I got paid in {currency} {past} and it's already been converted. What's my {acct} balance now? Just the balance, not the rate.",
    ],
    "transfer_money": [
        "I already froze my lost card, so now I just need to send {amount} to {payee} from my {acct}.",
        "Send {amount} to {payee} in {country}. I don't care about the exchange rate, just get it there.",
        "My balance is fine, I checked. Just move {amount} {acct_move}.",
        "This isn't a fraud thing, I just want to send {friend} {small_amt} for {split_reason}.",
        "I just opened a new savings account with you, please transfer {amount} into it from my checking.",
        "Instead of taking cash out at the ATM, can I just send {amount} straight to {payee}?",
        "Once my loan money comes in, schedule {amount} of it to go to {payee} for {future}.",
        "Don't open anything new, just move {amount} {acct_move}.",
    ],
    "card_lost_stolen": [
        "My {card} is missing. I don't see any weird charges yet, but please block it before anything happens. {lost_tail}",
        "I took cash out at an ATM {atm_loc} and then lost my wallet on the way home. Please block my {card}.",
        "I never even activated the new card and now I've lost it {lost_where}. Please cancel it.",
        "I don't want to dispute anything, I just need my stolen {card} blocked right away. {lost_tail}",
        "My {card} was stolen while I was traveling in {country}. Block it, please.",
        "My new card was stolen out of my mailbox {lost_when} before I could activate it. Can you block it?",
        "Not sure if it's lost or stolen, but my {card} isn't in my wallet anymore. Please lock it. {lost_tail}",
        "My balance looks normal so far, but my {card} was stolen {lost_when}. Freeze it before they use it.",
    ],
    "dispute_transaction": [
        "I reported my card stolen last week and it's already been replaced. Now I want to dispute the {charge} charge from {merchant} that went through before I blocked it.",
        "I want to dispute the {fee_amt} foreign transaction fee on my statement. My card is supposed to have no foreign fees.",
        "My card is still in my wallet so it's not lost, but there's a {charge} charge from {merchant} I definitely didn't make.",
        "Don't block my card, I just want to contest the {charge} charge from {merchant} that posted {past}.",
        "My balance is lower than it should be because of a {charge} charge from {merchant} that I never made.",
        "The exchange rate isn't the problem. {restaurant} in {country} charged me twice for one meal and I want one of the charges reversed.",
        "A {charge} charge from {merchant} showed up right after my new card arrived, and I didn't make it.",
        "Not an ATM problem: this is a {charge} card purchase at {merchant} that I never made.",
    ],
    "loan_inquiry": [
        "What's the remaining balance on my {loan}? {loan_acct_tail}",
        "Not the exchange rate, I mean what interest rate would I get on a {loan}? {loan_tail}",
        "I'm not looking to open a checking account, I want to take out a {loan}. What do I need? {loan_tail}",
        "Can I set up automatic payments from my checking to pay my {loan} each month? {loan_acct_tail}",
        "If I put an extra {amount} toward my {loan} today, will that lower my next payment?",
        "Can I apply for {biz_loan} without opening a business account with you first?",
        "How much do I still owe on my {loan}, and when will it be paid off?",
        "I have about {down} saved for a down payment. What size mortgage could I qualify for?",
    ],
    "update_personal_info": [
        "My phone number changed so I'm not getting the codes for transfers anymore. Please update it to {phone}.",
        "Not opening anything new, I just need the name on my existing joint account changed to {fullname} after the wedding.",
        "My replacement card was mailed to my old address. Please update my address to {address} so future mail goes there.",
        "I want my balance alerts going to {email} instead of my old email. Please update it.",
        "Before I apply for a mortgage, I need my address on file updated to {address}.",
        "My statements still show my maiden name. Please change it to {fullname}.",
        "I never got the activation link for my new card because my email changed. Please update it to {email}.",
    ],
    "open_account": [
        "Before I can transfer anything I need a {newacct}. How do I open one?",
        "I want to open a savings account so I can move {monthly} into it every month.",
        "Not a loan, I want to open a regular {newacct}. {open_tail}",
        "I travel to {country} a lot. Can I open an account that holds foreign currency?",
        "My current card works fine, I just want to open an additional {newacct}.",
        "What interest rate does your high-yield savings account pay if I open one with {deposit_round}?",
        "I just updated my address with you, and now I'd like to open a {newacct} with my {partner}.",
    ],
    "exchange_rate": [
        "Before I send money to my cousin in {country}, what's the exchange rate today?",
        "I don't want to transfer anything yet, just tell me what rate I'd get converting {fx_usd} to {currency}.",
        "What fee do you charge if I withdraw cash from an ATM in {country}?",
        "I'm not disputing it, I just want to know what exchange rate was applied to my {amount} purchase in {country}.",
        "What's the rate for {currency}? Not interest rates, the currency conversion rate. {fx_tail}",
        "My new card just arrived. Does it charge foreign transaction fees when I use it in {country}?",
        "Will I lose much to fees if I pay for my hotel in {country} with my {card}, or is your conversion rate fair?",
        "What rate and fee would apply if I sent {fx_usd} to {country}? Just the rate and fee for now.",
    ],
    "atm_issue": [
        "The ATM {atm_loc} didn't give me the {atm_amt} but it still shows on my statement. It's not fraud, the machine just failed.",
        "The ATM kept my card. It isn't lost or stolen, the machine {atm_loc} just swallowed it. How do I get it back?",
        "I tried to check my balance at the ATM {atm_loc} and it gave me an error code.",
        "My brand new card that I activated {past} got eaten by the ATM {atm_loc}.",
        "The ATM said 'transaction cannot be completed' but I think {atm_amt} was taken from my account anyway.",
        "I deposited cash at the ATM {atm_loc} and it counted it wrong. My balance is {short_amt} short.",
        "The ATM {atm_loc} took my money but no cash came out. I don't need a new card, I just want the {atm_amt} back.",
    ],
    "card_activation": [
        "The replacement for my stolen {card} came {past}. How do I activate it?",
        "My new card got declined at {merchant}. I think I forgot to activate it, how do I do that?",
        "Do I need to go to an ATM to activate my new {card} and set the PIN? {act_tail}",
        "I updated my address and the new {card} finally arrived. How do I activate it?",
        "Can I activate my new card now so it works on my trip to {country} next {timeframe}?",
        "I'm not reporting it lost, the new {card} is right here in my hand. I just need it activated.",
        "My new {card} came with a temporary PIN. How do I set my own PIN and activate it? {act_tail}",
    ],
}

ROWS_PER_LABEL = 120
HARD_SHARE = 0.2


def generate(rng: random.Random) -> list[dict]:
    parts = []
    for label in LABELS:
        name = label["name"]
        parts.append(
            label_items(
                rng,
                name,
                ROWS_PER_LABEL,
                TEMPLATES[name],
                SLOTS,
                hard_templates=HARD[name],
                hard_share=HARD_SHARE,
                prefixes=PREFIXES,
                suffixes=URGENT_SUFFIXES if name == "card_lost_stolen" else SUFFIXES,
            )
        )
    return merge(*parts)
