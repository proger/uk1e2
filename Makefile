ifeq ($(HATCH_ENV_ACTIVE),)
  $(warning HATCH_ENV_ACTIVE is not set. Use make inside `hatch shell` or do `hatch run make`.)
endif

# index for https://wilab.org.ua/uk1e2
uk1e2.db: local_utterances.jsonl data/segments/wav.scp
	rm -f $@
	< $< jq -rc '{id,domain,text,normalized_text,start,end:.end,utterance_url:"https://a.wilab.org.ua/wav/\(.id).wav"}' | sqlite-utils insert $@ utterances - --nl --pk id
	sqlite-utils enable-fts $@ utterances id domain text normalized_text

# aggregate source for utterances.csv
intermediate.db: uk1e2.jsonl zipytable1.jsonl zipytable2.jsonl
	rm -f $@
	sqlite-utils insert $@ utterances uk1e2.jsonl --nl --quiet
	sqlite-utils insert $@ utterances zipytable1.jsonl --nl --alter --quiet
	sqlite-utils insert $@ utterances zipytable2.jsonl --nl --alter --quiet
	sqlite-utils enable-fts $@ utterances text

data/local/dict/g2p.fst:
	mkdir -p data/local/dict
	cd data/local/dict && curl -LO https://a.wilab.org.ua/uk/g2p.fst

data/local/dict/uk_pron.v3.vcb:
	mkdir -p data/local/dict
	cd data/local/dict && curl -LO https://a.wilab.org.ua/uk/uk_pron.v3.vcb

# make prepare needs this view
utterances.csv: intermediate.db
	sqlite-utils rows $< utterances --csv -c rowid -c domain -c source -c utterance_id -c start_time -c speaker_id -c text -c normalized_text -c start -c end -c url > $@

# download youtube+uk1e2 data
local_utterances.jsonl: utterances.csv
	python -m uk1e2.download utterances.csv data/corpus > $@
	python -m uk1e2.download news data/corpus >> $@

# kaldi data directory
data/local/wav.scp: local_utterances.jsonl data/local/dict/g2p.fst data/local/dict/uk_pron.v3.vcb
	python -m uk1e2.prepare_kaldi local_utterances.jsonl
data/local/text data/local/spk2utt data/local/utt2spk data/local/segments: data/local/wav.scp

data/segments/wav.scp: data/local/wav.scp data/local/segments
	python -m uk1e2.extract_segments -o data/segments -i $^

data/segments/segments.csv: data/segments/wav.scp data/local/text
	join $^ | cut -d' ' -f2,3- | awk -v OFS=, 'BEGIN{print "path,text"} {printf "%s,", $$1; for (i = 2; i <= NF; i++) {printf "%s ", $$i}; printf "\n"}' > $@

# removing text that we think is bad
data/local/text.filt1: data/local/text exp/segmented+aligned.ids
	cat data/local/text | sort | join - exp/segmented+aligned.ids > $@
	grep -- '-I' $@ > data/local/text.interview
	grep -- '-P' $@ > data/local/text.podcast
	grep -- '-C' $@ > data/local/text.courses
	grep -- '-Y' $@ > data/local/text.youtube
	grep -- '-N' $@ > data/local/text.news
data/local/text.news data/local/text.interview data/local/text.podcast data/local/text.courses data/local/text.youtube: data/local/text.filt1

exp/wer: data/local/text.news data/local/text.interview data/local/text.podcast data/local/text.courses data/local/text.youtube
	rm -f $@
	compute-wer --mode=present ark:data/local/text.interview ark:exp/nemo_segmented+aligned | tee -a $@
	compute-wer --mode=present ark:data/local/text.podcast ark:exp/nemo_segmented+aligned | tee -a $@
	compute-wer --mode=present ark:data/local/text.courses ark:exp/nemo_segmented+aligned | tee -a $@
	compute-wer --mode=present ark:data/local/text.youtube ark:exp/nemo_segmented+aligned | tee -a $@
	compute-wer --mode=present ark:data/local/text.news ark:exp/nemo_segmented+aligned | tee -a $@
	compute-wer --mode=present ark:data/local/text.interview ark:exp/whisper.hyp | tee -a $@
	compute-wer --mode=present ark:data/local/text.podcast ark:exp/whisper.hyp | tee -a $@
	compute-wer --mode=present ark:data/local/text.courses ark:exp/whisper.hyp | tee -a $@
	compute-wer --mode=present ark:data/local/text.youtube ark:exp/whisper.hyp | tee -a $@
	compute-wer --mode=present ark:data/local/text.news ark:exp/whisper.hyp | tee -a $@

