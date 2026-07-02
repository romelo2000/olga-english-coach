"""AI coach logic: prompt building, lesson generation, speaking assessment.

Incorporates modern language teaching methodology:
- Communicative Language Teaching (CLT)
- Task-Based Language Teaching (TBLT)
- Noticing hypothesis (draw attention to form)
- Interleaving and spaced practice
- Immediate corrective feedback with explanation
- Scaffolding: i+1 (Krashen's input hypothesis)
"""

from __future__ import annotations

import json
import random
import re
from dataclasses import dataclass
from pathlib import Path

from curriculum import (
    CEFR_CAN_DO, GrammarPoint, grammar_point_by_id, minimal_pairs_for_level,
)
from worddb import (
    phrasal_verbs_for_level, collocations_for_level, common_errors_for_level,
    idioms_for_level, confusing_words_for_level, prepositions_for_level,
)
from worddb import get_db
from ollama_client import GenerateOptions, OllamaClient


COACH_NAME = "Ольга"
START_COMMAND = "Ольга, давай работать"

MODE_PROMPTS = {
    "Диалог": (
        "Веди живой диалог на английском по уровню пользователя. "
        "Отвечай на английском, после каждого ответа давай короткий разбор на русском: "
        "ошибки, полезные выражения, 1 совет. Поддерживай разговор вопросами. "
        "Используй естественный разговорный английский, не академический."
    ),
    "Проверка": (
        "Исправляй английский текст пользователя. "
        "Возвращай блоки: 1) исправленная версия, 2) объяснение ошибок на русском — "
        "почему так не говорят и как правильно, 3) альтернативные естественные варианты."
    ),
    "Объяснение": (
        "Объясняй английскую грамматику, слова и фразы простым русским языком. "
        "Сначала — суть правила одним предложением по-русски. "
        "Затем 3 примера на английском с переводом. Затем мини-задание для проверки: "
        "только пропуски предлогов или коротких служебных слов, не длинные слова. "
        "Объясняй так, чтобы было понятно без лингвистического образования."
    ),
    "Упражнение": (
        "Создавай мини-упражнения по английскому под уровень пользователя. "
        "ВАЖНО: в заданиях fill-in-the-blank используй ТОЛЬКО предлоги, артикли, "
        "короткие вспомогательные слова (in, on, at, the, a, is, are, to, for, of, with, by, from). "
        "НЕ заставляйте пользователя печатать длинные слова или фразы. "
        "Дай 3-5 заданий с пропусками коротких слов, затем коротко проверь ответы и объясни на русском. "
        "Объясняй не только что неправильно, но и ПОЧЕМУ — ссылайся на правило."
    ),
    "Собеседник": (
        "Играй роль собеседника или интервьюера на английском. "
        "Задавай по одному вопросу за раз, поддерживай разговор. "
        "После ответа давай сжатую обратную связь на русском: "
        "что хорошо, что исправить, как звучать естественнее."
    ),
    "Ролевая игра": (
        "Проведи ролевую игру на английском. Опиши ситуацию на русском, назначь роль пользователю. "
        "Веди диалог от второго персонажа на английском. После каждого обмена — короткий разбор на русском."
    ),
    "Письмо": (
        "Дай письменное задание на английском (50-100 слов). "
        "Дай чёткую тему и критерии. Когда пользователь пришлёт текст — "
        "проверь грамматику, стиль, лексику и объясни на русском. "
        "Покажи, как сделать текст естественнее, дай 2-3 улучшенных варианта."
    ),
    "Чтение": (
        "Дай короткий текст на английском для чтения (80-120 слов, уровень пользователя). "
        "Текст должен быть интересным: история, статья, диалог. "
        "После текста: 1) 3 вопроса на понимание (ответы короткие), "
        "2) ключевые слова и фразы с переводом на русский, "
        "3) 1 вопрос для обсуждения на английском. "
        "Жди ответов пользователя, проверь и объясни на русском."
    ),
    "Диалог-аудирование": (
        "Создай короткий диалог на английском между двумя людьми (A и B), 6-8 реплик, уровень пользователя. "
        "Диалог должен быть из реальной жизни: в кафе, на работе, в аэропорту. "
        "После диалога: 1) 3 вопроса на понимание (короткие ответы), "
        "2) полезные фразы из диалога с переводом, "
        "3) попроси пользователя ответить за персонажа B на последнюю реплику A. "
        "Жди ответов, проверь и объясни на русском."
    ),
    "Диктант": (
        "Проведи диктант на английском для уровня пользователя. "
        "Дай 5 очень коротких предложений (3-5 слов каждое). "
        "Пользователь должен напечатать только предлоги, артикли и короткие служебные слова в пропусках. "
        "НЕ заставляй печатать длинные слова. "
        "После проверки объясни ошибки на русском."
    ),
    "Shadowing": (
        "Проведи shadowing-практику для уровня пользователя. "
        "Дай 3 короткие английские фразы (3-6 слов) на тему. "
        "Пользователь повторит каждую вслух. "
        "Затем задай 1 вопрос по теме для свободного ответа. "
        "Проверь ответы, дай обратную связь на русском."
    ),
    "Minimal Pairs": (
        "Проведи практику minimal pairs для тренировки произношения. "
        "Покажи пары слов с близкими звуками (ship/sheep, bad/bed). "
        "Для каждой пары: 1) оба слова с IPA, 2) пример предложения для каждого, "
        "3) попроси пользователя сказать какое слово он слышит. "
        "Дай 5 пар, проверь ответы, объясни разницу звуков на русском."
    ),
    "Collocation Drill": (
        "Проведи тренировку словосочетаний (collocations). "
        "Дай 5 слов и попроси дополнить словосочетание одним коротким словом. "
        "Пример: heavy ___ (rain/traffic/bag). "
        "Пользователь печатает только короткие слова. "
        "Проверь ответы, объясни частые словосочетания на русском."
    ),
    "Error Correction": (
        "Проведи упражнение 'найди ошибку'. "
        "Дай 5 английских предложений с одной ошибкой в каждом (грамматика, предлог, артикль, время). "
        "Попроси пользователя найти и исправить ошибку. "
        "Пользователь печатает только исправленное слово/фразу. "
        "Проверь ответы, объясни каждую ошибку на русском."
    ),
    "Sentence Transformation": (
        "Проведи упражнение 'преобразование предложений' (FCE/CAE style). "
        "Дай предложение и начало второго. Пользователь должен завершить второе "
        "так, чтобы оно означало то же самое. "
        "Пример: 'I have never seen such a film.' → 'This is the first time ___' "
        "Дай 5 заданий. Проверь ответы, объясни грамматику на русском."
    ),
    "Phrasal Verbs": (
        "Проведи тренировку фразовых глаголов (phrasal verbs). "
        "Дай 5 фразовых глаголов с контекстом (get up, look after, put off, etc). "
        "Попроси пользователя дополнить предложение правильным фразовым глаголом. "
        "Пользователь печатает только короткий ответ. "
        "Проверь ответы, объясни значения на русском. "
        "Покажи синонимы (get up = wake up, put off = postpone)."
    ),
    "Dictogloss": (
        "Проведи dictogloss — реконструкцию текста. "
        "Шаг 1: дай короткий английский текст (40-60 слов, уровень пользователя) с целевой грамматикой. "
        "Шаг 2: попроси пользователя внимательно прочитать. "
        "Шаг 3: попроси реконструировать текст по памяти, сохраняя смысл и грамматику. "
        "Не требуй дословного повторения — главное смысл и структура. "
        "Шаг 4: сравни с оригиналом, объясни на русском что получилось и что можно улучшить. "
        "Обрати внимание на грамматические формы, которые пользователь пропустил или заменил."
    ),
    "Input Flood": (
        "Проведи input flood — насыщенное погружение в целевую форму. "
        "Дай короткий текст (80-100 слов) где одна грамматическая структура встречается 5-7 раз "
        "(например: Present Perfect, conditionals, passive voice). "
        "Текст должен быть естественным и интересным. "
        "После текста: 1) попроси пользователя найти все примеры целевой формы, "
        "2) объясни на русском почему используется именно эта форма в каждом случае, "
        "3) дай 2 предложения с пропусками для самостоятельного заполнения."
    ),
    "Pushed Output": (
        "Проведи pushed output task — задачу с грамматическим ограничением. "
        "Дай пользователю тему и требование: рассказать историю или описать ситуацию, "
        "используя минимум 3 конкретные грамматические структуры (укажи какие). "
        "Пример: 'Опиши свой последний отпуск, используя: 1) Past Continuous, 2) Past Perfect, 3) хотя бы один phrasal verb'. "
        "Дай пользователю 1 минуту на планирование. "
        "После ответа: проверь использование требуемых структур, объясни ошибки на русском, "
        "покажи как можно было выразить мысль точнее."
    ),
    "Lexical Chunks": (
        "Проведи тренировку лексических чанков (lexical chunks / formulaic sequences). "
        "Дай 6 высокочастотных речевых клише и устойчивых выражений по теме: "
        "дискурсивные маркеры (on the other hand, as a matter of fact), "
        "sentence stems (I think it's important to..., What I mean is...), "
        "collocations (make a decision, take a risk). "
        "Для каждого: 1) сам чанк, 2) перевод, 3) пример в контексте. "
        "Затем дай мини-диалог с пропусками — пользователь вставляет нужные чанки. "
        "Проверь ответы, объясни на русском когда и зачем используются эти выражения."
    ),
    "Task Repetition": (
        "Проведи task repetition with variation — повторение задачи в новом контексте. "
        "Шаг 1: дай пользователю короткую коммуникативную задачу (например: заказать еду в ресторане). "
        "Шаг 2: после ответа дай обратную связь на русском. "
        "Шаг 3: попроси выполнить ТОТ ЖЕ тип задачи, но в новом контексте "
        "(например: заказать такси, забронировать отель). "
        "Шаг 4: сравни оба ответа — отметь улучшения и что осталось проблемой. "
        "Цель: показать прогресс и закрепить структуры через вариативное повторение."
    ),
}

