# index for https://wilab.org.ua/uk1e2
uk1e2.db: uk1e2.jsonl ytable1.jsonl
	sqlite-utils insert $@ utterances uk1e2.jsonl --nl
	sqlite-utils insert $@ utterances ytable1.jsonl --nl --alter
	sqlite-utils enable-fts $@ utterances text

# make prepare needs this view
utterances.csv: uk1e2.db
	sqlite-utils rows uk1e2.db utterances --csv > $@

# prepare youtube+uk1e2 data for WER evaluation
prepare: utterances.csv
	python -m uk1e2.prep_test_data

# postprocess youtube txt brushlyk dump to tsv
youtube1.tsv: youtube1.txt
	cat $< | awk -v OFS="\t" '/__file__/{file=$$2; spk="Спікер"; next} /^# /{gsub("^# ", ""); spk=$$0; next} /^0[0-9-]+/{gsub("-",":"); ts=$$0; next} /Метадані:/{spk="__meta__"} /^..+$$/{print NR, file, ts, spk, $$0}' \
	| grep -v __meta__  > $@

# postprocess youtube tsv to jsonl with mp4 urls
ytable1.jsonl: youtube1.tsv
	cat $< | jq -Rrc 'split("\t") | {domain:"youtube", source:.[1], utterance_id: (.[0]|tonumber + 100000), start_time: .[2], speaker_id: .[3], text: .[4]}' \
		| python -m collapse_repeats | python -m add_urls  > $@

# convert csv from SaturdayTeam to jsonl with mp4 urls
uk1e2.jsonl: uk1e2.csv
	python -m csv2jsonl $< | python -m add_urls > $@

# jsonl with all news texts from brushlyk
news/text.jsonl: news/index.json
	< $^ jq -r '.rows[][0] | "news-\(.)"' | xargs python -m replay > $@

# file with all news urls
news/urls: news/index.json
	< $^ jq -r '.rows[][-2]' | sed 's,/wavesurfer/,/file/,g' > $@

# download a directory with individual news webm audios
news/webm: news/urls
	mkdir -p $@; cd $@; cat ../urls | xargs -n1 -P16 -t curl -s -u oco:mykolynapohoda -C - -O

# directory individual text files with news transcripts
news/text: news/text.jsonl
	mkdir -p $@; < $^ jq -rc 'to_entries[] | "cat > news/text/\(.key) << \"EOF\"\n\(.value)\nEOF"' | bash -x

clean:
	rm -f uk1e2.db uk1e2.jsonl ytable1.jsonl youtube1.tsv

.DELETE_ON_ERROR:
