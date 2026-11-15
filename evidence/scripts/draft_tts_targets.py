"""Draft TTS settings and pronunciation targets for data/tts_cases.csv (no API calls).

Written BEFORE any Timbre audio exists for these prompts, so accepted readings cannot be
chosen to fit a convenient output. Status becomes `targets_drafted`; a reviewer changes it to
`ready` (via the review page export + apply step) before generation.

Target format (expected_targets_json): list of
  {"id", "written": text as typed, "must_hear": what a listener must hear, "critical": bool}
Variant format (accepted_variants_json): {target_id: {"accept": [...], "reject": [...]}}
Scoring: a target is correct only if what the listener heard matches an `accept` form or is
unambiguously equivalent; anything in `reject`, ambiguous or unintelligible is not correct.
Every prompt is additionally rated for completeness, naturalness, prosody and artifacts.
"""
import csv
import json
import re
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
CASES = PROJECT / "data" / "tts_cases.csv"

SETTINGS = {"model": "timbre-v3.0", "voice": "Tarika", "speed": "1.0", "audio_format": "wav",
            "sample_rate_hz": "24000"}

T = {}  # case_id -> (targets, variants)


def tgt(case, *items):
    targets, variants = [], {}
    for item in items:
        tid, written, must, critical, accept, reject = item
        targets.append({"id": tid, "written": written, "must_hear": must, "critical": critical})
        variants[tid] = {"accept": accept, "reject": reject}
    T[case] = (targets, variants)


def t(tid, written, must, accept, reject=(), critical=True):
    return (tid, written, must, critical, list(accept), list(reject))


COMPLETE = "every word spoken once, in order; no omission, repetition or truncation"


def completeness(first, last, *extra):
    return (t("start", first, f"opening words '{first}' intact", [first], ["clipped first word"]),
            t("end", last, f"final words '{last}' intact, no cut-off", [last], ["truncated ending"]),
            *extra)


# ---------------------------------------------------------------- numeric (T01-T05, T39-T48)
tgt("T01", t("amount", "₹1,25,450", "one lakh twenty-five thousand four hundred fifty rupees",
             ["one lakh twenty-five thousand four hundred fifty rupees", "one lakh twenty-five thousand four hundred and fifty rupees",
              "rupees one lakh twenty-five thousand four hundred fifty", "one hundred twenty-five thousand four hundred fifty rupees"],
             ["digit-by-digit reading", "twelve thousand ...", "any other value", "amount without a currency word"]))
tgt("T02", t("amount", "₹1,57,890.50", "one lakh fifty-seven thousand eight hundred ninety rupees and fifty paise",
             ["one lakh fifty-seven thousand eight hundred ninety rupees and fifty paise",
              "one lakh fifty-seven thousand eight hundred ninety point five zero rupees",
              "one lakh fifty-seven thousand eight hundred ninety point fifty rupees",
              "one hundred fifty-seven thousand eight hundred ninety rupees fifty paise"],
             ["decimal dropped", "fifty rupees for the fractional part", "any other value"]))
tgt("T03", t("sip", "SIP", "S-I-P as letters, or 'sip'", ["S I P", "sip"], ["invented expansion"], critical=False),
    t("date", "23 November", "twenty-third November", ["twenty-third November", "November twenty-third", "the twenty-third of November",
                                                        "twenty-three November"], ["thirty-two", "twenty November", "any other day/month"]),
    t("year", "2026", "twenty twenty-six", ["twenty twenty-six", "two thousand twenty-six", "two thousand and twenty-six", "two zero two six"],
      ["twenty twenty", "two thousand two hundred six", "year omitted"]))
tgt("T04", t("percent", "12.75%", "twelve point seven five percent",
             ["twelve point seven five percent", "twelve point seventy-five percent"],
             ["twelve seventy-five percent", "minus/negative", "percent omitted", "twelve point five"]))
tgt("T05", t("from", "₹850", "eight hundred fifty rupees", ["eight hundred fifty rupees", "eight hundred and fifty rupees",
                                                            "rupees eight hundred fifty"], ["eighty-five", "eight five zero"]),
    t("to", "₹1,050", "one thousand fifty rupees", ["one thousand fifty rupees", "one thousand and fifty rupees", "rupees one thousand fifty"],
      ["ten fifty (ambiguous)", "one thousand five hundred", "one zero five zero"]),
    t("order", "from ₹850 to ₹1,050", "850 said before 1,050", ["from 850 to 1,050"], ["order swapped"]))
