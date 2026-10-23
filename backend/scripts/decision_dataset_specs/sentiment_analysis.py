"""Product review sentiment: positive / negative / neutral / mixed.

Reviews are assembled from review *patterns* (the sentence skeletons that
carry the sentiment structure) and per-product-type *aspect phrases*. Every
product type (headphones, coffee maker, novel, ...) defines four aspects,
each with praise (``pos``), complaint (``neg``) and purely factual (``neu``)
phrases. Patterns reference ``{pos_a}`` / ``{neg_b}`` etc.; at import time
each pattern is expanded for every product type and every ordered pair of
*distinct* aspects, so a review can never praise and criticise the same
aspect (no "the battery lasts all week ... the battery dies in two hours").

Complaints in the ``neg`` pools are substantive but not catastrophic, which
keeps ``mixed`` rows balanced; catastrophic failures live in ``fail`` and
are only used by ``negative`` patterns.
"""

from __future__ import annotations

import random
import re

from ._common import amount, label_items, merge

SLUG = "sentiment_analysis"
NAME = "Product Review Sentiment"
DESCRIPTION = (
    "1,200 synthetic e-commerce product reviews (electronics, home, kitchen, apparel, books, "
    "beauty, toys, outdoor gear), 300 each labeled positive, negative, neutral or mixed, "
    "including sarcasm, negation and trivial-caveat hard cases."
)
LANGUAGE = "en"
TASK = "What is the overall sentiment of this product review?"

LABELS = [
    {
        "name": "positive",
        "description": (
            "The review is clearly favorable overall: it praises the product and contains no substantive "
            "complaint about it. Negated criticism ('not bad at all', 'can't complain', 'no complaints') "
            "counts as praise. A trivial caveat that the reviewer downplays and that concerns only shipping, "
            "delivery or outer packaging (e.g. 'the box arrived a little crushed') keeps the review positive; "
            "any complaint about the product itself makes it mixed instead."
        ),
    },
    {
        "name": "negative",
        "description": (
            "The review is clearly unfavorable overall: it reports defects, failures, poor quality or "
            "disappointment, including sarcastic 'praise' that actually describes a failure ('Great, it broke "
            "on day two.'). A token compliment that the reviewer dismisses or that concerns only shipping or "
            "packaging ('the packaging was nice, I'll give it that') does not make it mixed."
        ),
    },
    {
        "name": "neutral",
        "description": (
            "The review expresses no clear praise or complaint about the product: it states facts (features, "
            "specs, size, contents, delivery dates, who it was bought for) and/or gives an explicitly "
            "indifferent verdict ('it's fine', 'nothing special', 'not great, not terrible', 'too early to "
            "tell'). As soon as the reviewer explicitly judges an aspect of the product as good or bad, the "
            "review is not neutral."
        ),
    },
    {
        "name": "mixed",
        "description": (
            "The review contains at least one explicit, substantive praise and at least one explicit, "
            "substantive complaint about the product itself (function, quality, comfort, durability, value), "
            "given comparable weight, with no overall verdict that clearly settles on one side. A complaint "
            "about how the product performs counts as substantive even when framed as 'my only complaint' or "
            "'would be five stars if not for'; a complaint limited to shipping or packaging does not."
        ),
    },
]


# ── Product types ─────────────────────────────────────────────────────────
# Each type: items (noun phrases used as "this {item}"), price range,
# usage phrases ("after ..."), catastrophic failures, and four aspects with
# pos / neg / neu clauses (lowercase, no final period).

