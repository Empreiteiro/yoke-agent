"""Agent tool routing — requests a user sends to an AI agent with eight tools.

The agent must call exactly one tool (or ``no_tool``). Hard rows borrow
vocabulary from a neighbouring tool — "search" in a weather request,
numbers in an email, a CSV that came from the CRM — while the tool that
actually fits stays unambiguous under the rules written into ``LABELS``.
"""

from __future__ import annotations

import random

from ._common import FIRST_NAMES, MONTHS, WEEKDAYS, amount, clock_time, integer, label_items, merge, order_id

SLUG = "tool_routing"
NAME = "Agent Tool Routing"
DESCRIPTION = (
    "1,200 synthetic requests to an AI agent, each labeled with the single tool it should call: "
    "web_search, calculator, calendar, send_email, weather, database_query, code_execution, or "
    "no_tool for requests answerable directly."
)
LANGUAGE = "en"
TASK = "Which tool should the agent call to handle this request?"

LABELS = [
    {
        "name": "web_search",
        "description": (
            "Searches the public internet for fresh or external information: news and current events, "
            "live prices and exchange rates, sports results, recent releases and versions, facts that "
            "change over time (current office-holders, statistics), and finding websites, businesses, "
            "documentation or reviews. Weather requests use weather; the company's own records use "
            "database_query; stable textbook facts need no_tool."
        ),
    },
    {
        "name": "calculator",
        "description": (
            "Evaluates math on numbers the user supplies: arithmetic, percentages, tips, discounts, "
            "averages, interest or loan formulas, and unit conversions with fixed factors (miles/km, "
            "°F/°C, hours/minutes). Applies whenever every input number is in the message; conversions "
            "that need live rates are web_search, totals over company records are database_query, and "
            "running user-supplied code is code_execution."
        ),
    },
    {
        "name": "calendar",
        "description": (
            "Reads and edits the user's own calendar: create, schedule, move, extend, cancel, decline "
            "or list meetings and events, and check free/busy time. If the user only wants people "
            "notified by email or message, that is send_email."
        ),
    },
    {
        "name": "send_email",
        "description": (
            "Composes and sends an email or message to a specific recipient on the user's behalf, "
            "including replies and forwards. Applies whenever something should be sent or someone "
            "notified, even if the content mentions meetings, numbers or code; writing a draft or "
            "template the user will send themselves is no_tool."
        ),
    },
    {
        "name": "weather",
        "description": (
            "Returns current conditions or forecasts — temperature, rain, snow, wind, humidity, UV, "
            "storms — for a place and time, even when the user says 'search' or 'look up'. Converting a "
            "temperature value the user already gives is calculator; writing about weather is no_tool."
        ),
    },
    {
        "name": "database_query",
        "description": (
            "Queries the company's internal database/CRM: customers and contacts, orders and their "
            "status, invoices and amounts owed, inventory and stock levels, returns, sales figures and "
            "reps — including counts, totals and averages computed over those records. Data in a file "
            "the user uploads or attaches is code_execution."
        ),
    },
    {
        "name": "code_execution",
        "description": (
            "Runs code in a sandbox: executes or tests a snippet or script the user provides, or writes "
            "and runs code to analyze, plot or transform an uploaded/attached file (CSV, JSON, SQLite) or "
            "to run a simulation. Wins over calculator when the user supplies code to run; only "
            "explaining code or a programming concept is no_tool."
        ),
    },
    {
        "name": "no_tool",
        "description": (
            "No tool is needed and the agent answers directly: chit-chat and thanks, opinions and "
            "advice, creative writing (poems, jokes, names), rewriting or translating text the user "
            "provides, drafting templates the user will send themselves, and explaining stable general "
            "knowledge or concepts. Anything needing fresh data, a computation, the user's calendar or "
            "mailbox, company records or running code needs a tool."
        ),
    },
]

# ── Slot generators ─────────────────────────────────────────────────────


def _choice(values: list) -> callable:
    def _gen(rng: random.Random) -> str:
        return str(rng.choice(values))

    return _gen


def _money_big(rng: random.Random) -> str:
    return f"${rng.randrange(2000, 900000, 500):,}"


def _price(rng: random.Random) -> str:
    return amount(rng, 5, 600)


def _decimal(low: float, high: float, places: int = 1) -> callable:
    def _gen(rng: random.Random) -> str:
        value = round(rng.uniform(low, high), places)
        return f"{value:g}" if value == int(value) else f"{value:.{places}f}"

    return _gen


def _inc_pair(rng: random.Random) -> str:
    a = rng.randint(20, 5000)
    b = a + rng.randint(1, a)
    return f"from {a} to {b}"


def _stock_pair(rng: random.Random) -> str:
    a = rng.uniform(5, 400)
    b = a * rng.uniform(0.6, 1.6)
    return f"from ${a:.2f} to ${b:.2f}"


def _cal_date(rng: random.Random) -> str:
    style = rng.randint(0, 2)
    if style == 0:
        return f"{rng.choice(MONTHS)} {rng.randint(1, 28)}"
    if style == 1:
        return f"next {rng.choice(WEEKDAYS)}"
    return f"the {rng.randint(4, 20)}th"


def _invoice(rng: random.Random) -> str:
    return f"INV-{rng.randint(1000, 99999)}"


def _sku(rng: random.Random) -> str:
    return f"SKU-{rng.randint(1000, 9999)}"


def _cust_id(rng: random.Random) -> str:
    return f"C-{rng.randint(10000, 99999)}"


_CSV_COLUMNS = {
    "sales_2025.csv": ["revenue", "units_sold", "discount"],
    "survey_results.csv": ["age", "satisfaction_score"],
    "website_traffic.csv": ["session_duration", "page_views"],
    "temperatures.csv": ["max_temp", "rainfall_mm"],
    "customer_churn.csv": ["tenure_months", "monthly_charges"],
    "ad_spend.csv": ["spend", "clicks", "conversions"],
    "orders.csv": ["order_total", "quantity"],
    "housing_prices.csv": ["sale_price", "square_feet"],
}


def _csv_col(rng: random.Random) -> str:
    file = rng.choice(sorted(_CSV_COLUMNS))
    return f"{rng.choice(_CSV_COLUMNS[file])} column of the {file} file"


def _reg_spec(rng: random.Random) -> str:
    file = rng.choice(sorted(_CSV_COLUMNS))
    return f"{file} with {_CSV_COLUMNS[file][0]} as the target"


