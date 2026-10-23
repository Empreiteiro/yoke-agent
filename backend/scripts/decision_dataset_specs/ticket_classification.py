"""Customer-support ticket classification (English).

Fictional company *Nimbrook* sells a subscription app (Nimbrook Cloud, plans
Starter → Enterprise) plus smart-home hardware shipped to customers. Every
ticket must be routed to exactly one of eight support queues.
"""

from __future__ import annotations

import random

from ._common import MONTHS, WEEKDAYS, FIRST_NAMES, LAST_NAMES, amount, digits, full_name, integer, label_items, merge, order_id

SLUG = "ticket_classification"
NAME = "Support Ticket Classification"
DESCRIPTION = (
    "1,200 English customer-support tickets for a company selling a SaaS app and shipped smart-home hardware, "
    "each routed to one of 8 queues: billing, technical issue, account access, shipping, returns/refunds, "
    "product inquiry, cancellation or feature request."
)
LANGUAGE = "en"
TASK = "Which support queue should handle this customer ticket?"

LABELS = [
    {
        "name": "billing",
        "description": (
            "Money already charged or owed on an existing account or order: charges, invoices and receipts, payment "
            "methods and failed payments, billing contact, price changes on a current plan, and duplicate, unexpected "
            "or incorrect charges — including asking for money back for a wrong charge, even one made after a "
            "cancellation or downgrade, or a wrong shipping fee. A refund for an item that was physically sent back is "
            "returns_refunds; pre-sales pricing questions are product_inquiry."
        ),
    },
    {
        "name": "technical_issue",
        "description": (
            "Something in the app, API, an integration or a device is malfunctioning and the customer wants it fixed: "
            "bugs, error messages, crashes, sync or connectivity failures, failed firmware updates, slow performance. "
            "Problems signing in (password, 2FA, lockout) are account_access even when an error appears; wanting to "
            "send a faulty device back is returns_refunds; asking for functionality that does not exist is "
            "feature_request."
        ),
    },
    {
        "name": "account_access",
        "description": (
            "Getting into or securing an account: login failures, password resets, two-factor authentication, locked "
            "or compromised accounts, recovering access, changing the login email or username, and granting or "
            "revoking a person's login/admin access. Changing where invoices are sent is billing; closing or deleting "
            "the account is cancellation."
        ),
    },
    {
        "name": "shipping_delivery",
        "description": (
            "Status or delivery of an order that has not been (fully) received: processing, dispatch, tracking, "
            "delays, carrier questions, changing the delivery address or date, and packages that are lost, missing, "
            "misdelivered or sent back as undeliverable. Once an item has been received and is damaged, wrong or "
            "unwanted it is returns_refunds; a dispute about a shipping fee charged is billing."
        ),
    },
    {
        "name": "returns_refunds",
        "description": (
            "A physical product the customer has received: returning or exchanging it (unwanted, defective, wrong "
            "size/colour), items that arrived damaged, incomplete or different from what was ordered, return labels "
            "and return policy, and the status of the refund for an item that was sent back. Money back for a wrong "
            "charge with no item returned is billing; a package never received is shipping_delivery."
        ),
    },
    {
        "name": "product_inquiry",
        "description": (
            "Pre-sales or informational questions about what is offered: hardware specs and features, compatibility, "
            "stock and availability, warranty, plans, plan comparison and list prices, trials and discounts. Asking "
            "whether something already exists is product_inquiry; asking for it to be built is feature_request; "
            "questions about a charge already made are billing."
        ),
    },
    {
        "name": "cancellation",
        "description": (
            "Ending or reducing a subscription or account: cancelling a subscription, plan or add-on, stopping "
            "auto-renewal, downgrading to a cheaper or free plan, ending a trial before it converts, closing or "
            "deleting an account. If the main ask is money back for a charge that already happened it is billing; "
            "returning hardware is returns_refunds."
        ),
    },
    {
        "name": "feature_request",
        "description": (
            "Suggestions or requests for functionality, integrations, compatibility or hardware improvements that do "
            "not exist today — including improvements to billing, login, tracking or subscription flows. Broken "
            "existing functionality is technical_issue; merely asking whether something exists is product_inquiry."
        ),
    },
]

# ── Slot pools ──────────────────────────────────────────────────────────

