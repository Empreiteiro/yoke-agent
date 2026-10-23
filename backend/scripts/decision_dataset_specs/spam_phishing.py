"""Email & SMS threat triage: legitimate / spam / phishing.

Messages are short SMS texts or emails written as ``Subject: ... — body``.
Every brand, domain and phone number is fictional: trusted services use
invented names (Velmora Bank, Brisklane Express, Shopvale, ...), phishing
links use obvious lookalike domains built from those names
(``velmora-secure-verify.co``, ``brisklane-redelivery.net``), and phone
numbers use the 555 range.

Templates reference brand categories as ``{bank}`` / ``{bank_url}`` /
``{bank_stem}``. At import time each template is expanded once per brand of
that category, so the brand named in the text always matches the brand in
its (fake) URL. Each template is replicated to the same number of entries,
so templates are sampled uniformly no matter how many brands they expand to.
"""

from __future__ import annotations

import itertools
import random
import re
import string

from ._common import FIRST_NAMES, LAST_NAMES, MONTHS, WEEKDAYS, amount, clock_time, digits, full_name, integer, label_items, merge, order_id

SLUG = "spam_phishing"
NAME = "Email & SMS Threat Triage"
DESCRIPTION = (
    "1,200 synthetic emails and SMS messages, 400 each labeled legitimate, spam or phishing, with "
    "hard cases such as genuine security alerts, urgent-but-harmless spam and calm, well-written phishing."
)
LANGUAGE = "en"
TASK = "How should this incoming message be classified?"

LABELS = [
    {
        "name": "legitimate",
        "description": (
            "A normal message the recipient would expect: personal or work conversation, or transactional/account "
            "mail from a service they use (order and shipping updates, receipts, bookings, reminders, bills, "
            "password resets or one-time codes they requested, newsletters they subscribed to). Security and "
            "billing notices are legitimate when they only inform, or tell the user to open the official app or "
            "website themselves, and never ask for passwords, card details or codes or push an unrequested login "
            "link. Expected transactional mail stays legitimate even if it contains a link or a promotion."
        ),
    },
    {
        "name": "spam",
        "description": (
            "Unsolicited bulk or scam messaging from a sender the recipient has no relationship with: hype "
            "marketing, prize/lottery/inheritance claims, get-rich-quick and fake job offers, crypto, casino, "
            "dating, diet-pill or SEO pitches. It may be urgent and may ask the user to reply, call, buy or visit "
            "a promo site, but it does not pose as a service, institution or person the recipient already trusts "
            "and does not try to obtain login credentials, card/bank details or verification codes. If it does "
            "both of those things, it is phishing."
        ),
    },
    {
        "name": "phishing",
        "description": (
            "Impersonates a trusted entity (the user's bank, payment app, courier, online store, streaming, cloud "
            "or social account, crypto exchange, employer IT/HR, a manager, a known vendor, a tax or toll agency) "
            "in order to steal credentials, card or bank details, recovery phrases or one-time codes, collect a "
            "fake fee, redirect a payment or gift-card purchase, or get the user to sign in or 'verify' through a "
            "link or attachment. Typical cues are lookalike domains and unrequested account threats or "
            "deadlines, but a calm, well-written message with one of these goals is still phishing."
        ),
    },
]


# ── Fictional brands ──────────────────────────────────────────────────────
# (display name, domain stem). Legitimate mail links to "<stem>.com";
# phishing links use lookalike hosts generated from the stem.

BRANDS: dict[str, list[tuple[str, str]]] = {
    "bank": [
        ("Velmora Bank", "velmora"), ("Harborline Credit Union", "harborline"),
        ("Quenby Bank", "quenbybank"), ("Northbank", "northbank"),
    ],
    "courier": [("Brisklane Express", "brisklane"), ("Swiftcrate Delivery", "swiftcrate"), ("ParcelPost", "parcelpost")],
    "store": [("Shopvale", "shopvale"), ("Marketnest", "marketnest"), ("Quillmart", "quillmart")],
    "stream": [("Cinelume", "cinelume"), ("Vidora+", "vidoraplus"), ("Tunebay", "tunebay")],
    "cloud": [("Trellik Drive", "trellik"), ("Nimbusbox", "nimbusbox")],
    "pay": [("PayQuill", "payquill"), ("Corvane Pay", "corvanepay")],
    "telecom": [("Mardell Mobile", "mardell"), ("Brightwave Telecom", "brightwavetel")],
    "social": [("Friendloop", "friendloop"), ("Glimmergram", "glimmergram")],
    "work": [("Teamhive", "teamhive"), ("Slatework", "slatework")],
    "tax": [("the National Revenue Office", "revenueoffice"), ("the Federal Tax Bureau", "fedtaxbureau")],
    "toll": [("Metro Toll Authority", "metrotoll"), ("Highway Express Tolls", "hwyexpresstoll")],
    "exchange": [("Coinvale Exchange", "coinvale"), ("Bitharbor", "bitharbor")],
    "esign": [("InkSeal", "inkseal"), ("Signara", "signara")],
}