def _eur(rng: random.Random) -> str:
    return f"{rng.choice([20, 50, 75, 100, 150, 200, 250, 300, 500, 750, 1000, 1200, 2500, 5000]):,}"


CODE = [
    "`print(sorted([5, 3, 9, 1, 7]))`",
    "`x = [i**2 for i in range(10)]; print(sum(x))`",
    "`import math; print(math.factorial(15))`",
    "`print('racecar'[::-1] == 'racecar')`",
    "`for i in range(3): print(i * 7)`",
    "`print(len(set('mississippi')))`",
    "`print(list(zip('abc', [1, 2, 3])))`",
    "`console.log([1, 2, 3].map(x => x * 2))`",
    "`print(round(sum([0.1] * 10), 2))`",
    "`import statistics; print(statistics.median([3, 8, 1, 9, 4]))`",
    "`print(sum(1 for c in 'banana' if c == 'a'))`",
    "`nums = [4, 8, 15, 16, 23, 42]; print(max(nums) - min(nums))`",
    "`print(' '.join(reversed('hello world'.split())))`",
    "`import datetime; print(datetime.date(2024, 2, 29) + datetime.timedelta(days=365))`",
    "`print([n for n in range(2, 30) if all(n % d for d in range(2, n))])`",
    "`s = 'Hello'; print(s.upper(), s.lower(), len(s))`",
    "`print(sum(int(d) for d in str(2 ** 100)))`",
    "`words = 'the quick brown fox'.split(); print(max(words, key=len))`",
    "`print(sorted({'b': 2, 'a': 1}.items()))`",
    "`import random; random.seed(42); print(random.sample(range(100), 5))`",
    "`print(int('ff', 16), bin(10), oct(64))`",
    "`print(list(map(str.title, ['alice', 'bob'])))`",
    "`from collections import Counter; print(Counter('abracadabra').most_common(2))`",
    "`print([x for x in range(50) if x % 7 == 3])`",
]
FUNCS = [
    "`def is_prime(n): return n > 1 and all(n % d for d in range(2, int(n**0.5) + 1))`",
    "`def slugify(s): return s.lower().strip().replace(' ', '-')`",
    "`def fizzbuzz(n): return 'Fizz' * (n % 3 == 0) + 'Buzz' * (n % 5 == 0) or str(n)`",
    "`def flatten(xs): return [y for x in xs for y in x]`",
    "`def median(xs): xs = sorted(xs); return xs[len(xs) // 2]`",
    "`def word_count(s): return len(s.split())`",
    "`const isEven = n => n % 2 === 0;`",
    "`def clamp(x, lo, hi): return max(lo, min(x, hi))`",
    "`def chunk(xs, n): return [xs[i:i + n] for i in range(0, len(xs), n)]`",
    "`def is_palindrome(s): return s == s[::-1]`",
    "`def gcd(a, b): return a if b == 0 else gcd(b, a % b)`",
    "`def celsius(f): return (f - 32) * 5 / 9`",
]
BUGGY = [
    "`print(undefined_var + 1)`",
    "`nums = [1, 2, 3]; print(nums[3])`",
    "`d = dict(a=1); print(d['b'])`",
    "`print('total: ' + 5)`",
    "`int('12a')`",
    "`for i in range(5) print(i)`",
    "`def add(a, b): return a + b; print(add(1))`",
    "`import numpyy as np`",
    "`x = None; print(x.upper())`",
    "`print(10 / 0)`",
    "`while True print('hi')`",
    "`s = 'abc'; s[0] = 'z'`",
]
JS = [
    "`console.log(typeof null)`",
    "`console.log([10, 1, 3].sort())`",
    "`console.log(0.1 + 0.2)`",
    "`console.log('5' * '2')`",
    "`console.log([...'hello'].reverse().join(''))`",
    "`console.log([] + {})`",
    "`console.log(parseInt('08abc'))`",
    "`console.log(new Date(0).toISOString())`",
    "`console.log('abc'.padStart(6, '*'))`",
    "`console.log(Math.max(...[3, 9, 2]))`",
]
BASH = [
    "`ls -la | wc -l`",
    "`python3 --version`",
    "`sort data.txt | uniq -c`",
    "`du -sh *`",
    "`grep -c ERROR app.log`",
    "`wc -l *.csv`",
    "`head -n 5 report.txt`",
    "`find . -name '*.py' | wc -l`",
    "`date -u`",
    "`env | sort | head`",
]
SQL = [
    "`SELECT country, COUNT(*) FROM customers GROUP BY country;`",
    "`SELECT * FROM orders WHERE total > 100 LIMIT 10;`",
    "`SELECT AVG(price) FROM products;`",
    "`SELECT name FROM users ORDER BY created_at DESC LIMIT 5;`",
    "`SELECT status, COUNT(*) FROM tickets GROUP BY status;`",
    "`SELECT * FROM events WHERE created_at > '2025-01-01';`",
]