LEVEL_HINTS = {
    "A1": (
        "Начинающий. Используй ТОЛЬКО: Present Simple, to be, have got, числа, цвета, дни недели. "
        "Словарь: 500–800 самых частотных слов. Предложения — максимум 6–8 слов. "
        "Объясняй каждое новое слово сразу. Никаких идиом и сложных структур. "
        "Исправляй каждую ошибку мягко, одно исправление за раз."
    ),
    "A2": (
        "Базовый уровень. Грамматика: Past Simple, Present Continuous, сравнительные степени, "
        "базовые предлоги (in/on/at/to), модальные can/must/should. "
        "Словарь: 1000–1500 слов, бытовые темы (семья, работа, шоппинг, путешествия). "
        "Предложения до 12 слов. Объясняй правила через простые паттерны."
    ),
    "B1": (
        "Средний уровень. Грамматика: Present Perfect vs Past Simple, First & Second Conditional, "
        "relative clauses (who/which/that), passive voice (basic), gerunds vs infinitives. "
        "Словарь: 2000–3000 слов, разговорные выражения, базовые phrasal verbs. "
        "Активно исправляй артикли и предлоги — самые частые ошибки на этом уровне."
    ),
    "B2": (
        "Уверенный уровень. Грамматика: все conditionals, reported speech, inversion (basic), "
        "advanced passives, wish/if only. Словарь: 4000–5000 слов, идиомы, коллокации, "
        "академическая лексика (base forms). Фокус: точность формулировок, "
        "избегание кальки с русского, естественный порядок слов."
    ),
    "C1": (
        "Продвинутый уровень. Грамматика: inversion (advanced), participle clauses, "
        "cleft sentences, ellipsis. Словарь: 6000–8000 слов, низкочастотная лексика, "
        "нюансы синонимов (e.g. big/large/vast). Исправляй стилистические неточности, "
        "неуместный регистр, избыточные хеджи. Давай задания на перефразирование."
    ),
    "C2": (
        "Экспертный уровень. Грамматика: все конструкции включая устаревшие и литературные. "
        "Словарь: 10000+ слов, академический и литературный регистры, тонкие коннотации. "
        "Фокус: стиль, когерентность, риторические приёмы. "
        "Исправляй только реальные ошибки, не вкусовщину."
    ),
}