_PHISH_HOSTS = {
    "default": [
        "{s}-secure-verify.co", "{s}-account-check.net", "secure-{s}-login.com", "{s}.account-review-center.info",
        "{s}-support-desk.help", "{s}-id-confirm.top", "my{s}-verify.online", "{s}-security-notice.co",
    ],
    "courier": ["{s}-redelivery.net", "{s}-parcel-fees.com", "{s}-delivery-reschedule.info", "{s}-tracking-update.co"],
    "toll": ["{s}-payment-portal.co", "{s}-unpaid-notice.net", "pay-{s}-online.info"],
    "tax": ["{s}-refund-claim.net", "{s}-taxpayer-portal.co", "secure-{s}-refunds.info"],
}
_PHISH_PATHS = {
    "default": ["/login", "/verify", "/account/confirm", "/session/restore", "/secure/update", "/auth"],
    "courier": ["/pay", "/reschedule", "/fee", "/delivery"],
    "toll": ["/pay", "/balance", "/notice"],
    "tax": ["/claim", "/refund", "/form"],
}


def _phish_url(stem: str, category: str):
    hosts = [h.format(s=stem) for h in _PHISH_HOSTS.get(category, _PHISH_HOSTS["default"])]
    paths = _PHISH_PATHS.get(category, _PHISH_PATHS["default"])

    def _gen(rng: random.Random) -> str:
        scheme = "http" if rng.random() < 0.25 else "https"
        url = f"{scheme}://{rng.choice(hosts)}{rng.choice(paths)}"
        if rng.random() < 0.4:
            url += f"?id={rng.randint(10000, 99999)}"
        return url

    return _gen


# ── Small slot generators ─────────────────────────────────────────────────

_ALNUM = string.ascii_letters + string.digits
_UPPER = "ABCDEFGHJKLMNPQRSTUVWXYZ"


def _token(rng: random.Random) -> str:
    return "".join(rng.choice(_ALNUM) for _ in range(18))


def _conf(rng: random.Random) -> str:
    return "".join(rng.choice(_UPPER + "23456789") for _ in range(8))


def _tracking(rng: random.Random) -> str:
    return f"{rng.choice(_UPPER)}{rng.choice(_UPPER)}{rng.randint(100000000, 999999999)}"


def _phone(rng: random.Random) -> str:
    style = rng.randint(0, 2)
    if style == 0:
        return f"(555) {rng.randint(200, 989)}-{rng.randint(1000, 9999)}"
    if style == 1:
        return f"555-01{rng.randint(10, 99)}"
    return f"1-800-555-01{rng.randint(10, 99)}"


def _fee(rng: random.Random) -> str:
    return f"${rng.randint(1, 4)}.{rng.randint(10, 99)}"


def _future_day(rng: random.Random) -> str:
    style = rng.randint(0, 2)
    if style == 0:
        return "tomorrow"
    if style == 1:
        return rng.choice(WEEKDAYS)
    return f"{rng.choice(MONTHS)} {rng.randint(1, 28)}"


def _past_date(rng: random.Random) -> str:
    if rng.random() < 0.4:
        return rng.choice(["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"])
    return f"{rng.choice(MONTHS)} {rng.randint(1, 28)}"


def _invoice(rng: random.Random) -> str:
    return f"INV-{rng.randint(10000, 99999)}"


def _promo(rng: random.Random) -> str:
    return rng.choice(["MEMBER", "LOYAL", "THANKYOU", "WEEKEND", "INSIDER"]) + str(rng.randint(10, 25))


def _sort_code(rng: random.Random) -> str:
    return f"{rng.randint(10, 99)}-{rng.randint(10, 99)}-{rng.randint(10, 99)}"


def _amount_m(rng: random.Random) -> str:
    return f"${rng.randint(2, 19)}.{rng.randint(1, 9)} million"


SENDER_NAMES = [
    "Tom", "Nadia", "Ben", "Clara", "Marcus", "Ines", "Leo", "Ruth", "Victor", "Mei", "Felix", "Tara",
    "Hugo", "Elena", "Jonas", "Rosa",
]
OTHER_NAMES = ["Petra", "Arjun", "Wendy", "Kofi", "Sienna", "Malik", "Ingrid", "Theo"]


def _spam_domains(*names: str) -> list[str]:
    return list(names)