SLOTS = {
    # people, companies, places
    "person": FIRST_NAMES,
    "person2": FIRST_NAMES,
    "company": [
        "Acme Corp", "Brightline Logistics", "Fernwood Supply", "Halcyon Labs", "Redwood Dynamics",
        "Bluefin Retail", "Orchid Health", "Summit Outdoor Co", "Tidewater Foods", "Vantage Motors",
        "Northwind Traders", "Silverleaf Hotels", "Quantum Paper Co", "Ironbridge Construction",
        "Pinewood Pharmacy", "Cobalt Systems", "Maplewood Bakeries", "Crestline Energy",
        "Harborpoint Shipping", "Granite Peak Software", "Lakeshore Clinics", "Starling Apparel",
        "Westfield Auto Parts", "Juniper Hospitality",
    ],
    "public_co": [
        "Halcyon Motors", "Vertex Airlines", "Novaterra Energy", "Lumio Phones", "Skyreach Telecom",
        "Orbitline Media", "Brightwave Robotics", "Solace Pharmaceuticals", "Meridian Foods", "Atlas Freight",
        "Corvid Games", "Nimbus Semiconductors",
    ],
    "city": [
        "Chicago", "London", "Tokyo", "Paris", "Seattle", "Denver", "Austin", "Boston", "Miami", "Toronto",
        "Berlin", "Sydney", "Madrid", "Mumbai", "Cape Town", "Oslo", "Dublin", "Lisbon", "Phoenix",
        "San Francisco", "Vancouver", "Rome", "Singapore", "Mexico City", "Nairobi", "Seoul", "Atlanta",
    ],
    "url_city": ["oslo", "lisbon", "denver", "tokyo", "chicago", "nairobi", "dublin"],
    "country": ["Brazil", "Japan", "Germany", "India", "Nigeria", "Canada", "Indonesia", "Mexico", "Vietnam", "Poland"],
    "country_cap": ["Australia", "Canada", "Kenya", "Peru", "Norway", "Vietnam", "Portugal", "Egypt", "Chile", "Austria"],
    "state": [
        "Texas", "Ohio", "California", "Florida", "Oregon", "New York", "Colorado", "Georgia", "Washington",
        "Arizona", "Illinois", "Michigan", "Nevada", "Virginia", "Massachusetts",
    ],
    "region": [
        "EMEA", "the West region", "North America", "APAC", "the Northeast", "Latin America", "the Midwest",
        "the Southeast", "Canada", "the UK", "Southern Europe",
    ],
    "warehouse": [
        "Denver", "Reno", "Atlanta", "Newark", "Columbus", "Dallas", "Memphis", "Phoenix", "Portland",
        "Louisville", "Charlotte",
    ],
    # time
    "when": ["tomorrow", "this weekend", "on Friday", "tonight", "next week", "on Saturday", "tomorrow morning", "this afternoon", "on Monday"],
    "when_cal": [
        "tomorrow", "on Friday", "next Tuesday", "on Monday", "this Thursday", "next Wednesday", "on the 14th",
        "the day after tomorrow", "next Monday", "this Friday", "on the 21st", "next Thursday",
        "this afternoon", "later today",
    ],
    "weekday": WEEKDAYS[:5],
    "date": _cal_date,
    "time": clock_time,
    "period": [
        "last month", "this month", "last quarter", "in Q3", "in Q2", "this year", "last week", "in September",
        "since January", "so far this year", "in 2025", "yesterday", "over the last 30 days",
        "in the first half of the year", "during the holiday sale",
    ],
    "mins": _choice([5, 10, 15, 20, 30]),
    # calendar
    "event_type": [
        "team standup", "1:1 with {person}", "design review", "sprint planning", "dentist appointment",
        "client call", "lunch with {person}", "all-hands", "interview", "budget review",
    ],
    "event_plain": [
        "standup", "design review", "sprint planning", "client call", "all-hands", "budget review", "retro",
        "product sync", "quarterly review", "onboarding session", "vendor call", "team lunch", "board prep",
    ],
    "dur": ["30-minute", "45-minute", "one-hour", "15-minute", "two-hour", "90-minute"],
    "dur_phrase": ["an hour", "two hours", "30 minutes", "the whole morning", "90 minutes"],
    "topic_work": ["the Q3 roadmap", "the hiring plan", "the budget", "the launch checklist", "the onboarding docs", "the vendor contract"],
    "personal_event": [
        "my mom's birthday dinner", "a dentist appointment", "the parent-teacher conference", "a haircut",
        "yoga class", "my flight to {city}", "a vet appointment for the dog", "date night",
    ],
    "event_name": ["Product Demo", "Quarterly Review", "Team Offsite", "Hackathon Kickoff", "Board Prep", "Customer Workshop"],
    "room": ["Conference Room B", "the 3rd floor huddle room", "Zoom", "the Oak room", "the cafe downstairs"],
    "conference": [
        "DevSummit", "DataWorld", "CloudConf", "UX Forward", "RetailTech Expo", "AI Frontiers", "SecureCon",
        "FinTech Week", "GreenBuild Summit", "MobileDev Days",
    ],
    # email
    "team": [
        "marketing", "engineering", "sales", "design", "finance", "support", "product", "legal", "operations",
        "HR", "data", "customer success",
    ],
    "doc": [
        "Q3 deck", "project proposal", "onboarding guide", "meeting notes", "design mockups",
        "signed contract", "budget spreadsheet", "release notes", "travel itinerary", "Q4 forecast",
        "user research summary", "contract draft",
    ],
    "message_content": [
        "the report will be ready by Friday", "I'm running late today", "the launch moved to next week",
        "we need the signed contract back", "the offsite is confirmed", "the demo went great",
        "I'll cover the support shift on Saturday",
    ],
    "short_msg": [
        "running 10 minutes late", "can we push to 4?", "great job today", "call me when you're free",
        "the files are in the shared drive", "happy Friday, see you Monday",
    ],
    "thanks_reason": ["the interview", "covering my shift", "the referral", "their help on the launch", "dinner last night", "the quick turnaround"],
    "request_item": ["the updated invoice", "their availability next week", "the slides from yesterday", "feedback on the draft", "a copy of the lease"],
    "status_update": ["the shipment went out today", "the bug is fixed", "I'll be out sick today", "the contract is signed", "the website is back up"],
    "subject": ["Project update", "Quick question", "Follow-up", "Invoice", "Schedule change", "Thank you"],
    "email_addr": lambda r: f"{r.choice(FIRST_NAMES).lower()}@{r.choice(['acme.test', 'fernwood.test', 'halcyonlabs.test', 'example.org'])}",
    "complaint": ["a late delivery", "a damaged package", "a double charge", "a broken login page", "slow support replies"],
    "achievement": ["the product launch", "closing the deal", "winning the hackathon", "their promotions", "finishing the marathon", "the conference talk"],
    "appliance": [
        "dishwasher", "heater", "fridge", "washing machine", "front door lock", "oven", "air conditioner",
        "garbage disposal", "bathroom fan", "water heater", "garage door",
    ],
    # database
    "order": order_id,
    "inv": _invoice,
    "sku": _sku,
    "cust_id": _cust_id,
    "product_name": [
        "the blue hiking backpack", "AA batteries", "the standing desk frame", "ceramic coffee mugs",
        "the X200 wireless mouse", "organic oat milk", "the large dog bed", "USB-C chargers",
        "the trail running shoes", "the 4K monitor", "the stainless water bottle", "bamboo cutting boards",
        "the kids' rain jacket", "the ergonomic office chair",
    ],
    # code
    "code": CODE,
    "func": FUNCS,
    "buggy": BUGGY,
    "js": JS,
    "bash": BASH,
    "sql": SQL,
    "csv_file": sorted(_CSV_COLUMNS),
    "crm_export": [
        "orders.csv", "customers_export.csv", "crm_dump.csv", "q3_deals.csv", "accounts_2025.csv",
        "pipeline_export.csv", "invoices_dump.csv", "leads.csv",
    ],
    "db_file": [
        "app.db", "sales.sqlite", "test_data.db", "inventory.sqlite", "users.db", "analytics.sqlite",
        "orders_backup.db",
    ],
    "csv_col": _csv_col,
    "reg_spec": _reg_spec,
    "group_by": ["month", "region", "week", "category", "country"],
    "date_str": lambda r: f"{r.randint(1, 31):02d}/{r.randint(1, 13):02d}/{r.randint(2019, 2027)}",
    # calculator numbers
    "pct": _choice([5, 7.5, 8, 10, 12, 12.5, 15, 18, 20, 22, 25, 30, 33, 35, 40, 45, 60, 75]),
    "tip": _choice([10, 12, 15, 18, 20, 22, 25]),
    "tax": _choice([5, 6, 6.25, 7, 7.5, 8, 8.875, 9.5, 10, 13, 20]),
    "num": integer(10, 5000),
    "a": integer(12, 9999),
    "b": integer(3, 999),
    "c": integer(2, 500),
    "d": integer(2, 500),
    "big": integer(500, 99999),
    "small": integer(3, 97),
    "sq": integer(2, 10000),
    "base": integer(2, 25),
    "p": integer(2, 12),
    "n": integer(2, 400),
    "n_people": integer(2, 12),
    "n_meet": integer(3, 25),
    "n_items": integer(2, 40),
    "k": integer(3, 10),
    "range_end": integer(11, 1001),
    "miles": _decimal(1, 900),
    "km": _decimal(1, 900),
    "kg": _decimal(0.5, 250),
    "gal": _decimal(1, 80),
    "mph": integer(25, 75),
    "temp": integer(-15, 110),
    "w": integer(6, 40),
    "l": integer(6, 60),
    "h": integer(1, 5),
    "m": integer(5, 55),
    "years": integer(2, 30),
    "rate": _choice([2.5, 3, 3.25, 3.75, 4, 4.5, 5, 5.5, 6, 6.25, 6.9, 7, 7.5, 8, 9.9]),
    "bill": lambda r: amount(r, 18, 450),
    "price": _price,
    "ship": lambda r: amount(r, 3, 40),
    "money": _money_big,
    "money2": _money_big,
    "inc_pair": _inc_pair,
    "stock_pair": _stock_pair,
    "eur": _eur,
    # web
    "news_topic": [
        "the Mars sample return mission", "the new EU AI rules", "the national rail strike",
        "the wildfires in California", "the central bank's interest rate decision", "the World Cup qualifiers",
        "the latest climate summit", "the {public_co} merger talks", "the port workers' strike",
        "the new data privacy law", "the bird flu outbreak", "the record heatwave in Europe",
        "the housing market slowdown", "the upcoming Olympics",
    ],
    "sport_event": [
        "the Formula 1 race this weekend", "last night's Champions League match", "the US Open final",
        "the {city} marathon", "yesterday's cricket test match", "the Tour de France stage today",
    ],
    "org_site": ["the {city} public library", "the passport office in {city}", "the {city} zoo", "the {city} transit authority"],
    "product": [
        "the Aurora X2 electric scooter", "the Nimbus 5 headphones", "the TerraBook 14 laptop",
        "the Lumio Fold phone", "the Kestrel air fryer", "the Halo smart thermostat", "the Vireo e-bike",
        "the Quill 3 tablet", "the Basalt hiking boots", "the Orbit robot vacuum",
        "the Cascade espresso machine", "the Zephyr gaming mouse",
    ],
    "asset": [
        "bitcoin", "gold", "Brent crude", "ethereum", "silver", "the S&P 500", "copper", "natural gas",
        "the Nasdaq", "the euro", "platinum",
    ],
    "place_attr": [
        "the science museum", "the botanical garden", "the city aquarium", "the history museum",
        "the public pool", "the art museum", "the planetarium", "the zoo", "the ice rink",
        "the farmers market",
    ],
    "research_topic": [
        "solid-state batteries", "CRISPR therapies", "microplastics in drinking water", "four-day work weeks",
        "fusion energy startups", "Alzheimer's drug trials", "lab-grown meat", "perovskite solar cells",
        "ocean carbon capture", "AI chip shortages", "long COVID treatments", "quantum error correction",
    ],
    "software": [
        "Python", "Node.js", "PostgreSQL", "Kubernetes", "React", "Rust", "Django", "TypeScript", "Go",
        "Docker", "Terraform", "Next.js", "MySQL", "Redis",
    ],
    "service": [
        "StreamPlus", "Nimbus Cloud", "Skyreach Telecom's network", "the PayLink app", "TuneBox",
        "the CityRail booking site", "MailHarbor", "PhotoNest", "the Lumio app store", "QuickMeet video calls",
    ],
    "cuisine": [
        "Thai", "ramen", "vegan", "Ethiopian", "tapas", "sushi", "Lebanese", "Korean barbecue", "Mexican",
        "Indian", "Greek", "Peruvian",
    ],
    "store": [
        "ShopNest", "MegaBuy Online", "Urban Threads", "HomeHaven Decor", "GadgetHub", "PetPals Store",
        "SneakerVault", "KitchenCraft",
    ],
    "election": ["the upcoming mayoral race in {city}", "the next national election", "the governor's race in {state}"],
    "upcoming": [
        "the next Kestrel game console", "season three of 'Starfall'", "the Lumio Fold 2", "the new TerraBook",
        "the Quill 4 tablet", "the next 'Ironclad' movie", "the Vireo e-bike 2", "the new Corvid Games RPG",
        "the Basalt trail shoe", "Lumio's new smartwatch",
    ],
    "headline_area": [
        "technology", "climate policy", "the economy", "space exploration", "healthcare", "the housing market",
        "sports", "artificial intelligence", "energy prices", "education", "elections", "travel",
    ],
    "service_biz": [
        "24-hour locksmith", "late-night vet", "plumber open on Sundays", "bike repair shop",
        "24-hour pharmacy", "tire shop", "notary public", "dog groomer", "tailor",
    ],
    "nobel_field": ["Physics", "Chemistry", "Medicine", "Literature", "Economics"],
    "lib_func": [
        "pandas' merge function", "NumPy's linspace", "lodash's debounce", "the requests Session object",
        "React's useEffect hook", "pandas' groupby", "Python's asyncio.gather", "the Express router",
        "NumPy's einsum", "Django's QuerySet.annotate",
    ],
    # no_tool
    "haiku_topic": [
        "autumn leaves", "morning coffee", "the ocean", "a sleepy cat", "city lights", "starting a new job",
        "Mondays", "the first snow", "a quiet library", "summer thunder", "an empty train station",
        "fresh bread", "a long weekend", "old friends", "the night sky",
    ],
    "concept_pair": [
        "a virus and a bacterium", "affect and effect", "a simile and a metaphor", "RAM and storage",
        "a crocodile and an alligator", "TCP and UDP", "baking soda and baking powder", "empathy and sympathy",
        "latitude and longitude", "a comet and an asteroid", "a democracy and a republic", "who and whom",
        "an LLC and a corporation", "mitosis and meiosis", "a stock and a bond", "machine learning and AI",
    ],
    "joke_topic": [
        "programmers", "cats", "coffee", "penguins", "accountants", "pirates", "dentists", "dinosaurs",
        "librarians", "astronauts", "dad jokes about cheese", "chemists", "teachers", "Mondays",
    ],
    "opinion_topic": [
        "pineapple on pizza", "remote work", "e-books versus paper books", "learning Latin", "standing desks",
        "open-plan offices", "four-day work weeks", "electric cars", "learning a second language as an adult",
        "cold showers", "tabs versus spaces", "reality TV", "living in a big city",
    ],
    "pet": [
        "golden retriever", "black cat", "parrot", "hamster", "goldfish", "rescue greyhound", "bearded dragon",
        "corgi puppy", "pair of guinea pigs", "tabby kitten", "rabbit", "betta fish", "husky",
    ],
    "book": [
        "Pride and Prejudice", "Moby-Dick", "The Odyssey", "Hamlet", "Frankenstein", "Don Quixote",
        "Jane Eyre", "The Great Gatsby", "War and Peace", "Wuthering Heights", "Les Misérables",
        "The Divine Comedy", "Dracula", "Great Expectations",
    ],
    "phrase": [
        "good morning, how are you?", "where is the train station?", "thank you very much", "I love this city",
        "can I have the check, please?", "how much does this cost?", "nice to meet you",
        "I'm allergic to peanuts", "see you tomorrow", "where is the nearest pharmacy?", "happy birthday",
    ],
    "language": [
        "Spanish", "French", "German", "Italian", "Portuguese", "Japanese", "Dutch", "Korean", "Swedish",
        "Polish", "Greek", "Turkish", "Hindi",
    ],
    "sentence": [
        "we need this done asap or else", "pls send me the file", "your idea is kinda bad",
        "i cant make it to the thing tomorrow", "this is the third time I'm asking",
        "fix this now its broken again", "i think ur wrong about the numbers", "send it whenever lol",
        "we messed up the order, sorry", "dont forget the meeting", "can u call me back",
    ],
    "concept": [
        "photosynthesis", "a hash table", "public-key encryption", "a refrigerator", "the immune system",
        "a blockchain", "garbage collection in Java", "the electoral college", "the water cycle", "inflation",
        "a jet engine", "DNS", "supply and demand", "plate tectonics", "an electric motor",
        "the placebo effect",
    ],
    "skill": [
        "guitar", "chess", "watercolor painting", "Spanish", "public speaking", "Python", "rock climbing",
        "piano", "knitting", "photography", "Japanese", "woodworking", "salsa dancing", "baking bread",
    ],
    "animal": [
        "octopuses", "honeybees", "sloths", "flamingos", "owls", "axolotls", "crows", "elephants", "penguins",
        "jellyfish", "hummingbirds", "tardigrades", "red pandas",
    ],
    "word": [
        "serendipity", "ephemeral", "ubiquitous", "sonder", "petrichor", "laconic", "quixotic", "hiraeth",
        "melancholy", "pragmatic", "zeitgeist", "ennui", "sanguine",
    ],
    "game": [
        "chess", "poker", "cricket", "mahjong", "bridge", "rugby", "backgammon", "go", "baseball", "bowling",
        "dominoes", "volleyball", "curling", "checkers",
    ],
    "blog_topic": [
        "minimalist living", "learning to code at 40", "my first marathon", "sourdough baking",
        "remote work burnout", "urban gardening", "budget travel in Europe", "raising twins",
        "switching careers into UX", "my year without social media", "home espresso",
    ],
    "mood": [
        "a bit down", "stressed", "bored", "really tired", "nervous about my exam", "unmotivated", "homesick",
        "overwhelmed with work", "lonely", "a little anxious", "burned out",
    ],
    "fav_thing": [
        "movie", "season", "book", "color", "food", "board game", "holiday", "song", "city", "dessert",
        "time of day", "animal",
    ],
    "relation": [
        "mom", "dad", "best friend", "sister", "grandpa", "boss", "aunt", "brother", "coworker", "grandma",
        "neighbor", "husband", "wife",
    ],
    "weather_word": [
        "rainy", "snowy", "foggy", "stormy", "sunny", "windy", "humid", "drizzly", "frosty", "hazy", "breezy",
    ],
    "formula": [
        "compound interest", "the area of a circle", "standard deviation", "the Pythagorean theorem",
        "percent change", "the volume of a sphere", "simple interest", "BMI", "the slope of a line",
        "kinetic energy", "speed",
    ],
    "sql_concept": [
        "INNER JOIN", "LEFT JOIN", "GROUP BY", "index", "subquery", "foreign key", "HAVING clause", "UNION",
        "primary key", "window function", "transaction", "CROSS JOIN",
    ],
    "email_purpose": [
        "declining a job offer", "asking for a raise", "following up after an interview",
        "requesting a deadline extension", "resigning from my job", "asking my landlord to fix the heating",
        "introducing myself to a new team", "complaining about a late order", "thanking a mentor",
        "asking a professor for a recommendation",
    ],
    "why_q": [
        "the sky is blue", "leaves change color in autumn", "ice floats on water", "we have leap years",
        "the moon has phases", "the ocean is salty", "we get goosebumps", "cats purr", "bread rises",
        "the sea looks blue", "planes leave contrails",
    ],
    "wx_pair": [
        "weather and climate", "a hurricane and a typhoon", "humidity and dew point",
        "a weather watch and a weather warning", "a tornado and a cyclone", "sleet and hail",
        "a cold front and a warm front", "fog and mist",
    ],
    "meeting_kind": [
        "meeting", "standup", "brainstorming session", "1:1", "retrospective", "kickoff meeting",
        "board meeting", "all-hands", "client workshop", "planning session",
    ],
    "py_concept": [
        "list comprehension", "decorator", "generator", "lambda", "context manager", "dictionary", "tuple",
        "class", "f-string", "virtual environment", "set", "namedtuple",
    ],
    "biz_sys": [
        "a CRM system", "an ERP system", "a data warehouse", "an inventory management system", "a ticketing system",
        "a point-of-sale system", "an HR information system", "a payroll system", "a BI dashboard",
    ],
    "etiquette": [
        "decline a meeting invite without a note", "reply-all to a company-wide email",
        "send work emails at midnight", "reschedule the same meeting twice", "eat lunch during a video call",
        "leave a group chat without saying anything", "mute myself for an entire meeting",
        "use emojis in work emails", "join a call five minutes late", "forward an email without asking",
    ],
}