@dataclass
class CoachSettings:
    model: str
    mode: str
    level: str
    topic: str
    concise: bool
    practice_type: str = "dialogue"


class Coach:
    """AI coach that builds prompts and processes responses."""

    MAX_HISTORY = 12

    def __init__(self, client: OllamaClient) -> None:
        self.client = client
        self.conversation_history: list[tuple[str, str]] = []

    def add_to_history(self, role: str, text: str) -> None:
        self.conversation_history.append((role, text))
        if len(self.conversation_history) > self.MAX_HISTORY * 2:
            self.conversation_history = self.conversation_history[-(self.MAX_HISTORY * 2):]

    def clear_history(self) -> None:
        self.conversation_history.clear()

    def save_history(self, path: Path) -> None:
        try:
            data = [{"role": r, "text": t} for r, t in self.conversation_history]
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    def load_history(self, path: Path) -> None:
        try:
            if not path.exists():
                return
            data = json.loads(path.read_text(encoding="utf-8"))
            self.conversation_history = [(item["role"], item["text"]) for item in data][-self.MAX_HISTORY * 2:]
        except Exception:
            self.conversation_history = []

    def _format_history(self) -> str:
        if not self.conversation_history:
            return ""
        history = self.conversation_history
        if len(history) <= 6:
            lines = []
            for role, text in history:
                label = "Пользователь" if role == "user" else COACH_NAME
                snippet = text[:200].replace("\n", " ").strip()
                lines.append(f"{label}: {snippet}")
            return "\n".join(lines)
        older = history[:-6]
        recent = history[-6:]
        summary_parts = []
        for role, text in older:
            label = "Пользователь" if role == "user" else COACH_NAME
            snippet = text[:60].replace("\n", " ").strip()
            summary_parts.append(f"{label}: {snippet}")
        summary = " | ".join(summary_parts)
        lines = [f"[Ранее в разговоре: {summary}]"]
        for role, text in recent:
            label = "Пользователь" if role == "user" else COACH_NAME
            snippet = text[:200].replace("\n", " ").strip()
            lines.append(f"{label}: {snippet}")
        return "\n".join(lines)

    def build_prompt(self, settings: CoachSettings, user_text: str, learning_context: str, error_patterns: list[tuple[str, int]] | None = None, profile_context: str = "", srs_recall_words: list[str] | None = None) -> str:
        topic = settings.topic.strip() or "свободная практика английского"
        mode_prompt = MODE_PROMPTS.get(settings.mode, MODE_PROMPTS["Диалог"])
        level_hint = LEVEL_HINTS.get(settings.level, LEVEL_HINTS["B1"])
        can_do = CEFR_CAN_DO.get(settings.level, "")

        brevity_rule = (
            "Отвечай очень компактно, без воды. Используй короткие блоки: "
            "ENGLISH, ИСПРАВЛЕНИЯ, ПОЧЕМУ, ФОКУС."
            if settings.concise
            else "Структурируй ответ, но оставайся практичным и понятным."
        )

        history = self._format_history() or "(пока нет предыдущих сообщений)"

        error_block = ""
        if error_patterns:
            error_lines = [f"  - {pat} (×{count})" for pat, count in error_patterns[:5]]
            error_block = "\nЧастые ошибки пользователя (обращай на них особое внимание):\n" + "\n".join(error_lines)

        profile_block = ""
        if profile_context:
            profile_block = f"\nПрофиль ученика: {profile_context}\nИспользуй эту информацию естественно в диалоге — обращайся по имени, связывай примеры с профессией и целями."

        recall_block = ""
        if srs_recall_words:
            recall_block = "\nСлова на повторение (естественно вставь в диалог или задание):\n" + ", ".join(srs_recall_words)

        db_block = ""
        if settings.mode == "Phrasal Verbs":
            pvs = phrasal_verbs_for_level(settings.level)[:10]
            if pvs:
                pv_lines = [f"  - {pv['verb']}: {pv['meaning']} | {pv['example']}" for pv in pvs]
                db_block = "\nИспользуй эти фразовые глаголы из базы:\n" + "\n".join(pv_lines)
        elif settings.mode == "Collocation Drill":
            cols = collocations_for_level(settings.level)[:10]
            if cols:
                col_lines = [f"  - {c['adjective']} + {c['noun']}: {c['example']}" for c in cols]
                db_block = "\nИспользуй эти коллокации из базы:\n" + "\n".join(col_lines)
        elif settings.mode == "Error Correction":
            errs = common_errors_for_level(settings.level)[:8]
            if errs:
                err_lines = [f"  - Wrong: {e['wrong']} → Correct: {e['correct']}" for e in errs]
                db_block = "\nИспользуй эти типичные ошибки как основу для заданий:\n" + "\n".join(err_lines)
        elif settings.mode == "Диалог" and settings.topic and "idiom" in settings.topic.lower():
            idms = idioms_for_level(settings.level)[:8]
            if idms:
                id_lines = [f"  - {i['idiom']}: {i['meaning']} | {i['example']}" for i in idms]
                db_block = "\nВключи эти идиомы в диалог:\n" + "\n".join(id_lines)
        elif settings.mode == "Упражнение" and settings.topic and "preposition" in settings.topic.lower():
            preps = prepositions_for_level(settings.level)[:10]
            if preps:
                prep_lines = [f"  - {p['prep']}: {p['usage']} | {p['example']}" for p in preps]
                db_block = "\nИспользуй эти предлоги в упражнении:\n" + "\n".join(prep_lines)
        elif settings.mode == "Диалог":
            try:
                words = get_db().random_words(settings.level, 8)
                if words:
                    word_lines = [f"  - {w['word']} ({w['cefr']}): {w['translation']}" for w in words if w["translation"]]
                    if word_lines:
                        db_block = "\nПостарайся естественно использовать эти слова в диалоге:\n" + "\n".join(word_lines)
            except Exception:
                pass

        return f"""Ты локальный AI-репетитор английского языка.
Твоё имя: {COACH_NAME}.

Обязательные правила:
- Если пользователь обращается к тебе как к Ольге или Olga, отзовись как {COACH_NAME}.
- Понимай русский и английский без переключения режима.
- Если пользователь пишет по-русски — отвечай на русском, объясняй правила на русском.
- Если пользователь пишет на английском — отвечай на английском, но разбор и пояснения — на русском.
- Все объяснения грамматики, правил, пояснения к исправлениям — ТОЛЬКО на русском.
- Английский используй для примеров, заданий и диалога.
- Будь дружелюбным, как живой преподаватель, но без воды.
- Если пользователь ошибается в английском — обязательно мягко исправляй и объясняй ПОЧЕМУ.
- Объясняй правила простым языком, без лингвистических терминов (или поясняй их).
- Если запрос не связан с английским — аккуратно верни разговор к изучению языка.
- Адаптируй обучение по слабым местам пользователя (см. контекст ниже).
- Используй принцип i+1: материал чуть выше текущего уровня пользователя.
- Не описывай свои рассуждения, давай только результат и короткое объяснение.
- В диалоге задавай не более одного вопроса за раз.
- Строго соблюдай уровень пользователя ({settings.level}): не используй грамматику и лексику выше этого уровня без объяснения.
- Адаптивная сложность: если пользователь отвечает без ошибок — делай следующий вопрос или задание чуть сложнее. Если ошибается — упрощай. Не перескакивай через уровни.
- В заданиях fill-in-the-blank используй только пропуски предлогов, артиклей и коротких служебных слов. Не заставляй печатать длинные слова.
- Corpus-based examples: приводи реальные, естественные примеры из живого английского, не выдуманные. Показывай как слово реально используется в речи и текстах.

Текущий режим: {settings.mode}
Инструкция режима: {mode_prompt}
Уровень пользователя: {settings.level}
Подсказка по уровню: {level_hint}
Can-do: {can_do}
Тема или цель: {topic}
Внутренний контекст обучения: {learning_context}
Стиль ответа: {brevity_rule}{error_block}{profile_block}{recall_block}{db_block}

Дополнительные инструкции:
- Если это первое сообщение сессии и режим диалог/упражнение — начни с короткого warmup: 1 вопрос на активацию знаний по теме.
- В конце каждого упражнения давай 1 мини-вопрос на закрепление (recap).
- Если знаешь имя ученика — обращайся по имени естественно, не в каждом сообщении.
- Хвали за серию правильных ответов, подбадривай после ошибок.

Предыдущие сообщения (для контекста диалога):
{history}

Сообщение пользователя:
{user_text}""".strip()

    def generate(self, settings: CoachSettings, user_text: str, learning_context: str, error_patterns: list[tuple[str, int]] | None = None, profile_context: str = "", srs_recall_words: list[str] | None = None) -> str:
        prompt = self.build_prompt(settings, user_text, learning_context, error_patterns, profile_context, srs_recall_words)
        options = GenerateOptions(
            temperature=0.7,
            num_predict=600 if settings.concise else 1000,
            top_p=0.9,
            num_ctx=4096,
        )
        # use_cache only for low-temperature (deterministic) non-dialogue calls
        cacheable = options.temperature < 0.5
        response = self.client.generate(settings.model, prompt, options, use_cache=cacheable)
        self.add_to_history("user", user_text)
        self.add_to_history("assistant", response)
        return response

    def generate_stream(self, settings: CoachSettings, user_text: str, learning_context: str, error_patterns: list[tuple[str, int]] | None = None, on_chunk=None, profile_context: str = "", srs_recall_words: list[str] | None = None) -> str:
        """Streaming generate — calls on_chunk(text) as chunks arrive, returns full response."""
        prompt = self.build_prompt(settings, user_text, learning_context, error_patterns, profile_context, srs_recall_words)
        options = GenerateOptions(
            temperature=0.7,
            num_predict=600 if settings.concise else 1000,
            top_p=0.9,
            num_ctx=4096,
        )
        full_response = ""
        try:
            for chunk in self.client.generate_stream(settings.model, prompt, options):
                full_response += chunk
                if on_chunk:
                    on_chunk(chunk)
        except Exception:
            if not full_response:
                raise
        full_response = full_response.strip()
        self.add_to_history("user", user_text)
        self.add_to_history("assistant", full_response)
        return full_response

    def build_grammar_lesson_prompt(self, level: str, grammar_point: GrammarPoint, concise: bool) -> str:
        examples_text = "\n".join(f"  - {ex}" for ex in grammar_point.examples)
        errors_text = "\n".join(f"  - {err}" for err in grammar_point.common_errors)
        style = "Кратко, без воды." if concise else "Подробно, но структурированно."
        return f"""Ты AI-репетитор английского. Имя: {COACH_NAME}.
Уровень: {level}
Тема грамматики: {grammar_point.title}
Описание: {grammar_point.summary}
Примеры:
{examples_text}
Типичные ошибки:
{errors_text}

Задача:
1. Объясни правило простым русским языком (2-3 предложения).
2. Дай 3 примера на английском с переводом.
3. Дай 4 задания на отработку: только пропуски предлогов, артиклей или коротких служебных слов (in/on/at/the/a/is/are/to/for/of/with/by). НЕ заставляй печатать длинные слова.
4. Пользователь ответит — проверь и объясни ошибки.
{style}""".strip()

    def build_vocab_review_prompt(self, level: str, cards: list[tuple[str, str, str]], concise: bool) -> str:
        cards_text = "\n".join(f"  - {word} → {trans} (пример: {ex})" for word, trans, ex in cards)
        style = "Кратко." if concise else "Развёрнуто."
        return f"""Ты AI-репетитор английского. Имя: {COACH_NAME}.
Уровень: {level}

Повтори эти слова с пользователем:
{cards_text}

Задача:
1. Покажи каждое слово с примером и произношением (IPA если есть).
2. Покажи словообразование (word family) для каждого слова.
3. Задай вопрос или дай мини-задание на каждое слово.
4. Проверь ответы, объясни ошибки на русском.
5. Дай совет, как запомнить трудные слова.
{style}""".strip()

    def build_writing_task_prompt(self, level: str, topic: str, concise: bool) -> str:
        style = "Кратко." if concise else "Подробно."
        return f"""Ты AI-репетитор английского. Имя: {COACH_NAME}.
Уровень: {level}
Тема: {topic}

Задача:
1. Дай writing task: тема, объём 50-100 слов, 2-3 критерия оценки.
2. Жди ответ пользователя.
3. Проверь: грамматику, лексику, стиль, связность.
4. Дай исправленную версию и объяснение на русском.
{style}""".strip()

    def build_speaking_drill_prompt(self, level: str, topic: str, concise: bool) -> str:
        style = "Кратко." if concise else "Развёрнуто."
        return f"""Ты AI-репетитор английского. Имя: {COACH_NAME}.
Уровень: {level}
Тема: {topic}

Задача:
1. Задай один вопрос на английском по теме.
2. Жди ответ пользователя (текст или голос).
3. Дай короткий разбор: грамматика, лексика, естественность.
4. Задай следующий вопрос (сложнее на шаг).
{style}""".strip()

    def build_roleplay_prompt(self, level: str, scenario: str, concise: bool) -> str:
        style = "Кратко." if concise else "Развёрнуто."
        return f"""Ты AI-репетитор английского. Имя: {COACH_NAME}.
Уровень: {level}
Сценарий: {scenario}

Задача:
1. Опиши ситуацию на русском (1-2 предложения).
2. Назначь роль пользователю.
3. Начни диалог от своего персонажа на английском.
4. После каждого обмена — короткий разбор ошибок на русском.
{style}""".strip()

    def build_listening_prompt(self, level: str, topic: str, concise: bool) -> str:
        style = "Кратко." if concise else "Развёрнуто."
        return f"""Ты AI-репетитор английского. Имя: {COACH_NAME}.
Уровень: {level}
Тема: {topic}

Задача — практика аудирования:
1. Напиши короткий текст на английском (60-80 слов, уровень {level}) на тему.
2. Текст должен быть естественным, с парой полезных выражений.
3. После текста задай 3 вопроса по содержанию на английском.
4. Жди ответы пользователя. Проверь и объясни на русском.
5. Дай ключевые слова и фразы из текста с переводом.
{style}""".strip()