SLOTS: dict = {
    # people
    "first": FIRST_NAMES,
    "sender": SENDER_NAMES,
    "other": OTHER_NAMES,
    "fullname": full_name,
    "last": LAST_NAMES,
    "family": ["Mum", "Dad", "Grandma", "Aunt Rita", "Uncle Joe"],
    "exec_title": ["CEO", "Managing Director", "VP of Finance", "Head of Operations"],
    # time
    "weekday": WEEKDAYS,
    "workday": WEEKDAYS[:5],
    "work_time": ["9am", "9:30am", "10am", "11am", "11:30am", "1pm", "2pm", "2:30pm", "3pm", "4pm"],
    "evening_time": ["5pm", "5:30pm", "6pm", "6:30pm", "7pm"],
    "dinner_time": ["7pm", "7:30pm", "8pm", "8:15pm"],
    "lunch_time": ["12pm", "12:30pm", "1pm", "1:15pm"],
    "morning_time": ["10am", "10:30am", "11am"],
    "table_time": ["12:30pm", "1pm", "7pm", "7:30pm", "8pm", "8:30pm"],
    "social_time": ["noon", "1pm", "3pm", "6pm", "7pm", "7:30pm"],
    "meal_plan": [
        "dinner on {weekday}? I can book a table at {restaurant} for {dinner_time}",
        "lunch on {weekday}? I can book a table at {restaurant} for {lunch_time}",
        "brunch on Sunday? I can book a table at {restaurant} for {morning_time}",
        "coffee on {weekday}? I can meet you at {cafe} around {morning_time}",
    ],
    "month": MONTHS,
    "time": clock_time,
    "future_day": _future_day,
    "past_date": _past_date,
    "past_when": ["today at {time}", "yesterday at {time}", "earlier today", "this morning"],
    "deadline": ["within 24 hours", "within 48 hours", "by midnight tonight", "within 12 hours", "before the end of today"],
    "window": ["8am and noon", "noon and 4pm", "10am and 2pm", "2pm and 6pm", "9am and 1pm"],
    "mins": ["5", "10", "15", "20", "25"],
    "nights": ["two", "three", "four", "five"],
    "secs": integer(12, 58),
    # numbers / ids
    "amount": lambda rng: amount(rng, 12, 900),
    "sub_price": lambda rng: f"${rng.choice([6, 8, 9, 10, 11, 12, 13, 14, 15, 17, 19])}.99",
    "bill_amount": lambda rng: amount(rng, 25, 140),
    "cafe_amount": lambda rng: amount(rng, 4, 45),
    "fee": _fee,
    "late_fee": ["$25", "$40", "$50", "$75"],
    "order": order_id,
    "tracking": _tracking,
    "code": digits(6),
    "last4": digits(4),
    "acct": digits(8),
    "sort": _sort_code,
    "inv": _invoice,
    "token": _token,
    "conf": _conf,
    "promo": _promo,
    "phone": _phone,
    "q": ["1", "2", "3", "4"],
    "n": integer(2, 6),
    "room": integer(101, 420),
    "pct_used": integer(41, 78),
    "n_cards": ["three", "four", "five", "six"],
    "gc_amount": ["$100", "$150", "$200", "$250"],
    # places / things
    "city": ["Lisbon", "Denver", "Toronto", "Manchester", "Austin", "Lyon", "Melbourne", "Porto", "Dublin"],
    "country": ["another country", "an unrecognized location", "overseas", "a new region"],
    "device": ["a new laptop", "a desktop browser", "a mobile browser", "a new tablet"],
    "restaurant": ["Luca's", "The Copper Pot", "Bramble Café", "Nori House", "Casa Verde", "The Green Fig"],
    "cafe": ["Bramble Café", "Hilltop Coffee", "The Daily Grind Bakery", "Juniper Kitchen"],
    "drink": ["a flat white", "a lemonade", "an iced tea", "a cappuccino"],
    "event": ["the barbecue", "Sam's wedding", "the hiking trip", "graduation", "the office party", "the reunion"],
    "grocery": ["milk", "bread and eggs", "coffee filters", "dish soap", "bananas", "some pasta"],
    "dish": ["pumpkin soup", "lemon pasta", "banana bread", "veggie chili", "a potato salad"],
    "meeting": ["weekly sync", "design review", "sprint planning", "budget meeting", "client call", "all-hands"],
    "topic": ["the onboarding flow", "the budget", "hiring", "the launch timeline", "vendor contracts", "the roadmap"],
    "project": ["checkout", "search", "billing", "mobile", "reporting", "onboarding"],
    "role": ["Data Analyst", "Product Designer", "Account Manager", "Backend Engineer", "Office Coordinator"],
    "hotel": ["Harbor View Hotel", "The Linden Inn", "Maple Court Suites", "Seabright Lodge"],
    "gym": ["Ironleaf Fitness", "CoreWorks Studio", "Riverside Climbing Gym"],
    "gym_class": ["Spin 45", "Morning Yoga", "HIIT Express", "Pilates Core"],
    "merchant": ["Greenleaf Grocers", "Urban Outfit Co.", "TechCorner", "Sunset Fuel", "Bluebird Books", "Pinecrest Pharmacy"],
    "street": ["Elm Street", "Station Road", "Market Square", "Oak Avenue"],
    "club": ["running club", "book club", "community garden", "chess club"],
    "raffle_prize": ["a weekend spa voucher", "a new bike helmet", "a picnic hamper", "two cinema tickets"],
    "vendor": ["Brightline Supplies", "Corbel Logistics", "Ashford Print Co.", "Meridale Packaging"],
    "shutoff_window": ["9am to noon", "10am to 2pm", "8am to 11am", "1pm to 4pm"],
    "shutoff_reason": ["pipe repairs", "boiler maintenance", "a water meter replacement", "a valve inspection"],
    "maint_window": ["10pm and 2am", "11pm and 3am", "midnight and 4am"],
    "year_group": integer(3, 11),
    "biz_site": ["your website", "your online store", "your company's site", "your blog", "your shop's website"],
    "seo_days": ["30", "45", "60", "90"],
    "double_time": ["one hour", "30 minutes", "two hours"],
    "followers_n": ["5,000", "10,000", "25,000", "50,000"],
    "contacts_n": ["1 million", "2 million", "5 million"],
    "visitors_n": ["5,000", "10,000", "20,000"],
    "hours_week": ["10", "15", "20", "25"],
    "card_kind": ["debit card", "credit card", "card"],
    "doc_name": ["Service Agreement", "NDA", "Lease Renewal", "Contractor Agreement", "Purchase Order"],
    # spam vocabulary
    "prize_cash": ["$500", "$1,000", "$2,500", "$5,000"],
    "amount_k": ["$3,000", "$5,000", "$8,500", "$10,000", "$12,000"],
    "amount_m": _amount_m,
    "amount_day": ["$300", "$450", "$500", "$800"],
    "hourly": ["$35", "$40", "$45", "$55"],
    "bonus": ["$200", "$500", "$1,000"],
    "small_invest": ["$250", "$300", "$500"],
    "bulk_price": ["$19", "$29", "$49", "$99"],
    "save_month": ["$300", "$450", "$600"],
    "pct": ["50", "60", "70", "75", "80", "90"],
    "kg": ["5", "8", "10", "12"],
    "days": ["7", "10", "14", "21"],
    "n_left": ["50", "100", "25", "10"],
    "short_code": ["55{n}21", "8{n}412", "6{n}009"],
    "gadget": ["smartwatch", "tablet", "robot vacuum", "laptop", "gaming console", "smart speaker", "drone"],
    "spam_prize": ["65-inch TV", "brand-new laptop", "luxury holiday package", "electric scooter"],
    "casino": ["Lucky Lotus Casino", "Golden Reel Casino", "SpinPalace Royale"],
    "coin": ["MoonFlare", "ZentaCoin", "PumpX"],
    "pill": ["Slimlex", "TrimVita", "KetoBurn Max"],
    "resort": ["Palm Crescent Resort", "Coral Sands Villas", "Blue Lagoon Retreat"],
    "spam_lawyer": ["James Okoro", "Michael Rowe", "Daniel Ferraz"],
    "romance_name": ["Anastasia", "Julia", "Natalie", "Viktoria"],
    "romance_email": ["sweet.julia88@lovemail-connect.net", "anastasia.dream@kisschat-mail.org", "natalie4u@heartmatch-inbox.net"],
    "shop_domain": _spam_domains("megadeal-outlet.biz", "flashsale-warehouse.store", "clearance-blowout.shop", "superdeals-now.biz"),
    "dating_domain": _spam_domains("hotsingles-chat.club", "lonelyhearts-meet.date", "flirtnow-singles.online"),
    "diet_domain": _spam_domains("trimfit-gummies.shop", "burnfat-fast.store", "miracle-slim-offer.shop"),
    "crypto_domain": _spam_domains("cryptomoon-signals.io", "aitrade-profits.vip", "coinrocket-club.biz"),
    "casino_domain": _spam_domains("play-bonus-spins.win", "vip-casino-rewards.bet", "jackpot-spin-club.win"),
    "pharma_domain": _spam_domains("cheapmeds-direct.shop", "pillsavings-online.biz"),
    "survey_domain": _spam_domains("freegift-survey.click", "reward-survey-center.top", "quickprize-poll.win"),
    "followers_domain": _spam_domains("followers-boost.top", "instafame-growth.biz"),
    "loan_domain": _spam_domains("refi-lowrates-now.biz", "best-rate-quotes.biz", "lowrate-refi-offers.top"),
    "prize_domain": _spam_domains("prize-claim-center.win", "lucky-winner-desk.top", "spinwheel-rewards.click"),
}

