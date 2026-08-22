# cfr_dispatch/parser/sanitize.py
# Raw STT transcript normalisation: filler removal, number words, punctuation.
# NOTE: For dispatch template definitions and regex segmentation fields, see docs/call_structure.md

import regex as re

def sanitize_transcript(text: str) -> str:
    """
    Cleans a transcript by converting to lowercase, applying phonetic corrections,
    mapping verbal numbers to digits, removing non-alphanumeric punctuation,
    and normalizing whitespace.
    """
    text = text.lower()

    # Compress commas, hyphens, and spaces between consecutive digits (e.g., 296, 8 -> 2968, 3-1-0-5 -> 3105, 110 0 -> 1100)
    while True:
        new_text = re.sub(r'(\d+)\s*,\s*(\d+)', r'\1\2', text)
        if new_text == text:
            break
        text = new_text

    while True:
        new_text = re.sub(r'(\d+)\s*-\s*(\d+)', r'\1\2', text)
        if new_text == text:
            break
        text = new_text

    while True:
        new_text = re.sub(r'\b(\d+)\s+(\d+)\b', r'\1\2', text)
        if new_text == text:
            break
        text = new_text

    # Apply phonetic corrections for common mishearings in dispatch templates and names
    phonetic_corrections = {
        # Unit number homophones & Engine 1 mishearings
        r'\b(engine|ladder|rescue|car|squad|medic|quint|tender|hazmat)\s+won\b': r'\1 1',
        r'\b(engine|ladder|rescue|car|squad|medic|quint|tender|hazmat)\s+juan\b': r'\1 1',
        r'\b(engine|ladder|rescue|car|squad|medic|quint|tender|hazmat)\s+run\b': r'\1 1',
        r'\b(engine|ladder|rescue|car|squad|medic|quint|tender|hazmat)\s+on\b': r'\1 1',
        r'\b(engine|ladder|rescue|car|squad|medic|quint|tender|hazmat)\s+when\b': r'\1 1',
        r'\b(engine|ladder|rescue|car|squad|medic|quint|tender|hazmat)\s+to\b': r'\1 2',
        r'\b(engine|ladder|rescue|car|squad|medic|quint|tender|hazmat)\s+too\b': r'\1 2',
        r'\b(engine|ladder|rescue|car|squad|medic|quint|tender|hazmat)\s+two\b': r'\1 2',
        r'\b(engine|ladder|rescue|car|squad|medic|quint|tender|hazmat)\s+free\b': r'\1 3',
        r'\b(engine|ladder|rescue|car|squad|medic|quint|tender|hazmat)\s+three\b': r'\1 3',
        r'\b(engine|ladder|rescue|car|squad|medic|quint|tender|hazmat)\s+for\b': r'\1 4',
        r'\b(engine|ladder|rescue|car|squad|medic|quint|tender|hazmat)\s+four\b': r'\1 4',

        # Unit type STT mishearings
        r'\b(agent|ancient|angel|asian)\s+(\d+|1|2|3|4|5|one|two|three|four|five)\b': r'engine \2',

        # Responding units & Coquitlam mishearings
        r'\bcolquitt\s+loom\b': 'coquitlam',
        r'\bcorporate\s+loan\b': 'coquitlam',
        r'\bcocoa\b': 'coquitlam',
        r'\bcocoon\b': 'coquitlam',
        r'\bkirk\s+whitman\b': 'coquitlam',
        r'\bquickly\b': 'coquitlam',
        r'\bcopeland\b': 'coquitlam',
        r'\bpoit\s*loma\b': 'coquitlam',
        r'\bpoint\s+loma\b': 'coquitlam',
        r'\bhope\s+that\s+1\b': 'coquitlam',
        r'\bhope\s+that\s+one\b': 'coquitlam',
        r'\bpopoetal\b': 'coquitlam',
        r'\bhoquiam\b': 'coquitlam',
        r'\bcrazy\s+an\b': 'coquitlam',
        r'\bcoquit\s*loom\b': 'coquitlam',
        r'\bcoquina\b': 'coquitlam',
        r'\bpoke\s+with\s+them\b': 'coquitlam',
        r'\bhope\s+with\s+them\b': 'coquitlam',
        r'\bpoke\s+with\s+him\b': 'coquitlam',
        r'\bhope\s+with\s+him\b': 'coquitlam',
        
        # Unit corrections
        r'\bengines\b': 'engine',
        r'\bladders\b': 'ladder',
        r'\bmedics\b': 'medic',
        r'\bquints\b': 'quint',
        r'\brescues\b': 'rescue',
        r'\bsquads\b': 'squad',
        r'\bcars\b': 'car',
        r'\btenders\b': 'tender',
        r'\bqueens\s+(\d+)\b': r'quint \1',
        
        # Respond & Priority
        r'\brespawn(ed)?s?\b': 'respond',
        r'\bresponses?\s+(emergency|routine)\b': r'respond \1',
        r'\bresponse\s+(emergency|routine)\b': r'respond \1',
        r'\bresign\b': 'respond',
        r'\breson\b': 'respond',
        r'\bwe\s+found\b': 'respond',
        r'\brespondents\b': 'respond',
        r'\bresponder\b': 'respond',
        r'\bregency\b': 'emergency',
        r'\bmedley\b': 'medical aid',
        r'\bvan\s+ruitens?\b': 'routine',
        r'\bportman(n)?\b': 'port mann',
        r'\benramp\b': 'on-ramp',
        r'\bonramp\b': 'on-ramp',
        
        # Cross streets and roads
        r'\bcross\s+roads?\b': 'cross roads',
        r'\bcross\s+streets?\b': 'cross roads',
        r'\b(?:cross|across)\s+up\b': 'cross of',
        r'\b(?:cross|across)\s+ark\b': 'cross of',
        r'\b(?:cross|across)\s+of\b': 'cross of',
        
        # Talk Group (channel)
        r'\buse\s+tax\b': 'use talk group',
        r'\buse\s+tack\b': 'use talk group',
        r'\buse\s+tag\b': 'use talk group',
        r'\bnews\s+tack\b': 'use talk group',
        r'\bmens\s+table\b': 'use talk group',
        r'\btalk\s*groups?\b': 'talk group',
        r'\btorque\s+groups?\b': 'talk group',
        
        # Map Grid
        r'\bmath\s+grids?\b': 'map grid',
        r'\bmath\s+grades?\b': 'map grid',
        r'\bmap\s+grades?\b': 'map grid',
        r'\bmath\s+griff\b': 'map grid',
        
        # Street suffixes
        r'\bpresidents?\b': 'crescent',
        r'\bpresents?\b': 'crescent',
        r'\bpresence?\b': 'crescent',
        r'\btreat\b': 'street',
        
        # Specific major streets / locations
        r'\bgrovener\b': 'grosvenor',
        r'\bgaiden\'s\s+burry\b': 'gatensbury',
        r'\bgaidens\s+burry\b': 'gatensbury',
        r'\bgateonsbury\b': 'gatensbury',
        r'\bgaitensbury\b': 'gatensbury',
        r'\bgatiensbury\b': 'gatensbury',
        r'\bleamax\b': 'lemax',
        r'\bdancing\s+(ave|avenue)\b': r'dancy \1',
        r'\bdayani\s+springs\b': 'dayanee springs',
        r'\bdeyani\s+springs\b': 'dayanee springs',
        r'\bdeyani\b': 'dayanee',
        r'\bdayani\b': 'dayanee',
        r'\bpintree\b': 'pinetree',
        r'\bpine\s+tree\s+whey\b': 'pinetree way',
        r'\bpinetree\s+whey\b': 'pinetree way',
        r'\bpine\s+tree\s+whay\b': 'pinetree way',
        r'\bpinetree\s+whay\b': 'pinetree way',
        r'\bpine\s+tree\s+weigh\b': 'pinetree way',
        r'\bpinetree\s+weigh\b': 'pinetree way',
        r'\bpintree\s+whay\b': 'pinetree way',
        r'\bheavily\s+(cres|crescent)\b': r'heffley \1',
        r'\blow\s+heat\s+high\s*ways?\b': 'lougheed highway',
        r'\blow\s+heed\s+high\s*ways?\b': 'lougheed highway',
        r'\blove\s+heat\s+high\s*ways?\b': 'lougheed highway',
        r'\blowheat\s+high\s*ways?\b': 'lougheed highway',
        r'\blowheat\s+hwy\b': 'lougheed highway',
        r'\blough\s+head\s+high\s*ways?\b': 'lougheed highway',
        r'\bsharp\s+treat\b': 'sharpe street',
        r'\bwig\s+on\s+throught\b': 'wigham drive',
        r'\bburden\s+cart\b': 'burton court',
        r'\bbroke\s+mirror\b': 'brookmere',
        r'\bdo\s+we\s+need\s+from\s+growing\b': 'dewdney trunk road',
        r'\bdo\s+we\s+need\s+from\s+bro\b': 'dewdney trunk road',
        r'\bdo\s+we\s+need\s+from\b': 'dewdney trunk road',
        
        # Phonetic street & school access fixes
        r'\ble\s+bleu\b': 'lebleu',
        r'\btime\b': 'thyme',
        r'\balvis\b': 'alvis',
        r'\bscott\s+creek\b': 'scott creek',
        r'\bglen\s+eagle\b': 'gleneagle',
        
        # Coquitlam / Quitlam mishearings and collapses
        r'\bquitlam\b': 'coquitlam',
        r'\bego\s+mountain\b': 'eagle mountain',
        r'\bcoquitlam\s+coquitlam\b': 'coquitlam',
        
        # Unit mishearings (e.g. water 1 -> ladder 1)
        r'\bwater\s+(\d+)\b': r'ladder \1',
    }
    for pattern, replacement in phonetic_corrections.items():
        text = re.sub(pattern, replacement, text)

    # Secondary sweep to collapse any remaining double occurrences of coquitlam
    text = re.sub(r'\b(coquitlam)\s+\1\b', r'\1', text, flags=re.IGNORECASE)

    number_words = {
        'zero': '0', 'one': '1', 'two': '2', 'three': '3', 'four': '4',
        'five': '5', 'six': '6', 'seven': '7', 'eight': '8', 'nine': '9',
        'ten': '10', 'eleven': '11', 'twelve': '12', 'thirteen': '13',
        'fourteen': '14', 'fifteen': '15', 'sixteen': '16', 'seventeen': '17',
        'eighteen': '18', 'nineteen': '19', 'twenty': '20'
    }

    # Replace whole word numbers with digits
    pattern = r'\b(' + '|'.join(number_words.keys()) + r')\b'
    text = re.sub(pattern, lambda m: number_words[m.group(0)], text)

    # Strip punctuation except alphanumeric characters and spaces
    text = re.sub(r'[^a-z0-9\s]', '', text)
    
    # Join consecutive single digits separated by spaces (e.g. "4 2 8" -> "428")
    text = re.sub(r'\b(\d)\s+(?=\d\b)', r'\1', text)
    
    # Trim and normalize spaces
    return ' '.join(text.split())