def analyze_speaking(voice_data: dict) -> dict:
    """Heuristic speaking assessment from voice transcription data."""
    transcript = (voice_data.get("transcript") or "").strip()
    words = [word for word in transcript.split() if word]
    word_count = len(words)
    speech_seconds = max(0.8, float(voice_data.get("speechSeconds") or voice_data.get("speech_seconds") or 0.0))
    confidence = max(0.0, min(1.0, float(voice_data.get("confidence") or 0.0)))
    wpm = int(word_count * 60 / speech_seconds) if word_count else 0

    pronunciation_score = int(min(100, max(20, confidence * 82 + min(word_count, 20) * 1.2)))
    if word_count < 4:
        pronunciation_score = max(20, pronunciation_score - 12)

    tempo_delta = abs(wpm - 118)
    tempo_score = max(18, min(100, 100 - int(tempo_delta * 0.9)))
    if wpm == 0:
        tempo_score = 0

    confidence_score = int(min(100, max(18, confidence * 75 + min(word_count, 18) * 1.4)))
    if speech_seconds < 1.5:
        confidence_score = max(18, confidence_score - 10)

    overall = int((pronunciation_score + tempo_score + confidence_score) / 3)
    if overall >= 80:
        overall_label = "сильный"
    elif overall >= 62:
        overall_label = "уверенный"
    elif overall >= 45:
        overall_label = "рабочий"
    else:
        overall_label = "нестабильный"

    scores = {
        "pronunciation": pronunciation_score,
        "tempo": tempo_score,
        "confidence": confidence_score,
    }
    focus_hint = min(scores, key=scores.get)

    return {
        "transcript": transcript,
        "word_count": word_count,
        "speech_seconds": round(speech_seconds, 1),
        "recognition_confidence": int(confidence * 100),
        "wpm": wpm,
        "pronunciation_score": pronunciation_score,
        "tempo_score": tempo_score,
        "confidence_score": confidence_score,
        "overall_score": overall,
        "overall_label": overall_label,
        "focus_hint": focus_hint,
    }


