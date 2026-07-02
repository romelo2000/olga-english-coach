"""CEFR-aligned English curriculum with grammar, vocabulary, and functional language.

Based on the Common European Framework of Reference for Languages (CEFR)
and modern corpus-based vocabulary research (NGSL, Oxford 3000).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from wordbank import (
    CEFR_LEVELS, VocabCard, VocabSet, VOCABULARY_SETS,
    PHRASAL_VERBS, COLOCATIONS, COMMON_ERRORS,
    IDIOMS, CONFUSING_WORDS, PREPOSITIONS,
)
from worddb import (
    vocabulary_for_level, all_vocab_cards_for_level,
    phrasal_verbs_for_level, collocations_for_level,
    common_errors_for_level, idioms_for_level,
    confusing_words_for_level, prepositions_for_level,
)


@dataclass(frozen=True)
class GrammarPoint:
    id: str
    level: str
    title: str
    summary: str
    examples: list[str]
    common_errors: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class FunctionSet:
    level: str
    function: str
    key_phrases: list[str]
    scenario: str

CEFR_CAN_DO = {
    "A1": "Понимаю и использую знакомые повседневные выражения и базовые фразы.",
    "A2": "Понимаю предложения и часто используемые выражения, связанные с повседневной жизнью.",
    "B1": "Понимаю основные идеи ясного стандартного текста на знакомые темы.",
    "B2": "Понимаю основные идеи сложного текста, включая технические обсуждения в моей области.",
    "C1": "Понимаю широкий спектр сложных длинных текстов и распознаю скрытый смысл.",
    "C2": "Понимаю практически всё услышанное или прочитанное без усилий.",
}

GRAMMAR_CURRICULUM: dict[str, list[GrammarPoint]] = {
    "A1": [
        GrammarPoint(
            id="a1-be",
            level="A1",
            title="Verb 'to be' (Present)",
            summary="am/is/are for identity, description, location.",
            examples=["I am a student.", "She is from Spain.", "They are happy."],
            common_errors=["He are a doctor → He is a doctor", "I am agree → I agree"],
        ),
        GrammarPoint(
            id="a1-present-simple",
            level="A1",
            title="Present Simple",
            summary="Habits, routines, facts. Add -s for 3rd person singular.",
            examples=["I work in London.", "She plays tennis every weekend.", "We don't live here."],
            common_errors=["He go to school → He goes to school", "Do she like tea? → Does she like tea?"],
        ),
        GrammarPoint(
            id="a1-articles",
            level="A1",
            title="Articles a/an/the",
            summary="a before consonants, an before vowels, the for specific things.",
            examples=["a book", "an apple", "The sun is hot."],
            common_errors=["a umbrella → an umbrella", "I have the cat → I have a cat (first mention)"],
        ),
        GrammarPoint(
            id="a1-possessives",
            level="A1",
            title="Possessive Adjectives",
            summary="my, your, his, her, its, our, their.",
            examples=["This is my book.", "Her name is Anna.", "Our dog is small."],
            common_errors=["She's name → Her name", "It's car → Its car"],
        ),
        GrammarPoint(
            id="a1-plurals",
            level="A1",
            title="Plural Nouns",
            summary="Regular: add -s. Irregular: man→men, child→children, person→people.",
            examples=["two books", "three children", "five people"],
            common_errors=["two childs → two children", "three mans → three men"],
        ),
        GrammarPoint(
            id="a1-can",
            level="A1",
            title="Can / Can't (Ability)",
            summary="Can + base verb for ability and inability.",
            examples=["I can swim.", "She can't drive.", "Can you cook?"],
            common_errors=["He can swims → He can swim", "I no can → I can't"],
        ),
        GrammarPoint(
            id="a1-prepositions-place",
            level="A1",
            title="Prepositions of Place",
            summary="in (inside), on (surface), at (point/location).",
            examples=["in the room", "on the table", "at the bus stop"],
            common_errors=["at the picture → in the picture", "on the room → in the room"],
        ),
        GrammarPoint(
            id="a1-demonstratives",
            level="A1",
            title="This / That / These / Those",
            summary="this/these for near, that/those for far.",
            examples=["This is my pen.", "Those are your books.", "That is a big house."],
            common_errors=["This books → These books", "Those is → Those are"],
        ),
    ],
    "A2": [
        GrammarPoint(
            id="a2-past-simple",
            level="A2",
            title="Past Simple",
            summary="Regular: -ed. Irregular: go→went, see→saw, have→had.",
            examples=["I worked yesterday.", "She went to Paris.", "They didn't see the film."],
            common_errors=["I goed → I went", "Did he went? → Did he go?"],
        ),
        GrammarPoint(
            id="a2-present-continuous",
            level="A2",
            title="Present Continuous",
            summary="am/is/are + -ing for actions happening now.",
            examples=["I am reading a book.", "She is cooking dinner.", "They aren't sleeping."],
            common_errors=["I am read → I am reading", "She is swiming → She is swimming"],
        ),
        GrammarPoint(
            id="a2-comparatives",
            level="A2",
            title="Comparatives & Superlatives",
            summary="-er/-est for short, more/most for long adjectives.",
            examples=["bigger than", "the most beautiful", "better than, the best"],
            common_errors=["more bigger → bigger", "the most good → the best"],
        ),
        GrammarPoint(
            id="a2-going-to",
            level="A2",
            title="Going to (Future Plans)",
            summary="am/is/are going to + base verb for plans and intentions.",
            examples=["I'm going to study tonight.", "They are going to travel."],
            common_errors=["I going to → I am going to", "She is going to studying → going to study"],
        ),
        GrammarPoint(
            id="a2-some-any",
            level="A2",
            title="Some / Any / Much / Many",
            summary="some in positive, any in negatives/questions. much=uncountable, many=countable.",
            examples=["some water", "any questions?", "much money", "many friends"],
            common_errors=["I don't have some → I don't have any", "much friends → many friends"],
        ),
        GrammarPoint(
            id="a2-frequency-adverbs",
            level="A2",
            title="Adverbs of Frequency",
            summary="always, usually, often, sometimes, rarely, never — before main verb.",
            examples=["I always drink coffee.", "She never eats meat.", "We often go out."],
            common_errors=["I drink always coffee → I always drink coffee", "She is never happy → She is never happy (correct before 'is')"],
        ),
        GrammarPoint(
            id="a2-prepositions-time",
            level="A2",
            title="Prepositions of Time",
            summary="at (clock time), on (days/dates), in (months/years/seasons).",
            examples=["at 7 o'clock", "on Monday", "in July"],
            common_errors=["in Monday → on Monday", "at July → in July"],
        ),
        GrammarPoint(
            id="a2-countable-uncountable",
            level="A2",
            title="Countable & Uncountable Nouns",
            summary="Countable: a/an, plural. Uncountable: no article, no plural.",
            examples=["an apple → two apples", "water (no plural)", "an advice → some advice"],
            common_errors=["an information → some information", "two waters → two bottles of water"],
        ),
    ],
    "B1": [
        GrammarPoint(
            id="b1-present-perfect",
            level="B1",
            title="Present Perfect (Experience)",
            summary="have/has + past participle for life experiences, recent actions.",
            examples=["I have visited Japan.", "She has lost her keys.", "Have you ever eaten sushi?"],
            common_errors=["I have went → I have gone/been", "I have seen him yesterday → I saw him yesterday"],
        ),
        GrammarPoint(
            id="b1-first-conditional",
            level="B1",
            title="First Conditional",
            summary="If + present simple, will + base verb for likely future situations.",
            examples=["If it rains, I will stay home.", "If you study, you'll pass."],
            common_errors=["If it will rain → If it rains", "If it rain → If it rains"],
        ),
        GrammarPoint(
            id="b1-second-conditional",
            level="B1",
            title="Second Conditional",
            summary="If + past simple, would + base verb for hypothetical situations.",
            examples=["If I had money, I would travel.", "If I were you, I'd study more."],
            common_errors=["If I would have → If I had", "If I was you → If I were you (formal)"],
        ),
        GrammarPoint(
            id="b1-relative-clauses",
            level="B1",
            title="Relative Clauses",
            summary="who (people), which (things), that (both), whose (possession).",
            examples=["The man who lives next door is nice.", "The book that I read was great."],
            common_errors=["The man which lives → The man who lives", "The book who I read → The book that/which I read"],
        ),
        GrammarPoint(
            id="b1-modals",
            level="B1",
            title="Modal Verbs (should, must, have to)",
            summary="should = advice, must = obligation (internal), have to = obligation (external).",
            examples=["You should see a doctor.", "I must finish this today.", "She has to wear a uniform."],
            common_errors=["You should to go → You should go", "I must to go → I must go"],
        ),
        GrammarPoint(
            id="b1-passive",
            level="B1",
            title="Passive Voice (Present/Past)",
            summary="be + past participle when the action is more important than the doer.",
            examples=["English is spoken here.", "The house was built in 1990."],
            common_errors=["The book was wrote → was written", "English is speaking → is spoken"],
        ),
        GrammarPoint(
            id="b1-used-to",
            level="B1",
            title="Used to (Past Habits)",
            summary="used to + base verb for past habits that no longer happen.",
            examples=["I used to play football.", "She didn't use to like coffee."],
            common_errors=["I used to playing → I used to play", "Did you used to? → Did you use to?"],
        ),
        GrammarPoint(
            id="b1-gerunds-infinitives",
            level="B1",
            title="Gerunds & Infinitives",
            summary="Some verbs + -ing (enjoy, avoid), others + to + base (want, decide).",
            examples=["I enjoy reading.", "She wants to leave.", "I stopped smoking."],
            common_errors=["I enjoy to read → I enjoy reading", "I want reading → I want to read"],
        ),
    ],
    "B2": [
        GrammarPoint(
            id="b2-past-perfect",
            level="B2",
            title="Past Perfect",
            summary="had + past participle for an action before another past action.",
            examples=["I had eaten before she arrived.", "They had never seen snow before."],
            common_errors=["I ate before she came (ambiguous) → I had eaten before she came", "I had eat → I had eaten"],
        ),
        GrammarPoint(
            id="b2-reported-speech",
            level="B2",
            title="Reported Speech",
            summary="Backshift tenses: present→past, will→would, can→could. Change pronouns/time.",
            examples=["He said he was tired.", "She told me she would call.", "He asked if I had eaten."],
            common_errors=["He said he is tired → He said he was tired", "She told she would call → She told me she would call"],
        ),
        GrammarPoint(
            id="b2-third-conditional",
            level="B2",
            title="Third Conditional",
            summary="If + past perfect, would have + past participle for unreal past situations.",
            examples=["If I had studied, I would have passed.", "If she had left earlier, she wouldn't have missed it."],
            common_errors=["If I would have studied → If I had studied", "I would passed → I would have passed"],
        ),
        GrammarPoint(
            id="b2-wish-if-only",
            level="B2",
            title="Wish / If Only",
            summary="wish + past simple (present), wish + past perfect (past regret).",
            examples=["I wish I had more time.", "I wish I had studied harder.", "If only I knew!"],
            common_errors=["I wish I have → I wish I had", "I wish I would have → I wish I had (past regret)"],
        ),
        GrammarPoint(
            id="b2-future-perfect-continuous",
            level="B2",
            title="Future Perfect & Future Continuous",
            summary="will have + past participle (completed by a point), will be + -ing (in progress).",
            examples=["By 2025, I will have graduated.", "This time tomorrow, I will be flying to Tokyo."],
            common_errors=["I will graduated → I will have graduated", "I will flying → I will be flying"],
        ),
        GrammarPoint(
            id="b2-advanced-modals",
            level="B2",
            title="Advanced Modals (could have, should have)",
            summary="modal + have + past participle for past possibility/criticism.",
            examples=["You should have told me.", "She could have won.", "They must have left early."],
            common_errors=["You should told me → You should have told me", "She could won → She could have won"],
        ),
        GrammarPoint(
            id="b2-cleft-sentences",
            level="B2",
            title="Cleft Sentences",
            summary="It-clefts for emphasis: 'It was X who/that...'",
            examples=["It was John who broke the window.", "It was in Paris that they met."],
            common_errors=["It was John which broke → It was John who broke", "It was in Paris where they met → It was in Paris that they met"],
        ),
        GrammarPoint(
            id="b2-mixed-conditionals",
            level="B2",
            title="Mixed Conditionals",
            summary="Combine different time frames: past condition → present result, or vice versa.",
            examples=["If I had studied medicine, I would be a doctor now.", "If I were rich, I would have bought it."],
            common_errors=["If I had studied, I would be → (correct! this is a mixed conditional)"],
        ),
    ],
    "C1": [
        GrammarPoint(
            id="c1-inversion",
            level="C1",
            title="Inversion for Emphasis",
            summary="Negative adverbial + auxiliary + subject for dramatic effect.",
            examples=["Never have I seen such beauty.", "Not only did she sing, but she also danced.", "Rarely do we get such opportunities."],
            common_errors=["Never I have seen → Never have I seen", "Not only she sang → Not only did she sing"],
        ),
        GrammarPoint(
            id="c1-causative-have",
            level="C1",
            title="Causative Have (have something done)",
            summary="have/get + object + past participle when someone does something for you.",
            examples=["I had my car repaired.", "She got her hair cut.", "We're having the roof fixed."],
            common_errors=["I had repaired my car (I did it) → I had my car repaired (someone else did it)"],
        ),
        GrammarPoint(
            id="c1-participle-clauses",
            level="C1",
            title="Participle Clauses",
            summary="Present participle (-ing) or past participle (-ed) to replace relative clauses or adverbial clauses.",
            examples=["Having finished dinner, we went for a walk.", "The book written by her is a bestseller."],
            common_errors=["Having finish dinner → Having finished dinner", "The book writing by her → The book written by her"],
        ),
        GrammarPoint(
            id="c1-subjunctive",
            level="C1",
            title="Subjunctive Mood",
            summary="Base form after 'suggest/recommend/insist that...' for formal/mandative subjunctive.",
            examples=["I suggest that he be present.", "She insisted that he leave immediately.", "It is essential that everyone attend."],
            common_errors=["I suggest that he is present → I suggest that he be present", "She insisted that he leaves → She insisted that he leave"],
        ),
        GrammarPoint(
            id="c1-ellipsis-substitution",
            level="C1",
            title="Ellipsis & Substitution",
            summary="Omitting redundant words; using do/so/one to avoid repetition.",
            examples=["She likes coffee; I do too.", "I think so.", "Can I borrow your pen? — I haven't got one."],
            common_errors=["She likes coffee; I too → I do too", "I think it → I think so"],
        ),
        GrammarPoint(
            id="c1-discourse-markers",
            level="C1",
            title="Advanced Discourse Markers",
            summary="nevertheless, furthermore, consequently, albeit, notwithstanding for cohesive writing.",
            examples=["The weather was terrible; nevertheless, we continued.", "It's a good plan, albeit an expensive one."],
            common_errors=["nevertheless the weather → nevertheless, the weather (needs comma)"],
        ),
    ],
    "C2": [
        GrammarPoint(
            id="c2-stylistic-inversion",
            level="C2",
            title="Stylistic Inversion",
            summary="Full inversion of subject and verb for literary/rhetorical effect.",
            examples=["Down the road came a tall figure.", "Gone are the days of cheap fuel.", "Blessed are the merciful."],
            common_errors=["Down the road a tall figure came → came a tall figure (inverted for style)"],
        ),
        GrammarPoint(
            id="c2-nominalization",
            level="C2",
            title="Nominalization",
            summary="Converting verbs/adjectives to nouns for academic/formal register.",
            examples=["The decision was made → The making of the decision...", "They arrived → Their arrival caused..."],
            common_errors=["Overuse makes text heavy — use sparingly for register shift"],
        ),
        GrammarPoint(
            id="c2-fronting-displacement",
            level="C2",
            title="Fronting & Displacement",
            summary="Moving information to sentence-start for topic management and emphasis.",
            examples=["That book, I've read three times.", "What he said, I'll never forget.", "The money, I gave to charity."],
            common_errors=["That book I've read it three times → That book, I've read three times (no redundant pronoun)"],
        ),
        GrammarPoint(
            id="c2-concessive-advanced",
            level="C2",
            title="Advanced Concessive Clauses",
            summary="while, whereas, granted, for all that, much as for sophisticated contrast.",
            examples=["Much as I admire him, I disagree.", "For all his wealth, he is unhappy.", "Granted, the plan has flaws, yet it remains our best option."],
            common_errors=["Much as I admire him, but I disagree → Much as I admire him, I disagree (no 'but')"],
        ),
    ],
}


FUNCTIONS_CURRICULUM: dict[str, list[FunctionSet]] = {
    "A1": [
        FunctionSet(
            level="A1",
            function="Greetings & Introductions",
            key_phrases=["Hello, my name is...", "Nice to meet you", "How are you?", "I'm fine, thanks"],
            scenario="Meet a new colleague at work for the first time.",
        ),
        FunctionSet(
            level="A1",
            function="Asking for Information",
            key_phrases=["What's your name?", "Where are you from?", "How old are you?", "What do you do?"],
            scenario="Ask a new classmate about themselves.",
        ),
        FunctionSet(
            level="A1",
            function="Numbers & Time",
            key_phrases=["It's three o'clock", "How much is it?", "Can I have two, please?", "What time is it?"],
            scenario="Buy items at a shop and ask the price.",
        ),
    ],
    "A2": [
        FunctionSet(
            level="A2",
            function="Making Plans",
            key_phrases=["Let's go...", "How about...?", "I'd like to...", "Why don't we...?"],
            scenario="Suggest weekend plans to a friend.",
        ),
        FunctionSet(
            level="A2",
            function="Shopping",
            key_phrases=["Can I have...?", "How much does it cost?", "Do you have...?", "I'll take it."],
            scenario="Buy clothes at a store and ask about sizes.",
        ),
        FunctionSet(
            level="A2",
            function="Directions",
            key_phrases=["Turn left/right", "Go straight on", "It's next to/opposite", "How do I get to...?"],
            scenario="Ask a stranger for directions to the train station.",
        ),
    ],
    "B1": [
        FunctionSet(
            level="B1",
            function="Expressing Opinions",
            key_phrases=["I think that...", "In my opinion...", "I agree/disagree because...", "From what I can see..."],
            scenario="Discuss whether social media is good or bad for society.",
        ),
        FunctionSet(
            level="B1",
            function="Telling Stories",
            key_phrases=["First,...", "Then,...", "After that,...", "Finally,...", "Suddenly..."],
            scenario="Tell a story about a memorable trip or event.",
        ),
        FunctionSet(
            level="B1",
            function="Making Suggestions",
            key_phrases=["We could...", "Why don't we...?", "I suggest...", "How about...?"],
            scenario="Suggest solutions to a friend's problem at work.",
        ),
    ],
    "B2": [
        FunctionSet(
            level="B2",
            function="Debating",
            key_phrases=["On the one hand,...", "I see your point, but...", "That's a valid argument, however...", "I'd counter that..."],
            scenario="Debate whether remote work is better than office work.",
        ),
        FunctionSet(
            level="B2",
            function="Hypothesizing",
            key_phrases=["If I were in that situation,...", "Imagine if...", "Suppose...", "What would happen if...?"],
            scenario="Discuss what you would do if you suddenly won a million dollars.",
        ),
        FunctionSet(
            level="B2",
            function="Formal & Informal Register",
            key_phrases=["I would appreciate it if...", "Could you possibly...?", "Can you...?", "Mind if I...?"],
            scenario="Write the same request in formal and informal contexts.",
        ),
    ],
    "C1": [
        FunctionSet(
            level="C1",
            function="Presenting & Structuring",
            key_phrases=["I'd like to draw your attention to...", "This leads us to the conclusion that...", "Turning now to...", "To put this in perspective..."],
            scenario="Give a short presentation on a topic of your choice.",
        ),
        FunctionSet(
            level="C1",
            function="Negotiating",
            key_phrases=["From our perspective...", "We might consider...", "Let me address that concern...", "I take your point, but..."],
            scenario="Negotiate a salary or contract terms with an employer.",
        ),
        FunctionSet(
            level="C1",
            function="Nuanced Argumentation",
            key_phrases=["While it's true that..., it's equally important to consider...", "Notwithstanding...", "One could argue that..., yet..."],
            scenario="Argue both sides of a complex ethical question.",
        ),
    ],
    "C2": [
        FunctionSet(
            level="C2",
            function="Persuasion & Rhetoric",
            key_phrases=["The evidence compellingly suggests...", "One cannot overlook the fact that...", "It would be remiss to ignore..."],
            scenario="Persuade an audience to adopt a controversial position.",
        ),
        FunctionSet(
            level="C2",
            function="Academic Discourse",
            key_phrases=["This paper argues that...", "The findings indicate a correlation between...", "Notwithstanding these limitations..."],
            scenario="Write the introduction to an academic paper.",
        ),
    ],
}


def grammar_for_level(level: str) -> list[GrammarPoint]:
    return GRAMMAR_CURRICULUM.get(level, [])


def functions_for_level(level: str) -> list[FunctionSet]:
    return FUNCTIONS_CURRICULUM.get(level, [])


def next_level(level: str) -> str | None:
    idx = CEFR_LEVELS.index(level) if level in CEFR_LEVELS else -1
    if idx < 0 or idx >= len(CEFR_LEVELS) - 1:
        return None
    return CEFR_LEVELS[idx + 1]


def grammar_point_by_id(point_id: str) -> GrammarPoint | None:
    for points in GRAMMAR_CURRICULUM.values():
        for gp in points:
            if gp.id == point_id:
                return gp
    return None


# ─── Minimal Pairs for pronunciation training ───
# Research: minimal pairs practice significantly improves pronunciation accuracy
# (Reponte-Sereño et al. 2023, Hamzah & Bawodood 2019)

MINIMAL_PAIRS = [
    {"pair": ("ship", "sheep"), "ipa": ("/ɪ/", "/iː/"), "examples": ("The ship is big.", "The sheep is white.")},
    {"pair": ("bad", "bed"), "ipa": ("/æ/", "/e/"), "examples": ("That's a bad idea.", "Go to bed now.")},
    {"pair": ("full", "fool"), "ipa": ("/ʊ/", "/uː/"), "examples": ("The cup is full.", "Don't be a fool.")},
    {"pair": ("cap", "cup"), "ipa": ("/æ/", "/ʌ/"), "examples": ("Wear a cap.", "Give me a cup.")},
    {"pair": ("live", "leave"), "ipa": ("/ɪ/", "/iː/"), "examples": ("I live here.", "Leave now.")},
    {"pair": ("pull", "pool"), "ipa": ("/ʊ/", "/uː/"), "examples": ("Pull the door.", "Swim in the pool.")},
    {"pair": ("sit", "seat"), "ipa": ("/ɪ/", "/iː/"), "examples": ("Sit down.", "Take a seat.")},
    {"pair": ("bat", "but"), "ipa": ("/æ/", "/ʌ/"), "examples": ("A bat flies.", "But I can't.")},
    {"pair": ("cought", "coat"), "ipa": ("/ɔː/", "/əʊ/"), "examples": ("I caught a cold.", "Wear a coat.")},
    {"pair": ("think", "sink"), "ipa": ("/θ/", "/s/"), "examples": ("Think about it.", "The ship will sink.")},
    {"pair": ("tree", "three"), "ipa": ("/t/", "/θ/"), "examples": ("A tall tree.", "Three apples.")},
    {"pair": ("vest", "best"), "ipa": ("/v/", "/b/"), "examples": ("Wear a vest.", "That's the best.")},
    {"pair": ("light", "night"), "ipa": ("/l/", "/n/"), "examples": ("Turn on the light.", "Good night.")},
    {"pair": ("rice", "lice"), "ipa": ("/r/", "/l/"), "examples": ("Eat some rice.", "Lice is bad.")},
    {"pair": ("berry", "very"), "ipa": ("/b/", "/v/"), "examples": ("A red berry.", "Very good.")},
    {"pair": ("pat", "bat"), "ipa": ("/p/", "/b/"), "examples": ("Pat the dog.", "A bat flies.")},
    {"pair": ("ferry", "fairy"), "ipa": ("/e/", "/eə/"), "examples": ("Take the ferry.", "A fairy tale.")},
    {"pair": ("hat", "hut"), "ipa": ("/æ/", "/ʌ/"), "examples": ("Wear a hat.", "A small hut.")},
    {"pair": ("not", "note"), "ipa": ("/ɒ/", "/əʊ/"), "examples": ("No, not that.", "Write a note.")},
    {"pair": ("walk", "work"), "ipa": ("/ɔː/", "/ɜː/"), "examples": ("Let's walk.", "Go to work.")},
]


def minimal_pairs_for_level(level: str) -> list[dict]:
    """Return minimal pairs suitable for the given level."""
    return MINIMAL_PAIRS


# ─── Phrasal Verbs database (offline) ───
# Based on frequency lists from COCA and BNC corpora

PHRASAL_VERBS = [
    {"verb": "get up", "meaning": "вставать (с постели)", "synonym": "wake up and rise", "example": "I get up at 7 AM every day.", "level": "A1"},
    {"verb": "give up", "meaning": "сдаваться, бросать", "synonym": "quit, surrender", "example": "Don't give up on your dreams.", "level": "A2"},
    {"verb": "go on", "meaning": "продолжать, происходить", "synonym": "continue, happen", "example": "What's going on here?", "level": "A2"},
    {"verb": "look for", "meaning": "искать", "synonym": "search for", "example": "I'm looking for my keys.", "level": "A1"},
    {"verb": "look after", "meaning": "заботиться, присматривать", "synonym": "take care of", "example": "She looks after her grandmother.", "level": "A2"},
    {"verb": "put off", "meaning": "откладывать", "synonym": "postpone, delay", "example": "Don't put off until tomorrow what you can do today.", "level": "B1"},
    {"verb": "take off", "meaning": "снимать, взлетать", "synonym": "remove (clothes), depart (plane)", "example": "The plane takes off at noon.", "level": "A2"},
    {"verb": "turn on", "meaning": "включать", "synonym": "activate, switch on", "example": "Turn on the lights, please.", "level": "A1"},
    {"verb": "turn off", "meaning": "выключать", "synonym": "deactivate, switch off", "example": "Turn off the TV before bed.", "level": "A1"},
    {"verb": "find out", "meaning": "узнавать, выяснять", "synonym": "discover, learn", "example": "I found out the truth yesterday.", "level": "B1"},
    {"verb": "give back", "meaning": "возвращать", "synonym": "return", "example": "Please give back my book.", "level": "A2"},
    {"verb": "go out", "meaning": "выходить, тухнуть", "synonym": "leave home, stop burning", "example": "Let's go out for dinner.", "level": "A2"},
    {"verb": "grow up", "meaning": "вырастать", "synonym": "mature, become an adult", "example": "I grew up in a small town.", "level": "B1"},
    {"verb": "hold on", "meaning": "подождать, держаться", "synonym": "wait, grip", "example": "Hold on, I'll be right there.", "level": "B1"},
    {"verb": "look forward to", "meaning": "ждать с нетерпением", "synonym": "anticipate eagerly", "example": "I look forward to seeing you.", "level": "B1"},
    {"verb": "look up", "meaning": "искать в справочнике", "synonym": "search for information", "example": "Look up the word in the dictionary.", "level": "B1"},
    {"verb": "make up", "meaning": "придумывать, мириться", "synonym": "invent, reconcile", "example": "She made up a funny story.", "level": "B1"},
    {"verb": "pass away", "meaning": "умирать", "synonym": "die (polite)", "example": "His grandfather passed away last year.", "level": "B2"},
    {"verb": "pick up", "meaning": "подбирать, забирать", "synonym": "collect, lift", "example": "I'll pick you up at 8.", "level": "A2"},
    {"verb": "point out", "meaning": "указывать, отмечать", "synonym": "highlight, mention", "example": "She pointed out the mistake.", "level": "B2"},
    {"verb": "put on", "meaning": "надевать", "synonym": "wear, dress", "example": "Put on your coat, it's cold.", "level": "A1"},
    {"verb": "run away", "meaning": "убегать", "synonym": "escape, flee", "example": "The dog ran away from home.", "level": "A2"},
    {"verb": "run out of", "meaning": "заканчиваться (иссякать)", "synonym": "exhaust supply", "example": "We ran out of milk.", "level": "B1"},
    {"verb": "set up", "meaning": "настраивать, учреждать", "synonym": "establish, configure", "example": "I set up my new computer.", "level": "B1"},
    {"verb": "show up", "meaning": "появляться, приходить", "synonym": "arrive, appear", "example": "He showed up late again.", "level": "B1"},
    {"verb": "stand up", "meaning": "вставать", "synonym": "rise to one's feet", "example": "Please stand up for the national anthem.", "level": "A1"},
    {"verb": "take after", "meaning": "быть похожим на", "synonym": "resemble (family)", "example": "She takes after her mother.", "level": "B1"},
    {"verb": "take back", "meaning": "забирать обратно", "synonym": "reclaim, withdraw", "example": "I take back what I said.", "level": "B2"},
    {"verb": "think over", "meaning": "обдумывать", "synonym": "consider carefully", "example": "Let me think it over.", "level": "B1"},
    {"verb": "try on", "meaning": "мерить", "synonym": "test fit (clothes)", "example": "Can I try on this jacket?", "level": "A2"},
    {"verb": "turn down", "meaning": "отклонять, убавлять", "synonym": "reject, lower volume", "example": "They turned down my offer.", "level": "B1"},
    {"verb": "turn up", "meaning": "появляться, увеличивать", "synonym": "arrive unexpectedly, increase", "example": "He turned up at the party.", "level": "B2"},
    {"verb": "wake up", "meaning": "просыпаться", "synonym": "awaken", "example": "I wake up early on weekdays.", "level": "A1"},
    {"verb": "work out", "meaning": "тренироваться, получаться", "synonym": "exercise, resolve", "example": "I work out three times a week.", "level": "B1"},
    {"verb": "break down", "meaning": "ломаться, разрушаться", "synonym": "stop working, collapse", "example": "My car broke down on the highway.", "level": "B1"},
    {"verb": "bring up", "meaning": "воспитывать, поднимать тему", "synonym": "raise (children), mention", "example": "She was brought up by her aunt.", "level": "B2"},
    {"verb": "call off", "meaning": "отменять", "synonym": "cancel", "example": "They called off the meeting.", "level": "B1"},
    {"verb": "carry on", "meaning": "продолжать", "synonym": "continue", "example": "Carry on with your work.", "level": "B1"},
    {"verb": "come across", "meaning": "наталкиваться, случайно встретить", "synonym": "find by chance", "example": "I came across an old photo.", "level": "B2"},
    {"verb": "count on", "meaning": "полагаться на", "synonym": "rely on, depend on", "example": "You can count on me.", "level": "B1"},
    {"verb": "deal with", "meaning": "иметь дело с, справляться", "synonym": "handle, manage", "example": "How do you deal with stress?", "level": "B1"},
    {"verb": "drop in", "meaning": "заскочить, навестить", "synonym": "visit unexpectedly", "example": "Drop in anytime you're nearby.", "level": "B2"},
    {"verb": "figure out", "meaning": "разобраться, понять", "synonym": "understand, solve", "example": "I can't figure out this puzzle.", "level": "B1"},
    {"verb": "get along", "meaning": "ладить", "synonym": "have good relations", "example": "They get along well.", "level": "B1"},
    {"verb": "get over", "meaning": "пережить, оправиться", "synonym": "recover from", "example": "It took time to get over the flu.", "level": "B2"},
    {"verb": "get together", "meaning": "собираться вместе", "synonym": "meet, gather", "example": "Let's get together next weekend.", "level": "B1"},
    {"verb": "keep up", "meaning": "поддерживать, не отставать", "synonym": "maintain pace", "example": "Keep up the good work!", "level": "B1"},
    {"verb": "look down on", "meaning": "смотреть свысока", "synonym": "despise, feel superior", "example": "Don't look down on others.", "level": "B2"},
    {"verb": "look out", "meaning": "остерегаться", "synonym": "be careful, watch out", "example": "Look out! There's a car coming.", "level": "B1"},
    {"verb": "make sure", "meaning": "убедиться", "synonym": "verify, confirm", "example": "Make sure the door is locked.", "level": "A2"},
    {"verb": "pull over", "meaning": "прижаться к обочине", "synonym": "stop vehicle by the road", "example": "The police asked him to pull over.", "level": "B2"},
    {"verb": "put away", "meaning": "убирать на место", "synonym": "store, tidy", "example": "Put away your toys.", "level": "A2"},
    {"verb": "run into", "meaning": "случайно встретить", "synonym": "bump into, meet unexpectedly", "example": "I ran into an old friend today.", "level": "B1"},
    {"verb": "sort out", "meaning": "разбираться, улаживать", "synonym": "resolve, organize", "example": "We need to sort out this problem.", "level": "B2"},
    {"verb": "take apart", "meaning": "разбирать на части", "synonym": "disassemble", "example": "He took apart the clock to fix it.", "level": "B2"},
    {"verb": "throw away", "meaning": "выбрасывать", "synonym": "discard, dispose", "example": "Don't throw away those papers.", "level": "A2"},
    {"verb": "try out", "meaning": "пробовать, тестировать", "synonym": "test, experiment", "example": "Try out the new app.", "level": "B1"},
    {"verb": "wear out", "meaning": "изнашивать(ся)", "synonym": "exhaust, use until worn", "example": "My shoes are worn out.", "level": "B2"},
]


def phrasal_verbs_for_level(level: str) -> list[dict]:
    """Return phrasal verbs suitable for the given level."""
    level_idx = CEFR_LEVELS.index(level) if level in CEFR_LEVELS else 3
    return [pv for pv in PHRASAL_VERBS if CEFR_LEVELS.index(pv["level"]) <= level_idx]


# ─── Collocations database (offline) ───
# Based on Oxford Collocations Dictionary and BNC frequency data

COLOCATIONS = [
    {"adjective": "heavy", "noun": "rain", "example": "We had heavy rain last night.", "level": "A2"},
    {"adjective": "heavy", "noun": "traffic", "example": "There was heavy traffic this morning.", "level": "A2"},
    {"adjective": "heavy", "noun": "smoker", "example": "My father is a heavy smoker.", "level": "B1"},
    {"adjective": "strong", "noun": "wind", "example": "A strong wind blew all night.", "level": "A2"},
    {"adjective": "strong", "noun": "coffee", "example": "I like strong coffee in the morning.", "level": "A2"},
    {"adjective": "strong", "noun": "opinion", "example": "She has strong opinions on politics.", "level": "B1"},
    {"adjective": "deep", "noun": "breath", "example": "Take a deep breath and relax.", "level": "B1"},
    {"adjective": "deep", "noun": "thought", "example": "He was lost in deep thought.", "level": "B1"},
    {"adjective": "high", "noun": "price", "example": "Houses have high prices here.", "level": "A2"},
    {"adjective": "high", "noun": "speed", "example": "The train moves at high speed.", "level": "A2"},
    {"adjective": "bright", "noun": "future", "example": "She has a bright future ahead.", "level": "B1"},
    {"adjective": "bright", "noun": "idea", "example": "That's a bright idea!", "level": "B1"},
    {"adjective": "sharp", "noun": "turn", "example": "There's a sharp turn ahead.", "level": "B1"},
    {"adjective": "sharp", "noun": "pain", "example": "I felt a sharp pain in my chest.", "level": "B1"},
    {"adjective": "soft", "noun": "voice", "example": "She spoke in a soft voice.", "level": "B1"},
    {"adjective": "soft", "noun": "rain", "example": "Soft rain fell on the roof.", "level": "B2"},
    {"adjective": "hard", "noun": "work", "example": "Building a house is hard work.", "level": "A2"},
    {"adjective": "hard", "noun": "rain", "example": "It's raining hard outside.", "level": "A2"},
    {"adjective": "light", "noun": "rain", "example": "There's light rain forecast today.", "level": "B1"},
    {"adjective": "light", "noun": "sleeper", "example": "I'm a light sleeper.", "level": "B1"},
    {"adjective": "fast", "noun": "food", "example": "Fast food is not very healthy.", "level": "A2"},
    {"adjective": "fast", "noun": "pace", "example": "We walked at a fast pace.", "level": "B1"},
    {"adjective": "broad", "noun": "shoulders", "example": "He has broad shoulders.", "level": "B1"},
    {"adjective": "broad", "noun": "smile", "example": "She gave a broad smile.", "level": "B1"},
    {"adjective": "wild", "noun": "animals", "example": "Wild animals live in the forest.", "level": "A2"},
    {"adjective": "wild", "noun": "guess", "example": "That's a wild guess.", "level": "B2"},
    {"adjective": "flat", "noun": "tyre", "example": "We got a flat tyre on the road.", "level": "B1"},
    {"adjective": "flat", "noun": "refusal", "example": "She gave a flat refusal.", "level": "B2"},
    {"adjective": "dry", "noun": "weather", "example": "We've had dry weather all week.", "level": "A2"},
    {"adjective": "dry", "noun": "humour", "example": "He has a dry sense of humour.", "level": "B2"},
    {"adjective": "fresh", "noun": "air", "example": "Let's get some fresh air.", "level": "A2"},
    {"adjective": "fresh", "noun": "start", "example": "It's a fresh start for everyone.", "level": "B1"},
    {"adjective": "close", "noun": "friend", "example": "She is a close friend of mine.", "level": "A2"},
    {"adjective": "close", "noun": "call", "example": "That was a close call!", "level": "B1"},
    {"adjective": "common", "noun": "mistake", "example": "That's a common mistake.", "level": "B1"},
    {"adjective": "common", "noun": "knowledge", "example": "It's common knowledge that...", "level": "B1"},
    {"adjective": "main", "noun": "reason", "example": "The main reason is cost.", "level": "A2"},
    {"adjective": "main", "noun": "course", "example": "What's the main course?", "level": "B1"},
    {"adjective": "public", "noun": "transport", "example": "I use public transport every day.", "level": "A2"},
    {"adjective": "public", "noun": "opinion", "example": "Public opinion is divided.", "level": "B2"},
    {"adjective": "social", "noun": "media", "example": "Social media is everywhere now.", "level": "B1"},
    {"adjective": "social", "noun": "life", "example": "She has an active social life.", "level": "B1"},
    {"adjective": "vital", "noun": "role", "example": "He played a vital role in the project.", "level": "B2"},
    {"adjective": "vital", "noun": "information", "example": "This is vital information.", "level": "B2"},
    {"adjective": "key", "noun": "factor", "example": "Money is a key factor.", "level": "B1"},
    {"adjective": "key", "noun": "issue", "example": "Let's discuss the key issues.", "level": "B2"},
    {"adjective": "major", "noun": "problem", "example": "We have a major problem.", "level": "B1"},
    {"adjective": "major", "noun": "change", "example": "There was a major change in plans.", "level": "B1"},
    {"adjective": "minor", "noun": "injury", "example": "He suffered a minor injury.", "level": "B2"},
    {"adjective": "minor", "noun": "issue", "example": "It's just a minor issue.", "level": "B2"},
    {"adjective": "absolute", "noun": "disaster", "example": "The party was an absolute disaster.", "level": "B2"},
    {"adjective": "absolute", "noun": "silence", "example": "There was absolute silence.", "level": "B2"},
]


def collocations_for_level(level: str) -> list[dict]:
    """Return collocations suitable for the given level."""
    level_idx = CEFR_LEVELS.index(level) if level in CEFR_LEVELS else 3
    return [c for c in COLOCATIONS if CEFR_LEVELS.index(c["level"]) <= level_idx]


# ─── Common errors database (for Error Correction mode) ───
# Based on Cambridge Learner Corpus error analysis

COMMON_ERRORS = [
    {"wrong": "I am agree with you.", "correct": "I agree with you.", "type": "grammar", "explanation": "Agree — это глагол, не нужен am. Не путайте с 'I am sure'."},
    {"wrong": "She has 20 years.", "correct": "She is 20 years old.", "type": "grammar", "explanation": "Возраст по-английски: be + age + years old, не have."},
    {"wrong": "I have visited London in 2019.", "correct": "I visited London in 2019.", "type": "tense", "explanation": "Past Simple для конкретного времени в прошлом. Present Perfect не используется с точным временем."},
    {"wrong": "He is more taller than me.", "correct": "He is taller than me.", "type": "grammar", "explanation": "Сравнительная степень tall → taller. Не нужно more перед -er."},
    {"wrong": "I want that you help me.", "correct": "I want you to help me.", "type": "grammar", "explanation": "Конструкция want + object + to + verb. Не want that."},
    {"wrong": "I am living here since 2020.", "correct": "I have been living here since 2020.", "type": "tense", "explanation": "Present Perfect Continuous для действия, начавшегося в прошлом и продолжающегося."},
    {"wrong": "There is many people here.", "correct": "There are many people here.", "type": "grammar", "explanation": "People — множественное число, нужно are, не is."},
    {"wrong": "I have been to Paris two times.", "correct": "I have been to Paris twice.", "type": "vocabulary", "explanation": "Twice вместо two times. Thrice не используется — three times."},
    {"wrong": "She said me that she was tired.", "correct": "She told me that she was tired.", "type": "grammar", "explanation": "Say без объекта, tell с объектом: tell somebody something."},
    {"wrong": "I am interesting in art.", "correct": "I am interested in art.", "type": "grammar", "explanation": "Interested (как я чувствую) vs interesting (как объект). 'I am interested, art is interesting.'"},
    {"wrong": "If I will have time, I will call you.", "correct": "If I have time, I will call you.", "type": "grammar", "explanation": "First Conditional: If + Present Simple, will + verb. Не will в if-clause."},
    {"wrong": "I look forward to hear from you.", "correct": "I look forward to hearing from you.", "type": "grammar", "explanation": "Look forward to + gerund (-ing). To здесь — предлог, не инфинитив."},
    {"wrong": "The news are good.", "correct": "The news is good.", "type": "grammar", "explanation": "News — неисчисляемое, всегда is. Хотя выглядит как множественное."},
    {"wrong": "I have a 5-years-old son.", "correct": "I have a 5-year-old son.", "type": "grammar", "explanation": "Составные прилагательные: единственное число между дефисами: 5-year-old."},
    {"wrong": "He suggested me to go home.", "correct": "He suggested that I go home.", "type": "grammar", "explanation": "Suggest не используется с to + infinitive. Suggest that + clause или suggest + gerund."},
    {"wrong": "I am used to live in a big city.", "correct": "I am used to living in a big city.", "type": "grammar", "explanation": "Be used to + gerund. 'Привык жить' — living, не live."},
    {"wrong": "Despite of the rain, we went out.", "correct": "Despite the rain, we went out.", "type": "grammar", "explanation": "Despite без of. In spite of — с of. Despite = in spite of."},
    {"wrong": "I have been working since two hours.", "correct": "I have been working for two hours.", "type": "preposition", "explanation": "Since — с точкой отсчёта (since 5 PM). For — с длительностью (for 2 hours)."},
    {"wrong": "Can you borrow me some money?", "correct": "Can you lend me some money?", "type": "vocabulary", "explanation": "Borrow = взять в долг (от кого-то). Lend = дать в долг (кому-то)."},
    {"wrong": "I don't know what does it mean.", "correct": "I don't know what it means.", "type": "word_order", "explanation": "Косвенный вопрос: прямой порядок слов. Не what does it mean, а what it means."},
]


def common_errors_for_level(level: str) -> list[dict]:
    """Return common errors for the given level."""
    return COMMON_ERRORS
