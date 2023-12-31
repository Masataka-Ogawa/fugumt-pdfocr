# -*- coding: utf-8 -*-


from abc import abstractmethod
import pickle
import argparse
import json
import logging
from datetime import datetime

import time
import sys
import os
import sqlite3
import pprint
import base64
import re
import html

import subprocess
import psutil
import functools

from subprocess import PIPE
from subprocess import TimeoutExpired

from io import StringIO
from pdfminer.converter import TextConverter
from pdfminer.layout import LAParams
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.pdfpage import PDFPage
from pdfminer.pdfparser import PDFParser

from fugumt.tojpn import FuguJPNTranslator
from fugumt.tojpn import get_err_translated

from fugumt.misc import make_marian_process
from fugumt.misc import close_marian_process
from fugumt.misc import ckeck_restart_marian_process

# for ocr
import pdf2image
import numpy as np
import layoutparser as lp
import torchvision.ops.boxes as bops
import torch
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image
from io import BytesIO

import gzip

def has_intersect(a, b):
  return max(a.x_1, b.x_1) <= min(a.x_2, b.x_2) and max(a.y_1, b.y_1) <= min(a.y_2, b.y_2)

def get_intersect_bound(a, b):
  x1 = max(a.x_1, b.x_1)
  y1 = max(a.y_1, b.y_1)
  x2 = min(a.x_2, b.x_2)
  y2 = min(a.y_2, b.y_2)

  return x1, y1, x2, y2  

def merge_block(block_1, block_2):
  if has_intersect(block_1.block, block_2.block):
    x_1, y_1, x_2, y_2 = get_intersect_bound(block_1.block, block_2.block)
    intersect_area = (x_2 - x_1) * (y_2 - y_1)
    block1_area  = (block_1.block.x_2 - block_1.block.x_1) * (block_1.block.y_2 - block_1.block.y_1)
    block2_area  = (block_2.block.x_2 - block_2.block.x_1) * (block_2.block.y_2 - block_2.block.y_1)
    if block1_area > block2_area:
      if intersect_area / block2_area > 0.9:
         block_2.set(type='None', inplace= True)


def ocr_pdf(pdf_file, logger=None, max_page = 1000000):
  pdf_images = pdf2image.convert_from_path(pdf_file)
  ocr_agent = lp.TesseractAgent(languages='eng')
  model = lp.models.Detectron2LayoutModel('lp://PubLayNet/mask_rcnn_X_101_32x8d_FPN_3x/config',
                                extra_config=["MODEL.ROI_HEADS.SCORE_THRESH_TEST", 0.4],
                                label_map={0: "Text", 1: "Title", 2: "List", 3:"Table", 4:"Figure"})
  return_blocks = []
  for page_idx, pdf_image in enumerate(pdf_images):
    if page_idx > max_page:
      break
    if logger:
      logger.info("now proc page_id = {}".format(page_idx))
    ocr_img = np.asarray(pdf_image)
    layout_result = model.detect(ocr_img)

    text_blocks = lp.Layout([b for b in layout_result if b.type=='Text' or b.type=='List' or b.type=='Title'])
    for layout_i in text_blocks:
        for layout_j in text_blocks:
            if layout_i != layout_j:
              merge_block(layout_i, layout_j)
    
    text_blocks_ocr = lp.Layout([b for b in text_blocks if b.type=='Text' or b.type=='List' or b.type=='Title'])

    for block in text_blocks_ocr:
      segment_image = (block
                       .pad(left=15, right=15, top=5, bottom=5)
                       .crop_image(ocr_img))
      text = ocr_agent.detect(segment_image)
      block.set(text=text, inplace=True)

    return_blocks.append((page_idx, pdf_image, text_blocks_ocr, text_blocks))

  return return_blocks