# One phishing-URL slot per brand: url__<category>__<index>.
for _cat, _brands in BRANDS.items():
    for _i, (_name, _stem) in enumerate(_brands):
        SLOTS[f"url__{_cat}__{_i}"] = _phish_url(_stem, _cat)


# ── Templates ─────────────────────────────────────────────────────────────

LEGITIMATE = [
    # personal
    "Hey {first}, are we still on for {meal_plan}.",
    "{family} here. Landed safely in {city}, will call you once I'm at the hotel. Love you x",
    "Running about {mins} minutes late, sorry! Grab us a table near the window and order me {drink}.",
    "Subject: Photos from {event} — Hi {first}, here are the photos from {=event}. The group shot came out great. Talk soon, {sender}",
    "Can you pick up {grocery} and {grocery} on your way home? We're out of both. Thanks!",
    "Happy birthday, {first}! Hope you have a brilliant day. Drinks are on me this {weekday}. – {sender}",
    "Subject: Re: weekend plans — Sounds good! I'll bring {dish}. Does {social_time} on Saturday still work for everyone?",
    "Hi {first}, it's {sender} from next door. A parcel for you was left with us by mistake. Pop round whenever you like to pick it up.",
    # work
    "Subject: Agenda for {workday}'s {meeting} — Hi team, I've added the agenda to the calendar invite. Main items: {topic} and {topic}. See you at {work_time}. {sender}",
    "Subject: Q{q} report draft — Hi {first}, I've put the draft of the Q{=q} report in our team folder. Could you check the figures in section {n} before {workday}? Thanks, {sender}",
    "Subject: Out of office — Hi {first}, I'm away from {workday} until the following {workday}. {sender} is covering anything urgent on {topic} while I'm out.",
    "Subject: Interview confirmation — Hi {first}, your interview for the {role} position is confirmed for {workday} at {work_time}. You'll meet {sender} and {other}. Just reply if you need to reschedule.",
    "Quick heads-up: the {meeting} moved to room {room} today. Same time, {work_time}.",
    "Subject: Friday lunch order — Hi all, please add your order to the shared sheet by Thursday noon. It's {restaurant} this week. {sender}",
    "Subject: Comments on your {project} pull request — Hey {first}, I left a few comments on your PR. Mostly naming nitpicks; the logic looks good to merge once they're addressed.",
    # transactional
    "Subject: Your {store} order {order} has shipped — Hi {first}, good news: your order is on its way with {courier}. Estimated delivery: {future_day}. You can follow it from the Orders page in your account.",
    "Subject: Order confirmation {order} — Thanks for shopping with {store}! We've received your order totalling {amount}. We'll send another email when it ships.",
    "{store}: your order {order} was delivered today at {time}. Enjoy!",
    "Subject: Your receipt from {cafe} — Total: {cafe_amount}. Paid by card ending in {last4}. Thanks for stopping by!",
    "Reminder: your appointment with Dr. {last} is {future_day} at {work_time}. Reply C to confirm or call {phone} to reschedule.",
    "{bank}: your {month} statement is now available. You can view it in the {=bank} app under Documents.",
    "{code} is your {store} verification code. It expires in 10 minutes. Don't share it with anyone.",
    "Subject: Your {stream} plan has renewed — Your monthly plan renewed on {past_date} for {sub_price}. No action is needed. You can manage your plan anytime in Account settings.",
    "Subject: Booking confirmed: {hotel}, {city} — Hi {first}, your {nights}-night stay starting {future_day} is confirmed. Check-in is from 3pm. Confirmation number: {conf}.",
    "{courier}: your parcel {tracking} will be delivered {future_day} between {window}. No signature needed.",
    "Subject: Your {telecom} bill is ready — Your bill for {month} is {bill_amount} and will be collected by direct debit {future_day}. No action needed.",
    "Subject: Password changed — Hi {first}, the password for your {store} account was changed on {past_date} at {time}. If this was you, no further action is needed. If not, contact us from the Help page in the app.",
    "Your table for {n} at {restaurant} is confirmed for {weekday} at {table_time}. See you then!",
    "Subject: Parent-teacher evening — Dear parents of Year {year_group}, parent-teacher evening is on {workday} from {evening_time}. Please book a slot with your child's form tutor through the school office.",
    "Subject: Library items due soon — Hi {first}, {n} items on your library card are due back {future_day}. You can renew them at the front desk or by phone.",
    "Subject: Water shut-off on {weekday} — Hi residents, the water will be off on {=weekday} from {shutoff_window} for {shutoff_reason}. Sorry for the inconvenience. – Building management",
    "{gym}: your {gym_class} class starts tomorrow at {time}. Need to cancel? You can do it in the app up to 2 hours before.",
    "Subject: Your refund has been processed — Hi {first}, we've refunded {amount} for order {order} to your original payment method. It can take 3-5 business days to appear.",
]

