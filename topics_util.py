"""
Shared topic normalization + duplicate detection.

Both topic_finder.py and upload.py use this, so they agree on what counts
as "the same topic". It catches:
  - exact matches
  - reworded matches ("sleep" vs "fall asleep")
  - singular/plural ("geyser" vs "geysers")
  - topics that share most of their meaningful words
"""

import re

STOPWORDS = {
    "why", "how", "what", "does", "do", "did", "is", "are", "the", "a", "an",
    "we", "you", "your", "our", "it", "its", "to", "of", "in", "on", "at",
    "and", "or", "actually", "really", "so", "can", "cant", "when", "that",
    "this", "with", "for", "from", "by", "as", "be", "i", "my", "us", "they",
    "their", "work", "works", "get", "gets", "cause", "causes", "instead",
    "even", "much", "many", "every", "single", "if", "than", "then", "feel",
    "feels", "feeling", "make", "makes", "made", "thing", "things", "people",
    "person", "human", "humans", "world", "way", "ways", "happen", "happens",
    "explain", "explained", "explains",
}

# Map different words for the same idea onto one word.
# This is what stops "why do we dream when we sleep" and
# "why do we dream when we fall asleep" from both being used.
SYNONYMS = {
    "asleep": "sleep", "sleeping": "sleep", "slept": "sleep", "slumber": "sleep",
    "fall": "", "falling": "", "fell": "",
    "automobile": "car", "cars": "car",
    "kids": "child", "kid": "child", "children": "child",
    "phone": "smartphone", "phones": "smartphone", "mobile": "smartphone",
    "fridge": "refrigerator", "fridges": "refrigerator",
    "plane": "airplane", "planes": "airplane", "aircraft": "airplane",
    "photo": "photograph", "photos": "photograph", "picture": "photograph",
    "bug": "insect", "bugs": "insect",
    "sick": "ill", "illness": "ill", "sickness": "ill",
    "mind": "brain",
    "big": "large", "huge": "large", "giant": "large",
    "tiny": "small", "little": "small", "mini": "small",
    "fast": "quick", "quickly": "quick",
    "freezing": "cold", "frozen": "cold",
    "electricity": "electric", "electrical": "electric",
    "noise": "sound", "audio": "sound",
    "odor": "smell", "scent": "smell",
    "flavor": "taste",
    "sight": "see", "vision": "see",
    "hearing": "hear",
}


def normalize(topic: str) -> str:
    t = str(topic).lower().replace("-", " ").replace("_", " ")
    t = re.sub(r"[^\w\s]", "", t)
    return re.sub(r"\s+", " ", t).strip()


def stem(w: str) -> str:
    """Crude but effective stemmer for topic words."""
    if len(w) > 4 and w.endswith("ies"):
        w = w[:-3] + "y"
    elif len(w) > 3 and w.endswith("es") and not w.endswith("ses"):
        w = w[:-2]
    elif len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        w = w[:-1]
    if len(w) > 5 and w.endswith("ing"):
        w = w[:-3]
    elif len(w) > 4 and w.endswith("ed"):
        w = w[:-2]
    if len(w) > 3 and w.endswith("e"):
        w = w[:-1]
    if len(w) > 3 and w[-1] == w[-2]:
        w = w[:-1]
    return w


def _clean_words(topic: str):
    out = []
    for w in normalize(topic).split():
        if w in STOPWORDS:
            continue
        w = SYNONYMS.get(w, w)
        if w:
            out.append(stem(w))
    return out


def signature(topic: str):
    return frozenset(_clean_words(topic))


def bigrams(topic: str):
    words = _clean_words(topic)
    return frozenset(f"{a} {b}" for a, b in zip(words, words[1:]))


def is_similar(sig_a, sig_b, bg_a=None, bg_b=None) -> bool:
    if not sig_a or not sig_b:
        return False

    shared = len(sig_a & sig_b)
    smaller = min(len(sig_a), len(sig_b))

    # 2+ shared meaningful words that are at least half of the shorter topic
    if shared >= 2 and shared / smaller >= 0.5:
        return True

    # 3+ shared meaningful words is always suspicious
    if shared >= 3:
        return True

    # Same word order in a large part of both topics
    if bg_a and bg_b:
        inter = len(bg_a & bg_b)
        if inter >= 1 and inter / min(len(bg_a), len(bg_b)) >= 0.5:
            return True

    return False


class DuplicateChecker:
    def __init__(self, topics):
        self.norms = set()
        self.sigs = []
        self.bgs = []
        for t in topics:
            self.add(t)

    def is_duplicate(self, topic: str) -> bool:
        n = normalize(topic)
        if not n:
            return True
        if n in self.norms:
            return True

        sig = signature(topic)
        bg = bigrams(topic)
        for used_sig, used_bg in zip(self.sigs, self.bgs):
            if is_similar(sig, used_sig, bg, used_bg):
                return True
        return False

    def add(self, topic: str):
        n = normalize(topic)
        if not n:
            return
        self.norms.add(n)
        self.sigs.append(signature(topic))
        self.bgs.append(bigrams(topic))
