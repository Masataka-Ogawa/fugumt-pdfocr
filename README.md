Fugu-Machine Translator PDF/OCR対応
====

[ぷるーふおぶこんせぷと](https://staka.jp/wordpress/?p=413)
で公開した機械翻訳エンジンを利用するPDF翻訳ソフトウェアです。

あくまで検証用の環境・ソフトウェアです。

Usage
----

### 翻訳サーバの実行
Dockerがセットアップされている場合、下記のように実行できます。
1. git clone後、model/ 以下に「[PDF/OCR用の機械翻訳モデルを作ってみた](https://fugumt.com/fugumt/paper/tmp/20220304-pdfocr-nmt.pdf) 」で配布されているモデルをダウンロード、展開
   - ``git clone http://github.com/s-taka/fugumt-pdfocr``
   - ``wget https://fugumt.com/pdf_ocr_model.zip``
   - ``sha1sum pdf_ocr_model.zip``
     - ハッシュ値が 854d6b945fcf70ccde6bd1de212cfad4112d9606 であることを確認
   - ``unzip pdf_ocr_model.zip``
   - 解凍した場所から移動 ``mv pdf_ocr_model/* fugumt-pdf/model``
2. Docker環境を構築
   - ``cd fugumt/docker``
   - ``docker build -t pdf_translator .``
     - ec2での実行を想定して「ec2-user」ユーザをuid:1000で作っています。環境に合わせて変更してください。  
3. コンテナを実行
   - homeディレクトリマウント先の作成（キャッシュ用）
      - ``mkdir /path/to/fugumt-pdfocr/docker_home``
   - PDFMinerを使った翻訳
      - ``docker run --rm -it --gpus all -v /path/to/fugumt-pdfocr:/opt -v /path/to/fugumt-pdfocr/docker_home:/home/ec2-user --user 1000:1000 pdf_translator bash /opt/run_pdfminer.sh /opt/test.pdf``
      - 「/path/to」は環境に合わせて変更してください。git cloneを行った先のディレクトリを指定する必要があります。
      - 「/opt/test.pdf」は翻訳対象のPDF名です。test.pdf.htmlなどファイル名の後に文字列がついたファイルが作成されます。.htmlで終わるファイルが翻訳結果です。
   - OCRを使った翻訳
      - ``docker run --rm -it --gpus all -v /path/to/fugumt-pdfocr:/opt -v /path/to/fugumt-pdfocr/docker_home:/home/ec2-user --user 1000:1000 pdf_translator bash /opt/run_ocr.sh /opt/test.pdf``
      - 「/path/to」は環境に合わせて変更してください。git cloneを行った先のディレクトリを指定する必要があります。
      - 「/opt/test.pdf」は翻訳対象のPDF名です。test.pdf.htmlなどファイル名の後に文字列がついたファイルが作成されます。.htmlで終わるファイルが翻訳結果です。
      - このモードではタイトルの自動取得、アブストラクトの自動作成が行われますが、論文形式のPDF以外ではうまく生成されない可能性があります。



謝辞・ライセンス
----

本ソフトウェアは下記のライブラリ・ソフトウェアを利用しています。
またDockerfileに記載の通り、ubuntuで使用可能なパッケージを多数使用しています。
OSSとして素晴らしいソフトウェアを公開された方々に感謝いたします。

* Marian-NMT (MIT-License): https://github.com/marian-nmt/marian
* SentencePiece(Apache-2.0 License): https://github.com/google/sentencepiece
* NLTK (Apache License Version 2.0): https://www.nltk.org/
* MeCab (BSDライセンス): https://taku910.github.io/mecab/
* mecab-python3 (Like MeCab itself, mecab-python3 is copyrighted free software by Taku Kudo taku@chasen.org and Nippon Telegraph and Telephone Corporation, and is distributed under a 3-clause BSD license ): https://github.com/SamuraiT/mecab-python3
* unidic-lite(BSD license): https://github.com/polm/unidic-lite
* bottle (MIT-License): https://bottlepy.org/docs/dev/
* gunicorn (MIT License): https://github.com/benoitc/gunicorn
* tensorflow (Apache 2.0): https://github.com/tensorflow/tensorflow
* Universal Sentence Encoder (Apache 2.0): https://tfhub.dev/google/universal-sentence-encoder/3
* allennlp (Apache 2.0):https://github.com/allenai/allennlp , [AllenNLP: A Deep Semantic Natural Language Processing Platform](https://www.semanticscholar.org/paper/AllenNLP%3A-A-Deep-Semantic-Natural-Language-Platform-Gardner-Grus/a5502187140cdd98d76ae711973dbcdaf1fef46d)
* spacy (MIT License): https://spacy.io/
* pdfminer (MIT-License): https://github.com/euske/pdfminer
* websocket-client (BSD-3-Clause License): https://github.com/websocket-client/websocket-client
* psutil(BSD-3-Clause License): https://github.com/giampaolo/psutil
* timeout-decorator (MIT License): https://github.com/pnpnpn/timeout-decorator 
* bootstrap(MIT-License) : https://getbootstrap.com/
* jquery(MIT-License): https://jquery.com/
* DataTables(MIT-License): https://datatables.net/
* pySBD(MIT-License): https://github.com/nipunsadvilkar/pySBD
* Layout Parser(Apache 2.0 License): https://github.com/Layout-Parser/layout-parser
* tesseract(Apache 2.0 License): https://github.com/tesseract-ocr/tesseract

本ソフトウェアは研究用を目的に公開しています。
作者（Satoshi Takahashi）は本ソフトウェアの動作を保証せず、本ソフトウェアを使用して発生したあらゆる結果について一切の責任を負いません。
本ソフトウェア（Code）はMIT-Licenseです。

モデル作成では上記ソフトウェアに加え、下記のデータセット・ソフトウェアを使用しています。
オープンなライセンスでソフトウェア・データセットを公開された方々に感謝いたします。
* Beautiful Soap (MIT License): https://www.crummy.com/software/BeautifulSoup/
* feedparser (BSD License): https://github.com/kurtmckee/feedparser
* LaBSE (Apache 2.0): https://tfhub.dev/google/LaBSE/
  * Fangxiaoyu Feng, Yinfei Yang, Daniel Cer, Narveen Ari, Wei Wang. Language-agnostic BERT Sentence Embedding. July 2020
* Japanese-English Subtitle Corpus (CC BY-SA 4.0): https://nlp.stanford.edu/projects/jesc/
  * Pryzant, R. and Chung, Y. and Jurafsky, D. and Britz, D.,
    JESC: Japanese-English Subtitle Corpus,
    Language Resources and Evaluation Conference (LREC), 2018
* 京都フリー翻訳タスク (KFTT) (CC BY-SA 3.0): http://www.phontron.com/kftt/index-ja.html
  * Graham Neubig, "The Kyoto Free Translation Task," http://www.phontron.com/kftt, 2011.
* Tanaka Corpus (CC BY 2.0 FR):http://www.edrdg.org/wiki/index.php/Tanaka_Corpus
  * > Professor Tanaka originally placed the Corpus in the Public Domain, and that status was maintained for the versions used by WWWJDIC. In late 2009 the Tatoeba Project decided to move it to a Creative Commons CC-BY licence (that project is in France, where the concept of public domain is not part of the legal framework.) It can be freely downloaded and used provided the source is attributed. 
* JSNLI (CC BY-SA 4.0):http://nlp.ist.i.kyoto-u.ac.jp/index.php?%E6%97%A5%E6%9C%AC%E8%AA%9ESNLI%28JSNLI%29%E3%83%87%E3%83%BC%E3%82%BF%E3%82%BB%E3%83%83%E3%83%88
  * 吉越 卓見, 河原 大輔, 黒橋 禎夫: 機械翻訳を用いた自然言語推論データセットの多言語化, 第244回自然言語処理研究会, (2020.7.3).
* WikiMatrix (Creative Commons Attribution-ShareAlike license):https://github.com/facebookresearch/LASER/tree/master/tasks/WikiMatrix
  * Holger Schwenk, Vishrav Chaudhary, Shuo Sun, Hongyu Gong and Paco Guzman, WikiMatrix: Mining 135M Parallel Sentences in 1620 Language Pairs from Wikipedia, arXiv, July 11 2019.
* Tatoeba (CC BY 2.0 FR): https://tatoeba.org/jpn
  * > https://tatoeba.org TatoebaのデータはCC-BY 2.0 FRで提供されています。
* CCAligned (No claims of intellectual property are made on the work of preparation of the corpus. ): http://www.statmt.org/cc-aligned/
  * El-Kishky, Ahmed and Chaudhary, Vishrav and Guzm{\'a}n, Francisco and Koehn, Philipp,
    CCAligned: A Massive Collection of Cross-lingual Web-Document Pairs,
    Proceedings of the 2020 Conference on Empirical Methods in Natural Language Processing (EMNLP 2020), 2020



PDFの通り本モデルは研究用を目的に[CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/deed.ja)で公開しています。
作者（Satoshi Takahashi）は本モデルの動作を保証せず、本モデルを使用して発生したあらゆる結果について一切の責任を負いません。

※ 出典を書く際はBlogのURL記載またはリンクをお願いします。
 https://staka.jp/wordpress/