exp/dur: data/local/text.news data/local/text.interview data/local/text.podcast data/local/text.courses data/local/text.youtube
	join data/local/utt2dur data/local/text.interview | awk '{print $$2}' | jq -rs 'add /60/60'
	join data/local/utt2dur data/local/text.podcast | awk '{print $$2}' | jq -rs 'add /60/60'
	join data/local/utt2dur data/local/text.courses  | awk '{print $$2}' | jq -rs 'add /60/60'
	join data/local/utt2dur data/local/text.youtube | awk '{print $$2}' | jq -rs 'add /60/60'
	join data/local/utt2dur data/local/text.news | awk '{print $$2}' | jq -rs 'add /60/60'

# postprocess youtube txt brushlyk dump to tsv
# this file has been edited manually to resolve timing monotonicity
## youtube1.tsv: youtube1.txt
## 	cat $^ | awk -v OFS="\t" '/__file__/{file=$$2; spk="Спікер"; next} /^# /{gsub("^# ", ""); spk=$$0; next} /^0[0-9-]+/{gsub("-",":"); ts=$$0; next} /Метадані:/{spk="__meta__"} /^..+$$/{print NR, file, ts, spk, $$0}' \
## 	| grep -v __meta__  > $@

youtube2.tsv: youtube2.txt
	cat $^ | awk -v c=20000 -v OFS="\t" '/__file__/{file=$$2; spk="Спікер"; next} /^# /{gsub("^# ", ""); spk=$$0; next} /^0[0-9-]+/{gsub("-",":"); ts=$$0; next} /Метадані:/{spk="__meta__"} /^..+$$/{print c, file, ts, spk, $$0; c+=1}' \
		| grep -v __meta__  > $@

# postprocess youtube tsv to jsonl with mp4 urls
ytable%.jsonl: youtube%.tsv
	cat $^ | jq -Rrc 'split("\t") | {domain:"youtube", source:.[1], utterance_id: (.[0]|tonumber + 100000), start_time: .[2], speaker_id: .[3], text: .[4]}' \
		| python -m collapse_repeats | python -m add_urls  > $@

# add normalized youtube utterances
zipytable1.jsonl: ytable1.jsonl youtube_normalized.csv
	python -m zip_jsonl_csv $^ > $@

zipytable2.jsonl: ytable2.jsonl youtube2_normalized.csv
	python -m zip_jsonl_csv $^ > $@

# convert csv from SaturdayTeam to jsonl with mp4 urls
uk1e2.jsonl: uk1e2.csv uk1e2_normalized.csv
	python -m csv2jsonl $^ | python -m add_urls > $@

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

# generate a Makefile script that aligns all news to news/align/
news/align.mk: news/index.json news/text news/webm
	< news/index.json jq -r '.rows[][0] | "$(PWD)/news/align/\(.).json: $(PWD)/news/webm/\(.).webm $(PWD)/news/text/news-\(.)\n\tpython -m align -o $$@ $$^"' > $@
	< news/index.json jq -r '.rows[][0] | "ALL += $(PWD)/news/align/\(.).json"' >> $@
	echo 'all: $$(ALL)' >> $@
	mkdir -p news/align

news/wav.scp: news/webm
	find news/webm/ | awk -F/ '{print $$3}' | sed 's,.webm,,g' | awk '{print $$1, "ffmpeg -i news/webm/"$$1".webm -f wav -acodec pcm_s16le -ar 16000 -ac 1 - |"}' > $@

clean:
	rm -f intermediate.db uk1e2.db uk1e2.jsonl ytable1.jsonl youtube1.tsv

.DELETE_ON_ERROR:
