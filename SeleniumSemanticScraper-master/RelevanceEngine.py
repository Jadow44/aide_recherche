import math
import re
from dataclasses import dataclass
from typing import Iterable, List, Sequence, Set, Tuple

from rapidfuzz import fuzz


def _normalize(text: str) -> str:
    cleaned = re.sub(r"[^\w\s-]", " ", text.lower())
    cleaned = re.sub(r"[_-]+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _dedupe_tokens(text: str) -> str:
    tokens = [token for token in re.split(r"\s+", text.strip()) if token]
    deduped = []
    for token in tokens:
        if deduped and token.lower() == deduped[-1].lower():
            continue
        deduped.append(token)
    return " ".join(deduped)


def _pluralize(base: str) -> Set[str]:
    results: Set[str] = {base}
    if len(base) <= 3:
        return results

    if base.endswith("y") and base[-2] not in "aeiou":
        results.add(base[:-1] + "ies")
    elif base.endswith("s") or base.endswith("x") or base.endswith("z"):
        results.add(base + "es")
    else:
        results.add(base + "s")

    if base.endswith("e"):
        results.add(base + "d")
    else:
        results.add(base + "ed")

    results.add(base + "ing")
    return results


_SYNONYM_BANK = {
    "dog": {"dog", "dogs", "canine", "canines", "chien", "chiens", "k9", "k-9", "working dog"},
    "canine": {"canine", "canines", "chien", "chiens", "k9", "dog", "dogs"},
    "mine": {
        "mine",
        "mines",
        "landmine",
        "landmines",
        "land mine",
        "land mines",
        "uxo",
        "ordnance",
        "explosive",
        "explosives",
        "ied",
        "ieds",
        "munition",
        "munitions",
    },
    "detection": {
        "detection",
        "detect",
        "detects",
        "detecting",
        "detected",
        "detector",
        "detectors",
        "repérage",
        "détection",
        "détecteur",
        "détecteurs",
        "identification",
    },
    "explosive": {
        "explosive",
        "explosives",
        "explosif",
        "explosifs",
        "bomb",
        "bombs",
        "bomblet",
        "mine",
        "ordnance",
        "ied",
        "ieds",
        "uxo",
    },
    "odor": {
        "odor",
        "odors",
        "odour",
        "odours",
        "scent",
        "scents",
        "olfaction",
        "olfactory",
        "olfactif",
        "odorant",
        "odorants",
        "smell",
        "smells",
        "sniff",
        "sniffing",
    },
    "dog-handler": {"handler", "guide", "team", "binôme", "handler"},
    "robot": {"robot", "robotics", "robotique", "autonomous", "autonome"},
    "review": {"review", "survey", "overview", "state of the art", "revue"},
}

_PHRASE_SYNONYMS = {
    "mine detection": {
        "mine detection",
        "landmine detection",
        "explosive detection",
        "explosives detection",
        "bomb detection",
        "detection de mine",
        "détection de mines",
        "détection des mines",
    },
    "explosive detection": {
        "explosive detection",
        "explosives detection",
        "explosive sniffing",
        "explosive sensing",
        "explosive trace detection",
        "détection d'explosifs",
    },
    "detection dog": {
        "detection dog",
        "detection dogs",
        "explosive detection dog",
        "sniffer dog",
        "chien détecteur",
        "chien de détection",
        "chien démineur",
    },
    "search dog": {
        "search dog",
        "search dogs",
        "working dog",
        "chien de recherche",
        "chien pisteur",
    },
}


def _merge_synonyms(base: str) -> Set[str]:
    words = _SYNONYM_BANK.get(base, set())
    expanded: Set[str] = set()
    for word in {base, *words}:
        expanded |= _pluralize(word)
        expanded.add(word)
    return {w for w in expanded if len(w) > 2}


def _extract_phrases(tokens: Sequence[str]) -> List[str]:
    phrases: List[str] = []
    for size in (3, 2):
        for index in range(len(tokens) - size + 1):
            phrase = " ".join(tokens[index:index + size])
            if phrase in _PHRASE_SYNONYMS:
                phrases.append(phrase)
    return phrases

@dataclass(frozen=True)
class ConceptGroup:
    name: str
    terms: Set[str]
    display_terms: Set[str]
    weight: float


@dataclass
class RelevanceResult:
    score: float
    matched_groups: int
    title_only_groups: int
    matched_terms: Set[str]
    matched_concepts: Set[str]
    core_matches: int
    mandatory_missing: Set[str]
    mandatory_hits: Set[str]
    optional_hits: Set[str]


class QueryRelevanceEngine:
    def __init__(
        self,
        raw_query: str,
        *,
        mandatory_keywords: Iterable[dict] | None = None,
        optional_keywords: Iterable[dict] | None = None,
    ):
        self.raw_query = raw_query or ""
        self.normalized_query = _normalize(self.raw_query)
        tokens = [token for token in self.normalized_query.split(" ") if len(token) > 2]
        self.keyword_groups: List[Set[str]] = []
        self.keyword_terms: Set[str] = set()
        self.concept_groups: List[ConceptGroup] = []
        self.mandatory_keywords: List[Tuple[str, Set[str]]] = []
        self.optional_keywords: List[Tuple[str, Set[str]]] = []

        phrases = _extract_phrases(tokens)
        used_indices: Set[int] = set()
        for phrase in phrases:
            parts = phrase.split()
            start = self.normalized_query.split().index(parts[0]) if parts[0] in tokens else None
            if start is not None:
                for offset in range(len(parts)):
                    try:
                        used_indices.add(tokens.index(parts[offset], start + offset if offset else start))
                    except ValueError:
                        continue
            expanded = set()
            for synonym in _PHRASE_SYNONYMS[phrase]:
                expanded |= _pluralize(synonym)
                expanded.add(synonym)
            normalized = {_normalize(term) for term in expanded}
            normalized = {term for term in normalized if term}
            if normalized:
                self.keyword_groups.append(normalized)
                self.keyword_terms |= normalized
                display_options = {phrase, *_PHRASE_SYNONYMS[phrase]}
                self.concept_groups.append(
                    ConceptGroup(
                        name=phrase,
                        terms=normalized,
                        display_terms={option for option in display_options if option},
                        weight=1.5,
                    )
                )

        for index, token in enumerate(tokens):
            if index in used_indices:
                continue
            expanded = _merge_synonyms(token)
            expanded.add(token)
            normalized = {_normalize(term) for term in expanded}
            normalized = {term for term in normalized if term}
            if normalized:
                self.keyword_groups.append(normalized)
                self.keyword_terms |= normalized
                display_options = {token, *_SYNONYM_BANK.get(token, set())}
                self.concept_groups.append(
                    ConceptGroup(
                        name=token,
                        terms=normalized,
                        display_terms={option for option in display_options if option},
                        weight=1.0,
                    )
                )

        self._integrate_user_keywords(mandatory_keywords, optional_keywords)

        self.keyword_groups = [group for group in self.keyword_groups if group]
        self.keyword_terms = {term for term in self.keyword_terms if term}

        self.total_concept_weight = sum(group.weight for group in self.concept_groups)

        core_groups = [group for group in self.concept_groups if group.weight >= 1.0]
        if len(core_groups) >= 2:
            self.required_core_matches = max(2, math.ceil(len(core_groups) * 0.75))
        else:
            self.required_core_matches = max(1, len(core_groups))

        core_group_count = len(core_groups)
        if core_group_count:
            self.min_groups_required = max(1, math.ceil(core_group_count * 0.5))
        else:
            self.min_groups_required = 0

        self.dynamic_threshold = 42 if len(self.keyword_groups) >= 3 else 35

    @staticmethod
    def normalize_text(text: str) -> str:
        return _normalize(text)

    def _integrate_user_keywords(
        self,
        mandatory_keywords: Iterable[dict] | None,
        optional_keywords: Iterable[dict] | None,
    ) -> None:
        def _process_keywords(
            keywords: Iterable[dict] | None,
            target_list: List[Tuple[str, Set[str]]],
            weight: float,
            add_to_groups: bool,
        ) -> None:
            if not keywords:
                return

            for keyword in keywords:
                if not isinstance(keyword, dict):
                    continue
                forms = keyword.get('forms')
                label = keyword.get('label')
                display_terms = keyword.get('display_terms')

                if not forms:
                    continue

                normalized_forms = {
                    _normalize(str(value))
                    for value in forms
                    if _normalize(str(value))
                }
                if not normalized_forms:
                    continue

                label_text = (label or next(iter(forms))).strip()
                target_list.append((label_text, normalized_forms))

                display = {str(value) for value in (display_terms or forms) if str(value)}

                self.concept_groups.append(
                    ConceptGroup(
                        name=label_text,
                        terms=normalized_forms,
                        display_terms=display or {label_text},
                        weight=weight,
                    )
                )

                if add_to_groups:
                    self.keyword_groups.append(normalized_forms)
                self.keyword_terms |= normalized_forms

        _process_keywords(mandatory_keywords, self.mandatory_keywords, 2.0, True)
        _process_keywords(optional_keywords, self.optional_keywords, 0.8, False)

    def _matched_terms(self, text: str) -> Set[str]:
        hits: Set[str] = set()
        for term in self.keyword_terms:
            if not term:
                continue
            if term in text:
                hits.add(term)
        return hits

    def evaluate(self, title: str, abstract: str) -> RelevanceResult:
        normalized_title = _normalize(title or "")
        normalized_abstract = _normalize(abstract or "")
        combined_text = f"{normalized_title} {normalized_abstract}".strip()
        text_for_keywords = normalized_abstract or combined_text

        matched_groups = 0
        title_only_groups = 0
        matched_concepts: Set[str] = set()
        core_matches = 0
        matched_weight = 0.0
        mandatory_hits: Set[str] = set()
        mandatory_missing: Set[str] = set()
        optional_hits: Set[str] = set()

        for label, terms in self.mandatory_keywords:
            if text_for_keywords and any(term in text_for_keywords for term in terms):
                mandatory_hits.add(label)
            else:
                mandatory_missing.add(label)

        for label, terms in self.optional_keywords:
            if text_for_keywords and any(term in text_for_keywords for term in terms):
                optional_hits.add(label)

        for group in self.concept_groups:
            abstract_hit = normalized_abstract and any(
                term in normalized_abstract for term in group.terms
            )
            title_hit = normalized_title and any(
                term in normalized_title for term in group.terms
            )

            if abstract_hit:
                matched_groups += 1
                matched_concepts.add(group.name)
                matched_weight += group.weight
                if group.weight >= 1.0:
                    core_matches += 1
            elif title_hit:
                title_only_groups += 1
                matched_concepts.add(group.name)
                matched_weight += group.weight * 0.4

        keyword_basis = text_for_keywords or combined_text
        if keyword_basis:
            matched_terms = self._matched_terms(keyword_basis)
            keyword_coverage = (len(matched_terms) / len(self.keyword_terms) * 100) if self.keyword_terms else 0
        else:
            matched_terms = set()
            keyword_coverage = 0

        ratio_title = fuzz.partial_ratio(self.normalized_query, normalized_title) if normalized_title else 0
        ratio_abstract = fuzz.partial_ratio(self.normalized_query, normalized_abstract) if normalized_abstract else 0

        coverage_ratio = 0
        if self.total_concept_weight:
            coverage_ratio = matched_weight / self.total_concept_weight * 100
        elif self.keyword_groups:
            coverage_ratio = (matched_groups / len(self.keyword_groups)) * 100

        score = (
            0.20 * ratio_title
            + 0.40 * ratio_abstract
            + 0.25 * coverage_ratio
            + 0.15 * keyword_coverage
        )
        score += 10 * len(mandatory_hits)
        score += 6 * len(optional_hits)
        score += 2 * title_only_groups

        return RelevanceResult(
            score=round(score, 2),
            matched_groups=matched_groups,
            title_only_groups=title_only_groups,
            matched_terms=matched_terms,
            matched_concepts=matched_concepts,
            core_matches=core_matches,
            mandatory_missing=mandatory_missing,
            mandatory_hits=mandatory_hits,
            optional_hits=optional_hits,
        )

    def should_keep(self, result: RelevanceResult, current_count: int, desired: int) -> bool:
        if result.mandatory_missing:
            return False

        if not self.keyword_groups and not self.mandatory_keywords:
            return result.score >= 30 or current_count < desired

        if result.core_matches >= self.required_core_matches:
            return True

        if result.matched_groups >= self.min_groups_required and result.score >= self.dynamic_threshold:
            return True

        if (
            result.core_matches + 1 >= self.required_core_matches
            and result.score >= self.dynamic_threshold + 5
        ):
            return True

        if current_count < desired and result.core_matches >= 1 and result.score >= max(25, self.dynamic_threshold - 5):
            return True

        return False

    def build_targeted_queries(
        self,
        max_groups: int = 3,
        max_terms_per_group: int = 4,
        max_combinations: int = 6,
    ) -> List[str]:
        if len(self.concept_groups) < 2:
            return []

        def _sort_terms(base: str, options: Set[str]) -> List[str]:
            cleaned_options = {option.strip() for option in options if option.strip()}
            ordered_candidates = sorted(
                cleaned_options,
                key=lambda value: (-value.count(" "), len(value)),
            )
            preferred: List[str] = []
            base_clean = base.strip()
            if base_clean:
                preferred.append(base_clean)
            for candidate in ordered_candidates:
                if len(preferred) >= max_terms_per_group:
                    break
                if base_clean and candidate.lower() == base_clean.lower():
                    continue
                preferred.append(candidate)
            return preferred[:max_terms_per_group]

        core_groups = [group for group in self.concept_groups if group.weight >= 1.0]
        if len(core_groups) < 2:
            core_groups = self.concept_groups[:2]

        selected_groups = core_groups[:max_groups]
        if len(selected_groups) < 2:
            return []

        option_lists: List[List[str]] = []
        for group in selected_groups:
            candidate_terms = set(group.display_terms)
            candidate_terms.add(group.name)
            terms = _sort_terms(group.name, candidate_terms)
            if not terms:
                return []
            option_lists.append(terms)

        combinations: List[str] = []
        seen: Set[str] = set()

        def _build(index: int, current: List[str]):
            if len(combinations) >= max_combinations:
                return
            if index == len(option_lists):
                query = " ".join(current)
                cleaned_query = _dedupe_tokens(query)
                normalized = _normalize(cleaned_query)
                if normalized and normalized not in seen:
                    seen.add(normalized)
                    combinations.append(cleaned_query)
                return

            for option in option_lists[index]:
                current.append(option)
                _build(index + 1, current)
                current.pop()

        _build(0, [])
        return combinations