PRODUCTS: dict[str, dict] = {
    "audio": {
        "items": [
            "pair of noise-cancelling headphones", "gaming headset", "pair of Voltra over-ear headphones",
            "pair of wireless headphones", "Lumora headset", "pair of studio headphones",
        ],
        "price": (25, 260),
        "usage": [
            "after a month of daily commutes", "after two weeks of use", "after a few long flights",
            "after three months of gym sessions", "after a couple of weeks working from home",
        ],
        "fail": [
            "the left side went completely silent after {short_time}",
            "the right channel started crackling and then died within {short_time}",
            "the headband cracked at the hinge within {short_time}",
            "the microphone stopped working after {short_time}",
        ],
        "aspects": {
            "sound": {
                "pos": [
                    "the sound is rich and clear at every volume",
                    "the bass is punchy without drowning out vocals",
                    "the noise cancelling blocks out an entire train carriage",
                    "the sound is so detailed I'm hearing new things in old songs",
                ],
                "neg": [
                    "the sound is muddy and the highs are harsh",
                    "the noise cancelling barely blocks anything",
                    "there is a constant faint hiss during quiet passages",
                    "the bass is so boomy it buries the vocals",
                ],
                "neu": [
                    "there is an EQ setting in the companion app",
                    "it has two noise-cancelling modes",
                    "it uses 40 mm drivers",
                    "it has a transparency mode",
                ],
            },
            "battery": {
                "pos": [
                    "the battery easily lasts a full week of commutes",
                    "a ten-minute charge gives me a few hours of listening",
                    "the battery outlasts even my longest flights",
                ],
                "neg": [
                    "the battery barely lasts four hours",
                    "the battery drains even when switched off",
                    "the battery indicator jumps around and it dies without warning",
                ],
                "neu": [
                    "it charges over USB-C",
                    "a full charge takes about two hours",
                    "the battery is rated for thirty hours",
                    "it can be used with a cable when the battery is empty",
                ],
            },
            "comfort": {
                "pos": [
                    "the ear cushions stay comfortable even after hours of wear",
                    "the headband is so light I barely notice it",
                    "the ear cushions are soft and never get hot",
                ],
                "neg": [
                    "the ear cushions start to hurt after about an hour",
                    "the headband clamps far too tightly",
                    "the ear cushions get hot and sweaty within minutes",
                ],
                "neu": [
                    "the ear cushions are replaceable",
                    "it weighs about 250 grams",
                    "the headband adjusts in ten click positions",
                    "the ear cups fold flat for travel",
                ],
            },
            "connection": {
                "pos": [
                    "pairing took about five seconds",
                    "switching between my phone and laptop is seamless",
                    "the connection never drops, even across the house",
                ],
                "neg": [
                    "the connection drops every few minutes",
                    "the Bluetooth connection won't come back without re-pairing",
                    "the audio lags noticeably behind video",
                ],
                "neu": [
                    "it can pair with two devices at once",
                    "it uses Bluetooth 5.3",
                    "pairing is done by holding the power button for three seconds",
                    "there is also a 3.5 mm headphone jack",
                ],
            },
        },
    },
    "smartwatch": {
        "items": [
            "smartwatch", "fitness tracker", "running watch", "Pulsewave fitness band",
            "Orbix smartwatch", "GPS sports watch",
        ],
        "price": (40, 320),
        "usage": [
            "after six weeks of wearing it every day", "after a month of runs",
            "after a few weeks of sleep tracking", "after two months on my wrist",
        ],
        "fail": [
            "the screen stopped turning on after {short_time}",
            "the strap pin snapped within {short_time}",
            "it stopped holding a charge after {short_time}",
            "the touchscreen became unresponsive within {short_time}",
        ],
        "aspects": {
            "battery": {
                "pos": [
                    "the battery lasts almost a week between charges",
                    "it charges from empty to full in under an hour",
                    "even with GPS on, the battery gets through a long run with plenty to spare",
                ],
                "neg": [
                    "the battery needs charging every single night",
                    "GPS drains the battery in about two hours",
                    "the magnetic charger keeps slipping off",
                ],
                "neu": [
                    "it uses a magnetic charger",
                    "battery life is listed as five days",
                    "there is a low-power mode in the settings",
                ],
            },
            "tracking": {
                "pos": [
                    "step and heart-rate tracking match my chest strap almost exactly",
                    "the GPS maps of my runs are spot on",
                    "sleep tracking picks up exactly when I wake up at night",
                ],
                "neg": [
                    "the heart-rate readings jump all over the place",
                    "it counts steps while I'm sitting in the car",
                    "the GPS draws my runs straight through buildings",
                ],
                "neu": [
                    "it tracks steps, heart rate and sleep",
                    "GPS is built in",
                    "it has around twenty workout profiles",
                ],
            },
            "app": {
                "pos": [
                    "the companion app is clean and easy to read",
                    "syncing with my phone happens instantly",
                    "the weekly summaries in the app are genuinely useful",
                ],
                "neg": [
                    "the app crashes every few days and forgets my settings",
                    "syncing takes several minutes and often fails",
                    "half the features are locked behind a subscription",
                ],
                "neu": [
                    "the app is available for both major phone platforms",
                    "data syncs over Bluetooth",
                    "the app shows daily, weekly and monthly views",
                ],
            },
            "design": {
                "pos": [
                    "the strap is soft and comfortable all day",
                    "the screen is bright and easy to read in sunlight",
                    "the design looks smart enough for the office",
                ],
                "neg": [
                    "the strap irritates my wrist after a few hours",
                    "the screen is too dim to read outdoors",
                    "the face scratches far too easily",
                ],
                "neu": [
                    "the strap is a standard 20 mm width",
                    "it comes in black, silver and rose gold",
                    "the screen is about 1.4 inches",
                ],
            },
        },
    },
    "vacuum": {
        "items": [
            "cordless vacuum", "stick vacuum", "Brisa cordless vacuum", "Dustra stick vacuum",
            "lightweight stick vacuum", "cordless pet-hair vacuum",
        ],
        "price": (80, 450),
        "usage": [
            "after a month of weekly cleaning", "after six weeks of daily use",
            "after cleaning the whole house a few times", "after two months with two shedding dogs",
        ],
        "fail": [
            "the motor burned out after {short_time}",
            "the charging port stopped working after {short_time}",
            "the bin latch snapped off within {short_time}",
            "the power trigger stopped responding after {short_time}",
        ],
        "aspects": {
            "suction": {
                "pos": [
                    "the suction pulls dog hair out of the rug in one pass",
                    "it picks up crumbs and sand from every corner",
                    "it handles hardwood and thick carpet equally well",
                ],
                "neg": [
                    "the suction is weak and leaves crumbs behind",
                    "it pushes debris around instead of picking it up",
                    "it struggles on anything thicker than a thin rug",
                ],
                "neu": [
                    "it has three suction levels",
                    "it comes with a crevice tool and a brush head",
                    "the floor head has a built-in LED light",
                ],
            },
            "battery": {
                "pos": [
                    "one charge cleans my whole apartment with time to spare",
                    "the battery swaps out in seconds",
                    "it recharges fully in a couple of hours",
                ],
                "neg": [
                    "the battery dies after about twelve minutes",
                    "it takes most of the day to recharge",
                    "the power drops off noticeably as the battery runs down",
                ],
                "neu": [
                    "the battery is removable",
                    "run time is listed as forty minutes on the lowest setting",
                    "it charges on a wall-mounted dock",
                ],
            },
            "noise": {
                "pos": [
                    "it is quiet enough to use while the baby naps",
                    "the noise is a low hum rather than a whine",
                    "I can vacuum without turning up the TV",
                ],
                "neg": [
                    "it is loud enough to scare the cat out of the room",
                    "there is a high-pitched whine at every setting",
                    "the motor rattles at full power",
                ],
                "neu": [
                    "it is rated at about 70 decibels",
                    "the boost mode is louder than the eco mode",
                    "the motor sits in the handle",
                ],
            },
            "maintenance": {
                "pos": [
                    "emptying the bin is quick and mess-free",
                    "the filter rinses clean under the tap",
                    "hair never tangles around the brush roll",
                ],
                "neg": [
                    "emptying the bin sends dust everywhere",
                    "hair wraps around the brush roll constantly",
                    "the filter clogs after every single use",
                ],
                "neu": [
                    "the bin holds about half a litre",
                    "the filter is washable",
                    "the brush roll can be removed for cleaning",
                ],
            },
        },
    },
    "pillow": {
        "items": [
            "memory foam pillow", "cooling pillow", "Somnella pillow", "side-sleeper pillow",
            "contour pillow", "shredded foam pillow",
        ],
        "price": (20, 95),
        "usage": [
            "after a month of sleeping on it", "after two weeks of use", "after a few weeks",
            "after sleeping on it every night for a month",
        ],
        "fail": [
            "a seam split open after {short_time}",
            "the foam crumbled into pieces within {short_time}",
            "the cover zipper broke off after {short_time}",
        ],
        "aspects": {
            "support": {
                "pos": [
                    "my neck pain has eased since switching to it",
                    "the support keeps my head level all night",
                    "the foam bounces back perfectly every morning",
                ],
                "neg": [
                    "the foam flattens within a few hours",
                    "my neck feels stiff every morning",
                    "it is so firm it feels like sleeping on a brick",
                ],
                "neu": [
                    "the foam is a medium firmness",
                    "the loft is about 12 cm",
                    "the filling can be added or removed through a zipper",
                ],
            },
            "temperature": {
                "pos": [
                    "it stays cool all night",
                    "I no longer wake up flipping it to the cold side",
                    "the cover feels pleasantly cool to the touch",
                ],
                "neg": [
                    "it traps heat and I wake up sweating",
                    "the so-called cooling cover feels warm within minutes",
                    "it gets uncomfortably hot by midnight",
                ],
                "neu": [
                    "it has a cooling gel layer under the cover",
                    "it is marketed as breathable",
                    "the foam has ventilation holes",
                ],
            },
            "smell": {
                "pos": [
                    "there was no chemical smell at all out of the box",
                    "it smelled fresh from the very first night",
                    "there was zero off-gassing odor, which I really appreciated",
                ],
                "neg": [
                    "the chemical smell lasted for over two weeks",
                    "it still smells like a tire factory",
                    "the odor gave me a headache the first few nights",
                ],
                "neu": [
                    "it arrived vacuum-packed and took a day to expand",
                    "the instructions say to air it out for 24 hours",
                    "it comes rolled up in a box",
                ],
            },
            "cover": {
                "pos": [
                    "the cover is soft and survives the washing machine",
                    "the zipper on the cover is sturdy and nicely hidden",
                    "the fabric feels lovely against my face",
                ],
                "neg": [
                    "the cover pilled after the first wash",
                    "the cover shrank so much it barely fits",
                    "the zipper scratches my face at night",
                ],
                "neu": [
                    "the cover is removable and machine washable",
                    "the cover is a bamboo blend",
                    "it comes in standard and king sizes",
                ],
            },
        },
    },
    "chair": {
        "items": [
            "office chair", "ergonomic chair", "desk chair", "Arvo mesh chair", "gaming chair", "task chair",
        ],
        "price": (90, 480),
        "usage": [
            "after a month of full workdays", "after six weeks of working from home",
            "after two months of daily use", "after a few weeks of long gaming sessions",
        ],
        "fail": [
            "the gas cylinder failed after {short_time}",
            "a caster snapped off within {short_time}",
            "the backrest bracket cracked after {short_time}",
            "a weld on the base broke after {short_time}",
        ],
        "aspects": {
            "comfort": {
                "pos": [
                    "I can sit through an eight-hour workday without back pain",
                    "the lumbar support sits exactly where I need it",
                    "the seat stays comfortable through long sessions",
                ],
                "neg": [
                    "the seat cushion is thin and my legs go numb",
                    "the lumbar support pushes into my back at an awkward spot",
                    "the armrests dig into my elbows",
                ],
                "neu": [
                    "the seat is about 50 cm wide",
                    "the seat is foam over a plywood base",
                    "it has a fixed lumbar pad",
                ],
            },
            "assembly": {
                "pos": [
                    "assembly took about fifteen minutes",
                    "every bolt lined up perfectly during assembly",
                    "the instructions were clear and all the tools were included",
                ],
                "neg": [
                    "two of the bolt holes didn't line up during assembly",
                    "the instructions skip half the steps",
                    "assembly took over two hours of wrestling with it",
                ],
                "neu": [
                    "it arrives in two boxes",
                    "it needs assembly with the included hex key",
                    "assembly involves about a dozen bolts",
                ],
            },
            "sturdiness": {
                "pos": [
                    "the frame feels solid and stable",
                    "the base and wheels feel built to last",
                    "the gas lift holds its height perfectly",
                ],
                "neg": [
                    "the seat slowly sinks during the day",
                    "the whole chair creaks every time I lean back",
                    "the wheels leave marks on the floor",
                ],
                "neu": [
                    "the weight limit is listed as 120 kg",
                    "the base is aluminum",
                    "it has five caster wheels",
                ],
            },
            "adjustability": {
                "pos": [
                    "every adjustment is easy to reach while seated",
                    "the armrests adjust in four directions",
                    "the recline lock works smoothly",
                ],
                "neg": [
                    "the height lever is stiff and hard to reach",
                    "the armrests wobble no matter how I set them",
                    "the recline tension can't be loosened enough",
                ],
                "neu": [
                    "the seat height adjusts by about 10 cm",
                    "the armrests move up and down",
                    "the recline locks in three positions",
                ],
            },
        },
    },
    "coffee": {
        "items": [
            "coffee maker", "drip coffee machine", "Brewlark coffee maker", "programmable coffee maker",
            "Kettora drip brewer", "10-cup coffee maker",
        ],
        "price": (30, 190),
        "usage": [
            "after a month of daily pots", "after six weeks of morning coffee", "after two months of use",
            "after a few weeks",
        ],
        "fail": [
            "the heating element died after {short_time}",
            "the carafe cracked within {short_time}",
            "it stopped powering on after {short_time}",
            "the water pump gave out after {short_time}",
        ],
        "aspects": {
            "taste": {
                "pos": [
                    "the coffee comes out hot, smooth and full of flavor",
                    "it brews a properly strong cup",
                    "the coffee tastes as good as my local café",
                ],
                "neg": [
                    "the coffee tastes burnt and bitter",
                    "the coffee has a plasticky aftertaste",
                    "every cup tastes weak and watery",
                ],
                "neu": [
                    "there is a strength selector with two settings",
                    "it brews up to ten cups",
                    "it works with ground coffee only",
                ],
            },
            "speed": {
                "pos": [
                    "a full pot is ready in about five minutes",
                    "it heats up almost instantly",
                    "the timer has coffee waiting for me when I wake up",
                ],
                "neg": [
                    "a full pot takes close to fifteen minutes",
                    "the timer resets itself after every power blip",
                    "it takes forever to heat up in the morning",
                ],
                "neu": [
                    "it has a 24-hour programmable timer",
                    "the hot plate switches off after 40 minutes",
                    "brewing a full pot takes about eight minutes",
                ],
            },
            "cleaning": {
                "pos": [
                    "the carafe and filter basket rinse clean in seconds",
                    "descaling is quick and painless",
                    "the carafe pours without a single drip",
                ],
                "neg": [
                    "the water tank is impossible to clean properly",
                    "the carafe dribbles coffee down the side every time I pour",
                    "it leaves a small puddle under the base",
                ],
                "neu": [
                    "the filter basket is dishwasher safe",
                    "there is a descaling reminder light",
                    "the water tank is not removable",
                ],
            },
            "build": {
                "pos": [
                    "it feels solid and looks great on the counter",
                    "the glass carafe is sturdy with a comfortable handle",
                    "it takes up very little counter space",
                ],
                "neg": [
                    "the plastic housing feels cheap and flimsy",
                    "the lid hinge feels like it will snap any day",
                    "it is much bulkier than the photos suggest",
                ],
                "neu": [
                    "it is mostly plastic with a steel trim",
                    "it is about 35 cm tall",
                    "it comes with a glass carafe",
                ],
            },
        },
    },
    "pan": {
        "items": [
            "nonstick frying pan", "skillet", "Ferrona frying pan", "12-inch skillet", "ceramic frying pan",
            "saute pan",
        ],
        "price": (15, 95),
        "usage": [
            "after a month of daily cooking", "after six weeks of use", "after cooking with it almost every night",
            "after two months",
        ],
        "fail": [
            "the handle came loose after {short_time}",
            "the base warped badly within {short_time}",
            "the coating peeled off in flakes after {short_time}",
            "a crack appeared across the base after {short_time}",
        ],
        "aspects": {
            "heating": {
                "pos": [
                    "it heats evenly with no hot spots",
                    "it gets hot fast and holds its heat",
                    "it sears steak beautifully",
                ],
                "neg": [
                    "the center gets scorching while the edges stay cold",
                    "it takes ages to heat up on my stove",
                    "food burns in the middle before the edges are cooked",
                ],
                "neu": [
                    "it works on gas, electric and induction",
                    "the base is about 24 cm across",
                    "it is oven safe up to 200°C",
                ],
            },
            "coating": {
                "pos": [
                    "eggs slide right off without any oil",
                    "the nonstick coating still looks brand new",
                    "nothing sticks, not even melted cheese",
                ],
                "neg": [
                    "eggs stick to the surface even with butter",
                    "the nonstick coating has already started to wear",
                    "the surface scratches at the slightest touch",
                ],
                "neu": [
                    "the coating is ceramic",
                    "the label says it is PFOA-free",
                    "the manual recommends wooden or silicone utensils",
                ],
            },
            "cleaning": {
                "pos": [
                    "cleanup takes a quick wipe with a sponge",
                    "it comes out of the dishwasher spotless",
                    "burnt bits rinse off with warm water",
                ],
                "neg": [
                    "the exterior stains permanently after a few uses",
                    "the outside discolored after one run through the dishwasher",
                    "grease builds up around the rivets",
                ],
                "neu": [
                    "it is listed as dishwasher safe",
                    "the manual recommends hand washing",
                    "the rivets are on the inside of the pan",
                ],
            },
            "handle": {
                "pos": [
                    "the handle stays cool and feels secure",
                    "the weight is perfectly balanced",
                    "the handle is comfortable to hold for long periods",
                ],
                "neg": [
                    "the handle gets too hot to touch",
                    "it is so heavy it's hard to lift with one hand",
                    "the handle wobbles slightly",
                ],
                "neu": [
                    "the handle is stainless steel",
                    "it weighs about one kilogram",
                    "it comes with a glass lid",
                ],
            },
        },
    },
    "jacket": {
        "items": [
            "rain jacket", "winter coat", "puffer jacket", "Northwind parka", "Trailmere shell jacket",
            "insulated jacket", "hooded parka",
        ],
        "price": (50, 280),
        "usage": [
            "after a full autumn of wearing it", "after a few weeks of commuting in it",
            "after a winter of dog walks", "after a rainy week in the hills",
        ],
        "fail": [
            "the main zipper broke after {short_time}",
            "a seam ripped open under the arm within {short_time}",
            "a pocket tore off after {short_time}",
            "the hood came detached after {short_time}",
        ],
        "aspects": {
            "weather": {
                "pos": [
                    "it kept me completely dry in a downpour",
                    "it blocks the wind on even the coldest mornings",
                    "the hood stays put in strong wind",
                ],
                "neg": [
                    "rain soaks through the shoulders within minutes",
                    "the wind cuts right through it",
                    "the hood blows back at the slightest breeze",
                ],
                "neu": [
                    "it has a water-resistance rating of 10,000 mm",
                    "the hood is adjustable",
                    "the seams are taped",
                ],
            },
            "fit": {
                "pos": [
                    "the fit is true to size",
                    "the sleeves are finally long enough for my arms",
                    "there is plenty of room for a sweater underneath",
                ],
                "neg": [
                    "it runs at least two sizes small",
                    "the sleeves are way too short",
                    "the cut is so boxy it looks like a tent on me",
                ],
                "neu": [
                    "I ordered my usual size",
                    "the model in the photos is wearing a medium",
                    "the size chart lists it as a regular fit",
                ],
            },
            "fabric": {
                "pos": [
                    "the fabric feels premium and soft",
                    "the material is lightweight and packs down small",
                    "the color is rich and exactly as pictured",
                ],
                "neg": [
                    "the fabric feels thin and crinkly",
                    "the color is much duller than in the photos",
                    "the lining is scratchy against my neck",
                ],
                "neu": [
                    "it is made of recycled polyester",
                    "the lining is mesh",
                    "the color is listed as navy",
                ],
            },
            "durability": {
                "pos": [
                    "the zippers are chunky and run smoothly",
                    "the stitching is neat and strong",
                    "it still looks new after a full season",
                ],
                "neg": [
                    "the zipper snags every single time",
                    "loose threads were hanging from several seams",
                    "the cuffs started fraying within weeks",
                ],
                "neu": [
                    "it has two zipped hand pockets",
                    "the main zipper is two-way",
                    "the care label says to machine wash cold",
                ],
            },
        },
    },
    "shoes": {
        "items": [
            "pair of running shoes", "pair of hiking boots", "pair of sneakers", "pair of trail runners",
            "pair of Stridon running shoes", "pair of walking shoes",
        ],
        "price": (45, 190),
        "usage": [
            "after about 200 kilometers", "after a month of daily walks", "after a few weekend hikes",
            "after six weeks of training",
        ],
        "fail": [
            "the sole peeled away from the upper after {short_time}",
            "a hole wore through the toe within {short_time}",
            "the heel cushioning collapsed after {short_time}",
        ],
        "aspects": {
            "comfort": {
                "pos": [
                    "the cushioning makes long days on my feet feel easy",
                    "there was no break-in period at all",
                    "the arch support is just right",
                ],
                "neg": [
                    "the shoes gave me blisters within a mile",
                    "the insole is flat and my feet ache by the evening",
                    "the heel rubs painfully on every walk",
                ],
                "neu": [
                    "the insole is removable",
                    "the heel-to-toe drop is listed as 8 mm",
                    "the upper is a mix of mesh and synthetic leather",
                ],
            },
            "look": {
                "pos": [
                    "they look great with jeans",
                    "the colorway is even nicer in person",
                    "they look sleek enough to wear to the office",
                ],
                "neg": [
                    "the color looks cheap in person",
                    "the logo is huge and garish",
                    "they look much bulkier than in the photos",
                ],
                "neu": [
                    "they come in five colors",
                    "the logo is reflective",
                    "the photos show the gray version",
                ],
            },
            "grip": {
                "pos": [
                    "the grip is excellent on wet trails",
                    "the soles never slip on wet pavement",
                    "the traction on loose gravel is great",
                ],
                "neg": [
                    "the soles are slippery on wet floors",
                    "the treads clog with mud immediately",
                    "I nearly fell twice on wet sidewalks",
                ],
                "neu": [
                    "the outsole is rubber",
                    "the lugs are about 4 mm deep",
                    "the sole is a neutral gray",
                ],
            },
            "durability": {
                "pos": [
                    "the stitching still looks perfect after hundreds of kilometers",
                    "the soles show barely any wear",
                    "the laces are tough and stay tied",
                ],
                "neg": [
                    "the laces keep coming undone",
                    "the sole is already wearing thin at the heel",
                    "the fabric is starting to fray around the toe",
                ],
                "neu": [
                    "they come with a spare set of laces",
                    "each shoe weighs about 280 grams",
                    "the upper is stitched rather than glued",
                ],
            },
        },
    },
    "novel": {
        "items": [
            "novel", "thriller", "mystery novel", "fantasy novel", "debut novel", "historical novel",
            "sci-fi novel",
        ],
        "price": (9, 30),
        "usage": [
            "after finishing it over a weekend", "having read it in two sittings", "after reading it on holiday",
            "now that I've finished it", "after reading it for my book club",
        ],
        "fail": [
            "the binding split within {short_time}",
            "pages started falling out within {short_time}",
            "chapter twelve was printed twice and chapter thirteen was missing",
        ],
        "aspects": {
            "plot": {
                "pos": [
                    "the plot twists genuinely surprised me",
                    "the premise is original and gripping",
                    "the central mystery is clever and fair",
                ],
                "neg": [
                    "the plot twist was obvious from chapter two",
                    "the story falls apart in the second half",
                    "the plot relies on one coincidence after another",
                ],
                "neu": [
                    "the story follows two sisters over thirty years",
                    "the plot is told across three timelines",
                    "the story is set in a small coastal town",
                ],
            },
            "characters": {
                "pos": [
                    "the characters feel like real people",
                    "the lead character is funny and memorable",
                    "the dialogue between the characters is sharp",
                ],
                "neg": [
                    "the characters are flat and forgettable",
                    "the narrator is so whiny I couldn't connect with her",
                    "the dialogue feels stiff and unnatural",
                ],
                "neu": [
                    "there are four main characters",
                    "it is narrated in the first person",
                    "the main character is a retired detective",
                ],
            },
            "writing": {
                "pos": [
                    "the prose is beautiful without being showy",
                    "the writing is clear and vivid",
                    "some passages are so well written I reread them",
                ],
                "neg": [
                    "the writing is clunky and repetitive",
                    "the prose is overwritten to the point of exhaustion",
                    "the book is full of typos",
                ],
                "neu": [
                    "the chapters are short",
                    "it is about 400 pages long",
                    "it is written in the present tense",
                ],
            },
            "pacing": {
                "pos": [
                    "the pacing never lets up",
                    "every chapter ends on a hook",
                    "the pacing is brisk without ever feeling rushed",
                ],
                "neg": [
                    "the middle drags for a hundred pages",
                    "the ending feels rushed and unearned",
                    "the pacing is painfully slow",
                ],
                "neu": [
                    "it is the first book in a planned trilogy",
                    "the ending sets up a sequel",
                    "there is an epilogue set ten years later",
                ],
            },
        },
    },
    "skincare": {
        "items": [
            "moisturizer", "face cream", "night cream", "Velvane gel moisturizer", "hydrating face cream",
            "Calenne day cream",
        ],
        "price": (12, 70),
        "usage": [
            "after a month of using it twice a day", "after three weeks", "after six weeks of nightly use",
            "after a full month of daily use",
        ],
        "fail": [
            "it gave me a rash within {short_time}",
            "it broke me out badly within {short_time}",
            "the lid cracked and the cream dried out within {short_time}",
        ],
        "aspects": {
            "texture": {
                "pos": [
                    "the texture is light and sinks in within seconds",
                    "it never feels greasy, even under makeup",
                    "a tiny amount covers my whole face",
                ],
                "neg": [
                    "it leaves a sticky film that never absorbs",
                    "it pills under makeup every time",
                    "the texture is so thick it feels like paste",
                ],
                "neu": [
                    "the texture is a gel",
                    "it is meant for normal to dry skin",
                    "the label says to apply it after cleansing",
                ],
            },
            "results": {
                "pos": [
                    "my dry patches disappeared within a week",
                    "my skin looks noticeably brighter",
                    "my skin stays hydrated all day",
                ],
                "neg": [
                    "my skin feels tight and dry again by lunchtime",
                    "it does nothing for my dry patches",
                    "it does nothing for the redness on my cheeks",
                ],
                "neu": [
                    "it contains hyaluronic acid and niacinamide",
                    "the label says to use it morning and night",
                    "it has SPF 30",
                ],
            },
            "scent": {
                "pos": [
                    "the scent is subtle and fresh",
                    "it smells lovely without being overpowering",
                    "it has no fragrance at all, which my sensitive skin appreciates",
                ],
                "neg": [
                    "the fragrance is overpowering",
                    "it smells like old crayons",
                    "the scent lingers for hours and gives me a headache",
                ],
                "neu": [
                    "it has a light cucumber scent",
                    "it is labeled fragrance-free",
                    "the scent is described as citrus",
                ],
            },
            "packaging": {
                "pos": [
                    "the pump dispenses exactly the right amount",
                    "the jar is beautiful and feels luxurious",
                    "one container lasts for months",
                ],
                "neg": [
                    "the pump stops working when the bottle is half full",
                    "the jar is tiny for the price",
                    "the tube cracked and leaked in my bag",
                ],
                "neu": [
                    "it comes in a 50 ml container",
                    "the jar is glass",
                    "the packaging is labeled recyclable",
                ],
            },
        },
    },
    "building": {
        "items": [
            "building block set", "construction kit", "Brickly castle set", "Brickly pirate ship set",
            "STEM building kit", "Brickly space shuttle set",
        ],
        "price": (20, 130),
        "usage": [
            "after a few weeks of playtime", "after my kids played with it all weekend",
            "after a month in the playroom", "after a rainy week indoors",
        ],
        "fail": [
            "several pieces cracked within {short_time}",
            "the base plate snapped within {short_time}",
            "half the connectors broke within {short_time}",
        ],
        "aspects": {
            "fun": {
                "pos": [
                    "my kids play with it for hours",
                    "my son builds something new with it every day",
                    "it keeps my daughter busy and focused",
                ],
                "neg": [
                    "my kids lost interest after one afternoon",
                    "there is really only one thing you can build",
                    "the finished model doesn't actually do anything",
                ],
                "neu": [
                    "it is recommended for ages six and up",
                    "the box shows three possible models",
                    "it can be combined with other sets from the same line",
                ],
            },
            "instructions": {
                "pos": [
                    "the instructions are clear enough for my seven-year-old to follow alone",
                    "the step-by-step booklet is easy to follow",
                    "the instructions are colorful and well illustrated",
                ],
                "neg": [
                    "the instructions skip steps and are hard to follow",
                    "the instruction diagrams are tiny and blurry",
                    "the instructions don't match the pieces in the box",
                ],
                "neu": [
                    "the instructions come as a printed booklet",
                    "there are also video instructions online",
                    "the booklet has 40 steps",
                ],
            },
            "pieces": {
                "pos": [
                    "the pieces snap together firmly",
                    "the pieces are bright and well made",
                    "every piece was there and neatly bagged",
                ],
                "neg": [
                    "the pieces don't snap together firmly",
                    "the plastic feels cheap and has rough edges",
                    "a few pieces were missing from the box",
                ],
                "neu": [
                    "there are about 300 pieces",
                    "the pieces come in numbered bags",
                    "the set includes a storage box",
                ],
            },
            "durability": {
                "pos": [
                    "the colors still look bright after months in a sunny room",
                    "nothing has cracked despite some very rough play",
                    "the pieces still look brand new despite plenty of rough handling",
                ],
                "neg": [
                    "the plastic scuffs and scratches very easily",
                    "the colors faded in the sun within weeks",
                    "the stickers peeled off almost immediately",
                ],
                "neu": [
                    "the pieces are made of ABS plastic",
                    "the set comes with a spare parts bag",
                    "some pieces come with pre-applied stickers",
                ],
            },
        },
    },
    "boardgame": {
        "items": [
            "board game", "card game", "party game", "strategy game", "co-op board game",
            "Tavern Quest board game", "Hexfall strategy game",
        ],
        "price": (15, 80),
        "usage": [
            "after five game nights", "after a dozen plays", "after playing it with friends all weekend",
            "after a few family game nights",
        ],
        "fail": [
            "the box arrived with a whole deck of cards missing",
            "the cards started splitting at the edges within {short_time}",
            "the box lid tore at the corners within {short_time}",
        ],
        "aspects": {
            "rules": {
                "pos": [
                    "the rules take about ten minutes to learn",
                    "the rulebook is clear and well organized",
                    "new players pick it up after a single round",
                ],
                "neg": [
                    "the rulebook is confusing and contradicts itself",
                    "it took us an hour just to understand the rules",
                    "key rules are buried in footnotes",
                ],
                "neu": [
                    "the rulebook is twelve pages",
                    "there is a quick-start guide included",
                    "a rules video is linked on the box",
                ],
            },
            "components": {
                "pos": [
                    "the cards and tokens are thick and high quality",
                    "the artwork is gorgeous",
                    "the box insert keeps everything organized",
                ],
                "neg": [
                    "the cards are thin and started bending after a few games",
                    "the tokens are flimsy cardboard",
                    "the box insert is useless and everything slides around",
                ],
                "neu": [
                    "it comes with 120 cards and 40 tokens",
                    "the box is about the size of a shoebox",
                    "all the artwork is by a single illustrator",
                ],
            },
            "replay": {
                "pos": [
                    "every game plays out differently",
                    "the variant modules add loads of variety",
                    "we have played it twenty times and still find new strategies",
                ],
                "neg": [
                    "every game plays out the same way",
                    "there is one winning strategy and it gets boring fast",
                    "the scenarios start repeating after a few plays",
                ],
                "neu": [
                    "there are six scenarios included",
                    "it has a solo mode",
                    "expansions are sold separately",
                ],
            },
            "gameplay": {
                "pos": [
                    "everyone at the table was laughing the whole time",
                    "the tension in the final rounds is fantastic",
                    "turns move quickly with almost no waiting",
                ],
                "neg": [
                    "there is far too much downtime between turns",
                    "games drag on much longer than the box says",
                    "one player usually runs away with the lead early",
                ],
                "neu": [
                    "it plays two to six people",
                    "a game takes about 45 minutes",
                    "the box says ages ten and up",
                ],
            },
        },
    },
    "backpack": {
        "items": [
            "backpack", "laptop backpack", "hiking daypack", "travel backpack", "Ridgeway daypack",
            "commuter backpack",
        ],
        "price": (30, 160),
        "usage": [
            "after a month of daily commuting", "after a two-week trip", "after a season of weekend hikes",
            "after a semester of carrying it to class",
        ],
        "fail": [
            "a shoulder strap ripped off within {short_time}",
            "the main zipper split within {short_time}",
            "the bottom seam tore open within {short_time}",
        ],
        "aspects": {
            "capacity": {
                "pos": [
                    "it swallows a laptop, lunch and a jacket with room to spare",
                    "the pockets are smartly laid out",
                    "there is a dedicated spot for everything",
                ],
                "neg": [
                    "the main compartment is much smaller than advertised",
                    "my 15-inch laptop barely squeezes in",
                    "the side pockets are too shallow to hold a bottle",
                ],
                "neu": [
                    "it is listed as 28 liters",
                    "it has a padded laptop sleeve",
                    "there are two side pockets",
                ],
            },
            "straps": {
                "pos": [
                    "the padded straps stay comfortable even fully loaded",
                    "the chest strap really spreads the weight",
                    "it sits comfortably on my back all day",
                ],
                "neg": [
                    "the shoulder straps dig in after twenty minutes",
                    "the straps keep loosening as I walk",
                    "the back panel makes me sweat through my shirt",
                ],
                "neu": [
                    "the straps are adjustable",
                    "there is a removable chest strap",
                    "it has a luggage pass-through on the back",
                ],
            },
            "zippers": {
                "pos": [
                    "the zippers glide smoothly",
                    "the zipper pulls are big enough to use with gloves",
                    "the lockable zippers give me peace of mind when traveling",
                ],
                "neg": [
                    "the zippers snag constantly",
                    "the zipper pulls feel flimsy",
                    "the main zipper sticks at the corners",
                ],
                "neu": [
                    "the main compartment has double zippers",
                    "the zippers are lockable",
                    "the zipper pulls are cord loops",
                ],
            },
            "material": {
                "pos": [
                    "the fabric shrugs off rain",
                    "the material feels tough and well stitched",
                    "the reinforced bottom has held up great",
                ],
                "neg": [
                    "rain soaks straight through the fabric",
                    "the fabric scuffs and stains easily",
                    "the material feels thin and cheap",
                ],
                "neu": [
                    "it is made of 600D polyester",
                    "it comes with a rain cover",
                    "it is available in four colors",
                ],
            },
        },
    },
}