def extract_speakable_text(payload: str, max_lines: int = 0) -> str:
    """Extract English text suitable for TTS, skipping Russian explanations.

    Args:
        payload: The full text to extract from.
        max_lines: If >0, limit to this many lines. If 0, use all lines.
    """
    lines = []
    for line in payload.splitlines():
        clean = line.strip()
        if not clean:
            continue
        if re.search(r"[А-Яа-яЁё]", clean):
            continue
        if clean.lower().startswith(("ошибки:", "разбор:", "почему:", "совет:", "focus:", "фокус:", "исправ")):
            continue
        lines.append(clean)
    if max_lines > 0:
        return " ".join(lines[:max_lines]) or payload
    return " ".join(lines) or payload


def count_errors(assistant_text: str) -> int:
    """Roughly count error corrections in assistant response."""
    markers = re.findall(r"(?i)(?:→|исправ|ошибк|correct|wrong|should be|instead)", assistant_text)
    return min(10, len(markers))


def build_feedback_report(user_text: str, assistant_text: str, level: str) -> str:
    """Build a prompt for generating a post-chat feedback report."""
    return f"""Ты — аналитик английского языка. Проанализируй диалог ученика уровня {level} и дай краткий отчёт.

Сообщение ученика:
{user_text}

Ответ преподавателя:
{assistant_text}

Дай отчёт в следующем формате (на русском, компактно):

📊 ОТЧЁТ ПО ДИАЛОГУ
─ Оценка fluency: X/10 (краткое обоснование)
─ Исправлено ошибок: N
─ Топ-3 ошибки (с правильным вариантом):
  1. ...
  2. ...
  3. ...
─ Новые слова из ответа (англ → рус):
  • word1 — перевод
  • word2 — перевод
─ Совет на следующий раз: одно короткое предложение

Если ошибок не было — похвали и предложи усложнение.
Не выдумывай ошибки — анализируй только реальный текст.""".strip()