tgt("T39", t("amount", "₹0.05", "five paise", ["five paise", "zero point zero five rupees", "rupees zero point zero five",
                                               "point zero five rupees"],
             ["five rupees", "zero point five", "fifty paise", "zero rupees"]))
tgt("T40", t("neg_amount", "−₹250.50", "minus two hundred fifty rupees fifty paise",
             ["minus two hundred fifty rupees and fifty paise", "negative two hundred fifty point five zero rupees",
              "minus rupees two hundred fifty point fifty", "minus two hundred fifty point five rupees"],
             ["sign dropped", "dash read as a pause only", "any other value"]),
    t("pos_amount", "₹250.50", "two hundred fifty rupees fifty paise (positive)",
      ["two hundred fifty rupees and fifty paise", "two hundred fifty point five zero rupees", "rupees two hundred fifty point fifty"],
      ["minus/negative", "any other value"]),
    t("not", "not", "'not' clearly audible", ["not"], ["omitted", "blurred into 'now'"]))
tgt("T41", t("qty", "15", "fifteen", ["fifteen"], ["fifty", "one five", "unclear fifteen/fifty"]),
    t("rejected", "50", "fifty", ["fifty"], ["fifteen", "five zero", "unclear fifteen/fifty"]),
    t("not", "not", "'not' audible", ["not"], ["omitted"]))
tgt("T42", t("old", "7.05%", "seven point zero five percent", ["seven point zero five percent", "seven point oh five percent"],
             ["seven point five", "seven point fifty", "seven point five zero"]),
    t("new", "7.50%", "seven point five zero percent", ["seven point five zero percent", "seven point five percent",
                                                        "seven point fifty percent"], ["seven point zero five", "seven fifty percent"]))
tgt("T43", t("amount", "₹10,00,000", "ten lakh rupees", ["ten lakh rupees", "one million rupees", "rupees ten lakh"],
             ["one lakh", "ten thousand", "one crore", "digit-by-digit"]))
tgt("T44", t("start", "9:05 AM", "nine oh five A M", ["nine oh five A M", "nine zero five A M", "five past nine in the morning"], ["nine fifty", "nine o'clock", "PM"]),
    t("end", "12:30 PM", "twelve thirty P M", ["twelve thirty P M", "half past twelve in the afternoon", "twelve thirty in the afternoon"],
      ["twelve three zero as a number", "AM", "twelve thirteen"]))
tgt("T45", t("date1", "03 November 2026", "third November twenty twenty-six",
             ["third November twenty twenty-six", "November third twenty twenty-six", "the third of November two thousand twenty-six",
              "zero three November twenty twenty-six"], ["thirtieth", "thirty", "third/thirtieth unclear"]),
    t("date2", "30 November 2026", "thirtieth November twenty twenty-six",
      ["thirtieth November twenty twenty-six", "November thirtieth", "thirty November twenty twenty-six"], ["third", "thirteenth"]),
    t("not", "not", "'not' audible", ["not"], ["omitted"]))
tgt("T46", t("range", "3–5", "three to five", ["three to five"], ["three minus five", "three five", "three dash five", "thirty-five"]))
tgt("T47", t("decimal", "0.125", "zero point one two five", ["zero point one two five", "point one two five", "zero point one twenty-five"],
             ["one hundred twenty-five", "zero point one five", "point twelve five (ambiguous)"]))
tgt("T48", t("held", "101", "one hundred one", ["one hundred one", "one hundred and one", "one zero one"], ["eleven", "one hundred ten"]),
    t("pending", "11", "eleven", ["eleven"], ["one one", "one hundred one", "seven"]))

# ---------------------------------------------------------------- identifiers (T35, T49-T58)
DIGITWISE = "digit by digit; 'oh' accepted for 0; 'double'/'triple' grouping accepted"
tgt("T35", t("id", "004291", "zero zero four two nine one",
             ["zero zero four two nine one", "double zero four two nine one", "oh oh four two nine one"],
             ["four thousand two hundred ninety-one", "four two nine one (leading zeros lost)", "any digit changed"]))
tgt("T49", t("id", "000042", "zero zero zero zero four two",
             ["zero zero zero zero four two", "double zero double zero four two", "oh oh oh oh four two"],
             ["forty-two", "zero zero zero four two (one zero lost)", "triple zero four two"]))