LEGITIMATE_HARD = [
    "Subject: New sign-in to your {bank} account — We noticed a sign-in from {device} in {city} {past_when}. If this was you, there's nothing to do. If not, open the {=bank} app yourself and change your password under Security. We will never ask for your password or PIN by email.",
    "Subject: Reset your {store} password — Hi {first}, we received your request to reset your password. Use this link within 30 minutes: https://account.{store_stem}.com/reset/{token} If you didn't ask for this, ignore this email and your password will stay the same.",
    "{bank}: did you make a card purchase of {amount} at {merchant}? Reply YES or NO. We will never ask for your PIN, password or full card number.",
    "Subject: Your {month} newsletter from {store} — New arrivals, a recipe for {dish}, and 15% off for members this weekend with code {promo}. You're receiving this because you subscribed at {store_stem}.com. Unsubscribe anytime in your account settings.",
    "Subject: Email maintenance this Saturday — Hi all, our email servers will be upgraded on Saturday night between {maint_window}. You don't need to do anything, and your password stays the same. Questions? Ask {sender} at the IT desk.",
    "Subject: We couldn't process your payment — Hi {first}, we couldn't charge your card for your {stream} plan, so we'll try again in 3 days. To update your card, open the {=stream} app and go to Account > Billing. We never ask for card details by email.",
    "Subject: Benefits enrollment opens Monday — Hi everyone, open enrollment runs until {future_day}. Plan details are on the HR page of the intranet, and {sender} from HR is hosting a Q&A on {workday} at {work_time}. No action is needed if you're keeping your current plan.",
    "Subject: Re: invoice {inv} — Hi {first}, thanks for the reminder. Our finance team paid invoice {=inv} on {past_date}, so it should reach you within two business days. We used the bank details from the original contract. Best, {sender}",
    "{courier}: we tried to deliver parcel {tracking} today but nobody was home. It's waiting at your local pickup point on {street} until {future_day}. Please bring photo ID.",
    "Subject: You won the raffle! — Hi {first}, you won the {club} raffle at last week's meetup! Your prize, {raffle_prize}, is waiting at the front desk. Pick it up any time this month. – {sender}",
    "URGENT: {first}, the client moved the deadline to 9am tomorrow. Can you send me the final slides tonight? Call me if anything's blocking you. – {sender}",
    "{pay}: you sent {amount} to {fullname} on {past_date}. If you don't recognize this payment, contact us through the Help section of the app.",
    "Subject: Your {cloud} storage summary — You're using {pct_used}% of your plan. Nothing to do right now; we'll let you know if you get close to the limit.",
]

