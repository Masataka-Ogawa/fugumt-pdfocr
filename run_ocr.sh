export TFHUB_CACHE_DIR=/home/ec2-user/.cache/
export ALLENNLP_CACHE_ROOT=/home/ec2-user/.cache/
cd /opt
echo "translate $1"
python3 pdf_translator.py --ocr 1 --pdf $1 --out $1.ocr.pickle --out_html $1.ocr.html --mk_process 1 /opt/config.json