tgt("T50", t("code", "448822", "four four eight eight two two", ["four four eight eight two two", "double four double eight double two", "forty-four eighty-eight twenty-two"],
             ["four lakh forty-eight thousand ...", "any digit lost or changed"]))
tgt("T51", t("id", "AB10O0", "A B one zero O zero (letter O distinct from both zeros)",
             ["A B one zero O zero", "A B one zero letter O zero"],
             ["A B one zero zero zero (letter O read as zero)", "A B one oh oh oh (letter/digit not distinguishable)", "A B ten O zero"]))
tgt("T52", t("digits", "0070", "zero zero seven zero", ["zero zero seven zero", "double zero seven zero", "oh oh seven oh"],
             ["seventy", "zero seventy", "seven zero (leading zeros lost)"]))
tgt("T53", t("ref", "ZX-204-009", "Z X two zero four zero zero nine",
             ["Z X two zero four zero zero nine", "zed X two oh four double zero nine", "zee X two zero four zero zero nine"],
             ["two hundred four", "nine (leading zeros lost)", "letters misread"]))
tgt("T54", t("ticket", "100100", "one zero zero one zero zero",
             ["one zero zero one zero zero", "one double zero one double zero", "one oh oh one oh oh"],
             ["one lakh one hundred (value reading; record separately as not digit-wise)", "one hundred thousand one hundred"]))
tgt("T55", t("code", "A1B2C3", "A one B two C three", ["A one B two C three"], ["A B C one two three (order changed)", "letters merged"]))
tgt("T56", t("digits", "0 0 4 2 9 1", "zero zero four two nine one", ["zero zero four two nine one", "oh oh four two nine one"],
             ["four thousand two hundred ninety-one", "any digit lost or changed"]))
tgt("T57", t("ref", "1234567890123456", "one two three four five six seven eight nine zero one two three four five six",
             ["all sixteen digits in order, any grouping"], ["number-word reading (trillions etc.)", "any digit lost, added or swapped"]))
tgt("T58", t("selected", "4821", "four eight two one", ["four eight two one", "forty-eight twenty-one"], ["four eight one two", "forty-eight twelve"]),
    t("not_selected", "4812", "four eight one two", ["four eight one two", "forty-eight twelve"], ["four eight two one", "forty-eight twenty-one"]),
    t("not", "is not", "'not' audible", ["not"], ["omitted"]))

# ---------------------------------------------------------------- abbreviations / names
LET = lambda s: " ".join(s)
tgt("T06", t("kyc", "KYC", "K-Y-C as letters", ["K Y C"], ["kick", "kayk", "know your customer (expansion: note, not counted correct)"]))
tgt("T07", t("ucc", "UCC", "U-C-C as letters", ["U C C"], ["U C", "you see see merged into one syllable", "U C G"]))
tgt("T08", t("ifsc", "IFSC", "I-F-S-C as letters", ["I F S C"], ["if-sick", "I S F C", "letters dropped"]))
tgt("T09", t("nav", "NAV", "N-A-V letters or 'nav'", ["N A V", "nav"], ["navy", "nave"]),
    t("amount", "₹112.50", "one hundred twelve rupees fifty paise",
      ["one hundred twelve rupees and fifty paise", "one hundred twelve point five zero rupees", "one hundred twelve point fifty rupees"],
      ["eleven", "one hundred twenty", "decimal dropped"]))
tgt("T10", t("sip", "SIP", "S-I-P letters or 'sip'", ["S I P", "sip"], ["ship", "zip"]),
    t("amount", "₹500", "five hundred rupees", ["five hundred rupees", "rupees five hundred"], ["fifty", "five thousand"]))
tgt("T16", t("hdfc", "HDFC Bank", "H-D-F-C Bank", ["H D F C Bank"], ["H D C F", "extra syllables", "Bank omitted"]))
tgt("T17", t("name", "Motilal Oswal", "MO-tee-laal OS-waal (Indian pronunciation)", ["Motilal Oswal"],
             ["Moti-lal read as English 'mottle'", "Os-wall with wrong stress making it unrecognisable", "syllable dropped"], critical=False))
tgt("T69", t("dr", "Dr.", "Doctor", ["Doctor"], ["D R", "Drive", "dropped"]),
    t("name", "Meera Rao", "MEE-raa RAA-o", ["Meera Rao"], ["Mira Ray", "unrecognisable"], critical=False))
