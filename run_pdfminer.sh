export TFHUB_CACHE_DIR=/home/ec2-user/.cache/
export ALLENNLP_CACHE_ROOT=/home/ec2-user/.cache/
cd /opt
echo "translate $1"
python3 pdf_translator.py --pdf $1 --out $1.pickle --out_html $1.html --mk_process 1 /opt/config.json