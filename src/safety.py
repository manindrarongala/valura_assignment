import re
from typing import Dict, Any, Optional
from dataclasses import dataclass

@dataclass
class SafetyVerdict:
    blocked: bool
    category: Optional[str]
    message: str

# Topic patterns mapped to category
TOPIC_PATTERNS = {
    "insider_trading": r"(insider trading|insider dealing|unannounced acquisition|material non-public information|front-running|confidential merger|earnings before.*announcement|tip about earnings)",
    "market_manipulation": r"(pump and dump|pump up the price|coordinated buying|spoofing|layering|wash trade|wash trading|market manipulat|telegram legal)",
    "money_laundering": r"(money laundering|reporting threshold|structuring|layer my trades|hide trading profits|bypass.*reporting|layering)",
    "guaranteed_returns": r"(guarantee.*returns|promise me.*double|100% certain|foolproof way|ponzi scheme|guaranteed return|guarantee me)",
    "reckless_advice": r"(all my retirement savings in crypto|margin loan|entire emergency fund into options|mortgage my house)",
    "sanctions_evasion": r"(sanctions|ofac|sanctioned entity|sanctioned russian company|sanctioned)",
    "fraud": r"(fraud|fake)"
}

EDUCATIONAL_SIGNALS = [
    r"\bexplain\b",
    r"\bwhat is\b",
    r"\bwhat's\b",
    r"\bwhat are\b",
    r"\bhow does\b",
    r"\bmeaning of\b",
    r"\bdifference\b",
    r"\brole\b",
    r"\bhistorical average\b",
    r"\bwhy are\b",
    r"\bpenalty\b",
    r"\bpenalties\b",
    r"\bregulations\b",
    r"\breporting requirements\b",
    r"\bcompliance\b",
    r"\billegal\b",
    r"\bdetect\b",
    r"\brules\b",
    r"\bhow should\b",
    r"\bfactors\b"
]

HARMFUL_SIGNALS = [
    r"\bhow to\b",
    r"\bhow do i\b",
    r"\bhow can i\b",
    r"\bhelp me\b",
    r"\bsteps to\b",
    r"\bways? to\b",
    r"\bstrategy to\b",
    r"\bdesign a\b",
    r"\bguarantee me\b",
    r"\bpromise me\b",
    r"\btell me\b",
    r"\bi need to know\b",
    r"\bi want to\b",
    r"\bdo it\b",
    r"\bdraft a\b",
    r"\bshould i\b",
    r"\bwhen should i\b",
    r"\bfoolproof\b"
]

PATTERN_BOOSTS = [
    (r"how to .* (manipulate|hide|avoid|bypass|guarantee)", 3),
    (r"help me .* (manipulate|hide|avoid|bypass|guarantee)", 3),
    (r"can i .* illegally", 3),
    (r"how do i .* without", 2),
    (r"ways? to .* (profit|make)", 2)
]

def check_safety(query: str) -> SafetyVerdict:
    """
    Synchronous safety guard that runs purely locally.
    Evaluates topic, intent, and outputs a block/allow decision.
    """
    q = query.lower()
    
    # Step 1: Detect harmful topic
    detected_topic = None
    for category, pattern in TOPIC_PATTERNS.items():
        if re.search(pattern, q):
            detected_topic = category
            break
            
    # Fallback keyword matching if regex misses
    if not detected_topic:
        if any(word in q for word in ["insider", "confidential", "earnings", "tip"]):
            detected_topic = "insider_trading"
        elif any(word in q for word in ["pump", "dump", "spoofing", "wash"]):
            detected_topic = "market_manipulation"
        elif any(word in q for word in ["laundering", "reporting", "structuring"]):
            detected_topic = "money_laundering"
        elif any(word in q for word in ["guarantee", "certain", "foolproof", "double"]):
            detected_topic = "guaranteed_returns"
        elif any(word in q for word in ["margin", "options", "mortgage", "all my"]):
            detected_topic = "reckless_advice"
        elif any(word in q for word in ["sanction", "ofac", "evasion"]):
            detected_topic = "sanctions_evasion"
        elif any(word in q for word in ["fraud", "fake"]):
             detected_topic = "fraud"

    if not detected_topic:
        return SafetyVerdict(blocked=False, category=None, message="Educational intent detected.")

    # Steps 2 & 3: Detect intent and score
    educational_score = 0
    harmful_score = 0

    for signal in EDUCATIONAL_SIGNALS:
        if re.search(signal, q):
            educational_score += 2
            
    for signal in HARMFUL_SIGNALS:
        if re.search(signal, q):
            harmful_score += 2

    # Step 5: Pattern boost
    for pattern, score in PATTERN_BOOSTS:
        if re.search(pattern, q):
            harmful_score += score

    # Step 4: Decision logic
    if harmful_score > educational_score:
        # Distinct message per category
        messages = {
            "insider_trading": "I cannot help with or discuss insider trading activities.",
            "market_manipulation": "I cannot provide strategies for market manipulation.",
            "money_laundering": "I cannot assist with money laundering or hiding funds.",
            "guaranteed_returns": "I cannot guarantee returns or promise risk-free investments.",
            "reckless_advice": "I cannot provide advice on highly reckless financial moves.",
            "sanctions_evasion": "I cannot assist with sanctions evasion.",
            "fraud": "I cannot help with fraudulent activities."
        }
        msg = messages.get(detected_topic, "I cannot fulfill this request due to safety policies.")
        return SafetyVerdict(blocked=True, category=detected_topic, message=msg)
    else:
        return SafetyVerdict(blocked=False, category=detected_topic, message="Educational intent detected.")