tgt("T70", t("neft", "NEFT", "N-E-F-T letters or 'neft'", ["N E F T", "neft"], ["nest", "N F T"]),
    t("upi", "UPI", "U-P-I letters", ["U P I"], ["oopy", "U P"]),
    t("contrast", "pending ... complete", "NEFT pending, UPI complete (not swapped)", ["pending then complete"], ["swapped", "either word lost"]))
tgt("T71", t("rtgs", "RTGS", "R-T-G-S letters", ["R T G S"], ["R G T S", "letters dropped"]),
    t("imps", "IMPS", "I-M-P-S letters or 'imps'", ["I M P S", "imps"], ["imp", "I P M S"]))
tgt("T72", t("pan", "PAN", "'pan' as a word or P-A-N", ["pan", "P A N"], ["pain", "pawn"]),
    t("gst", "GST", "G-S-T letters", ["G S T"], ["gist", "G T"]))
tgt("T73", t("emi", "EMI", "E-M-I letters", ["E M I"], ["emmy", "E M"]),
    t("sip", "SIP", "S-I-P letters or 'sip'", ["S I P", "sip"], ["ship"]))
tgt("T74", t("name1", "Shanmugapriya", "shun-MU-ga-PRI-ya, all five syllables", ["Shanmugapriya"], ["syllable dropped", "Shanmu Priya"], critical=False),
    t("name2", "Srinivasan", "SREE-ni-VAA-san", ["Srinivasan"], ["Srinivas (truncated)", "syllable dropped"], critical=False))
tgt("T75", t("name", "Satinder Kaur", "sa-TIN-der KOWR", ["Satinder Kaur", "Satinder Kor"], ["syllable dropped", "unrecognisable"], critical=False),
    t("city", "Bengaluru", "BAYN-ga-loo-roo", ["Bengaluru"], ["Bangalore (substitution, not a faithful reading)", "syllable dropped", "unrecognisable"], critical=False))
tgt("T76", t("st", "St. Johns Road", "Saint Johns Road", ["Saint Johns Road", "Saint John's Road"], ["Street Johns Road", "S T Johns Road"]))
tgt("T77", t("pdf", "PDF", "P-D-F letters", ["P D F"], ["P F", "pudf"]), t("qr", "QR", "Q-R letters", ["Q R"], ["queer", "Q"]))
tgt("T78", t("nav", "NAV", "N-A-V letters or 'nav'", ["N A V", "nav"], ["navy"]),
    t("isin", "ISIN", "I-S-I-N letters or 'eye-sin'", ["I S I N", "eye-sin"], ["is in", "I S N"]),
    t("kyc", "KYC", "K-Y-C letters", ["K Y C"], ["kick"]))
tgt("T38", t("kyc", "K Y C", "K-Y-C as letters", ["K Y C"], ["kick", "letters run together unintelligibly"]))

# ---------------------------------------------------------------- code-switching / scripts
tgt("T11", t("sip", "SIP", "S-I-P letters or 'sip'", ["S I P", "sip"], ["skipped"]),
    t("english", "successfully process", "English words pronounced as English", ["successfully process"], ["skipped", "garbled"]),
    t("hindi", "हो गया है", "Hindi ending complete", ["ho gaya hai"], ["skipped", "read letter by letter"]))
for case in ("T12", "T36"):
    tgt(case, t("hindi", "aapka ... abhi ... hua hai", "Hindi words with Hindi pronunciation (aap-ka, a-bhi, hu-aa hai)",
                ["aapka", "abhi", "hua hai"], ["Aapka read as English letters/syllables (ap-ka with English vowels)", "abhi as 'a-bee'"]),
        t("english", "portfolio balance update", "English loanwords clear", ["portfolio balance update"], ["skipped"]))
tgt("T14", t("hindi", "कल सुबह", "kal su-bah inside English sentence", ["kal subah"], ["skipped", "silence"]),
    t("english", "execute", "execute pronounced clearly", ["execute"], ["skipped"]))
tgt("T32", t("content", "आपका अनुरोध मिल गया है। हम कल आपसे संपर्क करेंगे।", "complete Hindi, natural pronunciation",
             ["anurodh", "sampark karenge"], ["word omitted", "anglicised vowels making words unclear"]))