# Pattern exclusions: some sentences only make sense for some product types.
_NOT_REPLACEABLE = frozenset({"novel", "boardgame", "building"})  # "my old one", "second one"
_NO_SECOND_COPY = frozenset({"novel", "boardgame"})
_COLOR_EXCHANGE = frozenset(PRODUCTS) - {"audio", "smartwatch", "jacket", "shoes", "backpack", "chair"}
_REPLACED_BROKEN = frozenset({"novel", "boardgame", "building", "skincare"})


# ── Review patterns ───────────────────────────────────────────────────────
# Slots: {item} {price} {usage}/{Usage} {fail}/{Fail}
#        {pos_a} {pos_b} {neg_a} {neg_b} {neu_a} {neu_b} (+ capitalized forms)
#        _a and _b always come from two different aspects of the same product.
# Generic: {who} {date} {pos_verdict} {neg_verdict} {mix_verdict} {neu_verdict}
#          {trivial} {trivial_up}
# A pattern may be a (text, excluded_product_types) tuple.

POSITIVE = [
    "{Pos_a}, and {pos_b}. {pos_verdict}",
    "Love this {item}! {Pos_a}.",
    "{Usage}, I can say {pos_a}. {pos_verdict}",
    "Really happy with this {item}. {Pos_a}, and {pos_b}.",
    "Bought this {item} for my {who} and it was a big hit. {Pos_a}.",
    "{Pos_a}. {Pos_b}. Couldn't ask for more.",
    "Five stars. {Pos_a}, and on top of that {pos_b}.",
    "This might be the best {item} I've ever bought. {Pos_a}.",
    "Great value for {price}. {Pos_a}, and {pos_b}.",
    "{Usage}, I'm still impressed: {pos_a}.",
    "Exactly what I was looking for. {Pos_a}.",
    "What a great {item}. {Pos_a}, and {pos_b}. {pos_verdict}",
    "My {who} recommended this {item}, and I'm so glad I listened. {Pos_a}.",
    "So glad I bought this. {Pos_a}, and {pos_b}.",
    "Impressed from day one: {pos_a}.",
    "{Pos_a}, which is exactly what I wanted. {pos_verdict}",
    ("This is the second one I've bought, because {pos_a}.", _NO_SECOND_COPY),
    "Top quality. {Pos_a}, and {pos_b}.",
    "Honestly one of my favorite purchases this year. {Pos_a}.",
    "If you're on the fence, go for it. {Pos_a}, and {pos_b}.",
    "Fantastic {item}. {Pos_a}. {pos_verdict}",
    "Everything about this {item} is well thought out: {pos_a}, and {pos_b}.",
    "Ordered it {date} and I'm delighted. {Pos_a}.",
    "Pleasantly surprised by how good this {item} is. {Pos_a}.",
    "Ten out of ten. {Pos_a}, and {pos_b}.",
    "I've tried a few of these, and this {item} is the clear winner. {Pos_a}.",
    "Worth every bit of the {price}. {Pos_a}, and {pos_b}.",
    "Superb. {Pos_a}. I'd happily buy it again.",
    ("A real upgrade over my old one: {pos_a}, and {pos_b}.", _NOT_REPLACEABLE),
    "Gave this {item} to my {who}, and now I want one too. {Pos_a}.",
    "Brilliant {item}. {Pos_a}.",
    "Thrilled with this purchase. {Pos_a}, plus {pos_b}.",
    "{Pos_a}, {pos_b}, and it arrived {date}. {pos_verdict}",
    "Love, love, love it. {Pos_a}.",
]