SPAM = [
    "CONGRATULATIONS! You've been selected to receive a {prize_cash} gift card! Reply YES now to claim your reward before it's gone!!!",
    "Subject: Make {amount_k} a week from home — No experience needed! Thousands of people are already earning with our simple system. Reply INFO to find out how.",
    "Lonely tonight? Hundreds of singles near {city} are waiting to chat with you. Join free at {dating_domain}",
    "Subject: {pct}% OFF luxury watches — LIMITED STOCK! Designer-style watches at factory prices with free worldwide shipping. Shop now: {shop_domain}",
    "Lose {kg} kg in {days} days with the one weird trick doctors hate! Order {pill} today at {diet_domain}",
    "Subject: {coin} is about to explode — Get in before it rises 1000%! Our VIP signals group made members {amount_k} last month. Join now: {crypto_domain}",
    "Claim 200 FREE SPINS plus a {bonus} welcome bonus at {casino}! No deposit needed. Play now at {casino_domain}",
    "Dear Friend, I am Barrister {spam_lawyer}. A late client of mine left {amount_m} with no next of kin, and you share his surname. Reply to me urgently so we can discuss the transfer.",
    "Subject: Get your website to page 1 — Hi, I noticed {biz_site} isn't ranking well on search engines. Our SEO team guarantees first-page rankings in {seo_days} days. Can I send you our price list?",
    "You have been PRE-APPROVED for a {amount_k} loan from QuickCash Direct! No credit check, money in 24 hours. Call {phone} now!",
    "FREE MSG: You've won a 7-night Caribbean cruise for 2! Call {phone} to claim. Txt STOP to opt out.",
    "Subject: Final notice on your vehicle warranty — Your car's extended warranty may be about to expire. Call {phone} today to extend your coverage before it's too late.",
    "Earn {amount_day} a day just by liking videos from your phone! Text JOB to {short_code} and start today.",
    "Subject: Cheap medication, no prescription needed — Generic pills at {pct}% off, discreet shipping worldwide. Order at {pharma_domain}",
    "Subject: Turn {small_invest} into {amount_k} in 30 days — Our AI trading bot never loses. Guaranteed returns, limited spots left: {crypto_domain}",
    "Subject: {contacts_n} verified email contacts — Reach millions of buyers! Bulk email lists from just {bulk_price}. Reply for a free sample.",
    "MEGA CLEARANCE!!! Everything must go — up to {pct}% off sofas, mattresses and more. This weekend only at {shop_domain}",
    "Get a FREE {gadget} — just complete our 30-second survey! Only {n_left} left: {survey_domain}",
    "Subject: Celebrities are raving about {pill} — Burn fat while you sleep! Claim your trial bottle today, just pay shipping: {diet_domain}",
    "WIN BIG tonight at {casino}! We'll double your first deposit up to {bonus}. 18+ only. Play at {casino_domain}",
    "Subject: Confidential business proposal — Dear Sir/Madam, I am an account manager at an overseas bank and I have a confidential proposal worth {amount_m} that will benefit us both. Kindly reply for details.",
    "Your number was drawn in our monthly lucky draw! You've won {prize_cash}! Text WIN to {short_code} now.",
    "Subject: Want more followers? — Get {followers_n} followers on any social platform in 24 hours. Packages from {bulk_price}. Order at {followers_domain}",
    "Subject: Hello dear — I saw your profile and felt a special connection. I am {romance_name}, 28, looking for a serious relationship. Please write back to me at {romance_email}",
    "Subject: $0-down solar for homeowners — Homeowners in your area now qualify for free solar panel installation. Call {phone} to book your free assessment!",
    "Subject: Free resort stay for two — You and a guest are invited to a FREE {nights}-night stay at {resort} in exchange for attending a short presentation. Reply YES by {weekday} to reserve your spot.",
    "Rates have never been lower! Refinance now and save up to {save_month} a month. Get your free quote: {loan_domain}",
    "Subject: {coin} giveaway event — Send any amount of crypto to our event wallet and get DOUBLE back within {double_time}! Only {n_left} spots left.",
    "Subject: Unclaimed prize notification — Our records show you still have an unclaimed {spam_prize} from our {month} promotion. Visit {prize_domain} to arrange delivery.",
    "STOP paying for TV! Watch 10,000 channels for just {bulk_price} a year with our streaming box. Order now: {shop_domain}",
    "Subject: Drowning in debt? — Our debt relief program can cut what you owe in half. Free consultation — call {phone} today!",
    "Subject: Remote data entry job — We are hiring remote assistants: {hourly}/hour for {hours_week} hours a week, no interview needed. Reply with the word INTERESTED to begin.",
]