PRODUCTS = [
    "Nimbrook Hub", "Hub Mini", "Cadence speaker", "Cadence Max speaker", "Lumen light strip",
    "Pulse motion sensor", "Halo thermostat", "Vista Cam", "Vista Cam Outdoor", "Dock Pro",
    "Beacon tracker", "Volt smart plug", "Lumen desk lamp", "Halo room sensor", "Tempo doorbell",
]
BATTERY_PRODUCTS = ["Beacon tracker", "Pulse motion sensor", "Tempo doorbell", "Halo room sensor", "Vista Cam Outdoor"]
UPGRADE_PAIRS = [
    "the Hub Mini for the Nimbrook Hub", "the Vista Cam for the Vista Cam Outdoor",
    "the Cadence speaker for the Cadence Max speaker", "the Halo room sensor for the Halo thermostat",
    "the Lumen desk lamp for the Lumen light strip kit", "the Volt smart plug single for the 4-pack",
]
VARIANTS = [
    "the white version", "the graphite version", "the sage green version", "the sand version",
    "the 2-pack", "the 4-pack", "the starter kit", "the outdoor model", "the larger model",
]
COLORS = ["white", "graphite", "sage green", "sand", "navy", "black"]
PLANS = ["Starter", "Plus", "Pro", "Business", "Team", "Enterprise"]
PLANS_HI = ["Pro", "Business", "Team", "Enterprise"]
PLANS_LO = ["Starter", "Plus"]
APPS = ["app", "mobile app", "web dashboard", "desktop app", "Nimbrook app", "tablet app"]
FEATURES = [
    "the automation editor", "the energy report", "the activity log", "the calendar view", "the scene builder",
    "the shared dashboard", "the guest access page", "the alerts center", "the device map", "the reports tab",
    "the room overview", "the usage history", "the CSV export", "the camera timeline",
]
PLAN_FEATURES = [
    "guest access", "multi-home support", "API access", "custom alerts", "the energy report",
    "unlimited automations", "30-day video history", "admin roles", "the Taskwell integration", "audit logs",
]
INTEGRATIONS = ["Taskwell", "Ledgerly", "Chatterbox", "PipeHub", "Calendro", "Zentrik", "Brightdesk", "Quillio"]
NEW_INTEGRATIONS = ["Fernly", "Haddock CRM", "Marlow Books", "Tidepool HR", "Orchid POS", "Sparrowmail", "Notekeep"]
PLATFORMS = [
    "the Corvo voice assistant", "Vela tablets", "HomeLink routers", "a 5 GHz-only Wi-Fi network",
    "a mesh Wi-Fi setup", "older Bluetooth 4.0 phones", "Linux desktops", "Kestrel smart TVs",
    "our office VPN", "the Maestro home controller", "220V outlets",
]
REQUEST_PLATFORMS = ["the Corvo voice assistant", "Vela tablets", "Kestrel smart TVs", "the Maestro home controller", "Linux desktops"]
NEW_FEATURES = [
    "a dark mode", "an offline mode", "a home screen widget", "custom user roles", "a weekly summary email",
    "two-way calendar sync", "keyboard shortcuts", "a vacation mode", "multi-language reports",
    "a public status page", "per-room energy goals", "a lock-screen control panel", "custom dashboard themes",
    "an undo button for automation edits", "a family sharing mode", "a guest mode for babysitters",
    "a printable monthly energy report", "voice notes on alerts", "a large-text accessibility mode",
    "an energy cost forecast",
]
CAPABILITIES_NEW = [
    "reorder rooms by drag and drop", "duplicate an existing automation", "set a different alert sound per device",
    "bulk-rename devices", "schedule a scene for a single date", "attach notes to devices",
    "export the activity log", "assign one device to several rooms", "mute alerts for a set time",
    "share a single camera with a neighbour", "set quiet hours for notifications", "copy a scene to another home",
    "tag devices with custom labels", "pin favourite devices to the top", "set automations by room temperature",
    "send alerts to a group chat",
]
CAPABILITIES_Q = [
    "share a dashboard with someone outside our team", "group devices by floor", "trigger automations at sunrise",
    "export reports as PDF", "see a device's battery history", "control the lights from the lock screen",
    "give a guest temporary access", "run two homes from one login",
]
ENHANCEMENTS = [
    "let us filter by room", "supported custom date ranges", "showed hourly data", "could be shared with guests",
    "remembered my last view", "had a search box", "showed totals per week",
]
HW_FEATURES = [
    "a USB-C port", "a battery backup", "a physical mute button", "replaceable batteries",
    "a dimmer status light", "a longer power cable", "a night mode for the LED ring",
]
API_THINGS = [
    "bulk device updates", "historical sensor data", "automation run history", "user management", "firmware status",
    "camera event clips", "room assignments", "energy usage per device",
]
SMALL_REQS = [
    "remember the last filter I used", "show battery percentage in the device list", "let me rename scenes",
    "sort devices alphabetically", "add a search box to the activity log", "make the font size adjustable",
]
EVENTS = [
    "low battery alerts", "a device going offline", "a firmware update finishing",
    "a new user joining the workspace", "a motion event",
]
FORMATS = ["XLSX", "PDF", "JSON", "XML", "TSV", "ODS"]
SSO = ["passkeys", "a single sign-on provider", "magic email links", "Keyport SSO", "our company SSO"]
HTTP_ERRORS = [
    "500s", "502s", "503s", "504 timeouts", "intermittent 500 errors", "429 Too Many Requests even at low volume",
    "empty responses", "malformed JSON",
]
LOGIN_CITIES = ["Lisbon", "Denver", "Manila", "Lagos", "Warsaw", "Toronto", "Osaka", "Bogotá", "Nairobi", "Hanoi"]
EMAIL_DOMAINS = ["example.com", "mailbox.example", "brightlabs.example", "acme-studio.example", "quayside.example", "corvid.example"]
STREETS = ["Maple", "Harbor", "Willow", "Juniper", "Cedar", "Lakeview", "Birch", "Orchard", "Granite", "Elm"]
STREET_KINDS = ["Street", "Avenue", "Road", "Lane", "Drive", "Court"]
TOWNS = ["Riverton", "Fairhaven", "Brookdale", "Port Ellis", "Ashford", "Millbrook", "Westcliff", "Oak Ridge"]
DISCOUNTS = ["10", "15", "20", "25", "30", "40"]