POSITIVE_HARD = [
    "Not bad at all. {Pos_a}, and {pos_b}.",
    "I can't complain about a single thing. {Pos_a}.",
    "I didn't expect much for {price}, but {pos_a}, and {pos_b}.",
    "I was put off by a few negative reviews, but I'm glad I ignored them: {pos_a}.",
    ("My old one was terrible, so I wasn't expecting much. This {item} is a different story: {pos_a}, and {pos_b}.",
     _NOT_REPLACEABLE),
    "{Pos_a}, and {pos_b}. Tiny nitpick: {trivial}, but that has nothing to do with the product itself.",
    "{Pos_a}. The only thing I'd mention is that {trivial}, which is hardly worth bringing up. {pos_verdict}",
    "Honestly, no complaints whatsoever. {Pos_a}.",
    "Never thought I'd get this excited about something so ordinary, but {pos_a}.",
    "Bought it on a whim and it turned out to be a great decision: {pos_a}, and {pos_b}.",
    "I hate writing reviews, but this {item} deserves one. {Pos_a}.",
    "Don't let the plain box fool you. {Pos_a}, and {pos_b}.",
    "Couldn't find a single flaw. {Pos_a}.",
    "I'm annoyed I didn't buy this sooner. {Pos_a}.",
]

NEGATIVE = [
    "{Neg_a}, and {neg_b}. {neg_verdict}",
    "Really disappointed with this {item}. {Neg_a}.",
    "{Fail}. {neg_verdict}",
    "{Usage}, I can say {neg_a}. {neg_verdict}",
    "Do not buy this {item}. {Neg_a}, and {neg_b}.",
    "Bought this {item} for my {who}, and it was a letdown. {Neg_a}.",
    "{Neg_a}. On top of that, {fail}.",
    "Terrible {item}. {Neg_a}.",
    "Not worth {price}. {Neg_a}, and {neg_b}.",
    "Worst {item} I've ever bought. {Neg_a}.",
    "Returned it within a week. {Neg_a}.",
    "{Neg_a}, which makes it pretty much useless to me.",
    "I wanted to like this {item}, but {neg_a}, and {neg_b}.",
    "Poor quality. {Fail}.",
    "Very unhappy. {Neg_a}, and customer service was no help at all.",
    "Ordered it {date} and already regret it. {Neg_a}.",
    "Save your money. {Neg_a}.",
    "Cheaply made and frustrating. {Neg_a}, and {neg_b}.",
    "One star. {Fail}, and before that {neg_a}.",
    "Big letdown. {Neg_a}. {neg_verdict}",
    "This {item} is a waste of {price}. {Neg_a}.",
    "Huge disappointment after all the hype. {Neg_a}, and {neg_b}.",
    "Already asked for a refund. {Fail}.",
    "I've had nothing but problems: {neg_a}, and {neg_b}.",
    "Avoid this {item}. {Fail}.",
    "Not what I expected at all. {Neg_a}.",
    "Two problems right away: {neg_a}, and {neg_b}.",
    "My {who} hated it. {Neg_a}.",
    "Awful. {Neg_a}, and {fail}.",
    ("{Neg_a}. I'm going back to my old one.", _NOT_REPLACEABLE),
    "Doesn't live up to the description. {Neg_a}. {neg_verdict}",
    "Junk. {Fail}.",
    "Frustrating from day one: {neg_a}.",
]