SPAM_HARD = [
    "LAST CHANCE!!! Your {pct}% discount on a {gadget} expires at MIDNIGHT. Don't miss out, order now at {shop_domain}",
    "URGENT: only 3 hours left to claim your {bonus} casino bonus! Your free spins expire tonight. Play now at {casino_domain}",
    "Hey, sorry for the random text! Got your number from a group chat. I've been making {amount_day} a day with this crypto app, you have to try it: {crypto_domain}",
    "Subject: Re: our call yesterday — Great speaking with you! As promised, here's our offer: {visitors_n} website visitors for just {bulk_price}. Reply to get started.",
    "Subject: Is your computer protected? — 9 out of 10 computers have hidden threats. Get {pct}% off ShieldMax Antivirus, today only: shieldmax-protect.shop",
    "Subject: 500 bonus points added to your player account — Your {casino} player account has been credited with 500 bonus points. Use them on any slot game before {weekday}!",
    "Subject: Important information about your prize — No payment or bank details needed! Simply reply CLAIM by {weekday} and our team will contact you about delivering your {spam_prize}.",
    "Dear valued customer, as a thank-you we're giving away {n_left} prizes this week, including a {gadget}. Spin the wheel to see if you've won: {prize_domain}",
    "FINAL NOTICE: your chance to lock in our lowest-ever price on a {gadget} ends today. After that, prices go up {pct}%. Shop now: {shop_domain}",
    "Subject: You've been hand-picked — Our partners selected you for an exclusive VIP investment club. Members earn {amount_k} a month. Spaces close {weekday}, reply YES to join.",
    "Hi {first}, your free gift is waiting! As one of our lucky shoppers, you can get a {gadget} for just the cost of shipping. Offer ends soon: {survey_domain}",
    "Subject: {first}, your exclusive invitation — You're one of 50 people chosen to test our new {gadget} for FREE. Reply TEST to secure your place before Friday.",
]

PHISHING = [
    "Subject: Your {bank} account has been suspended — We detected unusual activity on your account. To restore access, verify your identity {deadline}: {bank_url} Failure to do so will result in permanent closure.",
    "{courier}: your parcel {tracking} could not be delivered due to an unpaid shipping fee of {fee}. Pay now to reschedule delivery: {courier_url}",
    "Subject: Action required: your {pay} account is limited — We've limited your account until you confirm your card details. Log in to remove the limitation: {pay_url}",
    "Subject: Your mailbox is almost full — Your {cloud} storage is 99% full and new mail will be rejected. Sign in {deadline} to upgrade your storage at no cost: {cloud_url}",
    "{bank} ALERT: a payment of {amount} to {merchant} is pending. If you did not authorize it, cancel it immediately at {bank_url}",
    "Subject: Your {stream} payment failed — We were unable to process your payment. Update your billing details {deadline} to avoid losing access: {stream_url}",
    "Subject: Tax refund notification — Dear taxpayer, {tax} has calculated a refund of {amount} in your favor. To receive it, enter your card details on our secure form: {tax_url}",
    "Subject: Unusual sign-in attempt — Someone tried to sign in to your {store} account from {country}. If this wasn't you, confirm your password now to secure your account: {store_url}",
    "Subject: Password expiry notice — Your {work} password expires today. To keep your current password, log in here: {work_url} – IT Support",
    "Subject: Shared document: Invoice_{inv}.pdf — {fullname} has shared a document with you on {cloud}. Sign in with your email address and password to view it: {cloud_url}",
    "{telecom}: we could not process your last bill. Your line will be disconnected today unless you update your payment details at {telecom_url}",
    "Subject: Copyright violation on your {social} account — We received a complaint about content on your account. Appeal {deadline} or your account will be permanently deleted: {social_url}",
    "Subject: Mandatory security update — Dear {bank} customer, all customers must re-verify their online banking details following our system upgrade. Click here to continue: {bank_url}",
    "{bank}: your {card_kind} ending in {last4} has been temporarily blocked. To unblock it, reply to this message with your card number, expiry date and the 3-digit code on the back.",
    "Subject: Delivery attempt failed — {courier} was unable to deliver package {tracking}. Open the attached delivery form, enter your details and payment card, and send it back to book a new delivery slot.",
    "Subject: Your {store} order {order} has been cancelled — We couldn't verify your payment. Confirm your billing information {deadline} to restore your order: {store_url}",
    "Subject: New device added to your {pay} account — A new device was just linked to your account. If this wasn't you, log in immediately to remove it: {pay_url}",
    "{toll}: you have an unpaid toll balance of {fee}. Pay by {weekday} to avoid a {late_fee} penalty: {toll_url}",
    "Subject: Your updated salary letter — Hi {first}, your new compensation letter from HR is ready. Log in with your {work} email and password to view it: {work_url}",
    "Subject: Account closure notice — We are upgrading our servers and need all {cloud} users to confirm their login details. Accounts not confirmed by {weekday} will be closed. Confirm here: {cloud_url}",
    "{bank}: we've detected a suspicious transfer of {amount} from your account. To stop it, call our fraud team on {phone} and have your online banking password ready.",
    "Subject: Your {stream} account is on hold — Hi {first}, we couldn't verify your payment information. Please re-enter your card details to keep streaming: {stream_url}",
    "Subject: Wallet verification required — Dear {exchange} user, new regulations require you to verify your wallet. Enter your 12-word recovery phrase at {exchange_url} to keep your funds safe.",
    "Subject: You have 1 new voicemail — A voicemail ({secs} seconds) was left for you. Sign in with your {work} credentials to listen: {work_url}",
    "{courier}: your package is being held at customs. A clearance fee of {fee} is required before release. Pay by card here: {courier_url}",
    "Subject: Refund pending for order {order} — {store} owes you a refund of {amount}. To receive it, confirm your online banking login: {store_url}",
    "Subject: Final warning from {telecom} — Your account has been flagged for suspicious activity. Verify your identity now or your service will be suspended: {telecom_url}",
    "Subject: Confirm you still use {social} — We are removing inactive accounts. Sign in {deadline} to keep your account and photos: {social_url}",
    "{pay}: you've received {amount} from {fullname}. To accept the payment, log in and verify your bank details: {pay_url}",
    "Subject: Your secure {bank} statement — Your statement is attached as Statement_{month}.html. Open the attachment and sign in with your online banking details to view it.",
    "Subject: Please sign: {doc_name} — {fullname} sent you a document to review and sign via {esign}. Sign in with your email account to open it: {esign_url}",
    "{bank}: your account will be locked in 2 hours due to a failed security check. Verify now: {bank_url}",
]