def get_title_abstract(in_data, fgmt, make_marian_conf=None, logger=None):
    ocr_result = in_data['ocr_result']
    translated_blocks = in_data['translated_blocks']

    # 最初のタイトルの自動抽出
    first_page = ocr_result[0][2]
    title_blocks = sorted([b for b in first_page if b.type=='Title'], key=lambda x: x.block.y_1)
    title = ''
    if len(title_blocks) > 0:
        title = title_blocks[0].text
    title = re.sub(r'[^a-zA-Z0-9 \|\@\!\"\'\`\*\+\-\)\(\[\]\{\}\<\>\_\~\=\#\$\%\&\.\,\;\:]', '', title)

    def sort_func(lhs, rhs):
        threshold_xdiff_range = max(lhs['box_info'][2] - lhs['box_info'][0], rhs['box_info'][2] - rhs['box_info'][0]) / 1.5
        if abs(lhs['box_info'][0] - rhs['box_info'][0]) < threshold_xdiff_range:
            return lhs['box_info'][1] - rhs['box_info'][1]
        else:
            return lhs['box_info'][0] - rhs['box_info'][0]

    abstract_strs = []
    for page_num, blocks in enumerate(translated_blocks):
        if page_num > 1:
            break
        sorted_block = sorted(blocks, key=functools.cmp_to_key(sort_func))
        for block in sorted_block:
            block_id = block['block_id']
            coords = block['box_info']
            block_data = {'block_id': int(block_id), 'texts': [], 'coords':coords }
            translated_block = block['translated']
            for translated in translated_block:
                en = translated["en"]
                if len(en) > 100:
                    abstract_strs.append(en)

    from transformers import pipeline
    summarizer = pipeline('summarization', model='sshleifer/distilbart-cnn-12-6')
    import time

    src_txt = '.'.join(abstract_strs)[0:min(1024, len('.'.join(abstract_strs)))]
    src_txt = re.sub('\.\s*\.', '.', src_txt)

    if logger:
        logger.info("abstract text [{}]".format(src_txt))

    start = time.time()
    with torch.no_grad():
        ret_txt = summarizer(src_txt)

    marian_processes = []
    if make_marian_conf:
        marian_processes = make_marian_process(make_marian_conf["marian_command"],
                                               make_marian_conf["marian_args_pdf_translator"],
                                               make_marian_conf["pdf_ports"])
    
    if logger:
        logger.info("translate abstract {}".format(ret_txt))

    try:
        txt = ret_txt[0]['summary_text']
    except:
        txt = ''
        
    if len(src_txt) < 150:
        txt = src_txt
    to_translate = pre_proc_text(txt.replace('<n>', '\n\n'))
    translated = ''
    if len(to_translate):
        translated = fgmt.translate_text(to_translate)
        if fgmt.detected_marian_err:
            translated = ''

    to_translate = pre_proc_text(title.replace('\n\n', '\n'))
    title_ja = ''
    if len(to_translate):
        title_ja = fgmt.translate_text(title)
        if fgmt.detected_marian_err:
            title_ja = ''
    close_marian_process(marian_processes)

    return title, title_ja, translated



def pdf_translate_ocr(pdf_path, fgmt, make_marian_conf=None, logger=None):
    ocr_result = ocr_pdf(pdf_path, max_page=100, logger=logger)
    text_block_id = 0
    translated_blocks = []

    marian_processes = []
    if make_marian_conf:
        marian_processes = make_marian_process(make_marian_conf["marian_command"],
                                               make_marian_conf["marian_args_pdf_translator"],
                                               make_marian_conf["pdf_ports"])
    
    for (page_idx, pdf_image, text_blocks_ocr, text_blocks) in ocr_result:
        page_translated_blocks = []
        for (txt, block_info) in [(b.text, b.block) for b in text_blocks_ocr]:
            retry_max = 3
            translated = None
            marian_processes = ckeck_restart_marian_process(marian_processes, make_marian_conf["max_marian_memory"], make_marian_conf["marian_command"], make_marian_conf["marian_args_pdf_translator"], make_marian_conf["pdf_ports"], logger=logger)
            for i in range(retry_max):
                if logger:
                    logger.info("translate page={} block_id={}".format(page_idx, text_block_id))
                to_translate = pre_proc_text(txt.replace('\n\n', '\n'))
                translated = fgmt.translate_text(to_translate)
                if not fgmt.detected_marian_err:
                    block_data = {'original': txt, 'translated': translated, 'block_id': text_block_id, 'box_info':(block_info.x_1, block_info.y_1, block_info.x_2, block_info.y_2)}
                    page_translated_blocks.append(block_data)
                    text_block_id += 1
                    break
                else:
                    translated = None
                    close_marian_process(marian_processes)
                    marian_processes = make_marian_process(make_marian_conf["marian_command"],
                                                            make_marian_conf["marian_args_pdf_translator"],
                                                            make_marian_conf["pdf_ports"])

                    fgmt.detected_marian_err = False
                    if logger:
                        logger.info(fgmt.get_and_clear_logs())
                        logger.warning("recovery marian processes {}/{}".format(i, retry_max-1))
            if translated is None:
                block_data = {'original': txt, 'translated': get_err_translated(), 'block_id': text_block_id, 'box_info':(block_info.x_1, block_info.y_1, block_info.x_2, block_info.y_2)}
                page_translated_blocks.append(block_data)
            marian_processes = ckeck_restart_marian_process(marian_processes, make_marian_conf["max_marian_memory"],
                                                            make_marian_conf["marian_command"],
                                                            make_marian_conf["marian_args_pdf_translator"],
                                                            make_marian_conf["pdf_ports"],
                                                            logger=logger)
            if logger:
                logger.info(fgmt.get_and_clear_logs())
        translated_blocks.append(page_translated_blocks)

    if make_marian_conf:
        close_marian_process(marian_processes)
    
    return {'ocr_result':ocr_result, 'translated_blocks': translated_blocks}