NEGATIVE_HARD = [
    "Great, {fail}. Exactly what I paid {price} for.",
    "Oh wonderful, {neg_a}. Just what I always wanted.",
    "Wow, top-notch quality: {fail}.",
    "Love that {neg_a}. Said no one ever.",
    "Ten out of ten, would not buy again: {neg_a}, and {neg_b}.",
    "{trivial_up}, I'll give it that. Everything else is a letdown: {neg_a}, and {neg_b}.",
    "Not great. Not even okay, honestly. {Neg_a}.",
    "I really can't recommend it. {Neg_a}.",
    "Five stars for the speedy delivery, zero for the {item} itself: {neg_a}.",
    "Brilliant. Just brilliant. {Fail}.",
    "Now I know why it was so cheap. {Neg_a}, and {neg_b}.",
    "Impressive how fast this went wrong: {fail}.",
    "I wouldn't call it terrible, but it's close. {Neg_a}, and {neg_b}.",
    "Nothing positive to say. {Neg_a}.",
]

MIXED = [
    "{Pos_a}, but {neg_b}.",
    "{Neg_b}, though {pos_a}. {mix_verdict}",
    "The good: {pos_a}. The bad: {neg_b}.",
    "Pros: {pos_a}. Cons: {neg_b}.",
    "Love that {pos_a}; hate that {neg_b}.",
    "On one hand, {pos_a}. On the other hand, {neg_b}.",
    "{Pos_a}, which I love. Unfortunately, {neg_b}.",
    "Mixed bag. {Pos_a}, but {neg_b}.",
    "{Usage}, my feelings are mixed: {pos_a}, but {neg_b}.",
    "Some things about this {item} are great and some are not. {Pos_a}, yet {neg_b}.",
    "I really like that {pos_a}. What I don't like is that {neg_b}.",
    "Half great, half annoying. {Pos_a}, but {neg_b}.",
    "Bought this {item} for my {who}. {Pos_a}, but {neg_b}. {mix_verdict}",
    "{Pos_a}. Sadly, {neg_b}. {mix_verdict}",
    "For {price}, it's a trade-off: {pos_a}, but {neg_b}.",
    "It gets one thing very right and one thing very wrong. {Pos_a}, but {neg_b}.",
    "Credit where it's due: {pos_a}. That said, {neg_b}.",
    "{Neg_b}. On the plus side, {pos_a}. {mix_verdict}",
    "I'm torn on this {item}. {Pos_a}, but {neg_b}.",
    "Good news and bad news. Good: {pos_a}. Bad: {neg_b}.",
    "Strengths: {pos_a}. Weaknesses: {neg_b}.",
    "{Pos_a}, no question. But {neg_b}, and that matters too.",
    "Honestly a mixed experience: {pos_a}, while {neg_b}.",
    "There's a lot to like and a lot to dislike. {Pos_a}, but {neg_b}.",
    "What works: {pos_a}. What doesn't: {neg_b}.",
    "Three stars. {Pos_a}, but {neg_b}.",
    "{Pos_a}; the downside is that {neg_b}. {mix_verdict}",
    "Can't decide whether I like this {item}. {Pos_a}, but {neg_b}.",
    "I'd keep it for one reason and return it for another: {pos_a}, but {neg_b}.",
    "{Neg_b}, which is a real shame, because {pos_a}.",
    "Part of me loves this {item} and part of me is frustrated. {Pos_a}, but {neg_b}.",
]