PREFIXES = [
    "Hey,", "Hi,", "Quick one:", "Hey assistant,", "Can you help me?", "Hello,", "Question:", "Hi there,",
    "Okay,", "Please help:", "Morning,",
]
SUFFIXES = ["Thanks!", "Thanks.", "thx", "Appreciate it.", "Thank you.", "ty", "Cheers.", "No rush."]
CHAT_PREFIXES = ["Hey,", "Hi,", "Hello,", "Okay,", "Hi there,"]
CHAT_SUFFIXES = ["Thanks!", "Thank you.", "Cheers.", "ty"]

# ── Templates ───────────────────────────────────────────────────────────

TEMPLATES = {
    "web_search": [
        "What's the latest news on {news_topic}?",
        "Who won {sport_event}?",
        "Find me the official website for {org_site}.",
        "Search the web for reviews of {product}.",
        "What's the current price of {asset}?",
        "Who is the current CEO of {public_co}?",
        "What are the opening hours for {place_attr} in {city} today?",
        "Are there any flight delays at {city} airport right now?",
        "What movies are playing in theaters in {city} this weekend?",
        "Find recent articles about {research_topic}.",
        "What's the newest stable version of {software}?",
        "Is {service} down right now? It's not loading for me.",
        "Search for the best-rated {cuisine} restaurants in {city}.",
        "Look up the current population of {country}.",
        "Find the return policy on {store}'s website.",
        "Who's leading the polls in {election}?",
        "What's {public_co}'s stock price today?",
        "When does {upcoming} come out?",
        "Give me a summary of today's top headlines about {headline_area}.",
        "Find the phone number for a {service_biz} in {city}.",
        "What's the current minimum wage in {state}?",
        "What's the latest public news about {public_co}?",
    ],
    "calculator": [
        "What's {pct}% of {num}?",
        "Calculate {a} times {b}.",
        "What's {a} + {b} + {c}?",
        "If I invest {money} at {rate}% interest compounded annually, how much will I have after {years} years?",
        "Convert {miles} miles to kilometers.",
        "How much should I tip on a {bill} bill at {tip}%?",
        "What's {big} divided by {small}?",
        "What's the square root of {sq}?",
        "{a} * {b} - {c} = ?",
        "Something costs {price} and it's {pct}% off. What's the sale price?",
        "How many seconds are there in {n} days?",
        "What's the monthly payment on a {money} loan at {rate}% over {years} years?",
        "Convert {kg} kg to pounds.",
        "What's the average of {a}, {b}, {c} and {d}?",
        "What percentage of {big} is {small}?",
        "How many liters is {gal} gallons?",
        "Split {bill} evenly between {n_people} people.",
        "What's {base} to the power of {p}?",
        "If I drive {miles} miles at {mph} mph, how long will it take?",
        "Add {tax}% sales tax to {price}.",
        "What's the percentage increase {inc_pair}?",
        "How many square feet is a room that's {w} by {l} feet?",
        "{big} / {small}, rounded to two decimals?",
        "Convert {km} km to miles.",
    ],
    "calendar": [
        "Schedule a meeting with {person} {when_cal} at {time}.",
        "What's on my calendar {when_cal}?",
        "Push my {time} meeting back by {mins} minutes.",
        "Cancel my {event_type} {when_cal}.",
        "Book a {dur} slot with {person} next week to go over {topic_work}.",
        "Do I have anything scheduled on {weekday} {daypart}?",
        "Add {personal_event} to my calendar for {date} at {time}.",
        "Set up a recurring weekly 1:1 with {person} on {weekday}s at {time}.",
        "Am I free {when_cal} at {time}?",
        "Reschedule the {client_event} with {company} to {weekday}.",
        "Block {dur_phrase} on my calendar {when_cal} for focus time.",
        "When is my next meeting{next_with}?",
        "Invite {person} and {person2} to the {event_plain} on {weekday}.",
        "Decline the {event_plain} invite for {weekday}.",
        "Show me all my meetings {span}.",
        "Create an event called '{event_name}' for {date} at {time}.",
        "Clear my calendar for {weekday} {daypart}.",
        "How many meetings do I have {when_cal}?",
        "Find a time {when_cal} when {person} and I are both free.",
        "Change the location of my {time} meeting to {room}.",
        "Remove {personal_event_def} from my calendar.",
        "Extend tomorrow's {event_plain} by {mins} minutes.",
        "Move my {event_type} from {weekday} to {weekday}.",
    ],
    "send_email": [
        "Send an email to {person} saying {message_content}.",
        "Draft and send a thank-you email to {person} for {thanks_reason}.",
        "Send {person} a message: '{short_msg}'",
        "Email the {team} team the link to the {doc}.",
        "Write and send a follow-up email to {company} about {topic_work}.",
        "Shoot {person} an email asking for {request_item}.",
        "Reply to {person}'s last email and tell them {message_content}.",
        "Send a message to {person} wishing them a happy birthday.",
        "Email {email_addr} with the subject '{subject}' and tell them {message_content}.",
        "Let {person} know by email that {status_update}.",
        "Can you email my landlord that the {appliance} is broken?",
        "Forward the {doc} to {person}.",
        "Send {person} a reminder email about the overdue {doc}.",
        "Message {person} on my behalf and ask if they can review the {doc} today.",
        "Compose an email to {company}'s support team complaining about {complaint} and send it.",
        "Send a quick note to {person}: {short_msg}",
        "Email {person} and {person2} to congratulate them on {achievement}.",
        "Send my apologies to {person} and tell them {apology}.",
        "Email the {team} team that {status_update}.",
        "Send {person} the {doc} as an attachment with a short note.",
    ],
    "weather": [
        "What's the weather like in {city} right now?",
        "Will it rain in {city} {when}?",
        "What's the forecast for {city} {when}?",
        "How hot is it going to get in {city} {when}?",
        "Is it snowing in {city} at the moment?",
        "Do I need a jacket in {city} {when}?",
        "What's the temperature in {city} right now?",
        "Give me the {ndays} forecast for {city}.",
        "How humid is it in {city} today?",
        "Any storms expected in {city} {when}?",
        "What's the chance of rain in {city} {when}?",
        "Is it going to be sunny in {city} {when}?",
        "What's the wind speed in {city} right now?",
        "How cold will it get tonight in {city}?",
        "weather {city} {when}",
        "Will it be warm enough for the beach in {city} {when}?",
        "Is there a heat or frost warning for {city} {when}?",
        "What's the UV index in {city} today?",
        "When is the rain supposed to stop in {city}?",
        "What are the high and low temperatures for {city} {when}?",
        "Is it going to be foggy in {city} tomorrow morning?",
    ],
    "database_query": [
        "How many orders did {company} place {period}?",
        "Look up the contact details for {company} in our CRM.",
        "What's the status of order {order}?",
        "Pull up invoice {inv}.",
        "How many units of {sku} do we have in stock?",
        "What were our total sales in {region} {period}?",
        "List all customers who signed up {period}.",
        "Which invoices are overdue for {company}?",
        "Who is the account manager for {company}?",
        "Show me the top {k} products by revenue {period}.",
        "Find all orders over {price} placed {period}.",
        "What's the shipping address on file for {company}?",
        "How many open support tickets does {company} have in our system?",
        "Check the stock level for {product_name} at the {warehouse} warehouse.",
        "What did {company} buy from us last quarter?",
        "Get me a list of customers in {state} with unpaid invoices.",
        "What's the lifetime value of {company} in our records?",
        "Which sales rep closed the most deals {period}?",
        "Is {company} marked as an active customer in the CRM?",
        "How many returns did we process {period}?",
        "Retrieve the purchase history for customer ID {cust_id}.",
        "Which SKUs are below their reorder level at the {warehouse} warehouse?",
    ],
    "code_execution": [
        "Run this Python snippet and tell me the output: {code}",
        "Execute this script and tell me if it throws an error: {buggy}",
        "I've uploaded a spreadsheet. Can you compute the average of the {csv_col}?",
        "Test this function with a few inputs and show me the results: {func}",
        "Plot the data in the attached {csv_file} as a line chart.",
        "Run this JavaScript and show me what it logs: {js}",
        "Load {csv_file} and tell me how many rows have missing values.",
        "Benchmark this function on a list of 100,000 random numbers: {func}",
        "Use pandas to group the uploaded {csv_file} by {group_by} and sum the totals.",
        "Run this shell command in the sandbox and show the output: {bash}",
        "Does this actually run without errors? {buggy}",
        "Parse the JSON file I attached and count how many objects have status '{status}'.",
        "Make a histogram of the {csv_col} I just uploaded.",
        "Run this and tell me what's wrong: {buggy}",
        "Simulate {sims} dice rolls with code and give me the distribution.",
        "Write a quick script to dedupe the emails in the attached {csv_file} and run it.",
        "Execute this cell and show me the result: {code}",
        "Run a linear regression on the uploaded {reg_spec}.",
        "Can you run this code a few times and see if the output changes? {code}",
        "Run a Monte Carlo simulation with {sims} trials to estimate pi and report the result.",
    ],
    "no_tool": [
        "Explain {eli5} like I'm five.",
        "Write a haiku about {haiku_topic}.",
        "What's the difference between {concept_pair}?",
        "Tell me a joke about {joke_topic}.",
        "How's your {day_unit} going so far?",
        "What do you think about {opinion_topic}?",
        "Give me some name ideas for my new {pet}.",
        "Can you summarize the plot of {book}?",
        "Translate '{phrase}' into {language}.",
        "What's the capital of {country_cap}?",
        "Help me rewrite this to sound more professional: '{sentence}'",
        "Explain how {concept} works.",
        "Write a short poem for my {relation}'s birthday.",
        "What's a good way to start learning {skill}?",
        "Who wrote {book}?",
        "Give me a fun fact about {animal}.",
        "Brainstorm some team-building ideas for a remote team that loves {skill}.",
        "What does the word '{word}' mean?",
        "I'm feeling {mood} today. Can you cheer me up?",
        "Write a limerick about a cat who loves {cat_love}.",
        "Explain the basic rules of {game}.",
        "Suggest a catchy title for my blog post about {blog_topic}.",
        "What's your favorite {fav_thing}, if you had to pick?",
        "Thanks, that helped a lot with my {study_thing}!",
    ],
}