tgt("T59", t("content", "भुगतान ... रसीद", "complete Hindi incl. bhug-taan, ra-seed", ["bhugtaan", "raseed"], ["word omitted"]))
tgt("T60", t("amount", "₹1,250", "one thousand two hundred fifty rupees (Hindi or English words)",
             ["ek hazaar do sau pachaas rupaye", "baarah sau pachaas rupaye", "one thousand two hundred fifty rupees"],
             ["ek sau pachchees", "twelve fifty (ambiguous)", "digit-by-digit"]),
    t("english", "balance ... payment", "English loanwords clear", ["balance", "payment"], ["skipped"], critical=False),
    t("time", "कल", "kal (tomorrow)", ["kal"], ["omitted"]))
tgt("T61", t("cancel", "order cancel करें", "cancel requested", ["order cancel karein"], ["cancel omitted"]),
    t("negation", "confirm नहीं", "nahin clearly after confirm", ["confirm nahin"], ["nahin omitted", "nahin attached to cancel"]))
tgt("T62", t("hindi", "Aapka payment mil gaya hai. Kripya receipt sambhal kar rakhen.", "romanised Hindi read as Hindi",
             ["mil gaya hai", "kripya", "sambhal kar rakhen"], ["read as English letters/syllables", "words skipped"]))
tgt("T63", t("english", "refund ... pending ... check", "English words clear", ["refund", "pending", "check"], ["skipped"]),
    t("hindi", "अभी ... कल फिर", "abhi, kal phir", ["abhi", "kal phir"], ["skipped"]))
tgt("T64", t("kyc", "KYC", "K-Y-C letters inside Hindi", ["K Y C"], ["kick"]),
    t("english", "account activate", "English words clear", ["account activate"], ["skipped"]))
tgt("T65", t("content", "దయచేసి మీ ఖాతా వివరాలను మరోసారి తనిఖీ చేయండి.", "complete Telugu, natural pronunciation",
             ["dayachesi", "khata vivaralanu", "marosari tanikhi cheyandi"], ["word omitted", "read in Hindi phonology"]))
tgt("T66", t("english", "payment complete ... Receipt save", "English words clear inside Telugu", ["payment complete", "receipt save"], ["skipped"]),
    t("telugu", "అయింది ... చేసుకోండి", "Telugu verbs complete", ["ayindi", "chesukondi"], ["skipped"]))
tgt("T67", t("cancel", "order cancel చేయండి", "cancel requested", ["order cancel cheyandi"], ["cancel omitted"]),
    t("negation", "confirm చేయవద్దు", "do NOT confirm (cheyavaddu)", ["confirm cheyavaddu"], ["cheyandi (positive)", "omitted"]))
tgt("T68", t("time", "कल सुबह नौ बजे", "kal subah nau baje (9 tomorrow morning)", ["kal subah nau baje", "kal subah nine baje"],
             ["nau omitted", "any other hour"]),
    t("english", "support team ... call", "English words clear", ["support team", "call"], ["skipped"], critical=False))

# ---------------------------------------------------------------- prosody / meaning
tgt("T26", t("question", "?", "question intonation at the end", ["audibly a question"], ["flat statement ending", "cut-off ending"], critical=False))
tgt("T27", t("not", "Do not", "'not' clearly audible", ["do not", "don't"], ["not omitted (reverses meaning)"]),
    t("otp", "OTP", "O-T-P letters", ["O T P"], ["opt", "O P"]))
tgt("T28", t("list", "First, ... Next, ... Finally,", "pauses after each list word; three sentences", ["three separated steps"],
             ["run-together with no pauses", "a step omitted"], critical=False))
tgt("T29", t("read_present", "will read", "'read' as REED", ["reed"], ["red"], critical=False),
    t("read_past", "I read it yesterday", "'read' as RED", ["red"], ["reed"], critical=False))
tgt("T79", t("question", "?", "question intonation", ["audibly a question"], ["flat statement"], critical=False),
    t("fifteen", "fifteen", "fifteen", ["fifteen"], ["fifty"]), t("fifty", "fifty", "fifty", ["fifty"], ["fifteen"]))
tgt("T80", t("not", "Do not cancel", "'not' clearly audible", ["do not cancel", "don't cancel"], ["not omitted"]),
    t("only", "Cancel only the duplicate", "'only' present", ["cancel only the duplicate request"], ["only omitted"]))
tgt("T81", t("verb", "record the message", "re-CORD (verb)", ["ri-KORD"], ["REK-erd"], critical=False),
    t("noun", "The record", "REK-erd (noun)", ["REK-erd"], ["ri-KORD"], critical=False))
tgt("T82", t("contrast", "approved; however, ... pending", "pause at the semicolon; approved vs pending both clear",
             ["approved", "however", "still pending"], ["however omitted", "approved/pending swapped"], critical=False))