MIXED_HARD = [
    "Would be five stars if not for one thing: {neg_b}. {Pos_a}, though.",
    "I wanted to love it, and in some ways I do: {pos_a}. But {neg_b}.",
    "Not bad, but not great either: {pos_a}, while {neg_b}.",
    "I can't fault the fact that {pos_a}, but I also can't ignore that {neg_b}.",
    "My {who} loves it because {pos_a}; I'm less keen because {neg_b}.",
    "Only giving it three stars because {neg_b}, even though {pos_a}.",
    "Not the disaster some reviews claim, but not perfect either: {pos_a}, but {neg_b}.",
    "Love it and hate it in equal measure. {Pos_a}. {Neg_b}.",
    "My only real complaint is that {neg_b}. Otherwise, {pos_a}. {mix_verdict}",
    "Pretty good in one way, pretty bad in another: {pos_a}, yet {neg_b}.",
]

NEUTRAL = [
    "{Neu_a}. {Neu_b}.",
    "Arrived {date}. {Neu_a}.",
    "{Neu_a}, and {neu_b}.",
    "Bought this {item} for my {who}. {Neu_a}.",
    "Details for anyone comparing: {neu_a}; {neu_b}.",
    "It's an okay {item}. {Neu_a}.",
    "Neither impressed nor disappointed. {Neu_a}.",
    "{Neu_a}. {neu_verdict}",
    "Ordered this {item} {date}. {Neu_a}, and {neu_b}.",
    "For those asking: {neu_a}.",
    "It is a standard {item}. {Neu_a}. {Neu_b}.",
    "Nothing stands out either way. {Neu_a}.",
    "Too early for a verdict. {Neu_a}. {Neu_b}.",
    "Quick facts: {neu_a}, and {neu_b}.",
    "This is the first one of these I've owned, so I have nothing to compare it to. {Neu_a}.",
    "{Neu_a}. Not much else to say.",
    "Some details the listing leaves out: {neu_a}, and {neu_b}.",
    "Average {item}. {Neu_a}.",
    "It's fine. {Neu_a}. {Neu_b}.",
    "Picked this {item} up {date}. {Neu_a}.",
    "Got this as a gift for my {who}, so I can't say how it performs. {Neu_a}.",
    "{Neu_a}. {Neu_b}. {neu_verdict}",
    "Just noting for other buyers: {neu_a}.",
    "Received it {date}. {Neu_a}. Haven't formed an opinion yet.",
    "Middle of the road. {Neu_a}.",
    "{Usage}, I have no strong opinion either way. {Neu_a}.",
    "Bought it because it was the one in stock. {Neu_a}.",
    "Paid {price}. {Neu_a}, and {neu_b}.",
    "For reference: {neu_a}; {neu_b}.",
    "Standard stuff. {Neu_a}. {neu_verdict}",
    "One review won't tell you much, so here are the facts: {neu_a}, and {neu_b}.",
]

NEUTRAL_HARD = [
    "Not great, not terrible. {Neu_a}.",
    ("Bought this to replace one that broke. {Neu_a}. Too soon to say how it compares.", _REPLACED_BROKEN),
    "The listing calls it a best seller. {Neu_a}. {Neu_b}.",
    "No complaints yet, but no praise yet either; I've only had it a couple of days. {Neu_a}.",
    "People seem to either love or hate these. {Neu_a}, and {neu_b}.",
    "Reviewing for the product details only: {neu_a}. {Neu_b}.",
    "Can't rate the {item} itself yet. {Neu_a}.",
    "It's neither the best nor the worst {item} I've had. {Neu_a}.",
    ("Exchanged it for a different color, not because of any problem. {Neu_a}.", _COLOR_EXCHANGE),
    "No issues to report and nothing special to highlight. {Neu_a}.",
    "I don't love it and I don't hate it. {Neu_a}. {Neu_b}.",
]

# ── Generic slots ─────────────────────────────────────────────────────────

GENERIC_SLOTS = {
    "who": [
        "son", "daughter", "partner", "mum", "dad", "roommate", "sister", "brother", "wife", "husband",
        "nephew", "niece", "best friend",
    ],
    "date": [
        "last week", "on Tuesday", "two days ago", "a week ago", "yesterday", "last month", "on Friday",
        "over the weekend", "earlier this month",
    ],
    "short_time": ["two days", "a week", "nine days", "three weeks", "a month", "five days", "ten days"],
    "pos_verdict": [
        "Highly recommend.", "Would buy again in a heartbeat.", "Worth every penny.", "Couldn't be happier.",
        "Best purchase I've made this year.", "Absolutely love it.", "Five stars.", "Exceeded my expectations.",
        "Very impressed.", "I'd recommend it to anyone.",
    ],
    "neg_verdict": [
        "Returning it.", "Don't waste your money.", "Very disappointed.", "Would not recommend.",
        "Sending it back for a refund.", "Avoid.", "Complete waste of money.", "I regret buying it.",
        "Save yourself the hassle and look elsewhere.", "One star is generous.",
    ],
    "mix_verdict": [
        "Mixed feelings overall.", "I'm honestly torn on this one.", "Three stars.", "Some good, some bad.",
        "Not sure yet whether I'll keep it.", "It's a trade-off.", "Good in some ways, frustrating in others.",
        "Hard to give it a clear thumbs up or down.", "Can't decide if I like it.",
    ],
    "neu_verdict": [
        "Nothing special, nothing wrong.", "No strong feelings either way.", "It is what it is.",
        "Neither impressed nor disappointed.", "Average.", "Three stars, I suppose.", "It's fine.",
        "Haven't formed an opinion yet.", "Can't say much more than that.",
    ],
    "trivial": [
        "the shipping box arrived a little crushed", "delivery took a day longer than estimated",
        "the outer packaging was a pain to open", "the courier left it at the wrong door at first",
        "the shipping box was far bigger than it needed to be", "the courier's delivery updates were slow",
    ],
    "trivial_up": [
        "The packaging was nice", "Shipping was quick", "It arrived on time", "The box looked nice",
        "Delivery was fast",
    ],
}