def escape_break_word(txt):
    return re.sub('([a-zA-Z0-9\/\.\-\:\%\-\~\\\*\"\'\&\$\#\(\)\?\_\,,\@]{100,}?)', "\\1 ", html.escape(txt))


def pre_proc_text(txt):
    if txt:
        ret = txt.replace('i.e.', 'i e ')
        ret = txt.replace('e.g.', 'e g ')
        ret = ret.replace('et al.', 'et al ')
        ret = ret.replace('state of the art', 'state-of-the-art')
        ret = ret.replace(' Fig.', ' Fig ')
        ret = ret.replace(' fig.', ' fig ')
        ret = ret.replace(' cf. ', ' cf ')
        ret = ret.replace(' Eq.', ' Eq ')
        ret = ret.replace(' Appx.', ' Appx ')
        ret = re.sub(r'^Fig. ', 'Fig ', ret)
        ret = re.sub(r'^fig. ', 'fig ', ret)
        ret = re.sub(r'^Eq. ', 'Eq ', ret)       
    else:
        ret = txt
    return ret


def pdf_translate(pdf_path, fgmt, make_marian_conf=None, logger=None):
    page_split_tag = '\n\n<<PAGE_SPLIT_TAG>>\n\n'
    output_string = StringIO()
    with open(pdf_path, 'rb') as in_file:
        parser = PDFParser(in_file)
        doc = PDFDocument(parser)
        rsrcmgr = PDFResourceManager()
        device = TextConverter(rsrcmgr, output_string, laparams=LAParams(boxes_flow=0.3, line_margin=1.0))
        interpreter = PDFPageInterpreter(rsrcmgr, device)
        for idx, page in enumerate(PDFPage.create_pages(doc)):
            interpreter.process_page(page)
            output_string.write(page_split_tag)
    pdf_text = output_string.getvalue()
    pdf_pages = pdf_text.split(page_split_tag)
    marian_processes = []
    if make_marian_conf:
        marian_processes = make_marian_process(make_marian_conf["marian_command"],
                                               make_marian_conf["marian_args_pdf_translator"],
                                               make_marian_conf["pdf_ports"])
    ret = []
    for pdf_idx, pdf_page in enumerate(pdf_pages[:-1]):
        retry_max = 3
        translated = None
        marian_processes = ckeck_restart_marian_process(marian_processes, make_marian_conf["max_marian_memory"], make_marian_conf["marian_command"], make_marian_conf["marian_args_pdf_translator"], make_marian_conf["pdf_ports"], logger=logger)
        for i in range(retry_max):
            if logger:
                logger.info("translate page={}".format(pdf_idx))
            to_translate = pre_proc_text(pdf_page)
            translated = fgmt.translate_text(to_translate)
            if not fgmt.detected_marian_err:
                ret.append(translated)
                break
            else:
                translated = None
                close_marian_process(marian_processes)
                marian_processes = make_marian_process(make_marian_conf["marian_command"],
                                                       make_marian_conf["marian_args_pdf_translator"],
                                                       make_marian_conf["pdf_ports"])

                fgmt.detected_marian_err = False
                if logger:
                    logger.info(fgmt.get_and_clear_logs())
                    logger.warning("recovery marian processes {}/{}".format(i, retry_max-1))
        if translated is None:
            ret.append(get_err_translated())
        marian_processes = ckeck_restart_marian_process(marian_processes, make_marian_conf["max_marian_memory"],
                                                        make_marian_conf["marian_command"],
                                                        make_marian_conf["marian_args_pdf_translator"],
                                                        make_marian_conf["pdf_ports"],
                                                        logger=logger)
        if logger:
            logger.info(fgmt.get_and_clear_logs())

    if make_marian_conf:
        close_marian_process(marian_processes)

    return ret


