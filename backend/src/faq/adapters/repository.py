import re
import uuid
from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from faq.domain.models import FAQItem
from shared.tenant import TenantContext

_TOKEN_RE = re.compile(r"[a-z0-9]+")

# Common filler words stripped from both inbound text and merchant-supplied
# keywords before scoring -- without this, e.g. "what are your timings" and
# "what is your address" share enough stopwords ("what", "are", "your",
# "is") to score as a false match even with zero real keyword overlap.
_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "is",
        "are",
        "am",
        "was",
        "were",
        "do",
        "does",
        "did",
        "what",
        "when",
        "where",
        "who",
        "why",
        "how",
        "which",
        "you",
        "your",
        "yours",
        "i",
        "we",
        "us",
        "our",
        "to",
        "for",
        "of",
        "in",
        "on",
        "at",
        "by",
        "with",
        "from",
        "my",
        "me",
        "can",
        "could",
        "would",
        "will",
        "shall",
        "should",
        "please",
        "hi",
        "hello",
        "hey",
        "there",
        "it",
        "this",
        "that",
        "and",
        "or",
        "but",
        "have",
        "has",
        "had",
        "be",
        "been",
    }
)


def _tokenize(text: str) -> set[str]:
    return {token for token in _TOKEN_RE.findall(text.lower()) if token not in _STOPWORDS}


def _keyword_tokens(keywords: Iterable[str]) -> set[str]:
    tokens: set[str] = set()
    for keyword in keywords:
        tokens |= _tokenize(keyword)
    return tokens


def _jaccard_score(item_tokens: set[str], input_tokens: set[str]) -> float:
    if not item_tokens or not input_tokens:
        return 0.0
    intersection = item_tokens & input_tokens
    if not intersection:
        return 0.0
    union = item_tokens | input_tokens
    return len(intersection) / len(union)


class FAQItemRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # NOTE: every method whose signature spells out a bare `list[...]`
    # generic has to be defined above `list()` itself, below -- once that
    # method exists, its own name shadows the `list` builtin for every
    # annotation evaluated afterwards, in this class's namespace, for both
    # Python at runtime and mypy statically.
    async def create(
        self,
        tenant: TenantContext,
        question_text: str,
        answer_text: str,
        keywords: list[str],
    ) -> FAQItem:
        faq_item = FAQItem(
            merchant_id=tenant.merchant_id,
            question_text=question_text,
            answer_text=answer_text,
            keywords=keywords,
        )
        self._session.add(faq_item)
        await self._session.flush()
        return faq_item

    async def get(self, tenant: TenantContext, faq_item_id: uuid.UUID) -> FAQItem | None:
        faq_item = await self._session.get(FAQItem, faq_item_id)
        if faq_item is None or faq_item.merchant_id != tenant.merchant_id:
            return None
        return faq_item

    async def update(
        self,
        tenant: TenantContext,
        faq_item_id: uuid.UUID,
        *,
        question_text: str | None = None,
        answer_text: str | None = None,
        keywords: list[str] | None = None,
        is_active: bool | None = None,
    ) -> FAQItem | None:
        faq_item = await self.get(tenant, faq_item_id)
        if faq_item is None:
            return None

        if question_text is not None:
            faq_item.question_text = question_text
        if answer_text is not None:
            faq_item.answer_text = answer_text
        if keywords is not None:
            faq_item.keywords = keywords
        if is_active is not None:
            faq_item.is_active = is_active

        await self._session.flush()
        return faq_item

    async def match(
        self, tenant: TenantContext, text: str, *, threshold: float = 0.15, limit: int = 5
    ) -> list[FAQItem]:
        """Rule-based keyword matching, not free-text AI parsing (explicitly
        out of scope per docs/project-brief.txt) -- lowercases and tokenizes
        `text`, scores each active FAQItem by Jaccard overlap between its
        keyword tokens and the inbound tokens, and returns matches scoring at
        or above `threshold`, sorted best-first (ties broken by creation
        order, oldest first, for deterministic results)."""
        input_tokens = _tokenize(text)
        if not input_tokens:
            return []

        items = await self.list(tenant, include_inactive=False)
        scored = [
            (item, _jaccard_score(_keyword_tokens(item.keywords), input_tokens)) for item in items
        ]
        matches = [(item, score) for item, score in scored if score >= threshold]
        matches.sort(key=lambda pair: (-pair[1], pair[0].created_at))
        return [item for item, _ in matches[:limit]]

    async def list(self, tenant: TenantContext, include_inactive: bool = True) -> list[FAQItem]:
        stmt = select(FAQItem).where(FAQItem.merchant_id == tenant.merchant_id)
        if not include_inactive:
            stmt = stmt.where(FAQItem.is_active.is_(True))
        result = await self._session.execute(stmt.order_by(FAQItem.created_at))
        return list(result.scalars().all())