# ── Expansion ─────────────────────────────────────────────────────────────

_TYPE_SLOT_RE = re.compile(r"\{(item|price|usage|Usage|fail|Fail)\}")
_ASPECT_SLOT_RE = re.compile(r"\{(pos|Pos|neg|Neg|neu|Neu)_(a|b)\}")


def _cap(text: str) -> str:
    return text[:1].upper() + text[1:]


def _price_slot(low: int, high: int):
    def _gen(rng: random.Random) -> str:
        return amount(rng, low, high)

    return _gen


def _build_slots() -> dict:
    slots: dict = dict(GENERIC_SLOTS)
    for tname, spec in PRODUCTS.items():
        slots[f"{tname}__item"] = spec["items"]
        slots[f"{tname}__price"] = _price_slot(*spec["price"])
        slots[f"{tname}__usage"] = spec["usage"]
        slots[f"{tname}__Usage"] = [_cap(x) for x in spec["usage"]]
        slots[f"{tname}__fail"] = spec["fail"]
        slots[f"{tname}__Fail"] = [_cap(x) for x in spec["fail"]]
        for aspect, pools in spec["aspects"].items():
            for pol in ("pos", "neg", "neu"):
                slots[f"{tname}__{aspect}__{pol}"] = pools[pol]
                slots[f"{tname}__{aspect}__{_cap(pol)}"] = [_cap(x) for x in pools[pol]]
    return slots


def _expand(patterns: list) -> list[str]:
    """Expand each pattern for every product type and ordered aspect pair."""
    out: list[str] = []
    for pattern in patterns:
        text, excluded = (pattern, frozenset()) if isinstance(pattern, str) else pattern
        for tname, spec in PRODUCTS.items():
            if tname in excluded:
                continue
            typed = _TYPE_SLOT_RE.sub(lambda m: "{%s__%s}" % (tname, m.group(1)), text)
            aspects = list(spec["aspects"])
            for a in aspects:
                for b in aspects:
                    if a == b:
                        continue
                    out.append(
                        _ASPECT_SLOT_RE.sub(
                            lambda m: "{%s__%s__%s}" % (tname, a if m.group(2) == "a" else b, m.group(1)),
                            typed,
                        )
                    )
    return out


SLOTS = _build_slots()

PATTERNS = {
    "positive": (POSITIVE, POSITIVE_HARD),
    "negative": (NEGATIVE, NEGATIVE_HARD),
    "neutral": (NEUTRAL, NEUTRAL_HARD),
    "mixed": (MIXED, MIXED_HARD),
}
TEMPLATES = {label: _expand(core) for label, (core, _) in PATTERNS.items()}
HARD = {label: _expand(hard) for label, (_, hard) in PATTERNS.items()}

ROWS_PER_LABEL = 300


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
            for label in ("positive", "negative", "neutral", "mixed")
        )
    )