def make_static_html(pdf_path, pickle_path, html_path, template="template/pdf_server_static.tmpl", add_data=""):
    with open(template, encoding="utf-8") as in_file:
        tmpl = in_file.read()

    with open(pdf_path, "rb") as in_pdf:
        pdf_base64 = base64.b64encode(in_pdf.read()).decode("utf-8")

    table_header_tmpl = "<div id='translated_{}'><table border='1'><tr><th>英語</th><th>日本語</th><th>スコア</th></tr>\n"
    table_footer_tmpl = "</table></div>\n"
    tr_tmpl = "<tr> <td>{}</td> <td>{}</td> <td>{:.2f}</td></tr>\n"
    tr_tmpl_parse = "<tr> <td>{}</td> <td>{} <br /><small>訳抜け防止モード: {}</small></td> <td>{:.2f}</td></tr>\n"

    pickle_data = pickle.load(open(pickle_path, "rb"))
    translated_tables = ""
    for page_num, translated_page in enumerate(pickle_data):
        translated_tables += table_header_tmpl.format(page_num+1)
        add_item = {"en": "", "ja_best": "", "ja_norm": "", "scores": []}
        for translated in translated_page:
            best_is_norm = 1
            add_item["scores"].append(translated["ja_best_score"])
            add_item["en"] += translated["en"]
            add_item["ja_best"] += translated["ja_best"]
            add_item["ja_norm"] += translated["ja_norm"]
            if translated["best_is_norm"] == 0:
                best_is_norm = 0
            if len(add_item["ja_best"]) < 10:
                continue
            show_score = sum(add_item["scores"]) / len(add_item["scores"])
            if best_is_norm == 1:
                translated_tables += tr_tmpl.format(escape_break_word(add_item["en"]),
                                                    escape_break_word(add_item["ja_best"]), show_score)
            else:
                translated_tables += tr_tmpl_parse.format(escape_break_word(add_item["en"]),
                                                          escape_break_word(add_item["ja_norm"]),
                                                          escape_break_word(add_item["ja_best"]),
                                                          show_score)
            add_item = {"en": "", "ja_best": "", "ja_norm": "", "scores": []}
        if len(add_item["en"]):
            show_score = sum(add_item["scores"]) / len(add_item["scores"])
            translated_tables += tr_tmpl.format(escape_break_word(add_item["en"]),
                                                escape_break_word(add_item["ja_best"]), show_score)
        translated_tables += table_footer_tmpl

    page_list_tmpl = "<button id='nav_{}' onclick='renderPage({})'>{}</button>\n"
    page_list = "&nbsp;".join([page_list_tmpl.format(idx+1, idx+1, idx+1) for idx in range(len(pickle_data))])

    with open(html_path, "w") as out:
        write_data = tmpl.replace("{{translated_tables}}", translated_tables)
        write_data = write_data.replace("{{navigation}}", page_list)
        write_data = write_data.replace("{{base64_pdf}}", pdf_base64)
        write_data = write_data.replace("{{add_data}}", add_data)
        out.write(write_data)

    return


def make_static_html_ocr(pdf_path, pickle_path, html_path, template="template/template_vue.html", add_data=""):

    pickle_data = pickle.load(gzip.open(pickle_path, "rb"))
    ocr_result = pickle_data['ocr_result']
    translated_blocks = pickle_data['translated_blocks']

    out_dic = {'png_images':[], 'png_size':[], 'pages':[], 'pdf':'', 'paper_info': pickle_data['paper_info']}

    for idx, (page_idx, pdf_image, text_blocks_ocr, text_blocks) in enumerate(ocr_result):
        buffer = BytesIO()
        img_data = lp.draw_box(pdf_image, text_blocks_ocr,  box_width=5, box_alpha=0.2, show_element_type=True)
        img_data.save(buffer, 'png')
        img_str = base64.b64encode(buffer.getvalue()).decode("ascii")
        out_dic['png_images'].append(img_str)
        out_dic['png_size'].append({'height':img_data.height, 'width': img_data.width})

    for page_num, _ in enumerate(ocr_result):
        page_blocks = []
        for block in translated_blocks[page_num]:
            block_id = block['block_id']
            coords = block['box_info']
            block_data = {'block_id': int(block_id), 'texts': [], 'coords':coords }
            translated_block = block['translated']
            for translated in translated_block:
                block_data['texts'].append({
                    'best_is_norm': translated["best_is_norm"],
                    'en': html.escape(translated["en"]),
                    'ja_best': html.escape(translated["ja_best"]),
                    'ja_best_score': translated["ja_best_score"],
                    'ja_norm': html.escape(translated["ja_norm"]),
                    'ja_norm_score': translated["ja_norm_score"],          
                    'ja_parse': html.escape(translated["ja_parse"]),
                    'ja_parse_score': translated["ja_parse_score"]
                })
            page_blocks.append(block_data)
        out_dic['pages'].append(page_blocks)


    with open(pdf_path, "rb") as in_pdf:
        out_dic['pdf'] = base64.b64encode(in_pdf.read()).decode("utf-8")
    

    with open(html_path, 'w') as out:
        with open(template) as in_html:
            out_html = in_html.read().replace('%%JSON_DATA%%', 'translated_data = {} ;'.format(json.dumps(out_dic)))
            abstract = ''
            for elm in out_dic['paper_info']['abstract']:
                abstract += elm['ja_best']
            out_html = out_html.replace('%%TITLE%%', escape_break_word(out_dic['paper_info']['title'])).replace('%%ABSTRACT%%', escape_break_word(abstract))
            out.write('{}'.format(out_html))

    with gzip.open(pickle_path+'.json.gz', 'wt') as out:
        out.write('{}'.format(json.dumps(out_dic)))

    return