PHISHING_HARD = [
    "Subject: Annual account review — Hi {first}, as part of our annual review we ask all customers to confirm their contact and sign-in details. It only takes a minute: {bank_url} Thank you for banking with {bank}.",
    "Hi {first}, it's {sender} ({exec_title}). Writing from my personal email as I'm in meetings all day. Could you buy {n_cards} {store} gift cards at {gc_amount} each for a client thank-you? Email me the codes and I'll reimburse you today.",
    "Subject: Updated bank details — Hello {first}, please note our bank details have changed. Kindly use account {acct}, sort code {sort} for invoice {inv} and all future payments. Our phones are being upgraded this week, so please reply by email only. Best regards, Accounts Team, {vendor}",
    "Subject: Shared with you: Q{q} bonus allocations — {fullname} has shared a spreadsheet with you on {cloud}. To open it, sign in with your work email and password: {cloud_url}",
    "Subject: New sign-in to your {store} account — We noticed a sign-in from a new device. If this was you, you can ignore this message. If not, please confirm your account details here so we can secure your account: {store_url}",
    "Subject: Password reset request — Hi {first}, we received a request to reset your {work} password. If you didn't make this request, please sign in here to cancel it: {work_url}",
    "Subject: Your parcel is on its way — Hi {first}, your {courier} parcel {tracking} is scheduled for delivery {future_day}. A small delivery-protection fee of {fee} applies, which you can pay securely here: {courier_url}",
    "Subject: Benefits enrollment closes {weekday} — Hi team, please review your selections and confirm your employee ID and {work} password on the new benefits portal: {work_url} Thanks, HR",
    "{bank}: for your security, we've placed a temporary hold on a {amount} transaction. A member of our team will call you shortly; please have the one-time passcode we text you ready so we can confirm it's you.",
    "Subject: Thank you for your payment — Your {stream} membership has renewed for {sub_price}. If you did not authorize this charge, you can request a refund by signing in at {stream_url}",
    "Hi {first}, this is {sender} from the IT service desk. We're migrating everyone's mailbox to {work} tonight. To avoid losing any email, please reply with your username and current password so we can move your account.",
    "Subject: Your {pay} receipt — You sent {amount} to {merchant}. Didn't make this purchase? Review the transaction by signing in here: {pay_url}",
]


# ── Brand expansion ───────────────────────────────────────────────────────

_BRAND_RE = re.compile(r"\{(=?)(" + "|".join(BRANDS) + r")(_url|_stem)?\}")
_COPIES = 36  # every template contributes this many entries (36 is divisible by 1, 2, 3, 4, 6, 9, 12)


def _expand(patterns: list[str]) -> list[str]:
    out: list[str] = []
    for pattern in patterns:
        cats = sorted({m.group(2) for m in _BRAND_RE.finditer(pattern)})
        variants: list[str] = []
        for combo in itertools.product(*(range(len(BRANDS[c])) for c in cats)):
            pick = dict(zip(cats, combo))

            def repl(m: re.Match, pick=pick) -> str:
                cat, suffix = m.group(2), m.group(3) or ""
                name, stem = BRANDS[cat][pick[cat]]
                if suffix == "_url":
                    return "{url__%s__%d}" % (cat, pick[cat])
                if suffix == "_stem":
                    return stem
                return name

            variants.append(_BRAND_RE.sub(repl, pattern))
        out.extend(variants[i % len(variants)] for i in range(_COPIES))
    return out


PATTERNS = {
    "legitimate": (LEGITIMATE, LEGITIMATE_HARD),
    "spam": (SPAM, SPAM_HARD),
    "phishing": (PHISHING, PHISHING_HARD),
}
TEMPLATES = {label: _expand(core) for label, (core, _) in PATTERNS.items()}
HARD = {label: _expand(hard) for label, (_, hard) in PATTERNS.items()}

ROWS_PER_LABEL = 400


def generate(rng: random.Random) -> list[dict]:
    return merge(
        *(
            label_items(
                rng,
                label,
                ROWS_PER_LABEL,
                TEMPLATES[label],
                SLOTS,
                hard_templates=HARD[label],
                hard_share=0.2,
            )
            for label in ("legitimate", "spam", "phishing")
        )
    )