tgt("T83", t("condition", "confirm only if both are correct", "'only if' clearly present", ["only if both are correct"],
             ["only omitted", "if omitted"]),
    t("list", "First, ... second, ... finally,", "three steps separated", ["three separated steps"], ["step omitted"], critical=False))

# ---------------------------------------------------------------- baselines / length
tgt("T31", t("content", "Your request has been received. We will contact you tomorrow.", COMPLETE, ["complete sentence pair"], ["word omitted"]))
tgt("T33", t("yes", "Yes.", "audible 'yes' with intact start and end", ["yes"], ["silent", "clipped 'es'", "extra words"]))
tgt("T34", t("value", "−2.5%", "minus two point five percent",
             ["minus two point five percent", "negative two point five percent"],
             ["two point five percent (sign lost)", "dash read as pause only", "twenty-five percent"]))
tgt("T37", t("amount", "one lakh twenty-five thousand four hundred fifty rupees", "same amount as T01",
             ["one lakh twenty-five thousand four hundred fifty rupees"], ["any word omitted or changed"]))
tgt("T21", *completeness("Your payment has been received", "if further information is required"))
tgt("T23", *completeness("Your request has been received", "when you ask us for an update",
                         t("negation", "You do not need to submit the same request again", "'do not' audible", ["do not", "don't"], ["not omitted"])))
LONG_NEG = t("negation", "Do not share your password or verification code", "'not' audible", ["do not share", "don't share"], ["not omitted"])
tgt("T25", *completeness("Your request has been received", "save the receipt for your records", LONG_NEG))
tgt("T84", *completeness("Your request is saved", "go back and edit the details"))
tgt("T85", *completeness("We have received your application", "while this review is in progress",
                         t("negation", "You do not need to create another application", "'do not' audible", ["do not", "don't"], ["not omitted"])))
tgt("T86", *completeness("Your statement shows the opening balance", "Do not share passwords or verification codes",
                         t("negation", "Do not share passwords", "'not' audible", ["do not", "don't"], ["not omitted"])))
tgt("T87", *completeness("Your payment has been received", "when you ask us for an update",
                         t("negation", "You do not need to submit the same request again", "'do not' audible", ["do not", "don't"], ["not omitted"])))
tgt("T88", *completeness("Your request has been received", "Contact support if the status remains unclear", LONG_NEG,
                         t("negation2", "it does not guarantee that a pending request will succeed", "'not' audible", ["does not", "doesn't"],
                           ["not omitted (reverses meaning)"])))


def language_for(text: str, current: str) -> str:
    deva = bool(re.search(r"[ऀ-ॿ]", text))
    telugu = bool(re.search(r"[ఀ-౿]", text))
    latin_words = re.findall(r"[A-Za-z]{2,}", text)
    native = deva or telugu
    if native and latin_words:
        return "auto"                       # mixed script: let Timbre route by script
    if deva:
        return "hi-IN"
    if telugu:
        return "te-IN"
    roman_hindi = {"aapka", "abhi", "hua", "hai", "kripya", "mil", "gaya", "sambhal", "rakhen"}
    if roman_hindi & {w.lower() for w in latin_words}:
        return "auto"                       # romanised Hindi: routing behaviour is part of the test
    return "en-IN"


def main() -> None:
    with CASES.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        fields, rows = reader.fieldnames, list(reader)
    missing = [r["case_id"] for r in rows if r["case_id"] not in T]
    extra = sorted(set(T) - {r["case_id"] for r in rows})
    if missing or extra:
        raise SystemExit(f"target coverage mismatch: missing={missing} extra={extra}")
    for r in rows:
        targets, variants = T[r["case_id"]]
        r.update(SETTINGS)
        r["language"] = language_for(r["input_text"], r["language"])
        r["expected_targets_json"] = json.dumps(targets, ensure_ascii=False)
        r["accepted_variants_json"] = json.dumps(variants, ensure_ascii=False)
        r["prompt_status"] = "targets_drafted"
    with CASES.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    n_t = sum(len(T[r["case_id"]][0]) for r in rows)
    n_c = sum(sum(x["critical"] for x in T[r["case_id"]][0]) for r in rows)
    langs = {}
    for r in rows:
        langs[r["language"]] = langs.get(r["language"], 0) + 1
    print(f"drafted {len(rows)} prompts, {n_t} targets ({n_c} critical); languages {langs}")


if __name__ == "__main__":
    main()
