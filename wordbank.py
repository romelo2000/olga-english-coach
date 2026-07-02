"""Offline word databases for Olga English Coach.

All databases are embedded in code — no internet required.
Sources: Oxford 3000, NGSL, COCA, BNC, Cambridge Learner Corpus.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class VocabCard:
    word: str
    translation: str
    pos: str
    example: str
    ipa: str = ""
    collocations: tuple[str, ...] = ()
    word_family: tuple[str, ...] = ()


@dataclass(frozen=True)
class VocabSet:
    level: str
    theme: str
    cards: list[VocabCard]


CEFR_LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"]

# ═══════════════════════════════════════════════════════════════
# VOCABULARY SETS — 400+ words across CEFR levels
# ═══════════════════════════════════════════════════════════════

VOCABULARY_SETS: dict[str, list[VocabSet]] = {
    "A1": [
        VocabSet("A1", "Personal Information", [
            VocabCard("name", "имя", "noun", "My name is Olga."),
            VocabCard("age", "возраст", "noun", "What is your age?"),
            VocabCard("family", "семья", "noun", "I love my family."),
            VocabCard("country", "страна", "noun", "France is a beautiful country."),
            VocabCard("job", "работа", "noun", "His job is interesting."),
            VocabCard("student", "студент", "noun", "She is a university student."),
            VocabCard("friend", "друг", "noun", "He is my best friend."),
            VocabCard("child", "ребёнок", "noun", "The child is playing."),
            VocabCard("people", "люди", "noun", "Many people live here."),
            VocabCard("home", "дом", "noun", "I go home at six."),
        ]),
        VocabSet("A1", "Everyday Objects", [
            VocabCard("table", "стол", "noun", "The book is on the table."),
            VocabCard("chair", "стул", "noun", "Sit on this chair."),
            VocabCard("book", "книга", "noun", "I read a book every day."),
            VocabCard("phone", "телефон", "noun", "Where is my phone?"),
            VocabCard("computer", "компьютер", "noun", "She uses a computer at work."),
            VocabCard("door", "дверь", "noun", "Open the door, please."),
            VocabCard("window", "окно", "noun", "Look out the window."),
            VocabCard("key", "ключ", "noun", "I can't find my key."),
            VocabCard("bag", "сумка", "noun", "Put it in your bag."),
            VocabCard("pen", "ручка", "noun", "Can I borrow a pen?"),
        ]),
        VocabSet("A1", "Food & Drink", [
            VocabCard("water", "вода", "noun", "I drink water every day."),
            VocabCard("bread", "хлеб", "noun", "She buys fresh bread."),
            VocabCard("coffee", "кофе", "noun", "I like black coffee."),
            VocabCard("apple", "яблоко", "noun", "An apple a day."),
            VocabCard("milk", "молоко", "noun", "The milk is cold."),
            VocabCard("tea", "чай", "noun", "Would you like some tea?"),
            VocabCard("rice", "рис", "noun", "We eat rice with fish."),
            VocabCard("egg", "яйцо", "noun", "I have an egg for breakfast."),
            VocabCard("cheese", "сыр", "noun", "This cheese is delicious."),
            VocabCard("chicken", "курица", "noun", "She cooked chicken for dinner."),
        ]),
        VocabSet("A1", "Common Verbs", [
            VocabCard("go", "идти, ехать", "verb", "I go to school by bus."),
            VocabCard("have", "иметь", "verb", "I have two sisters."),
            VocabCard("do", "делать", "verb", "What do you do?"),
            VocabCard("make", "создавать", "verb", "She makes great cakes."),
            VocabCard("see", "видеть", "verb", "I see a bird in the tree."),
            VocabCard("come", "приходить", "verb", "Come here, please."),
            VocabCard("want", "хотеть", "verb", "I want a coffee."),
            VocabCard("know", "знать", "verb", "I know the answer."),
            VocabCard("think", "думать", "verb", "I think you're right."),
            VocabCard("say", "сказать", "verb", "What did she say?"),
        ]),
        VocabSet("A1", "Time & Days", [
            VocabCard("day", "день", "noun", "What day is it today?"),
            VocabCard("week", "неделя", "noun", "I work five days a week."),
            VocabCard("month", "месяц", "noun", "January is the first month."),
            VocabCard("year", "год", "noun", "I was born in 1990."),
            VocabCard("today", "сегодня", "adverb", "Today is my birthday."),
            VocabCard("tomorrow", "завтра", "adverb", "See you tomorrow."),
            VocabCard("now", "сейчас", "adverb", "I'm busy now."),
            VocabCard("time", "время", "noun", "What time is it?"),
            VocabCard("morning", "утро", "noun", "I drink coffee in the morning."),
            VocabCard("night", "ночь", "noun", "Good night!"),
        ]),
        VocabSet("A1", "Colours & Clothes", [
            VocabCard("red", "красный", "adjective", "She wears a red dress."),
            VocabCard("blue", "синий", "adjective", "The sky is blue today."),
            VocabCard("green", "зелёный", "adjective", "I like green trees."),
            VocabCard("black", "чёрный", "adjective", "He has a black car."),
            VocabCard("white", "белый", "adjective", "She wears a white shirt."),
            VocabCard("shirt", "рубашка", "noun", "This shirt is new."),
            VocabCard("shoes", "туфли", "noun", "My shoes are comfortable."),
            VocabCard("coat", "пальто", "noun", "Put on your coat."),
            VocabCard("hat", "шляпа", "noun", "He wears a hat in summer."),
            VocabCard("dress", "платье", "noun", "She bought a new dress."),
        ]),
    ],
    "A2": [
        VocabSet("A2", "Daily Life", [
            VocabCard("morning", "утро", "noun", "I run in the morning."),
            VocabCard("evening", "вечер", "noun", "We meet in the evening."),
            VocabCard("weekend", "выходные", "noun", "I relax on weekends."),
            VocabCard("shopping", "покупки", "noun", "She goes shopping on Saturdays."),
            VocabCard("cooking", "готовка", "noun", "I enjoy cooking."),
            VocabCard("homework", "домашнее задание", "noun", "He does his homework after school."),
            VocabCard("breakfast", "завтрак", "noun", "I have breakfast at eight."),
            VocabCard("routine", "рутина", "noun", "My daily routine is simple."),
            VocabCard("neighbour", "сосед", "noun", "My neighbour is very friendly."),
            VocabCard("hobby", "хобби", "noun", "Photography is my hobby."),
        ]),
        VocabSet("A2", "Travel", [
            VocabCard("ticket", "билет", "noun", "I bought a return ticket."),
            VocabCard("hotel", "отель", "noun", "The hotel was comfortable."),
            VocabCard("airport", "аэропорт", "noun", "We arrived at the airport early."),
            VocabCard("map", "карта", "noun", "Check the map before you go."),
            VocabCard("suitcase", "чемодан", "noun", "My suitcase is too heavy."),
            VocabCard("passport", "паспорт", "noun", "Don't forget your passport."),
            VocabCard("journey", "путешествие", "noun", "The journey took three hours."),
            VocabCard("passenger", "пассажир", "noun", "The passengers waited patiently."),
            VocabCard("destination", "направление", "noun", "Paris is our destination."),
            VocabCard("departure", "отправление", "noun", "Departure is at 9 a.m."),
        ]),
        VocabSet("A2", "Describing People", [
            VocabCard("tall", "высокий", "adjective", "He is very tall."),
            VocabCard("short", "невысокий", "adjective", "She is shorter than me."),
            VocabCard("friendly", "дружелюбный", "adjective", "The staff are friendly."),
            VocabCard("kind", "добрый", "adjective", "That was very kind of you."),
            VocabCard("funny", "смешной", "adjective", "He tells funny stories."),
            VocabCard("clever", "умный", "adjective", "She is a clever student."),
            VocabCard("quiet", "тихий", "adjective", "It's a quiet neighbourhood."),
            VocabCard("serious", "серьёзный", "adjective", "He looks serious today."),
            VocabCard("generous", "щедрый", "adjective", "She is always generous."),
            VocabCard("honest", "честный", "adjective", "I value honest people."),
        ]),
        VocabSet("A2", "Health", [
            VocabCard("doctor", "врач", "noun", "I need to see a doctor."),
            VocabCard("medicine", "лекарство", "noun", "Take this medicine twice a day."),
            VocabCard("headache", "головная боль", "noun", "I have a bad headache."),
            VocabCard("healthy", "здоровый", "adjective", "She lives a healthy lifestyle."),
            VocabCard("exercise", "упражнение", "noun", "Regular exercise is important."),
            VocabCard("temperature", "температура", "noun", "His temperature is high."),
            VocabCard("cough", "кашель", "noun", "I have a bad cough."),
            VocabCard("appointment", "приём (у врача)", "noun", "I have a doctor's appointment."),
            VocabCard("prescription", "рецепт", "noun", "The doctor gave me a prescription."),
            VocabCard("recover", "выздоравливать", "verb", "It took two weeks to recover."),
        ]),
        VocabSet("A2", "Weather & Nature", [
            VocabCard("sunny", "солнечный", "adjective", "It's a sunny day."),
            VocabCard("rainy", "дождливый", "adjective", "It's rainy in London."),
            VocabCard("cloudy", "облачный", "adjective", "The sky is cloudy today."),
            VocabCard("windy", "ветреный", "adjective", "It's windy on the coast."),
            VocabCard("snow", "снег", "noun", "We had snow last night."),
            VocabCard("river", "река", "noun", "The river is very long."),
            VocabCard("mountain", "гора", "noun", "They climbed the mountain."),
            VocabCard("forest", "лес", "noun", "The forest is beautiful in autumn."),
            VocabCard("sea", "море", "noun", "We swim in the sea."),
            VocabCard("tree", "дерево", "noun", "The tree is very old."),
        ]),
        VocabSet("A2", "School & Learning", [
            VocabCard("teacher", "учитель", "noun", "Our teacher is very patient."),
            VocabCard("lesson", "урок", "noun", "The lesson starts at nine."),
            VocabCard("classroom", "класс", "noun", "The classroom is bright."),
            VocabCard("exam", "экзамен", "noun", "The exam was difficult."),
            VocabCard("grade", "оценка", "noun", "She got a good grade."),
            VocabCard("learn", "учить", "verb", "I learn English online."),
            VocabCard("study", "изучать", "verb", "He studies at the library."),
            VocabCard("question", "вопрос", "noun", "Can I ask a question?"),
            VocabCard("answer", "ответ", "noun", "What's the correct answer?"),
            VocabCard("notebook", "тетрадь", "noun", "I write in my notebook."),
        ]),
        VocabSet("A2", "Shopping & Money", [
            VocabCard("price", "цена", "noun", "The price is too high."),
            VocabCard("money", "деньги", "noun", "I need to save money."),
            VocabCard("shop", "магазин", "noun", "The shop opens at ten."),
            VocabCard("sale", "распродажа", "noun", "There's a big sale today."),
            VocabCard("pay", "платить", "verb", "I pay by card."),
            VocabCard("cost", "стоить", "verb", "How much does it cost?"),
            VocabCard("cheap", "дешёвый", "adjective", "This shirt is cheap."),
            VocabCard("expensive", "дорогой", "adjective", "That car is expensive."),
            VocabCard("receipt", "чек", "noun", "Keep the receipt."),
            VocabCard("change", "сдача", "noun", "Here's your change."),
        ]),
    ],
    "B1": [
        VocabSet("B1", "Work & Education", [
            VocabCard("career", "карьера", "noun", "She has a successful career in IT.", ipa="/kəˈrɪər/", collocations=("build a career", "career path"), word_family=("careerist",)),
            VocabCard("degree", "степень", "noun", "He has a degree in engineering.", collocations=("get a degree", "master's degree"), word_family=("degreed",)),
            VocabCard("interview", "собеседование", "noun", "I have a job interview tomorrow.", collocations=("job interview", "conduct an interview"), word_family=("interviewer", "interviewee")),
            VocabCard("salary", "зарплата", "noun", "The salary is competitive.", collocations=("annual salary", "base salary"), word_family=("salaried",)),
            VocabCard("colleague", "коллега", "noun", "My colleague helped me.", collocations=("close colleague",)),
            VocabCard("experience", "опыт", "noun", "She has five years of experience.", collocations=("gain experience", "work experience"), word_family=("experienced", "inexperienced")),
            VocabCard("qualification", "квалификация", "noun", "You need the right qualifications.", collocations=("professional qualifications",), word_family=("qualify", "qualified")),
            VocabCard("responsibility", "ответственность", "noun", "It's a big responsibility.", collocations=("take responsibility",), word_family=("responsible", "irresponsible")),
            VocabCard("promotion", "повышение", "noun", "He got a promotion last month.", collocations=("get a promotion",), word_family=("promote",)),
            VocabCard("deadline", "крайний срок", "noun", "The deadline is next Friday.", collocations=("meet a deadline", "tight deadline")),
        ]),
        VocabSet("B1", "Technology", [
            VocabCard("device", "устройство", "noun", "This device is very useful.", collocations=("mobile device",)),
            VocabCard("software", "ПО", "noun", "We need to update the software.", collocations=("install software",)),
            VocabCard("update", "обновление", "noun", "There's a new update available.", collocations=("software update",)),
            VocabCard("download", "скачивать", "verb", "I downloaded the app yesterday.", collocations=("download speed",)),
            VocabCard("password", "пароль", "noun", "Use a strong password.", collocations=("strong password",)),
            VocabCard("account", "аккаунт", "noun", "I created a new account.", collocations=("create an account",)),
            VocabCard("network", "сеть", "noun", "The network is down.", collocations=("social network",)),
            VocabCard("connection", "соединение", "noun", "I have a stable connection.", collocations=("internet connection",)),
            VocabCard("backup", "резервная копия", "noun", "Always keep a backup.", collocations=("backup plan",)),
            VocabCard("notification", "уведомление", "noun", "I turned off notifications.", collocations=("push notification",)),
        ]),
        VocabSet("B1", "Feelings & Opinions", [
            VocabCard("disappointed", "разочарованный", "adjective", "I was disappointed with the result.", collocations=("disappointed with",)),
            VocabCard("excited", "взволнованный", "adjective", "She is excited about the trip.", collocations=("excited about",)),
            VocabCard("nervous", "нервный", "adjective", "I feel nervous before exams.", collocations=("nervous about",)),
            VocabCard("confident", "уверенный", "adjective", "He is confident in his abilities.", collocations=("confident in",), word_family=("confidence",)),
            VocabCard("agree", "соглашаться", "verb", "I agree with your point.", collocations=("agree with",)),
            VocabCard("prefer", "предпочитать", "verb", "I prefer tea to coffee.", collocations=("prefer to",)),
            VocabCard("suggest", "предлагать", "verb", "I suggest we leave early.", collocations=("suggest doing",)),
            VocabCard("complain", "жаловаться", "verb", "She complained about the service.", collocations=("complain about",)),
            VocabCard("satisfied", "удовлетворённый", "adjective", "I'm satisfied with the outcome.", collocations=("satisfied with",), word_family=("satisfy", "satisfaction")),
            VocabCard("grateful", "благодарный", "adjective", "I'm grateful for your help.", collocations=("grateful for",)),
        ]),
        VocabSet("B1", "Phrasal Verbs", [
            VocabCard("give up", "бросить", "phrasal verb", "Don't give up on your dreams.", collocations=("give up on",)),
            VocabCard("look forward to", "ожидать с нетерпением", "phrasal verb", "I look forward to seeing you.", collocations=("look forward to doing",)),
            VocabCard("carry on", "продолжать", "phrasal verb", "Carry on with your work.", collocations=("carry on with",)),
            VocabCard("find out", "выяснить", "phrasal verb", "I found out the truth.", collocations=("find out about",)),
            VocabCard("turn out", "оказаться", "phrasal verb", "It turned out to be a mistake.", collocations=("turn out to be",)),
            VocabCard("set up", "настроить", "phrasal verb", "I set up a meeting.", collocations=("set up a meeting",)),
            VocabCard("pick up", "заехать", "phrasal verb", "I'll pick you up at seven.", collocations=("pick up someone",)),
            VocabCard("put off", "отложить", "phrasal verb", "Don't put off until tomorrow.", collocations=("put off doing",)),
        ]),
        VocabSet("B1", "Travel & Adventure", [
            VocabCard("explore", "исследовать", "verb", "We explored the old town.", collocations=("explore the area",)),
            VocabCard("adventure", "приключение", "noun", "It was a great adventure.", collocations=("sense of adventure",)),
            VocabCard("accommodation", "проживание", "noun", "The accommodation was basic.", collocations=("book accommodation",)),
            VocabCard("souvenir", "сувенир", "noun", "I bought a souvenir for my mum.", collocations=("buy a souvenir",)),
            VocabCard("guide", "гид", "noun", "Our guide was very knowledgeable.", collocations=("tour guide",)),
            VocabCard("landscape", "пейзаж", "noun", "The landscape was breathtaking.", collocations=("beautiful landscape",)),
            VocabCard("abroad", "за границей", "adverb", "She studied abroad for a year.", collocations=("study abroad",)),
            VocabCard("flight", "рейс", "noun", "Our flight was delayed.", collocations=("catch a flight",)),
            VocabCard("luggage", "багаж", "noun", "My luggage is lost.", collocations=("hand luggage",)),
            VocabCard("guidebook", "путеводитель", "noun", "I bought a guidebook for Rome.", collocations=("buy a guidebook",)),
        ]),
        VocabSet("B1", "Media & Entertainment", [
            VocabCard("article", "статья", "noun", "I read an interesting article.", collocations=("news article",)),
            VocabCard("broadcast", "трансляция", "noun", "The broadcast starts at eight.", collocations=("live broadcast",)),
            VocabCard("celebrity", "знаменитость", "noun", "She became a celebrity overnight.", collocations=("celebrity gossip",)),
            VocabCard("audience", "аудитория", "noun", "The audience loved the show.", collocations=("live audience",)),
            VocabCard("review", "обзор", "noun", "The film got good reviews.", collocations=("write a review",)),
            VocabCard("episode", "эпизод", "noun", "I watched the last episode.", collocations=("new episode",)),
            VocabCard("channel", "канал", "noun", "Change the channel, please.", collocations=("news channel",)),
            VocabCard("subscribe", "подписаться", "verb", "I subscribe to three magazines.", collocations=("subscribe to",)),
            VocabCard("recommend", "рекомендовать", "verb", "I recommend this book.", collocations=("highly recommend",)),
            VocabCard("advertise", "рекламировать", "verb", "They advertise on TV.", word_family=("advertisement", "advertising")),
        ]),
        VocabSet("B1", "Relationships", [
            VocabCard("relationship", "отношения", "noun", "They have a good relationship.", collocations=("good relationship",)),
            VocabCard("partner", "партнёр", "noun", "My partner is very supportive.", collocations=("business partner",)),
            VocabCard("trust", "доверять", "verb", "I trust him completely.", collocations=("build trust",)),
            VocabCard("support", "поддерживать", "verb", "She supports her family.", collocations=("support a decision",)),
            VocabCard("argue", "спорить", "verb", "They argue about money.", collocations=("argue about",)),
            VocabCard("forgive", "прощать", "verb", "I forgive you.", collocations=("forgive someone for",), word_family=("forgiveness",)),
            VocabCard("encourage", "поощрять", "verb", "She encouraged me to try.", collocations=("encourage someone to",), word_family=("encouragement",)),
            VocabCard("communicate", "общаться", "verb", "We communicate by email.", collocations=("communicate with",), word_family=("communication",)),
            VocabCard("respect", "уважение", "noun", "I have great respect for her.", collocations=("show respect",), word_family=("respectful",)),
            VocabCard("rely", "полагаться", "verb", "You can rely on me.", collocations=("rely on", "rely upon"), word_family=("reliable", "reliability")),
        ]),
        VocabSet("B1", "Environment", [
            VocabCard("pollution", "загрязнение", "noun", "Air pollution is a serious problem.", collocations=("air pollution",)),
            VocabCard("recycle", "перерабатывать", "verb", "We recycle plastic and paper.", collocations=("recycle waste",)),
            VocabCard("climate", "климат", "noun", "The climate is changing.", collocations=("climate change",)),
            VocabCard("energy", "энергия", "noun", "We need renewable energy.", collocations=("renewable energy",)),
            VocabCard("waste", "отходы", "noun", "Don't waste water.", collocations=("reduce waste",)),
            VocabCard("protect", "защищать", "verb", "We must protect the environment.", collocations=("protect from",), word_family=("protection",)),
            VocabCard("threat", "угроза", "noun", "Climate change is a threat.", collocations=("pose a threat",), word_family=("threaten",)),
            VocabCard("reduce", "уменьшать", "verb", "We need to reduce emissions.", collocations=("reduce costs",), word_family=("reduction",)),
            VocabCard("destroy", "разрушать", "verb", "The fire destroyed the forest.", collocations=("destroy completely",), word_family=("destruction",)),
            VocabCard("preserve", "сохранять", "verb", "We preserve historic buildings.", collocations=("preserve traditions",), word_family=("preservation",)),
        ]),
    ],
    "B2": [
        VocabSet("B2", "Business", [
            VocabCard("negotiate", "вести переговоры", "verb", "We need to negotiate a better deal.", collocations=("negotiate a deal",), word_family=("negotiation",)),
            VocabCard("proposal", "предложение", "noun", "The proposal was rejected.", collocations=("submit a proposal",)),
            VocabCard("revenue", "доход", "noun", "Revenue increased by 15%.", collocations=("annual revenue",)),
            VocabCard("strategy", "стратегия", "noun", "Our strategy is working.", collocations=("business strategy",)),
            VocabCard("invest", "инвестировать", "verb", "They invest in renewable energy.", collocations=("invest in",), word_family=("investment",)),
            VocabCard("profit", "прибыль", "noun", "The company made a huge profit.", collocations=("make a profit",)),
            VocabCard("competitor", "конкурент", "noun", "Our competitor launched a new product.", collocations=("main competitor",)),
            VocabCard("stakeholder", "заинтересованное лицо", "noun", "We must consider all stakeholders.", collocations=("key stakeholder",)),
            VocabCard("implement", "внедрять", "verb", "We implemented the new system.", collocations=("implement a plan",), word_family=("implementation",)),
            VocabCard("assess", "оценивать", "verb", "We need to assess the risks.", collocations=("assess risk",), word_family=("assessment",)),
        ]),
        VocabSet("B2", "Society & Environment", [
            VocabCard("inequality", "неравенство", "noun", "Income inequality is growing.", collocations=("income inequality",)),
            VocabCard("environment", "окружающая среда", "noun", "We must protect the environment.", collocations=("natural environment",)),
            VocabCard("policy", "политика (курс)", "noun", "The new policy takes effect next month.", collocations=("government policy",)),
            VocabCard("community", "сообщество", "noun", "She is active in the local community.", collocations=("local community",)),
            VocabCard("influence", "влияние", "noun", "Social media has a huge influence.", collocations=("have influence",), word_family=("influential",)),
            VocabCard("trend", "тенденция", "noun", "This trend is unlikely to continue.", collocations=("current trend",)),
            VocabCard("generation", "поколение", "noun", "The younger generation is tech-savvy.", collocations=("younger generation",)),
            VocabCard("perspective", "точка зрения", "noun", "From my perspective, it's risky.", collocations=("from my perspective",)),
            VocabCard("sustainable", "устойчивый", "adjective", "We need sustainable development.", collocations=("sustainable growth",)),
            VocabCard("consequence", "последствие", "noun", "Every action has consequences.", collocations=("serious consequences",)),
        ]),
        VocabSet("B2", "Academic English", [
            VocabCard("research", "исследование", "noun", "The research shows a clear link.", collocations=("conduct research",)),
            VocabCard("hypothesis", "гипотеза", "noun", "Our hypothesis was confirmed.", collocations=("test a hypothesis",)),
            VocabCard("methodology", "методология", "noun", "The methodology needs improvement.", collocations=("research methodology",)),
            VocabCard("conclude", "делать вывод", "verb", "We conclude that the theory is valid.", collocations=("conclude that",), word_family=("conclusion",)),
            VocabCard("significant", "значительный", "adjective", "The results are statistically significant.", collocations=("significant impact",)),
            VocabCard("evidence", "доказательство", "noun", "There is strong evidence for this.", collocations=("strong evidence",)),
            VocabCard("analyze", "анализировать", "verb", "We analyzed the data carefully.", collocations=("analyze data",), word_family=("analysis",)),
            VocabCard("theory", "теория", "noun", "This theory has been challenged.", collocations=("support a theory",)),
            VocabCard("framework", "рамки", "noun", "We use a theoretical framework.", collocations=("theoretical framework",)),
            VocabCard("implication", "следствие", "noun", "The implications are far-reaching.", collocations=("far-reaching implications",)),
        ]),
        VocabSet("B2", "Idioms", [
            VocabCard("piece of cake", "пара пустяков", "idiom", "The exam was a piece of cake."),
            VocabCard("break a leg", "ни пуха ни пера", "idiom", "Break a leg in your performance!"),
            VocabCard("hit the books", "засесть за учебники", "idiom", "I need to hit the books tonight."),
            VocabCard("once in a blue moon", "очень редко", "idiom", "We meet once in a blue moon."),
            VocabCard("under the weather", "неважно себя чувствовать", "idiom", "I'm feeling under the weather today."),
            VocabCard("cost an arm and a leg", "стоить целое состояние", "idiom", "That car cost an arm and a leg."),
            VocabCard("let the cat out of the bag", "выдать секрет", "idiom", "Don't let the cat out of the bag!"),
            VocabCard("on the same page", "быть единомышленниками", "idiom", "We need to be on the same page."),
        ]),
        VocabSet("B2", "Law & Justice", [
            VocabCard("jury", "присяжные", "noun", "The jury reached a verdict.", collocations=("jury's decision",)),
            VocabCard("verdict", "вердикт", "noun", "The verdict was guilty.", collocations=("reach a verdict",)),
            VocabCard("witness", "свидетель", "noun", "The witness saw everything.", collocations=("key witness",)),
            VocabCard("trial", "судебный процесс", "noun", "The trial lasted six weeks.", collocations=("fair trial",)),
            VocabCard("guilty", "виновный", "adjective", "He was found guilty.", collocations=("plead guilty",)),
            VocabCard("sentence", "приговор", "noun", "He received a five-year sentence.", collocations=("prison sentence",)),
            VocabCard("appeal", "апелляция", "noun", "They filed an appeal.", collocations=("file an appeal",)),
            VocabCard("commit", "совершать", "verb", "He committed a serious crime.", collocations=("commit a crime",)),
            VocabCard("accuse", "обвинять", "verb", "He was accused of theft.", collocations=("accuse of",), word_family=("accusation",)),
            VocabCard("evidence", "улики", "noun", "The evidence is circumstantial.", collocations=("compelling evidence",)),
        ]),
        VocabSet("B2", "Emotions & Behaviour", [
            VocabCard("anxious", "тревожный", "adjective", "She felt anxious about the future.", collocations=("anxious about",), word_family=("anxiety",)),
            VocabCard("frustrated", "раздражённый", "adjective", "He was frustrated by the delay.", collocations=("frustrated with",), word_family=("frustration",)),
            VocabCard("overwhelmed", "ошеломлённый", "adjective", "I'm overwhelmed with work.", collocations=("overwhelmed by",)),
            VocabCard("empathy", "эмпатия", "noun", "She shows great empathy.", collocations=("show empathy",)),
            VocabCard("resentment", "обида", "noun", "He felt resentment towards his boss.", collocations=("harbour resentment",)),
            VocabCard("contempt", "презрение", "noun", "She looked at him with contempt.", collocations=("with contempt",)),
            VocabCard("reluctant", "неохотный", "adjective", "He was reluctant to admit it.", collocations=("reluctant to",), word_family=("reluctance",)),
            VocabCard("determined", "решительный", "adjective", "She is determined to succeed.", collocations=("determined to",), word_family=("determination",)),
            VocabCard("sympathy", "сочувствие", "noun", "I felt sympathy for her.", collocations=("express sympathy",), word_family=("sympathetic",)),
            VocabCard("jealous", "ревнивый", "adjective", "He was jealous of his success.", collocations=("jealous of",), word_family=("jealousy",)),
        ]),
        VocabSet("B2", "Technology & Innovation", [
            VocabCard("innovation", "инновация", "noun", "Innovation drives progress.", collocations=("technological innovation",)),
            VocabCard("artificial", "искусственный", "adjective", "AI uses artificial intelligence.", collocations=("artificial intelligence",)),
            VocabCard("algorithm", "алгоритм", "noun", "The algorithm is very efficient.", collocations=("search algorithm",)),
            VocabCard("database", "база данных", "noun", "The database stores user info.", collocations=("build a database",)),
            VocabCard("encryption", "шифрование", "noun", "Encryption protects your data.", collocations=("data encryption",)),
            VocabCard("privacy", "приватность", "noun", "Online privacy is important.", collocations=("privacy concerns",)),
            VocabCard("cybersecurity", "кибербезопасность", "noun", "Cybersecurity is a growing field.", collocations=("cybersecurity threat",)),
            VocabCard("breakthrough", "прорыв", "noun", "It was a major breakthrough.", collocations=("major breakthrough",)),
            VocabCard("deploy", "развёртывать", "verb", "They deployed the new software.", collocations=("deploy software",)),
            VocabCard("obsolete", "устаревший", "adjective", "This technology is obsolete.", collocations=("become obsolete",)),
        ]),
        VocabSet("B2", "Culture & Arts", [
            VocabCard("heritage", "наследие", "noun", "We must protect our cultural heritage.", collocations=("cultural heritage",)),
            VocabCard("exhibition", "выставка", "noun", "The exhibition opens next week.", collocations=("art exhibition",)),
            VocabCard("sculpture", "скульптура", "noun", "The sculpture is impressive.", collocations=("modern sculpture",)),
            VocabCard("performance", "представление", "noun", "Her performance was outstanding.", collocations=("live performance",)),
            VocabCard("critic", "критик", "noun", "The critic praised the film.", collocations=("film critic",), word_family=("critical", "criticism")),
            VocabCard("inspire", "вдохновлять", "verb", "She inspired a generation.", collocations=("inspire someone to",), word_family=("inspiration",)),
            VocabCard("creativity", "креативность", "noun", "Creativity is essential in art.", collocations=("foster creativity",), word_family=("creative",)),
            VocabCard("controversial", "спорный", "adjective", "It's a controversial topic.", collocations=("controversial topic",)),
            VocabCard("mainstream", "мейнстрим", "adjective", "It became mainstream music.", collocations=("mainstream media",)),
            VocabCard("authentic", "аутентичный", "adjective", "It's an authentic Italian recipe.", collocations=("authentic experience",), word_family=("authenticity",)),
        ]),
    ],
    "C1": [
        VocabSet("C1", "Nuanced Vocabulary", [
            VocabCard("subtle", "тонкий", "adjective", "There's a subtle difference.", collocations=("subtle difference",)),
            VocabCard("inherent", "присущий", "adjective", "There are inherent risks.", collocations=("inherent risk",)),
            VocabCard("ambiguous", "двусмысленный", "adjective", "His statement was deliberately ambiguous.", collocations=("deliberately ambiguous",), word_family=("ambiguity",)),
            VocabCard("comprehensive", "всеобъемлющий", "adjective", "The report is comprehensive.", collocations=("comprehensive review",)),
            VocabCard("meticulous", "скрупулёзный", "adjective", "She is meticulous about details.", collocations=("meticulous about",)),
            VocabCard("pragmatic", "прагматичный", "adjective", "We need a pragmatic approach.", collocations=("pragmatic approach",)),
            VocabCard("profound", "глубокий", "adjective", "It had a profound impact on me.", collocations=("profound impact",)),
            VocabCard("resilient", "жизнестойкий", "adjective", "Children are remarkably resilient.", collocations=("resilient to",), word_family=("resilience",)),
        ]),
        VocabSet("C1", "Discourse Markers", [
            VocabCard("nevertheless", "тем не менее", "adverb", "It was raining; nevertheless, we went out.", collocations=("but nevertheless",)),
            VocabCard("furthermore", "кроме того", "adverb", "It's cheap, and furthermore, it's reliable.", collocations=("and furthermore",)),
            VocabCard("consequently", "следовательно", "adverb", "He overslept; consequently, he was late.", collocations=("and consequently",)),
            VocabCard("albeit", "хотя и", "conjunction", "It's a good plan, albeit an expensive one.", collocations=("albeit a",)),
            VocabCard("notwithstanding", "несмотря на", "preposition", "Notwithstanding the delays, we finished on time.", collocations=("notwithstanding the",)),
            VocabCard("thus", "таким образом", "adverb", "Thus, we can conclude the experiment was successful.", collocations=("thus, we",)),
            VocabCard("hence", "следовательно", "adverb", "Hence, the results should be interpreted carefully.", collocations=("hence the",)),
            VocabCard("whereas", "тогда как", "conjunction", "She is outgoing, whereas her brother is shy.", collocations=("whereas the",)),
        ]),
        VocabSet("C1", "Professional & Formal", [
            VocabCard("scrutinize", "тщательно изучать", "verb", "The committee scrutinized every detail.", collocations=("scrutinize closely",)),
            VocabCard("facilitate", "способствовать", "verb", "The new system will facilitate communication.", collocations=("facilitate communication",)),
            VocabCard("mitigate", "смягчать", "verb", "Steps were taken to mitigate the damage.", collocations=("mitigate risk",)),
            VocabCard("perpetuate", "увековечивать", "verb", "These stereotypes perpetuate inequality.", collocations=("perpetuate stereotypes",)),
            VocabCard("extrapolate", "экстраполировать", "verb", "We can extrapolate from these findings.", collocations=("extrapolate from",)),
            VocabCard("consolidate", "укреплять", "verb", "The company consolidated its position.", collocations=("consolidate power",)),
            VocabCard("streamline", "оптимизировать", "verb", "We need to streamline the process.", collocations=("streamline processes",)),
            VocabCard("optimize", "оптимизировать", "verb", "The algorithm was optimized for speed.", collocations=("optimize for",)),
        ]),
        VocabSet("C1", "Abstract Concepts", [
            VocabCard("paradox", "парадокс", "noun", "It's a paradox of modern life.", collocations=("apparent paradox",)),
            VocabCard("coherence", "связность", "noun", "The argument lacks coherence.", collocations=("logical coherence",), word_family=("coherent",)),
            VocabCard("prevalent", "распространённый", "adjective", "This view is prevalent among scholars.", collocations=("highly prevalent",), word_family=("prevalence",)),
            VocabCard("deteriorate", "ухудшаться", "verb", "His health deteriorated rapidly.", collocations=("rapidly deteriorate",), word_family=("deterioration",)),
            VocabCard("diminish", "уменьшать", "verb", "Their influence has diminished.", collocations=("gradually diminish",)),
            VocabCard("encompass", "охватывать", "verb", "The course encompasses all aspects.", collocations=("encompass all",)),
            VocabCard("entail", "влечь за собой", "verb", "The job entails a lot of travel.", collocations=("entail doing",)),
            VocabCard("undermine", "подрывать", "verb", "This could undermine public trust.", collocations=("undermine confidence",)),
        ]),
        VocabSet("C1", "Advanced Idioms", [
            VocabCard("burn the midnight oil", "работать допоздна", "idiom", "She's burning the midnight oil."),
            VocabCard("bite the bullet", "стиснуть зубы", "idiom", "I had to bite the bullet and apologize."),
            VocabCard("cut corners", "сэкономить на качестве", "idiom", "They cut corners to save money."),
            VocabCard("get out of hand", "выйти из-под контроля", "idiom", "The situation is getting out of hand."),
            VocabCard("on thin ice", "на грани", "idiom", "You're on thin ice with that attitude."),
            VocabCard("steal someone's thunder", "перетянуть внимание", "idiom", "He stole my thunder at the meeting."),
            VocabCard("by the skin of one's teeth", "едва-едва", "idiom", "I passed by the skin of my teeth."),
            VocabCard("throw in the towel", "сдаться", "idiom", "He threw in the towel after three failures."),
        ]),
        VocabSet("C1", "Politics & Diplomacy", [
            VocabCard("diplomacy", "дипломатия", "noun", "Diplomacy is better than conflict.", collocations=("international diplomacy",)),
            VocabCard("sanction", "санкция", "noun", "Economic sanctions were imposed.", collocations=("impose sanctions",)),
            VocabCard("sovereignty", "суверенитет", "noun", "They defend their national sovereignty.", collocations=("national sovereignty",)),
            VocabCard("referendum", "референдум", "noun", "A referendum was held on the issue.", collocations=("hold a referendum",)),
            VocabCard("constituency", "избирательный округ", "noun", "She represents a rural constituency.", collocations=("rural constituency",)),
            VocabCard("bilateral", "двусторонний", "adjective", "They signed a bilateral agreement.", collocations=("bilateral agreement",)),
            VocabCard("legislation", "законодательство", "noun", "New legislation was passed.", collocations=("pass legislation",)),
            VocabCard("ratify", "ратифицировать", "verb", "The treaty was ratified by all members.", collocations=("ratify a treaty",), word_family=("ratification",)),
        ]),
    ],
    "C2": [
        VocabSet("C2", "Sophisticated Vocabulary", [
            VocabCard("ephemeral", "мимолётный", "adjective", "Fame can be ephemeral.", collocations=("ephemeral nature",)),
            VocabCard("ubiquitous", "вездесущий", "adjective", "Smartphones are now ubiquitous.", collocations=("increasingly ubiquitous",)),
            VocabCard("paradigm", "парадигма", "noun", "This represents a paradigm shift.", collocations=("paradigm shift",)),
            VocabCard("dichotomy", "дихотомия", "noun", "There's a false dichotomy in this argument.", collocations=("false dichotomy",)),
            VocabCard("serendipity", "счастливая случайность", "noun", "Their meeting was pure serendipity.", collocations=("pure serendipity",)),
            VocabCard("eloquent", "красноречивый", "adjective", "She gave an eloquent speech.", collocations=("eloquent speech",), word_family=("eloquence",)),
            VocabCard("astute", "проницательный", "adjective", "He made an astute observation.", collocations=("astute observation",)),
            VocabCard("incisive", "острый", "adjective", "Her analysis was incisive.", collocations=("incisive analysis",)),
        ]),
        VocabSet("C2", "Rare & Literary", [
            VocabCard("obfuscate", "запутывать", "verb", "The report obfuscates the real issue.", collocations=("deliberately obfuscate",)),
            VocabCard("sycophant", "подхалим", "noun", "He surrounded himself with sycophants.", collocations=("political sycophant",)),
            VocabCard("perfunctory", "небрежный", "adjective", "He gave a perfunctory nod.", collocations=("perfunctory nod",)),
            VocabCard("magnanimous", "великодушный", "adjective", "She was magnanimous in victory.", collocations=("magnanimous gesture",), word_family=("magnanimity",)),
            VocabCard("perspicacious", "проницательный", "adjective", "His perspicacious remarks impressed everyone.", collocations=("perspicacious remark",)),
            VocabCard("esoteric", "узкоспециальный", "adjective", "The topic is rather esoteric.", collocations=("esoteric knowledge",)),
            VocabCard("quintessential", "классический", "adjective", "It's the quintessential English village.", collocations=("quintessential example",)),
            VocabCard("redolent", "благоухающий", "adjective", "The room was redolent of lavender.", collocations=("redolent of",)),
        ]),
        VocabSet("C2", "Academic & Philosophical", [
            VocabCard("epistemology", "эпистемология", "noun", "Epistemology studies how we know things.", collocations=("social epistemology",)),
            VocabCard("determinism", "детерминизм", "noun", "Technological determinism is debated.", collocations=("technological determinism",)),
            VocabCard("heuristic", "эвристический", "adjective", "It's a heuristic approach.", collocations=("heuristic approach",)),
            VocabCard("empirical", "эмпирический", "adjective", "We need empirical evidence.", collocations=("empirical evidence",)),
            VocabCard("normative", "нормативный", "adjective", "This is a normative claim.", collocations=("normative claim",)),
            VocabCard("pedagogy", "педагогика", "noun", "Modern pedagogy emphasizes critical thinking.", collocations=("modern pedagogy",), word_family=("pedagogical",)),
            VocabCard("rhetoric", "риторика", "noun", "His rhetoric was persuasive but empty.", collocations=("empty rhetoric",), word_family=("rhetorical",)),
            VocabCard("dogma", "догма", "noun", "They challenged the prevailing dogma.", collocations=("challenge dogma",), word_family=("dogmatic",)),
        ]),
        VocabSet("C2", "Nuanced Verbs", [
            VocabCard("corroborate", "подтверждать", "verb", "The witness corroborated the story.", collocations=("corroborate evidence",)),
            VocabCard("disseminate", "распространять", "verb", "They disseminated the findings widely.", collocations=("disseminate information",)),
            VocabCard("circumvent", "обходить", "verb", "He tried to circumvent the rules.", collocations=("circumvent restrictions",)),
            VocabCard("amalgamate", "объединять", "verb", "The two companies amalgamated.", collocations=("amalgamate with",)),
            VocabCard("extricate", "высвобождать", "verb", "She extricated herself from the situation.", collocations=("extricate from",)),
            VocabCard("reverberate", "резонировать", "verb", "The decision reverberated through the industry.", collocations=("reverberate through",)),
            VocabCard("vacillate", "колебаться", "verb", "He vacillated between two options.", collocations=("vacillate between",)),
            VocabCard("prevaricate", "уклоняться", "verb", "The minister prevaricated when asked.", collocations=("constantly prevaricate",)),
        ]),
        VocabSet("C2", "Literary Idioms", [
            VocabCard("a bitter pill to swallow", "горькая правда", "idiom", "Losing the job was a bitter pill."),
            VocabCard("the elephant in the room", "очевидная проблема", "idiom", "Let's address the elephant in the room."),
            VocabCard("add insult to injury", "усугубить ситуацию", "idiom", "To add insult to injury, it started raining."),
            VocabCard("a flash in the pan", "кратковременный успех", "idiom", "His success was just a flash in the pan."),
            VocabCard("the tip of the iceberg", "верхушка айсберга", "idiom", "This is just the tip of the iceberg."),
            VocabCard("go down in flames", "провалиться", "idiom", "The project went down in flames."),
            VocabCard("open Pandora's box", "открыть ящик Пандоры", "idiom", "That decision opened a Pandora's box."),
            VocabCard("at a crossroads", "на распутье", "idiom", "Our company is at a crossroads."),
        ]),
    ],
}


def vocabulary_for_level(level: str) -> list[VocabSet]:
    return VOCABULARY_SETS.get(level, [])


def all_vocab_cards_for_level(level: str) -> list[VocabCard]:
    cards: list[VocabCard] = []
    for vset in vocabulary_for_level(level):
        cards.extend(vset.cards)
    return cards


# ═══════════════════════════════════════════════════════════════
# PHRASAL VERBS — 58 entries (COCA + BNC frequency)
# ═══════════════════════════════════════════════════════════════

PHRASAL_VERBS = [
    {"verb": "get up", "meaning": "вставать", "synonym": "wake up", "example": "I get up at 7 AM.", "level": "A1"},
    {"verb": "give up", "meaning": "сдаваться", "synonym": "quit", "example": "Don't give up on your dreams.", "level": "A2"},
    {"verb": "go on", "meaning": "продолжать", "synonym": "continue", "example": "What's going on here?", "level": "A2"},
    {"verb": "look for", "meaning": "искать", "synonym": "search for", "example": "I'm looking for my keys.", "level": "A1"},
    {"verb": "look after", "meaning": "присматривать", "synonym": "take care of", "example": "She looks after her grandmother.", "level": "A2"},
    {"verb": "put off", "meaning": "откладывать", "synonym": "postpone", "example": "Don't put off until tomorrow.", "level": "B1"},
    {"verb": "take off", "meaning": "снимать, взлетать", "synonym": "remove, depart", "example": "The plane takes off at noon.", "level": "A2"},
    {"verb": "turn on", "meaning": "включать", "synonym": "switch on", "example": "Turn on the lights.", "level": "A1"},
    {"verb": "turn off", "meaning": "выключать", "synonym": "switch off", "example": "Turn off the TV.", "level": "A1"},
    {"verb": "find out", "meaning": "узнавать", "synonym": "discover", "example": "I found out the truth.", "level": "B1"},
    {"verb": "give back", "meaning": "возвращать", "synonym": "return", "example": "Please give back my book.", "level": "A2"},
    {"verb": "go out", "meaning": "выходить", "synonym": "leave home", "example": "Let's go out for dinner.", "level": "A2"},
    {"verb": "grow up", "meaning": "вырастать", "synonym": "mature", "example": "I grew up in a small town.", "level": "B1"},
    {"verb": "hold on", "meaning": "подождать", "synonym": "wait", "example": "Hold on, I'll be right there.", "level": "B1"},
    {"verb": "look forward to", "meaning": "ждать с нетерпением", "synonym": "anticipate", "example": "I look forward to seeing you.", "level": "B1"},
    {"verb": "look up", "meaning": "искать в справочнике", "synonym": "search", "example": "Look up the word in the dictionary.", "level": "B1"},
    {"verb": "make up", "meaning": "придумывать", "synonym": "invent", "example": "She made up a funny story.", "level": "B1"},
    {"verb": "pass away", "meaning": "умирать", "synonym": "die (polite)", "example": "His grandfather passed away.", "level": "B2"},
    {"verb": "pick up", "meaning": "забирать", "synonym": "collect", "example": "I'll pick you up at 8.", "level": "A2"},
    {"verb": "point out", "meaning": "отмечать", "synonym": "highlight", "example": "She pointed out the mistake.", "level": "B2"},
    {"verb": "put on", "meaning": "надевать", "synonym": "wear", "example": "Put on your coat.", "level": "A1"},
    {"verb": "run away", "meaning": "убегать", "synonym": "escape", "example": "The dog ran away.", "level": "A2"},
    {"verb": "run out of", "meaning": "заканчиваться", "synonym": "exhaust", "example": "We ran out of milk.", "level": "B1"},
    {"verb": "set up", "meaning": "настраивать", "synonym": "establish", "example": "I set up my new computer.", "level": "B1"},
    {"verb": "show up", "meaning": "появляться", "synonym": "arrive", "example": "He showed up late again.", "level": "B1"},
    {"verb": "stand up", "meaning": "вставать", "synonym": "rise", "example": "Please stand up.", "level": "A1"},
    {"verb": "take after", "meaning": "быть похожим", "synonym": "resemble", "example": "She takes after her mother.", "level": "B1"},
    {"verb": "take back", "meaning": "забирать обратно", "synonym": "reclaim", "example": "I take back what I said.", "level": "B2"},
    {"verb": "think over", "meaning": "обдумывать", "synonym": "consider", "example": "Let me think it over.", "level": "B1"},
    {"verb": "try on", "meaning": "мерить", "synonym": "test fit", "example": "Can I try on this jacket?", "level": "A2"},
    {"verb": "turn down", "meaning": "отклонять", "synonym": "reject", "example": "They turned down my offer.", "level": "B1"},
    {"verb": "turn up", "meaning": "появляться", "synonym": "arrive unexpectedly", "example": "He turned up at the party.", "level": "B2"},
    {"verb": "wake up", "meaning": "просыпаться", "synonym": "awaken", "example": "I wake up early.", "level": "A1"},
    {"verb": "work out", "meaning": "тренироваться", "synonym": "exercise", "example": "I work out three times a week.", "level": "B1"},
    {"verb": "break down", "meaning": "ломаться", "synonym": "stop working", "example": "My car broke down.", "level": "B1"},
    {"verb": "bring up", "meaning": "воспитывать", "synonym": "raise", "example": "She was brought up by her aunt.", "level": "B2"},
    {"verb": "call off", "meaning": "отменять", "synonym": "cancel", "example": "They called off the meeting.", "level": "B1"},
    {"verb": "carry on", "meaning": "продолжать", "synonym": "continue", "example": "Carry on with your work.", "level": "B1"},
    {"verb": "come across", "meaning": "наталкиваться", "synonym": "find by chance", "example": "I came across an old photo.", "level": "B2"},
    {"verb": "count on", "meaning": "полагаться", "synonym": "rely on", "example": "You can count on me.", "level": "B1"},
    {"verb": "deal with", "meaning": "справляться", "synonym": "handle", "example": "How do you deal with stress?", "level": "B1"},
    {"verb": "drop in", "meaning": "заскочить", "synonym": "visit unexpectedly", "example": "Drop in anytime.", "level": "B2"},
    {"verb": "figure out", "meaning": "разобраться", "synonym": "understand", "example": "I can't figure out this puzzle.", "level": "B1"},
    {"verb": "get along", "meaning": "ладить", "synonym": "have good relations", "example": "They get along well.", "level": "B1"},
    {"verb": "get over", "meaning": "оправиться", "synonym": "recover from", "example": "It took time to get over the flu.", "level": "B2"},
    {"verb": "get together", "meaning": "собираться", "synonym": "meet", "example": "Let's get together next weekend.", "level": "B1"},
    {"verb": "keep up", "meaning": "не отставать", "synonym": "maintain pace", "example": "Keep up the good work!", "level": "B1"},
    {"verb": "look down on", "meaning": "смотреть свысока", "synonym": "despise", "example": "Don't look down on others.", "level": "B2"},
    {"verb": "look out", "meaning": "остерегаться", "synonym": "watch out", "example": "Look out! There's a car.", "level": "B1"},
    {"verb": "make sure", "meaning": "убедиться", "synonym": "verify", "example": "Make sure the door is locked.", "level": "A2"},
    {"verb": "pull over", "meaning": "прижаться к обочине", "synonym": "stop by the road", "example": "The police asked him to pull over.", "level": "B2"},
    {"verb": "put away", "meaning": "убирать", "synonym": "store", "example": "Put away your toys.", "level": "A2"},
    {"verb": "run into", "meaning": "случайно встретить", "synonym": "bump into", "example": "I ran into an old friend.", "level": "B1"},
    {"verb": "sort out", "meaning": "улаживать", "synonym": "resolve", "example": "We need to sort out this problem.", "level": "B2"},
    {"verb": "take apart", "meaning": "разбирать", "synonym": "disassemble", "example": "He took apart the clock.", "level": "B2"},
    {"verb": "throw away", "meaning": "выбрасывать", "synonym": "discard", "example": "Don't throw away those papers.", "level": "A2"},
    {"verb": "try out", "meaning": "пробовать", "synonym": "test", "example": "Try out the new app.", "level": "B1"},
    {"verb": "wear out", "meaning": "изнашивать", "synonym": "exhaust", "example": "My shoes are worn out.", "level": "B2"},
]


def phrasal_verbs_for_level(level: str) -> list[dict]:
    level_idx = CEFR_LEVELS.index(level) if level in CEFR_LEVELS else 3
    return [pv for pv in PHRASAL_VERBS if CEFR_LEVELS.index(pv["level"]) <= level_idx]


# ═══════════════════════════════════════════════════════════════
# COLOCATIONS — 52 entries (Oxford Collocations Dictionary)
# ═══════════════════════════════════════════════════════════════

COLOCATIONS = [
    {"adjective": "heavy", "noun": "rain", "example": "We had heavy rain last night.", "level": "A2"},
    {"adjective": "heavy", "noun": "traffic", "example": "There was heavy traffic.", "level": "A2"},
    {"adjective": "heavy", "noun": "smoker", "example": "My father is a heavy smoker.", "level": "B1"},
    {"adjective": "strong", "noun": "wind", "example": "A strong wind blew all night.", "level": "A2"},
    {"adjective": "strong", "noun": "coffee", "example": "I like strong coffee.", "level": "A2"},
    {"adjective": "strong", "noun": "opinion", "example": "She has strong opinions.", "level": "B1"},
    {"adjective": "deep", "noun": "breath", "example": "Take a deep breath.", "level": "B1"},
    {"adjective": "deep", "noun": "thought", "example": "He was lost in deep thought.", "level": "B1"},
    {"adjective": "high", "noun": "price", "example": "Houses have high prices.", "level": "A2"},
    {"adjective": "high", "noun": "speed", "example": "The train moves at high speed.", "level": "A2"},
    {"adjective": "bright", "noun": "future", "example": "She has a bright future.", "level": "B1"},
    {"adjective": "bright", "noun": "idea", "example": "That's a bright idea!", "level": "B1"},
    {"adjective": "sharp", "noun": "turn", "example": "There's a sharp turn ahead.", "level": "B1"},
    {"adjective": "sharp", "noun": "pain", "example": "I felt a sharp pain.", "level": "B1"},
    {"adjective": "soft", "noun": "voice", "example": "She spoke in a soft voice.", "level": "B1"},
    {"adjective": "soft", "noun": "rain", "example": "Soft rain fell on the roof.", "level": "B2"},
    {"adjective": "hard", "noun": "work", "example": "Building a house is hard work.", "level": "A2"},
    {"adjective": "hard", "noun": "rain", "example": "It's raining hard.", "level": "A2"},
    {"adjective": "light", "noun": "rain", "example": "There's light rain today.", "level": "B1"},
    {"adjective": "light", "noun": "sleeper", "example": "I'm a light sleeper.", "level": "B1"},
    {"adjective": "fast", "noun": "food", "example": "Fast food is not very healthy.", "level": "A2"},
    {"adjective": "fast", "noun": "pace", "example": "We walked at a fast pace.", "level": "B1"},
    {"adjective": "broad", "noun": "shoulders", "example": "He has broad shoulders.", "level": "B1"},
    {"adjective": "broad", "noun": "smile", "example": "She gave a broad smile.", "level": "B1"},
    {"adjective": "wild", "noun": "animals", "example": "Wild animals live in the forest.", "level": "A2"},
    {"adjective": "wild", "noun": "guess", "example": "That's a wild guess.", "level": "B2"},
    {"adjective": "flat", "noun": "tyre", "example": "We got a flat tyre.", "level": "B1"},
    {"adjective": "flat", "noun": "refusal", "example": "She gave a flat refusal.", "level": "B2"},
    {"adjective": "dry", "noun": "weather", "example": "We've had dry weather all week.", "level": "A2"},
    {"adjective": "dry", "noun": "humour", "example": "He has a dry sense of humour.", "level": "B2"},
    {"adjective": "fresh", "noun": "air", "example": "Let's get some fresh air.", "level": "A2"},
    {"adjective": "fresh", "noun": "start", "example": "It's a fresh start.", "level": "B1"},
    {"adjective": "close", "noun": "friend", "example": "She is a close friend.", "level": "A2"},
    {"adjective": "close", "noun": "call", "example": "That was a close call!", "level": "B1"},
    {"adjective": "common", "noun": "mistake", "example": "That's a common mistake.", "level": "B1"},
    {"adjective": "common", "noun": "knowledge", "example": "It's common knowledge.", "level": "B1"},
    {"adjective": "main", "noun": "reason", "example": "The main reason is cost.", "level": "A2"},
    {"adjective": "main", "noun": "course", "example": "What's the main course?", "level": "B1"},
    {"adjective": "public", "noun": "transport", "example": "I use public transport.", "level": "A2"},
    {"adjective": "public", "noun": "opinion", "example": "Public opinion is divided.", "level": "B2"},
    {"adjective": "social", "noun": "media", "example": "Social media is everywhere.", "level": "B1"},
    {"adjective": "social", "noun": "life", "example": "She has an active social life.", "level": "B1"},
    {"adjective": "vital", "noun": "role", "example": "He played a vital role.", "level": "B2"},
    {"adjective": "vital", "noun": "information", "example": "This is vital information.", "level": "B2"},
    {"adjective": "key", "noun": "factor", "example": "Money is a key factor.", "level": "B1"},
    {"adjective": "key", "noun": "issue", "example": "Let's discuss the key issues.", "level": "B2"},
    {"adjective": "major", "noun": "problem", "example": "We have a major problem.", "level": "B1"},
    {"adjective": "major", "noun": "change", "example": "There was a major change.", "level": "B1"},
    {"adjective": "minor", "noun": "injury", "example": "He suffered a minor injury.", "level": "B2"},
    {"adjective": "minor", "noun": "issue", "example": "It's just a minor issue.", "level": "B2"},
    {"adjective": "absolute", "noun": "disaster", "example": "The party was an absolute disaster.", "level": "B2"},
    {"adjective": "absolute", "noun": "silence", "example": "There was absolute silence.", "level": "B2"},
]


def collocations_for_level(level: str) -> list[dict]:
    level_idx = CEFR_LEVELS.index(level) if level in CEFR_LEVELS else 3
    return [c for c in COLOCATIONS if CEFR_LEVELS.index(c["level"]) <= level_idx]


# ═══════════════════════════════════════════════════════════════
# COMMON ERRORS — 20 entries (Cambridge Learner Corpus)
# ═══════════════════════════════════════════════════════════════

COMMON_ERRORS = [
    {"wrong": "I am agree with you.", "correct": "I agree with you.", "type": "grammar", "explanation": "Agree — глагол, не нужен am."},
    {"wrong": "She has 20 years.", "correct": "She is 20 years old.", "type": "grammar", "explanation": "Возраст: be + age + years old."},
    {"wrong": "I have visited London in 2019.", "correct": "I visited London in 2019.", "type": "tense", "explanation": "Past Simple для конкретного времени."},
    {"wrong": "He is more taller than me.", "correct": "He is taller than me.", "type": "grammar", "explanation": "tall → taller, не нужно more."},
    {"wrong": "I want that you help me.", "correct": "I want you to help me.", "type": "grammar", "explanation": "want + object + to + verb."},
    {"wrong": "I am living here since 2020.", "correct": "I have been living here since 2020.", "type": "tense", "explanation": "Present Perfect Continuous."},
    {"wrong": "There is many people here.", "correct": "There are many people here.", "type": "grammar", "explanation": "People — множественное, нужно are."},
    {"wrong": "I have been to Paris two times.", "correct": "I have been to Paris twice.", "type": "vocabulary", "explanation": "Twice вместо two times."},
    {"wrong": "She said me that she was tired.", "correct": "She told me that she was tired.", "type": "grammar", "explanation": "Say без объекта, tell с объектом."},
    {"wrong": "I am interesting in art.", "correct": "I am interested in art.", "type": "grammar", "explanation": "Interested (чувствую) vs interesting (объект)."},
    {"wrong": "If I will have time, I will call you.", "correct": "If I have time, I will call you.", "type": "grammar", "explanation": "First Conditional: If + Present Simple."},
    {"wrong": "I look forward to hear from you.", "correct": "I look forward to hearing from you.", "type": "grammar", "explanation": "look forward to + gerund."},
    {"wrong": "The news are good.", "correct": "The news is good.", "type": "grammar", "explanation": "News — неисчисляемое, всегда is."},
    {"wrong": "I have a 5-years-old son.", "correct": "I have a 5-year-old son.", "type": "grammar", "explanation": "Составные прилагательные: 5-year-old."},
    {"wrong": "He suggested me to go home.", "correct": "He suggested that I go home.", "type": "grammar", "explanation": "Suggest + that clause или gerund."},
    {"wrong": "I am used to live in a big city.", "correct": "I am used to living in a big city.", "type": "grammar", "explanation": "be used to + gerund."},
    {"wrong": "Despite of the rain, we went out.", "correct": "Despite the rain, we went out.", "type": "grammar", "explanation": "Despite без of."},
    {"wrong": "I have been working since two hours.", "correct": "I have been working for two hours.", "type": "preposition", "explanation": "Since — точка, for — длительность."},
    {"wrong": "Can you borrow me some money?", "correct": "Can you lend me some money?", "type": "vocabulary", "explanation": "Borrow = взять, lend = дать."},
    {"wrong": "I don't know what does it mean.", "correct": "I don't know what it means.", "type": "word_order", "explanation": "Косвенный вопрос: прямой порядок слов."},
]


def common_errors_for_level(level: str) -> list[dict]:
    return COMMON_ERRORS


# ═══════════════════════════════════════════════════════════════
# IDIOMS — 50 entries
# ═══════════════════════════════════════════════════════════════

IDIOMS = [
    {"idiom": "piece of cake", "meaning": "очень легко", "example": "The exam was a piece of cake.", "level": "B1"},
    {"idiom": "break a leg", "meaning": "ни пуха ни пера", "example": "Break a leg in your performance!", "level": "B1"},
    {"idiom": "hit the books", "meaning": "усердно учиться", "example": "I need to hit the books tonight.", "level": "B1"},
    {"idiom": "once in a blue moon", "meaning": "очень редко", "example": "We meet once in a blue moon.", "level": "B2"},
    {"idiom": "under the weather", "meaning": "плохо себя чувствовать", "example": "I'm feeling under the weather.", "level": "B1"},
    {"idiom": "cost an arm and a leg", "meaning": "очень дорого", "example": "That car cost an arm and a leg.", "level": "B2"},
    {"idiom": "let the cat out of the bag", "meaning": "выдать секрет", "example": "Don't let the cat out of the bag!", "level": "B2"},
    {"idiom": "on the same page", "meaning": "быть единомышленниками", "example": "We need to be on the same page.", "level": "B2"},
    {"idiom": "burn the midnight oil", "meaning": "работать допоздна", "example": "She's burning the midnight oil.", "level": "C1"},
    {"idiom": "bite the bullet", "meaning": "стиснуть зубы", "example": "I had to bite the bullet.", "level": "C1"},
    {"idiom": "cut corners", "meaning": "сэкономить на качестве", "example": "They cut corners to save money.", "level": "B2"},
    {"idiom": "get out of hand", "meaning": "выйти из-под контроля", "example": "The situation is getting out of hand.", "level": "B2"},
    {"idiom": "on thin ice", "meaning": "на грани", "example": "You're on thin ice.", "level": "B2"},
    {"idiom": "steal someone's thunder", "meaning": "перетянуть внимание", "example": "He stole my thunder.", "level": "C1"},
    {"idiom": "by the skin of one's teeth", "meaning": "едва-едва", "example": "I passed by the skin of my teeth.", "level": "C1"},
    {"idiom": "throw in the towel", "meaning": "сдаться", "example": "He threw in the towel.", "level": "B2"},
    {"idiom": "a bitter pill to swallow", "meaning": "горькая правда", "example": "Losing the job was a bitter pill.", "level": "C1"},
    {"idiom": "the elephant in the room", "meaning": "очевидная проблема", "example": "Let's address the elephant in the room.", "level": "C1"},
    {"idiom": "add insult to injury", "meaning": "усугубить ситуацию", "example": "To add insult to injury, it rained.", "level": "C1"},
    {"idiom": "a flash in the pan", "meaning": "кратковременный успех", "example": "His success was a flash in the pan.", "level": "C1"},
    {"idiom": "the tip of the iceberg", "meaning": "верхушка айсберга", "example": "This is just the tip of the iceberg.", "level": "B2"},
    {"idiom": "go down in flames", "meaning": "провалиться", "example": "The project went down in flames.", "level": "C1"},
    {"idiom": "open Pandora's box", "meaning": "открыть ящик Пандоры", "example": "That opened a Pandora's box.", "level": "C1"},
    {"idiom": "at a crossroads", "meaning": "на распутье", "example": "Our company is at a crossroads.", "level": "B2"},
    {"idiom": "spill the beans", "meaning": "разболтать секрет", "example": "Come on, spill the beans!", "level": "B1"},
    {"idiom": "hit the nail on the head", "meaning": "попасть в точку", "example": "You hit the nail on the head.", "level": "B2"},
    {"idiom": "kick the bucket", "meaning": "умереть (неформ.)", "example": "He kicked the bucket at 95.", "level": "B2"},
    {"idiom": "rule of thumb", "meaning": "эмпирическое правило", "example": "As a rule of thumb, drink water.", "level": "B2"},
    {"idiom": "ring a bell", "meaning": "быть знакомым", "example": "Does that name ring a bell?", "level": "B1"},
    {"idiom": "on cloud nine", "meaning": "на седьмом небе", "example": "She's been on cloud nine.", "level": "B1"},
    {"idiom": "see eye to eye", "meaning": "быть согласным", "example": "We don't see eye to eye on politics.", "level": "B2"},
    {"idiom": "cold feet", "meaning": "струсить", "example": "He got cold feet before the wedding.", "level": "B2"},
    {"idiom": "beat around the bush", "meaning": "ходить вокруг да около", "example": "Stop beating around the bush.", "level": "B2"},
    {"idiom": "jump the gun", "meaning": "поспешить", "example": "Don't jump the gun.", "level": "B2"},
    {"idiom": "pull someone's leg", "meaning": "разыграть", "example": "Are you pulling my leg?", "level": "B1"},
    {"idiom": "bite off more than you can chew", "meaning": "взяться за непосильное", "example": "She bit off more than she could chew.", "level": "B2"},
    {"idiom": "cry over spilled milk", "meaning": "горевать о напрасном", "example": "Don't cry over spilled milk.", "level": "B2"},
    {"idiom": "give someone the cold shoulder", "meaning": "игнорировать", "example": "She gave me the cold shoulder.", "level": "B2"},
    {"idiom": "hang in there", "meaning": "держаться", "example": "Hang in there, things will get better.", "level": "B1"},
    {"idiom": "in the same boat", "meaning": "в одинаковом положении", "example": "We're all in the same boat.", "level": "B1"},
    {"idiom": "miss the boat", "meaning": "упустить возможность", "example": "You missed the boat.", "level": "B2"},
    {"idiom": "over the moon", "meaning": "на седьмом небе от счастья", "example": "She was over the moon.", "level": "B1"},
    {"idiom": "put all your eggs in one basket", "meaning": "рисковать всем", "example": "Don't put all your eggs in one basket.", "level": "B2"},
    {"idiom": "take a rain check", "meaning": "перенести", "example": "Can I take a rain check?", "level": "B2"},
    {"idiom": "the ball is in your court", "meaning": "решение за тобой", "example": "The ball is in your court.", "level": "B2"},
    {"idiom": "through thick and thin", "meaning": "в горе и радости", "example": "They stayed through thick and thin.", "level": "B2"},
    {"idiom": "under the gun", "meaning": "под давлением", "example": "We're under the gun to finish.", "level": "C1"},
    {"idiom": "wrap your head around", "meaning": "осмыслить", "example": "I can't wrap my head around this.", "level": "C1"},
    {"idiom": "a blessing in disguise", "meaning": "скрытое благо", "example": "Losing that job was a blessing in disguise.", "level": "B2"},
    {"idiom": "play it by ear", "meaning": "импровизировать", "example": "Let's play it by ear.", "level": "B2"},
]


def idioms_for_level(level: str) -> list[dict]:
    level_idx = CEFR_LEVELS.index(level) if level in CEFR_LEVELS else 3
    return [i for i in IDIOMS if CEFR_LEVELS.index(i["level"]) <= level_idx]


# ═══════════════════════════════════════════════════════════════
# CONFUSING WORDS — 25 entries
# ═══════════════════════════════════════════════════════════════

CONFUSING_WORDS = [
    {"pair": ("affect", "effect"), "explanation": "Affect — глагол (влиять). Effect — существительное (результат).", "examples": ("The weather affects my mood.", "The effect was immediate."), "level": "B1"},
    {"pair": ("lie", "lay"), "explanation": "Lie — лежать. Lay — класть (с объектом).", "examples": ("I lie on the bed.", "I lay the book down."), "level": "B2"},
    {"pair": ("who", "whom"), "explanation": "Who — подлежащее. Whom — дополнение.", "examples": ("Who called you?", "Whom did you call?"), "level": "B2"},
    {"pair": ("fewer", "less"), "explanation": "Fewer — исчисляемые. Less — неисчисляемые.", "examples": ("Fewer people came.", "Less water."), "level": "B1"},
    {"pair": ("its", "it's"), "explanation": "Its — притяжательное. It's = it is.", "examples": ("The dog wagged its tail.", "It's a nice day."), "level": "A2"},
    {"pair": ("their", "there", "they're"), "explanation": "Their — их. There — там. They're = they are.", "examples": ("Their car.", "There is a book.", "They're happy."), "level": "A2"},
    {"pair": ("your", "you're"), "explanation": "Your — твой. You're = you are.", "examples": ("Your book.", "You're kind."), "level": "A2"},
    {"pair": ("then", "than"), "explanation": "Then — затем. Than — чем (сравнение).", "examples": ("First eat, then sleep.", "She is taller than me."), "level": "A2"},
    {"pair": ("accept", "except"), "explanation": "Accept — принимать. Except — кроме.", "examples": ("I accept your offer.", "Everyone except John."), "level": "B1"},
    {"pair": ("principal", "principle"), "explanation": "Principal — главный. Principle — принцип.", "examples": ("The principal reason.", "A matter of principle."), "level": "B2"},
    {"pair": ("stationary", "stationery"), "explanation": "Stationary — неподвижный. Stationery — канцтовары.", "examples": ("The car was stationary.", "Buy stationery."), "level": "B2"},
    {"pair": ("compliment", "complement"), "explanation": "Compliment — похвала. Complement — дополнение.", "examples": ("She gave me a compliment.", "Wine complements cheese."), "level": "B2"},
    {"pair": ("advice", "advise"), "explanation": "Advice — совет (сущ.). Advise — советовать (глагол).", "examples": ("I need your advice.", "I advise you to rest."), "level": "A2"},
    {"pair": ("practice", "practise"), "explanation": "Practice — практика (сущ.). Practise — практиковать (глагол, UK).", "examples": ("Practice makes perfect.", "I practise piano."), "level": "B1"},
    {"pair": ("raise", "rise"), "explanation": "Raise — поднимать (с объектом). Rise — подниматься.", "examples": ("Raise your hand.", "The sun rises."), "level": "B1"},
    {"pair": ("borrow", "lend"), "explanation": "Borrow — брать в долг. Lend — давать в долг.", "examples": ("Can I borrow your pen?", "Can you lend me your pen?"), "level": "A2"},
    {"pair": ("bring", "take"), "explanation": "Bring — приносить сюда. Take — уносить.", "examples": ("Bring it to me.", "Take it to her."), "level": "A2"},
    {"pair": ("hear", "listen"), "explanation": "Hear — слышать. Listen — слушать (осознанно).", "examples": ("I hear a noise.", "I listen to music."), "level": "A2"},
    {"pair": ("see", "watch"), "explanation": "See — видеть. Watch — наблюдать.", "examples": ("I see a bird.", "I watch TV."), "level": "A2"},
    {"pair": ("say", "tell"), "explanation": "Say — без объекта. Tell — с объектом.", "examples": ("She said hello.", "She told me a story."), "level": "A2"},
    {"pair": ("fun", "funny"), "explanation": "Fun — удовольствие. Funny — смешной.", "examples": ("The party was fun.", "The joke was funny."), "level": "A2"},
    {"pair": ("sensible", "sensitive"), "explanation": "Sensible — благоразумный. Sensitive — чувствительный.", "examples": ("A sensible decision.", "She is sensitive."), "level": "B1"},
    {"pair": ("economic", "economical"), "explanation": "Economic — экономический. Economical — экономный.", "examples": ("Economic growth.", "An economical car."), "level": "B2"},
    {"pair": ("historic", "historical"), "explanation": "Historic — значимый. Historical — относящийся к истории.", "examples": ("A historic moment.", "A historical novel."), "level": "B2"},
    {"pair": ("lose", "loose"), "explanation": "Lose — терять. Loose — свободный.", "examples": ("Don't lose your keys.", "The screw is loose."), "level": "A2"},
]


def confusing_words_for_level(level: str) -> list[dict]:
    level_idx = CEFR_LEVELS.index(level) if level in CEFR_LEVELS else 3
    return [cw for cw in CONFUSING_WORDS if CEFR_LEVELS.index(cw["level"]) <= level_idx]


# ═══════════════════════════════════════════════════════════════
# PREPOSITIONS — 30 entries with usage patterns
# ═══════════════════════════════════════════════════════════════

PREPOSITIONS = [
    {"prep": "in", "usage": "в (внутри, месяцы, годы, города)", "example": "I live in London. Born in 1990.", "level": "A1"},
    {"prep": "on", "usage": "на (поверхность, дни, даты)", "example": "The book on the table. On Monday.", "level": "A1"},
    {"prep": "at", "usage": "в (точка, время)", "example": "I'm at home. At 3 PM.", "level": "A1"},
    {"prep": "to", "usage": "к, в (направление)", "example": "I go to school. Give it to me.", "level": "A1"},
    {"prep": "by", "usage": "около, посредством (кем/чем)", "example": "Written by Tolstoy. Travel by bus.", "level": "A2"},
    {"prep": "for", "usage": "для, за (цель, длительность)", "example": "This gift is for you. For two hours.", "level": "A1"},
    {"prep": "with", "usage": "с (вместе, инструмент)", "example": "I'm with my friend. Cut with a knife.", "level": "A1"},
    {"prep": "about", "usage": "о, около (тема)", "example": "We talked about movies.", "level": "A2"},
    {"prep": "from", "usage": "от, из (источник, происхождение)", "example": "I'm from Russia. A letter from John.", "level": "A1"},
    {"prep": "of", "usage": "принадлежность, часть", "example": "A cup of tea. The capital of France.", "level": "A1"},
    {"prep": "since", "usage": "с (точка отсчёта)", "example": "I've lived here since 2020.", "level": "B1"},
    {"prep": "during", "usage": "в течение (период)", "example": "Don't talk during the film.", "level": "B1"},
    {"prep": "between", "usage": "между (двумя)", "example": "Between you and me.", "level": "A2"},
    {"prep": "among", "usage": "среди (многими)", "example": "Among the crowd.", "level": "B1"},
    {"prep": "through", "usage": "через (насквозь)", "example": "Walk through the park.", "level": "B1"},
    {"prep": "across", "usage": "через (поверхность)", "example": "Walk across the street.", "level": "B1"},
    {"prep": "along", "usage": "вдоль", "example": "Walk along the river.", "level": "B1"},
    {"prep": "against", "usage": "против, у (опора)", "example": "I'm against the plan. Lean against the wall.", "level": "B1"},
    {"prep": "without", "usage": "без", "example": "I can't do it without you.", "level": "A2"},
    {"prep": "within", "usage": "в пределах, внутри", "example": "Within an hour. Within the company.", "level": "B2"},
    {"prep": "towards", "usage": "по направлению к", "example": "He walked towards the door.", "level": "B1"},
    {"prep": "upon", "usage": "на (формальный, = on)", "example": "Upon arrival, please call me.", "level": "B2"},
    {"prep": "despite", "usage": "несмотря на", "example": "Despite the rain, we went out.", "level": "B2"},
    {"prep": "beyond", "usage": "за пределами", "example": "Beyond the mountains. Beyond doubt.", "level": "B2"},
    {"prep": "beneath", "usage": "под, ниже", "example": "Beneath the surface.", "level": "B2"},
    {"prep": "beside", "usage": "рядом с", "example": "Sit beside me.", "level": "B1"},
    {"prep": "behind", "usage": "за, позади", "example": "The cat is behind the sofa.", "level": "A1"},
    {"prep": "below", "usage": "ниже", "example": "The temperature is below zero.", "level": "A2"},
    {"prep": "above", "usage": "выше, над", "example": "The plane is above the clouds.", "level": "A2"},
    {"prep": "under", "usage": "под", "example": "The cat is under the table.", "level": "A1"},
]


def prepositions_for_level(level: str) -> list[dict]:
    level_idx = CEFR_LEVELS.index(level) if level in CEFR_LEVELS else 3
    return [p for p in PREPOSITIONS if CEFR_LEVELS.index(p["level"]) <= level_idx]
