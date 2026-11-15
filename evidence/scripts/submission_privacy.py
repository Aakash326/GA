"""Release transformations only. Working evidence is never overwritten or deleted."""
import csv
import io
import json
from pathlib import Path
import re

PRIVATE_ID=re.compile(r'^CALL-\d{2}$')
PRIVATE_PATH=re.compile(r'(^|/)CALL-\d{2}([_/.]|$)')
SAFE_FIELDS=set('clip_id case_id id source_id cohort category tags language lang primary_language selected model model_returned output_mode sample_rate_hz duration_s noise_snr_db codec input_path input_sha256 audio_sha256 audio_hash is_no_speech case_status status attempt latency_ms retry_inclusive_ms server_processing_s reference_status evaluation_group evaluation_split scoring_eligible evidence_visibility substitutions deletions insertions false_transcription no_speech_inserted_words environment'.split())
SCORE_FIELDS=set('ref_word_count word_edits ref_char_count char_edits nospace_ref_chars nospace_char_edits raw_ref_word_count raw_ref_char_count raw_word_edits raw_char_edits wer cer raw_wer raw_cer edits_word edits_cross_script edits_number edits_deletion edits_insertion ref_words ref_chars source_word_edits source_ref_word_count'.split())


def excluded(rel):
    parts=Path(rel).parts
    if parts[:3]==('results','next','call'):return True
    if 'owner_exports' in parts:return True
    if PRIVATE_PATH.search(rel):return True
    if rel.endswith('.html') and rel not in ['data/listening/tts_quality_study.html','results/playback_validation/index.html','results/timbre_followup/index.html','timbre_comparison.html','results/report4/index.html','results/report4_quality/listening.html','results/report4_quality/rewrites.html']:
        return True  # Historical pages can inline call text; regenerate locally if needed.
    return False


def private_row(row):
    values=[str(v) for v in row.values() if isinstance(v,(str,int,float))]
    return any(re.search(r'CALL-\d{2}(?!\d)',v) or 'results/next/call/' in v.replace('\\','/') for v in values)


def csv_payload(raw, rel, counts):
    reader=csv.DictReader(io.StringIO(raw.decode('utf-8-sig')));fields=list(reader.fieldnames or []);rows=[]
    private=False
    for row in reader:
        if private_row(row):
            private=True
            continue
        rows.append(row)
    if not private:return raw
    fields=list(dict.fromkeys(fields+[k for row in rows for k in row]))
    out=io.StringIO(newline='');writer=csv.DictWriter(out,fieldnames=fields);writer.writeheader();writer.writerows(rows)
    return out.getvalue().encode('utf-8-sig')


def private_json(data):
    if isinstance(data,dict):
        if private_row(data):
            return None
        return {k:clean for k,v in data.items() if not PRIVATE_ID.fullmatch(k) and (clean:=private_json(v)) is not None}
    if isinstance(data,list):return [clean for v in data if (clean:=private_json(v)) is not None]
    return data


def secrets_from_env(project):
    values=[];path=project/'.env'
    if path.exists():
        for line in path.read_text(encoding='utf-8-sig').splitlines():
            if '=' not in line or line.lstrip().startswith('#'):continue
            key,value=line.split('=',1);value=value.strip().strip('\"\'')
            if re.search(r'KEY|TOKEN|SECRET|PASSWORD',key,re.I) and len(value)>=12:values.append(value.encode())
    return values


def check_secrets(data, name, secrets):
    if any(value in data for value in secrets):raise ValueError('Private credential found in release payload: '+name)
    patterns=[rb'AIza[0-9A-Za-z_-]{30,}',rb'sk-(?:proj-)?[A-Za-z0-9_-]{35,}']
    if any(re.search(pattern,data) for pattern in patterns):raise ValueError('Credential-shaped value found in release payload: '+name)