HARD = {
    "web_search": [
        "How much is {eur} euros in US dollars at today's exchange rate?",
        "What's the current GDP of {country}?",
        "Find the website for the {conference} conference and its dates. Don't add anything to my calendar yet.",
        "Search online for the release notes of the latest {software} version and tell me what changed.",
        "I don't need our internal numbers. What's the public news about {public_co}'s latest earnings?",
        "Who won the Nobel Prize in {nobel_field} this year?",
        "Look up the official docs for {lib_func} online.",
        "Check the news: did {public_co} announce layoffs today?",
        "What are average 30-year mortgage rates in {state} this week?",
    ],
    "calculator": [
        "Our revenue was {money} in Q3 and {money2} in Q4. What's the growth percentage?",
        "Convert {temp} degrees Fahrenheit to Celsius.",
        "How many minutes is a {h}-hour {m}-minute meeting?",
        "I have {n_meet} meetings this week, {m} minutes each. How many hours is that in total?",
        "An order has {n_items} items at {price} each plus {ship} shipping. What's the total?",
        "I don't need any code, just the number: what's {a} squared plus {b} squared?",
        "No need to look anything up: if a stock goes {stock_pair}, what's the percent change?",
        "Our dashboard shows {a} orders last month and {b} this month. What's the percent change?",
    ],
    "calendar": [
        "Cancel my {time} with {company}. No need to email anyone, just take it off my calendar.",
        "Do I have any meetings with {company} this week?",
        "Move tomorrow's {event_plain} to {time}. The weather looks awful so we're going remote anyway.",
        "Add the {conference} conference to my calendar for {date}. I already looked up the dates online.",
        "Block {dur_phrase} on my calendar {when_cal} to review the Q3 sales numbers.",
        "Schedule a {dur} code review session with {person} {when_cal}.",
        "How much free time do I have on {weekday} between meetings?",
        "Put a reminder on my calendar {when_cal} at {time} to email {person} the contract.",
    ],
    "send_email": [
        "Email the team to let them know I'll be {mins} minutes late to the {time} meeting.",
        "Send {person} an email with these numbers: Q3 revenue {money}, Q4 revenue {money2}.",
        "Email {person} this snippet so they can test it on their machine: {code}",
        "Don't book anything yet, just email {person} and ask which day works for the {event_plain}.",
        "Email {company}'s account manager and ask them to resend invoice {inv}.",
        "Send a message to {person} saying the picnic {when} is moving indoors because of the rain.",
        "Reply to {person} and tell them the calculation is done: the total came to {money}.",
    ],
    "weather": [
        "Should we hold the team lunch outside in {city} {when}? Will it rain?",
        "Search the forecast for {city} {when} for me.",
        "My flight lands in {city} {when}. Any thunderstorms expected?",
        "Is it below freezing in {city} right now? Give me the temperature in Celsius.",
        "Before I email the team about the offsite, what's the weather going to be in {city} {when}?",
        "Don't put anything on my calendar, just tell me if it'll snow in {city} {when}.",
        "Look up how windy it'll be in {city} {when}, we're planning a sailing trip.",
        "Is it raining in {city} right now? I need to decide whether to cancel my run.",
    ],
    "database_query": [
        "Calculate the total value of all invoices for {company} {period}.",
        "Search our CRM for the email address of the buyer at {company}.",
        "What's the latest status on order {order}?",
        "What's the average order value for {company} {period}? Pull it from our database.",
        "Before I email {company}, look up how much they currently owe us.",
        "How many customers do we have in {city}?",
        "Do we have any orders scheduled to ship {when}?",
        "Not the public news, what were our own sales to {company} {period}?",
    ],
    "code_execution": [
        "Run this and tell me what it prints: `print(sum(range(1, {range_end})))`",
        "I've attached {crm_export} exported from our CRM. Use pandas to find the top {k} customers by revenue.",
        "Run this snippet that calls the weather API and show me the output: `requests.get('https://api.example-weather.test/v1/now?city={url_city}').json()`",
        "Execute this SQL against the attached {db_file} and show me the rows: {sql}",
        "Test whether my date parser handles '{date_str}' correctly: `datetime.strptime(s, '%d/%m/%Y')`",
        "Run this smtplib script against my local test server on port {port} and tell me if it errors: `smtplib.SMTP('localhost', {=port}).noop()`",
        "Don't just explain it, actually run this code and show me the result: {code}",
        "Use code to compute the standard deviation of the {csv_col} I attached.",
    ],
    "no_tool": [
        "Write a short poem about {weather_word} weather.",
        "What's the formula for {formula}? Just explain it, no numbers needed.",
        "How does a SQL {sql_concept} work, conceptually?",
        "Write me a template for an email {email_purpose}. I'll send it myself.",
        "No need to look anything up, just explain why {why_q}.",
        "Explain the difference between {wx_pair}.",
        "Give me a few tips for running a more productive {meeting_kind}.",
        "Explain what a {py_concept} is in Python. No need to run anything.",
        "What does {biz_sys} actually do, in general terms?",
        "Is it rude to {etiquette}? What do you think?",
    ],
}

