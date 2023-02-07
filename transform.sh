cat < youtube1.txt | awk -v OFS="\t" '/__file__/{file=$2; spk="Спікер"; next} /^# /{gsub("^# ", ""); spk=$0; next} /^0/{gsub("-",":"); ts=$0; next} /Метадані:/{spk="__meta__"} /^..+$/{print NR, file, ts, spk, $0}' | grep -v __meta__  > youtube1.tsv

cat youtube1.tsv | jq -Rrc 'split("\t") | {domain:"youtube", source:.[1], utterance_id: (.[0]|tonumber + 100000), start_time: .[2], speaker_id: .[3], text: .[4]}' > ytable1.jsonl

cat ytable1.jsonl | python -m collapse_repeats  > ytable-collapsed.jsonl

cat ytable-collapsed.jsonl | python -m add_urls | sqlite-utils insert --nl uk1e2.db utterances - --alter