_STORY_TOPICS = [
    "a mystery at an old hotel",
    "a job interview gone wrong",
    "a strange encounter on a train",
    "a teenager's first day at a new school",
    "an unexpected inheritance",
    "a cooking competition",
    "a lost dog finding its way home",
    "a scientist's discovery",
    "a traveler stranded in a foreign city",
    "a neighbor's secret",
    "a birthday surprise gone wrong",
    "a musician's big break",
    "a misunderstanding at a restaurant",
    "a hike that went wrong",
    "an old photograph",
    "a new roommate",
    "a power outage in a small town",
    "a chance meeting at a bookstore",
    "a difficult choice",
    "a family reunion",
]


def build_story_prompt(level: str, srs_words: list[str], topic: str = "") -> str:
    """Build a prompt for generating a short story using the learner's SRS words."""
    words_str = ", ".join(srs_words) if srs_words else "(любые полезные слова)"
    if not topic:
        topic = random.choice(_STORY_TOPICS)
    return f"""Напиши короткий рассказ на английском языке для ученика уровня {level}.

Тема рассказа: {topic}
Это тема ОБЯЗАТЕЛЬНА. Рассказ должен быть именно про это, а не про экологию или окружающую среду.

Обязательные требования:
- Используй ВСЕ эти слова из словаря ученика: {words_str}
- Каждое слово из списка должно быть использовано естественно в контексте
- Длина: 150–250 слов
- Уровень лексики и грамматики: строго {level} (i+1 — чуть выше)
- Рассказ должен быть интересным и связным
- В конце раздели чертой и напиши:
  1. Список использованных SRS-слов с их значением в контексте (англ → рус)
  2. Три вопроса по содержанию на английском

Формат:
[рассказ]

---
SRS слова:
• word1 — значение в контексте
• word2 — ...

Вопросы:
1. ...
2. ...
3. ...""".strip()