ACCOUNT_REFS = ["my account", "our team account", "the admin account", "my Nimbrook account", "my work account", "my personal account"]
LOST_PHONE = [
    "lost my phone", "had my phone stolen", "broke my phone", "switched to a new phone", "reset my phone to factory settings",
    "dropped my phone in the pool",
]
RIGHT_AWAY = ["right away", "within a minute", "seconds after it arrives", "the moment I get it"]
SECURITY_REASONS = [
    "", "Our security team now requires it.", "I got a phishing email and want to be safe.", "Our auditor asked about it.",
    "A friend's account was hacked last week.",
]
OLD_DEVICES = ["phone", "work phone", "tablet", "personal phone"]
OLD_DEVICE_FATES = ["trade it in", "wipe it", "give it to my son", "send it for repair", "sell it"]
WAIT_TIMES = ["24 hours", "12 hours", "an hour", "until tomorrow"]
FINANCE_PEOPLE = ["auditor", "accountant", "finance team", "tax advisor", "bookkeeper"]
EXPORT_WHAT = ["the activity log", "energy data", "sensor readings", "the device list", "automation history", "camera events"]
DEVICE_KINDS = ["devices", "cameras", "sensors", "smart plugs", "light strips", "door sensors"]
FOR_WHOM = ["", " for a small office", " for a family", " for a team of 10", " if we mostly use cameras", " for a rental property"]
TRIAL_TAILS = ["", " for teams", " that doesn't need a card", " longer than a week"]
OUTDOOR_PRODUCTS = ["Vista Cam Outdoor", "Tempo doorbell", "Beacon tracker"]
WEATHER = ["heavy rain", "snow", "direct sun all day", "salty sea air", "freezing temperatures"]
USAGE = ["", " with normal use", " in cold weather", " if I use it every day", " in power-saving mode"]
DATA_TAILS = ["", ", including camera recordings", ", including the device history", " — please confirm once it's done", " as soon as possible"]
REASONS_SHORT = [
    "I'll come back if I need it.", "I'm moving abroad.", "money's tight right now.", "we sold the house.",
    "I switched jobs.", "I don't use it enough.",
]
DEL_TAILS = ["", " from the app", " and remove all my devices", " including my camera footage", " so you no longer keep my data"]
ADDONS = ["extra storage", "video history", "extra seats", "premium support", "SMS alerts", "advanced reports"]