SLOTS.update(
    {
        "ndays": ["3-day", "5-day", "7-day", "10-day", "weekend", "hourly"],
        "port": ["25", "1025", "2525", "8025", "587"],
        "next_with": ["", " with {person}", " with {company}", " with the {team} team", " today", " after lunch"],
        "span": ["this week", "next week", "for tomorrow", "for the rest of today", "on {weekday}", "this month", "with external guests this week"],
        "daypart": ["morning", "afternoon", "evening", "after 4pm", "before noon", "around lunch"],
        "status": ["failed", "pending", "error", "active", "cancelled", "timeout"],
        "eli5": [
            "recursion", "inflation", "gravity", "photosynthesis", "black holes", "machine learning", "the stock market",
            "how vaccines work", "electricity", "why we sleep",
        ],
        "day_unit": ["day", "week", "morning", "Monday", "weekend", "afternoon"],
        "client_event": ["quarterly review", "vendor call", "kickoff meeting", "contract review", "product demo", "check-in call"],
        "sims": [
            "1,000", "5,000", "10,000", "50,000", "100,000", "a million", "20,000", "250,000", "2 million",
            "500",
        ],
        "personal_event_def": [
            "the dentist appointment", "my haircut", "yoga class", "the parent-teacher conference", "date night",
            "my flight to {city}", "the vet appointment", "my mom's birthday dinner",
        ],
        "cat_love": [
            "lasagna", "cardboard boxes", "jazz", "the vacuum cleaner", "rainy days", "knitting", "sunbeams",
            "tuna sandwiches", "chasing laser pointers", "sitting on keyboards", "classical music",
        ],
        "study_thing": [
            "homework", "essay", "presentation", "exam prep", "cover letter", "lesson plan", "thesis",
            "job interview prep", "book report", "science project", "grant proposal",
        ],
        "apology": [
            "I can't make it tonight", "I missed their call earlier", "the delivery will be a day late",
            "I forgot to send the notes", "I double-booked us on Thursday",
        ],
    }
)

ROWS_PER_LABEL = 150
HARD_SHARE = 0.2


def generate(rng: random.Random) -> list[dict]:
    parts = []
    for label in LABELS:
        name = label["name"]
        chatty = name == "no_tool"
        parts.append(
            label_items(
                rng,
                name,
                ROWS_PER_LABEL,
                TEMPLATES[name],
                SLOTS,
                hard_templates=HARD[name],
                hard_share=HARD_SHARE,
                prefixes=CHAT_PREFIXES if chatty else PREFIXES,
                suffixes=CHAT_SUFFIXES if chatty else SUFFIXES,
                p_suffix=0.2 if chatty else 0.35,
            )
        )
    return merge(*parts)