def build_reading_adaptation_prompt(level: str, article_text: str) -> str:
    """Build a prompt to adapt a web article to the learner's CEFR level."""
    # Truncate very long articles
    if len(article_text) > 4000:
        article_text = article_text[:4000] + "..."
    return f"""Ты — редактор учебных материалов. Адаптируй текст статьи на английском язык для ученика уровня {level}.

Исходный текст:
{article_text}

Задачи:
1. Упрости лексику и грамматику до уровня {level} (i+1 — чуть выше текущего)
2. Сохрани основной смысл и ключевые факты
3. Длина: 200–400 слов
4. Выдели **жирным** (используй **word**) 5–8 ключевых слов для изучения
5. После текста раздели чертой и дай:
   - Глоссарий: каждое выделенное слово → перевод на русский
   - 2 вопроса на понимание на английском

Формат:
[адаптированный текст]

---
Глоссарий:
• **word1** — перевод
• **word2** — перевод

Вопросы:
1. ...
2. ...""".strip()


def build_quiz_prompt(level: str, chat_text: str) -> str:
    """Build a prompt for generating a quiz from recent chat content."""
    if len(chat_text) > 3000:
        chat_text = chat_text[-3000:]
    return f"""Ты — создатель тестов по английскому. На основе диалога ученика уровня {level} составь мини-викторину.

Диалог:
{chat_text}

Составь 4 вопроса (на русском):
1. Два вопроса на понимание содержания (с 3 вариантами ответа каждый)
2. Один вопрос на грамматику из диалога (с 3 вариантами)
3. Один вопрос на лексику — "что значит слово X в контексте?" (с 3 вариантами)

Формат:
❓ Вопрос 1: ...
  A) ...  B) ...  C) ...
  ✅ Правильный ответ: B

❓ Вопрос 2: ...
  ...

В конце дай краткий комментарий: что ученику стоит повторить.""".strip()


def build_mnemonic_prompt(word: str, translation: str, level: str) -> str:
    """Build a prompt for generating a mnemonic association for a difficult word."""
    return f"""Придумай мнемонику для запоминания английского слова.

Слово: {word}
Перевод: {translation}
Уровень ученика: {level}

Дай:
1. Ассоциацию на русском (созвучие или образ)
2. Короткое предложение-запоминалку на русском с этим словом
3. Пример на английском с этим словом

Формат (3 строки):
🧠 Ассоциация: ...
📝 Запоминалка: ...
💬 Пример: ...""".strip()


def build_dictation_prompt(level: str, topic: str = "") -> str:
    """Build a prompt for generating a dictation sentence at the learner's level."""
    topic_str = f" на тему {topic}" if topic else ""
    return f"""Сгенерируй одно предложение на английском для диктанта.
Уровень: {level}{topic_str}.
Длина: 8-15 слов. Простое, понятное, без сложной пунктуации.
Ответь ТОЛЬКО самим предложением на английском, без пояснений.""".strip()


def build_debate_prompt(level: str, topic: str = "") -> str:
    """Build a prompt for AI debate mode — Olga takes a position and argues."""
    topic_str = topic if topic else "выбери любую интересную тему (технологии, образование, путешествия)"
    return f"""Ты — Ольга, преподаватель английского и партнёр для дебатов.
Уровень ученика: {level}.

Тема для дебатов: {topic_str}.

Задачи:
1. Займи чёткую позицию по теме (можно спорную)
2. Представь аргумент на английском (3-5 предложений, уровень {level})
3. В конце задай ученику вопрос, приглашая его возразить
4. Будь дружелюбной, но настойчивой в споре
5. Используй связующие: Firstly, Moreover, However, On the other hand

Начни с: "Let's debate! I believe that..." и закончи вопросом.""".strip()