def main():
    parser = argparse.ArgumentParser(description='run fugu machine translator for pdf')
    parser.add_argument('config_file', help='config json file')
    parser.add_argument('--pdf', help='PDF file')
    parser.add_argument('--out', help='out pickle file')
    parser.add_argument('--mk_process', help='make marian process')
    parser.add_argument('--out_html', help='out html file')
    parser.add_argument('--ocr', help='use ocr mode')

    args = parser.parse_args()
    config = json.load(open(args.config_file))

    pdf_file = ""
    if args.pdf:
        pdf_file = args.pdf
        out_pickle_file = args.out

    out_html_file = ""
    if args.out_html:
        out_html_file = args.out_html

    make_marian_conf = None
    if args.mk_process:
        make_marian_conf = config

    logging.basicConfig(format='%(asctime)s : %(levelname)s : %(message)s', level=logging.INFO)
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    def can_translate(en_txt):
        words = en_txt.split()
        if len(words) == 0:
            return False
        words_en = list(filter(lambda x: re.search("[a-zA-Z]", x), words))
        if len(words_en) == 0:
            return False
        if len(words_en) / len(words) < 0.2:
            return False
        if re.search("[a-zA-Z]", en_txt):
            return True
        else:
            return False
        
    fgmt = FuguJPNTranslator(config["pdf_ports"], retry_max=0, batch_size=3, use_constituency_parsing=False, can_translate_func=can_translate, use_sentence_tokenize='pysbd')

    if args.ocr and pdf_file:
        logger.info("pickle [{}] html [{}]".format(out_pickle_file, out_html_file))
        if not os.path.exists(out_pickle_file):
            logger.info("translate [{}] using ocr mode".format(pdf_file))
            ret =  pdf_translate_ocr(pdf_file, fgmt, make_marian_conf=make_marian_conf, logger=logger)
            title, title_ja, abstract = get_title_abstract(ret, fgmt, make_marian_conf=make_marian_conf, logger=logger)
            ret['paper_info'] = {'title':title, 'title_ja':title_ja, 'abstract':abstract}
            with gzip.open(out_pickle_file, 'wb') as out:
                pickle.dump(ret, out)
            logger.info(fgmt.get_and_clear_logs())
        else:
            logger.info("file {} exist. omit translating".format(out_pickle_file))

        if out_html_file:
            make_static_html_ocr(pdf_file, out_pickle_file, out_html_file)

    elif pdf_file:
        if not os.path.exists(out_pickle_file):
            logger.info("translate [{}]".format(pdf_file))
            ret = pdf_translate(pdf_file, fgmt, make_marian_conf=make_marian_conf, logger=logger)
            with open(out_pickle_file, "wb") as f:
                pickle.dump(ret, f)
            logger.info(fgmt.get_and_clear_logs())
        else:
            logger.info("file {} exist. omit translating".format(out_pickle_file))

        if out_html_file:
            logger.info("make html  [{}]".format(pdf_file))
            make_static_html(pdf_file, out_pickle_file, out_html_file,
                            template=os.path.join(config["template_dir"], config["static_pdfhtml_template"]))

    else:
        logger.error('no pdf file')


if __name__ == '__main__':
    main()