def _ordinal(n: int) -> str:
    if 10 <= n % 100 <= 20:
        return f"{n}th"
    return f"{n}" + {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")


def when(rng: random.Random) -> str:
    """A standalone time adverbial: 'March 3', 'last Tuesday', '5 days ago', 'on the 12th'."""
    style = rng.randint(0, 4)
    if style == 0:
        return f"on {rng.choice(MONTHS)} {rng.randint(1, 28)}"
    if style == 1:
        return f"last {rng.choice(WEEKDAYS)}"
    if style == 2:
        return f"{rng.randint(2, 14)} days ago"
    if style == 3:
        return f"on the {_ordinal(rng.randint(1, 28))}"
    return rng.choice(["yesterday", "this morning", "last week", "earlier this week"])


def since_date(rng: random.Random) -> str:
    """A date usable after 'since': 'March 3', 'last Tuesday', 'the 12th'."""
    style = rng.randint(0, 2)
    if style == 0:
        return f"{rng.choice(MONTHS)} {rng.randint(1, 28)}"
    if style == 1:
        return f"last {rng.choice(WEEKDAYS)}"
    return f"the {_ordinal(rng.randint(1, 28))}"


def since(rng: random.Random) -> str:
    return rng.choice([
        "since yesterday", "since this morning", "for two days now", "all week", "since the last update",
        f"since {since_date(rng)}", f"since {since_date(rng)}", "for the past few hours", "since we updated the app",
        "for about a week",
    ])


def errcode(rng: random.Random) -> str:
    style = rng.randint(0, 4)
    if style == 0:
        return f"error {rng.choice(['500', '502', '503', '504', '422', '408'])}"
    if style == 1:
        return f"error E{rng.randint(100, 999)}"
    if style == 2:
        return f"error code ERR-{rng.randint(1000, 9999)}"
    if style == 3:
        return f"error 0x{rng.randint(4096, 65535):X}"
    return rng.choice([
        "a 'Something went wrong' message", "an 'Unexpected server error' message",
        "a 'Request timed out' message", "a 'Sync failed' banner",
    ])


COMPARE_PAIRS = [
    "the Hub Mini and the Nimbrook Hub", "the Vista Cam and the Vista Cam Outdoor",
    "the Cadence speaker and the Cadence Max speaker", "the Halo room sensor and the Halo thermostat",
    "the Lumen light strip and the Lumen desk lamp", "the Pulse motion sensor and the Vista Cam",
    "the Tempo doorbell and the Vista Cam Outdoor",
]
MALE_FIRST_NAMES = ["John", "Lucas", "Diego", "Noah", "Kenji", "Mateo", "Omar", "Ivan", "Rafael", "Samuel", "Daniel"]


def _usd(value: float, whole: bool) -> str:
    return f"${int(value)}" if whole else f"${value:,.2f}"


def price_jump(rng: random.Random) -> str:
    """'$49 to $79' — a plausible price increase (+15% to +120%)."""
    base = rng.uniform(12, 600)
    whole = rng.random() < 0.4
    return f"{_usd(base, whole)} to {_usd(base * rng.uniform(1.15, 2.2), whole)}"


def login_err(rng: random.Random) -> str:
    style = rng.randint(0, 2)
    if style == 0:
        return f"error E{rng.randint(400, 499)}"
    if style == 1:
        return f"error code AUTH-{rng.randint(100, 999)}"
    return rng.choice(["an 'Invalid code' error", "a 'Verification failed' message", "a 'Code expired' message"])


def future_date(rng: random.Random) -> str:
    style = rng.randint(0, 3)
    if style == 0:
        return f"{rng.choice(MONTHS)} {rng.randint(1, 28)}"
    if style == 1:
        return f"the {_ordinal(rng.randint(1, 28))}"
    if style == 2:
        return f"next {rng.choice(WEEKDAYS)}"
    return rng.choice(["the first of next month", "the end of this month", "the end of the quarter"])


def _ascii(s: str) -> str:
    return s.replace("ü", "ue").replace("á", "a").lower()


def email(rng: random.Random) -> str:
    first, last = _ascii(rng.choice(FIRST_NAMES)), _ascii(rng.choice(LAST_NAMES))
    local = rng.choice([f"{first}.{last}", f"{first}{last[0]}", f"{first[0]}{last}", f"{first}.{last}{rng.randint(1, 99)}"])
    return f"{local}@{rng.choice(EMAIL_DOMAINS)}"


def username(rng: random.Random) -> str:
    first, last = _ascii(rng.choice(FIRST_NAMES)), _ascii(rng.choice(LAST_NAMES))
    return rng.choice([f"{first}{rng.randint(1, 999)}", f"{first}_{last}", f"{first[0]}{last}{rng.randint(1, 99)}"])


def address(rng: random.Random) -> str:
    base = f"{rng.randint(10, 9999)} {rng.choice(STREETS)} {rng.choice(STREET_KINDS)}"
    if rng.random() < 0.3:
        base += f", Apt {rng.randint(1, 40)}"
    return f"{base}, {rng.choice(TOWNS)}"


def invoice(rng: random.Random) -> str:
    return f"INV-{rng.choice(['2025', '2026'])}-{rng.randint(1000, 99999)}"


def rma(rng: random.Random) -> str:
    return f"RMA-{rng.randint(10000, 99999)}"


def wrong_item(rng: random.Random) -> str:
    a, b = rng.sample(PRODUCTS, 2)
    return f"a {a} instead of the {b} I ordered"


def cap(pool):
    return lambda rng: (lambda s: s[0].upper() + s[1:])(rng.choice(pool))


SLOTS = {
    "amount": amount,
    "amt_lo": lambda rng: amount(rng, 9, 300),
    "amt_hi": lambda rng: amount(rng, 320, 1500),
    "order": order_id,
    "when": when,
    "since": since,
    "since_date": since_date,
    "month": MONTHS,
    "product": PRODUCTS,
    "battery_product": BATTERY_PRODUCTS,
    "accessory": [p for p in PRODUCTS if "Hub" not in p],
    "upgrade_pair": UPGRADE_PAIRS,
    "wrong_item": wrong_item,
    "variant": VARIANTS,
    "color": COLORS,
    "plan": PLANS,
    "plan_hi": PLANS_HI,
    "plan_lo": PLANS_LO,
    "appn": APPS,
    "feature": FEATURES,
    "Feature": cap(FEATURES),
    "plan_feature": PLAN_FEATURES,
    "integration": INTEGRATIONS,
    "new_integration": NEW_INTEGRATIONS,
    "platform": PLATFORMS,
    "request_platform": REQUEST_PLATFORMS,
    "new_feature": NEW_FEATURES,
    "capability_new": CAPABILITIES_NEW,
    "capability_q": CAPABILITIES_Q,
    "enhancement": ENHANCEMENTS,
    "hw_feature": HW_FEATURES,
    "api_thing": API_THINGS,
    "small_req": SMALL_REQS,
    "event": EVENTS,
    "format": FORMATS,
    "sso": SSO,
    "http_errors": HTTP_ERRORS,
    "errcode": errcode,
    "secs": integer(8, 45),
    "pct": integer(12, 97),
    "discount": DISCOUNTS,
    "n": integer(3, 21),
    "n_units": integer(5, 60),
    "n2": integer(2, 6),
    "seats": integer(20, 90),
    "seats_small": integer(3, 15),
    "invoice": invoice,
    "rma": rma,
    "last4": digits(4),
    "email": email,
    "email2": email,
    "username": username,
    "name": full_name,
    "name2": full_name,
    "city": LOGIN_CITIES,
    "domain": EMAIL_DOMAINS,
    "address": address,
    "year": ["2024", "2025"],
    "account_ref": ACCOUNT_REFS,
    "Account_ref": cap(ACCOUNT_REFS),
    "lost_phone": LOST_PHONE,
    "right_away": RIGHT_AWAY,
    "security_reason": SECURITY_REASONS,
    "old_device": OLD_DEVICES,
    "old_device_fate": OLD_DEVICE_FATES,
    "wait_time": WAIT_TIMES,
    "finance_person": FINANCE_PEOPLE,
    "export_what": EXPORT_WHAT,
    "device_kind": DEVICE_KINDS,
    "for_whom": FOR_WHOM,
    "trial_tail": TRIAL_TAILS,
    "outdoor_product": OUTDOOR_PRODUCTS,
    "weather": WEATHER,
    "usage": USAGE,
    "data_tail": DATA_TAILS,
    "reason_short": REASONS_SHORT,
    "del_tail": DEL_TAILS,
    "addon": ADDONS,
    "cancel_tail": ["", " today", " effective immediately", " at the end of this month", " before the next charge", " — the account email is {email}"],
    "shutdown_when": ["at the end of the month", "in {month}", "next week", "this quarter"],
    "cam_product": ["Vista Cam", "Vista Cam Outdoor", "Tempo doorbell"],
    "login_err": login_err,
    "price_jump": price_jump,
    "compare_pair": COMPARE_PAIRS,
    "home_type": ["a small apartment", "a two-story house", "a home office", "a rental property", "a family with kids"],
    "future_date": future_date,
    "male_name": lambda rng: f"{rng.choice(MALE_FIRST_NAMES)} {rng.choice(LAST_NAMES)}",
}

PREFIXES = [
    "Hi,", "Hello,", "Hi team,", "Hey there,", "Good morning,", "Hi support,", "Hello Nimbrook team,", "Hey,",
    "Good afternoon,",
]
SUFFIXES = [
    "Thanks.", "Thank you!", "Thanks in advance.", "Appreciate the help.", "Regards.", "Please advise.",
    "Any help is appreciated.", "Cheers.", "Thanks for looking into it.",
]

# ── Templates ───────────────────────────────────────────────────────────

TEMPLATES = {
    "billing": [
        "I was charged {amount} twice for my {plan} subscription {when}. Please refund the duplicate charge.",
        "Why is my invoice for {month} {amt_hi} when my plan is supposed to cost {amt_lo}?",
        "Can you resend invoice {invoice} as a PDF? Our finance team needs it for the {month} close.",
        "I need to update the credit card on file for my {plan} plan — the old one expires this month.",
        "There's a {amount} charge from Nimbrook on my statement that I don't recognize — it went through {when}. What is it for?",
        "Our invoices need to show our company name and VAT number. How do I add those before the {month} invoice goes out?",
        "My payment of {amount} failed and now the account shows a past-due balance. Can I pay by bank transfer instead?",
        "You billed us for {seats} seats but we only have {seats_small} active users. Please correct invoice {invoice}.",
        "I was promised {discount}% off for switching to annual billing, but I was charged the full {amount}.",
        "Please switch our {plan} plan from monthly to annual billing starting next cycle.",
        "Card ending in {last4} was charged {amount} {when} for a {product} I never ordered. Please reverse it.",
        "The sales tax on invoice {invoice} looks wrong. We're tax exempt and I already sent you the certificate.",
        "How do I get a receipt for the {amount} payment I made {when}?",
        "We were overcharged {amount} on invoice {invoice}. Can you issue a credit or refund the difference?",
        "Can we pay our {plan} invoices by ACH or wire transfer instead of card?",
        "Why did my bill go from {price_jump} this month? Nobody told us about a price change.",
        "My card keeps getting declined when I try to pay the {plan} renewal, but my bank says everything is fine.",
        "Please remove the old card ending in {last4} and charge the company card from now on.",
        "I upgraded to {plan_hi} in the middle of the month and got charged the full {amount} instead of a prorated amount.",
        "Where can I download all of our invoices from {year}? Our {finance_person} needs them.",
        "Double charge again!! {amount} twice {when}. Fix this please.",
        "We were charged {amount} for an add-on we never turned on. Please take it off and refund it.",
        "Our accounts payable team needs the invoices sent to {email} instead of my address.",
        "invoice {invoice} is wrong, we're on {plan_lo} not {plan_hi}",
        "The amount debited from our account {when} was {amt_hi}, but invoice {invoice} says {amt_lo}. Which is right?",
    ],
    "technical_issue": [
        "The {appn} crashes every time I open {feature}.",
        "{Feature} hasn't worked {since}. It just shows a spinner forever.",
        "Our {integration} integration fails with {errcode} whenever we try to sync.",
        "The API has been returning {http_errors} on the /devices endpoint {since}.",
        "My {product} keeps disconnecting from Wi-Fi every few hours and I have to unplug it to get it back.",
        "The {appn} is extremely slow — pages take around {secs} seconds to load.",
        "I get {errcode} when I try to save an automation. Tried two different browsers, same result.",
        "The {product} shows as offline in the app even though its light is solid green.",
        "After the latest update, {feature} shows data from the wrong day.",
        "Webhooks to our endpoint haven't fired {since}; nothing shows up in the delivery log either.",
        "The firmware update for my {product} fails at {pct}% and then the device reboots.",
        "Exporting {export_what} to CSV gives me an empty file, whatever date range I pick.",
        "Push notifications from the {appn} haven't arrived {since}.",
        "The {appn} freezes when I try to add a new device. I can't get past the pairing screen.",
        "My {product} won't pair over Bluetooth; the app just says 'device not found'.",
        "Data from our {product} isn't syncing to the dashboard — the last reading is from {since_date}.",
        "The charts on the dashboard have been blank for everyone on our team {since}.",
        "{http_errors} on every request to your API, our integration is completely down. Urgent.",
        "The {appn} eats so much memory that my laptop fan never stops. Is this a known bug?",
        "Automations have been firing twice {since} — every scheduled action runs two times.",
        "Uploading a floor plan fails with {errcode}, whatever file size I use.",
        "The audio on my Cadence speaker cuts out every few seconds when I stream from the {appn}.",
        "Search in the {appn} returns nothing, even for devices I can see in the list.",
        "{Feature} throws {errcode} the moment I open it.",
        "The {integration} connector disconnects itself every night and we have to reconnect it each morning.",
        "Motion clips from the {cam_product} record fine but haven't shown up in the camera timeline {since}.",
    ],
    "account_access": [
        "I forgot my password and the reset link never arrives at {email}.",
        "{Account_ref} got locked after too many login attempts. How do I unlock it?",
        "I {lost_phone} and can't get my 2FA codes anymore. Please help me get back into {account_ref}.",
        "I need to change the email on my account from {email} to {email2}.",
        "The password reset link says it has expired, even when I click it {right_away}. I've requested {n2} new links already.",
        "Can't log in — it says 'invalid credentials' but I'm sure the password is right. Username is {username}.",
        "I'm not receiving the SMS verification code on my number ending {last4} when I try to sign in.",
        "How do I turn on two-factor authentication for {account_ref}? {security_reason}",
        "Our former admin {name} left the company and we need admin access transferred to {name2}.",
        "I signed up with {email} but I no longer have access to that mailbox. How do I get into my account?",
        "I got a login alert from {city} that wasn't me. I think someone got into my account — please secure it.",
        "Can you reset my password? My username is {username}.",
        "My authenticator app was reset {when} and now none of the 2FA codes work.",
        "I want to change my username, the current one ({username}) has a typo.",
        "I've been locked out of my account since {since_date} and nobody answered my previous email.",
        "We moved our company domain to {domain}. How do I update the login email for my account?",
        "I set up 2FA on my old {old_device}. How do I move it to my new one before I {old_device_fate}?",
        "An employee left the company — please revoke {email}'s login access to our workspace.",
        "pw reset not working for {email}, need access asap",
        "It says {account_ref} is locked for security reasons. What do I need to do to verify my identity?",
        "I can't remember which email I used to register. Can you find my account under the name {name}?",
        "I entered the wrong password a few times and now it says to wait {wait_time}. Can you unlock it sooner?",
        "Please add {name2} as a second admin on our account so we're not locked out if I'm away.",
        "My login stopped working after I changed my password {when}. The new one isn't accepted.",
    ],
    "shipping_delivery": [
        "Where is my order {order}? It was supposed to arrive {when}.",
        "Tracking for order {order} hasn't updated in {n} days.",
        "I entered the wrong shipping address on order {order}. Can you change it to {address}?",
        "My package shows as delivered but it's not at my door or with my neighbors. Order {order}.",
        "When will order {order} ship? I placed it {when}.",
        "Can I get the tracking number for my {product} order?",
        "The courier tried to deliver while I was out. How do I reschedule delivery for order {order}?",
        "Order {order} has been stuck 'in transit' at the same facility since {since_date}.",
        "I paid for express shipping and my {product} still hasn't arrived after {n} days.",
        "Has order {order} shipped yet? I never got a shipping confirmation email.",
        "Can you send order {order} to my office at {address} instead of my home?",
        "The tracking link for my {product} has said 'label created' for {n} days and nothing else.",
        "Is there a new delivery estimate for the {product} I ordered {when}? It says delayed.",
        "Order {order} was split into two shipments and only one has arrived so far.",
        "The courier left order {order} at the wrong address — the delivery photo shows a house that isn't mine.",
        "where's my stuff?? order {order}",
        "I'm travelling next week. Can you hold order {order} at the depot instead of delivering it?",
        "Order {order} has said 'processing' for over a week. Is something wrong?",
        "Which carrier is delivering order {order}? The tracking page doesn't say.",
        "The delivery date for my {product} keeps moving. First it was {since_date}, now there's no date at all.",
        "I moved recently — can you confirm order {order} is going to {address}?",
        "It's been {n} days and order {order} still hasn't arrived. This is ridiculous.",
        "The carrier says order {order} is held at a pickup point but didn't say which one. Where do I collect it?",
        "My {product} order placed {when} still shows 'awaiting dispatch'. When does it actually leave the warehouse?",
    ],
    "returns_refunds": [
        "I'd like to return the {product} I bought — it's not what I expected.",
        "The {product} arrived with a cracked casing. Can I get a replacement?",
        "You sent me {wrong_item}. Order {order}.",
        "How do I get a return label for order {order}?",
        "I returned the {product} {n} days ago. When will I see my refund?",
        "Can I exchange my {product} for {variant}?",
        "The box was crushed and the {product} inside is dented. I want to send it back.",
        "Is it too late to return the {product}? I bought it {n} days ago and haven't opened it.",
        "The {product} I received is missing its power adapter. Can you send one or should I return the whole thing?",
        "Your warehouse received my return {n} days ago but the {amount} refund still hasn't been issued.",
        "I ordered the {color} {product} and got a different color. I'd like to swap it.",
        "My return for order {order} is marked as received — how long until the refund reaches my card?",
        "I want to return the {product} for a refund, it doesn't fit our space.",
        "The {product} was dead on arrival — it wouldn't power on out of the box. Please send a replacement.",
        "I received two {product} units but only ordered one. How do I send the extra back?",
        "Do I need the original packaging to return the {product}?",
        "Can I return just one of the {n2} units from order {order}?",
        "I'd like to exchange {upgrade_pair} and pay the difference.",
        "My aunt gave me a {product} as a gift and I already have one. Can I return it for store credit?",
        "The return label you emailed for order {order} is rejected at the drop-off point. How else can I send it back?",
        "The screen on my {product} came scratched. I want an exchange.",
        "Refund for my returned {product} ({rma}) is still pending after {n} days.",
        "The packaging was already open and the {product} looked used when it arrived. I want a new one or my money back.",
        "What's your return policy for the {product}? Mine arrived {when} and I'd like to send it back.",
    ],
    "product_inquiry": [
        "Does the {product} work with {platform}?",
        "What's the difference between the {plan_lo} and {plan_hi} plans{for_whom}?",
        "Is the {product} back in stock? It's been showing sold out for a while.",
        "Does the {plan} plan include {plan_feature}?",
        "How many {device_kind} can a single Nimbrook Hub handle? We're planning on about {n_units}.",
        "Is the {outdoor_product} fully weatherproof, or does it need a cover in {weather}?",
        "We're thinking about buying {n_units} units of the {product} for our office. Do you offer volume pricing?",
        "Can I try {plan_hi} before committing? Is there a free trial{trial_tail}?",
        "What's the battery life on the {battery_product}{usage}?",
        "How many users can we have on the {plan} plan?",
        "Will the {product} still work if the Wi-Fi goes down?",
        "What's the difference between {compare_pair}? Which would you recommend for {home_type}?",
        "Is the {accessory} compatible with the older Hub Mini, or do I need the new Nimbrook Hub?",
        "Does the {plan_hi} plan come with priority support?",
        "When will the {product} in {color} be available again?",
        "Can the {product} be wall mounted? Is the bracket included?",
        "Do all plans include {plan_feature}, or only the paid ones?",
        "Does your API have rate limits on the {plan} plan? We're comparing vendors.",
        "What comes in the box with the {product} starter kit?",
        "Is there a student or nonprofit discount on the {plan} plan?",
        "Can I use the Nimbrook app on the {plan} plan without buying any hardware?",
        "Before I buy — what warranty comes with the {product}?",
        "Is the {integration} integration available on {plan_lo}, or only on higher tiers?",
        "How much does the {plan_hi} plan cost per user for a team of {seats}?",
        "Does the {accessory} need a hub, or can it connect straight to Wi-Fi?",
    ],
    "cancellation": [
        "Please cancel my {plan} subscription{cancel_tail}.",
        "I want to close {account_ref} and delete all the data{data_tail}.",
        "How do I turn off auto-renewal? I don't want to renew in {month}.",
        "Please downgrade us from {plan_hi} to {plan_lo} at the end of this billing cycle.",
        "We're moving to a different tool, please cancel our team's subscription effective {future_date}.",
        "cancel my {plan} sub pls",
        "I'd like to stop my {plan} subscription from renewing next month.",
        "Can you cancel my annual {plan} plan at the end of the term instead of renewing it?",
        "Please close the account registered to {email}.",
        "I'm cancelling. The {plan} plan is too expensive for how little I use it.",
        "How do I delete my Nimbrook account completely{del_tail}?",
        "Our company is shutting down {shutdown_when}; please cancel the {plan} plan and close the workspace.",
        "I want to downgrade to the free plan. I don't need {plan_feature} anymore.",
        "Stop renewing my {plan} plan — {reason_short}",
        "I clicked cancel on my {plan} plan {when} but never got a confirmation. Is my subscription actually cancelled?",
        "I signed up for the {plan_hi} trial {when} and don't want to continue to a paid plan. How do I cancel before it converts?",
        "Please cancel the {addon} add-on on our account, we don't need it anymore.",
        "We'd like to terminate our {plan} contract at the end of the current term in {month}.",
        "I'd like to cancel my {plan} membership. I barely use the {appn} these days.",
        "We're consolidating accounts — please close the duplicate account under {email}.",
        "How much notice do you need for us to cancel our {plan_hi} agreement before it renews in {month}?",
        "Take me off the paid {plan} plan, I'll stick with the free version.",
        "Please cancel the {plan} subscription for my father, {male_name}. He doesn't use it anymore.",
        "We only need {plan_lo} going forward — downgrade our workspace from {plan_hi} before the {month} renewal.",
    ],
    "feature_request": [
        "It would be great if the app had {new_feature}.",
        "Please add {new_feature}. Our team would use it every day.",
        "Feature request: {new_feature}.",
        "Any plans to build {new_feature}? Would love to see it.",
        "Suggestion: let us {capability_new} directly from the dashboard.",
        "Please consider making the {product} work with {request_platform} — right now it doesn't, and I'd buy two more if it did.",
        "{Feature} would be much more useful if it also {enhancement}.",
        "Would you consider adding {new_feature} to the mobile app?",
        "Idea for the roadmap: {new_feature}.",
        "We'd happily pay extra for {new_feature}. Please consider it.",
        "Can you add an option to {capability_new}? Right now we have to do it by hand.",
        "Love the {product}, but the next version really needs {hw_feature}.",
        "Please make it possible to {capability_new}.",
        "My only wish: {new_feature}. Otherwise the app is perfect.",
        "Has anyone else asked for {new_feature}? Adding my vote.",
        "Would love an API endpoint for {api_thing}.",
        "The dashboard should let us {capability_new}.",
        "Please add an integration with {new_integration} — we use it for everything.",
        "Suggestion for the {product}: {hw_feature} would make it so much better.",
        "Small request: {small_req}.",
        "Can the {appn} get {new_feature}? Pretty please.",
        "Every competitor has {new_feature} by now. Please add it.",
        "Our admins keep asking for a way to {capability_new}. Could you build that?",
    ],
}

HARD = {
    "billing": [
        "The app itself works fine — the problem is a {amount} charge {when} for a renewal I never authorized. I want that money back.",
        "We cancelled our {plan} plan back in {month}, but you still charged us {amount} on the latest renewal. Please refund that charge.",
        "I downgraded to {plan_lo} last month but was still billed the {plan_hi} price of {amount}. Please fix the charge; nothing else needs to change.",
        "Order {order} arrived fine, no problem with the delivery itself — but I was charged {amount} for express shipping when I picked free standard shipping.",
        "I don't want to return the {product}, I love it — but my card was charged {amount} twice for order {order}. Please refund the extra charge.",
        "I can log in fine, I just can't find where to update the payment card for the next {plan} renewal.",
        "Not a bug report: invoice {invoice} lists {seats} seats and we only pay for {seats_small}.",
        "I'm not asking to change plans — I just need someone to explain the {amount} 'usage overage' line on invoice {invoice}.",
        "No need to cancel anything, but our renewal price jumped from {price_jump} without notice and I want it corrected.",
    ],
    "technical_issue": [
        "I can sign in without any problem, but right after login {feature} freezes and the tab crashes.",
        "This isn't a feature request — {feature} worked fine last week and now it throws {errcode}.",
        "The {product} arrived in perfect condition and I don't want to return it; it just won't connect to the app ({errcode}).",
        "Our subscription is paid up and active, but the API has been returning {http_errors} {since}.",
        "I don't want a refund, I want the {integration} sync fixed. It has been failing {since}.",
        "Delivery was quick, but the firmware update on the {product} keeps failing at {pct}% so I can't use it.",
        "Logging in with 2FA works fine, but after that every page in the {appn} takes {secs} seconds to load.",
        "Not asking for anything new — the existing export button in {feature} simply does nothing when I click it.",
        "I'm not cancelling yet, but {feature} has been broken {since} and my team can't work. Please fix it.",
    ],
    "account_access": [
        "I'm not getting the password reset email at {email} — maybe a bug on your side? Either way, I need access to my account restored.",
        "My card was charged fine for {month}, but I'm locked out of the account after too many login attempts.",
        "I don't want to cancel or close anything, I just need the login email changed from {email} to {email2}.",
        "I get {login_err} every time I enter my 2FA code, so I can't get into my account.",
        "Not a delivery question — the new {product} asks me to sign in to my Nimbrook account and my password isn't accepted.",
        "Keep sending invoices where they go now, but please change the email I log in with to {email}.",
        "I'd like to keep my {plan} subscription, I just lost my authenticator app and need 2FA reset so I can sign in.",
        "The app works fine on my partner's phone; it's only my account ({username}) that won't accept my password anymore.",
    ],
    "shipping_delivery": [
        "I don't want to return anything, I just want to know where order {order} is — tracking hasn't moved since {since_date}.",
        "Tracking says delivered {when}, but no package ever showed up, so there's nothing for me to return or exchange.",
        "Payment went through and the charge is on my card, but order {order} still says 'processing' after {n} days.",
        "The tracking page in the app shows an error, but honestly I don't care about that — just tell me when order {order} will arrive.",
        "Order {order} was due {when}. I don't want a refund, I still want the {product} — where is it?",
        "Only one of the two boxes from order {order} arrived; the tracking for the second box hasn't moved since {since_date}.",
        "My package for order {order} was sent back to your warehouse as undeliverable. Please ship it out again to {address}.",
        "Not a billing question, the amount was right — I need the delivery address on order {order} changed to {address} before it ships.",
    ],
    "returns_refunds": [
        "The package arrived on time, no complaints about delivery — but the {product} inside was cracked. I'd like a replacement.",
        "I sent the {product} back {n} days ago and the carrier confirmed it reached your warehouse. When will my {amount} refund show up?",
        "Nothing is broken and it works fine, I just ordered the wrong one — I'd like to exchange it for {variant}.",
        "Tracking says delivered and yes, I got it — but the {product} is the wrong color. How do I swap it?",
        "I'm keeping my {plan} subscription, I just want to return the {product} I bought separately.",
        "The {product} stopped working after {n} days and honestly I'd rather send it back than troubleshoot it. How do I start a return?",
        "This isn't a billing dispute, the charge was correct — I just haven't received the refund for the {product} I returned {n} days ago.",
        "Not reporting a bug: the {product} works, but it arrived with a deep scratch across the front, so I want to exchange it.",
    ],
    "product_inquiry": [
        "Not reporting a bug — I just want to know whether the {product} works with {platform} before I buy one.",
        "Before I place an order: is the {product} in stock, and does it come with the mounting kit?",
        "Is there already a way to {capability_q} in the app, or is that not supported?",
        "Is the {product} compatible with {platform}? I'd hate to buy it and then have to return it.",
        "How much would it cost to move our team of {seats} from {plan_lo} to {plan_hi}? Just exploring for now, no changes to our billing yet.",
        "Not looking to cancel or switch yet — does {plan_hi} include {plan_feature}, or is that an add-on?",
        "Does the {product} need a paid subscription, or does it work without a monthly fee?",
        "I'm not requesting anything new, just checking: is it already possible to {capability_q} in the {appn}?",
    ],
    "cancellation": [
        "There's nothing wrong with the billing, we just don't need the tool anymore — please cancel our {plan} subscription.",
        "The {appn} has been buggy for weeks and I'm done. Cancel my {plan} subscription effective today.",
        "Please turn off auto-renewal before {future_date}; I don't want to be charged again.",
        "I can still log in fine, but I want {account_ref} closed and all of the data deleted.",
        "No need to fix the {integration} sync anymore, I've decided to leave. How do I cancel?",
        "We asked for {new_feature} months ago and nothing ever happened, so we're leaving. Please close our workspace.",
        "I'm not asking for a refund for past months, just cancel the {plan} plan so it doesn't renew in {month}.",
        "Keep the hardware, I'm not returning the {product} — I just want to cancel the {plan} cloud subscription.",
    ],
    "feature_request": [
        "Not a bug, everything works as designed — but it would be great if the export also supported {format}.",
        "The billing page should let us download all invoices at once as a ZIP; it would save our {finance_person} hours every month.",
        "Could you add an option to log in with {sso}? Right now there's only email and password and it's a pain for our team.",
        "It'd be nice if the order tracking page showed an estimated delivery window instead of just 'in transit' — I've placed {n} orders with you this year.",
        "Suggestion: let us pause the {plan} subscription for a month or two instead of having to cancel it.",
        "The app works great, no complaints — I'd just love {new_feature}.",
        "Not asking for a refund or anything, just a suggestion: let customers start a return for things like the {product} from inside the app.",
        "It would really help if the API had a webhook for {event}.",
        "We're not leaving or anything, but we'd love to see {new_feature} — several people here have mentioned it.",
    ],
}

COUNTS = {
    "billing": 150,
    "technical_issue": 150,
    "account_access": 150,
    "shipping_delivery": 150,
    "returns_refunds": 150,
    "product_inquiry": 150,
    "cancellation": 150,
    "feature_request": 150,
}


def generate(rng: random.Random) -> list[dict]:
    return merge(*[
        label_items(
            rng, label, n, TEMPLATES[label], SLOTS,
            hard_templates=HARD[label], hard_share=0.2,
            prefixes=PREFIXES, suffixes=SUFFIXES,
        )
        for label, n in COUNTS.items()
    ])