def build_recommendation_prompt(
    level: str,
    learning_context: str,
    error_patterns: list[tuple[str, int]],
    profile_ctx: str,
    srs_due: int,
    weekly_xp: int,
    weekly_xp_goal: int,
    streak: int,
) -> str:
    """Build a prompt for personalised learning recommendations when user asks 'Дальше?'."""
    error_str = ", ".join(f"{k} ({v} раз)" for k, v in error_patterns[:3]) if error_patterns else "ошибок пока мало"
    profile_str = profile_ctx if profile_ctx else "профиль не заполнен"
    return f"""Ты — Ольга, преподаватель английского.
Ученик спрашивает «Дальше?» — он хочет узнать, что делать дальше для прогресса.

Дай 2-3 конкретные рекомендации на русском (коротко, дружелюбно):
1. Что потренировать прямо сейчас (на основе слабых зон и ошибок)
2. Что повторить (SRS, грамматика)
3. Что-то новое для разнообразия

Данные ученика:
- Уровень: {level}
- Контекст: {learning_context}
- Частые ошибки: {error_str}
- Профиль: {profile_str}
- Карточек к повторению: {srs_due}
- XP за неделю: {weekly_xp}/{weekly_xp_goal}
- Streak: {streak} дней

Формат:
🎯 **Следующий шаг:** [конкретное задание на английском, 1-2 предложения]
📋 **Повторить:** [что повторить из SRS/грамматики]
💡 **Совет:** [мотивационный совет или что-то новое]

Не пиши длинные тексты. Будь конкретной и дружелюбной.""".strip()


def _fallback_words(level: str, count: int = 12) -> list[str]:
    """Return English words from the database when SRS is empty."""
    try:
        db = get_db()
        words = db.random_words(level, count)
        return [w["word"] for w in words if w.get("word")]
    except Exception:
        return []


def build_diglot_prompt(level: str, srs_words: list[str], topic: str = "") -> str:
    """Build a prompt for a Diglot Weave bilingual story.

    The story starts in Russian and gradually substitutes Russian words
    with English ones, using the learner's SRS vocabulary. Based on the
    Diglot Weave technique (comprehensible input via gradual L2 immersion).
    """
    words = list(srs_words[:15])
    if not words:
        words = _fallback_words(level, 12)
    if not words:
        words = [
            "table", "chair", "kitchen", "coffee", "window", "door",
            "book", "friend", "phone", "city", "weather", "morning",
        ]
    words_str = ", ".join(words)
    if not topic:
        topic = random.choice(_STORY_TOPICS)

    return f"""Ты пишешь билингвальный рассказ (Diglot Weave) для русского ученика уровня {level}.

Тема: {topic}
Английские слова для вплетения: {words_str}

=== ЖЁСТКИЕ ПРАВИЛА ===
1. БАЗОВЫЙ ЯЗЫК — РУССКИЙ. Каждое предложение должно содержать русские слова.
2. Английские слова из списка заменяют русские слова, но не заменяют ВСЕ слова.
3. Английские слова выделяй **жирным**: **table**, **coffee**.
4. НЕЛЬЗЯ писать целые предложения только на английском в абзацах 1-3.
5. Контекст должен объяснять значение английского слова без перевода.

=== ПРИМЕР ===
Слова: table, chair, kitchen
Тема: завтрак

Утром Мария вошла на **kitchen**. Она увидела **table** и **chair**. На **table** стояла тарелка. Рядом с **chair** лежала книга. Она хотела **coffee**, но в чайнике закончилась вода.

=== СТРУКТУРА ===
Абзац 1 — 90% русский, 10% английский:
  Замени только 1-2 слова из списка: {words_str}.
  ~3-4 предложения. Русский язык — основа.

Абзац 2 — 70% русский, 30% английский:
  Замени 3-5 слов. Короткие фразы тоже можно вплетать.
  ~3-4 предложения. База всё ещё русская.

Абзац 3 — 50% русский, 50% английский:
  Замени больше слов, но предложения всё равно должны начинаться/заканчиваться на русском.
  ~3-4 предложения.

Абзац 4 — 30% русский, 70% английский:
  В основном английский, но русские слова должны связывать текст.
  ~3-4 предложения.

Абзац 5 — 90% английский:
  Почти полностью на английском, уровень {level}. Только 1-2 русских слова для связи.
  ~3-4 предложения.

=== ПРОВЕРЬ СЕБЯ ===
Если в абзацах 1-3 больше английских слов, чем русских — это ошибка. Исправь.

=== ФОРМАТ ===
[рассказ с 5 абзацами]

---
English words used:
• word1
• word2
...

Questions:
1. ...
2. ...
3. ...

Длина: 200-350 слов всего. Рассказ должен быть связным и интересным.""".strip()
