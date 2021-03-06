#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import time
import base64
import html5lib
from lxml import etree
import re
import argparse
import ftfy
from lxml.html.clean import Cleaner
from bs4 import BeautifulSoup

#Inline tags that don't start on a new line and only take up as much width as necessary. From https://www.w3schools.com/html/html_blocks.asp
inline_tags={"a","abbr","acronym","b","bdo","big","br","button","cite","code","dfn","em","i","img","input","kbd","label","map","object","q","samp","script","select","small","span","strong","sub","sup","textarea","time","tt","var"}

def getElementText(element,document):
    """Returns a list with word plain text of a tree element of lxml and the corresponding text
    """
    #Return variables for plain text
    text=""
    if element.text != None:        #If we have text in tag
        #Add interpreted space for non-inline tags
        if element.tag not in inline_tags:
            text = "\n"  #Add artificial separation as browser parser does if tag is not inline
        text = text + element.text
    
    #Now we recursively iterate through the childs
    for child in element:
        if type(child) is etree._Element and child.tag != "script" and child.tag != "style":
            text = text + getElementText(child,document)

    #Add interpreted space for non-inline tags after all processing of the actual tag content
    if element.tag not in inline_tags:
        text = text + "\n"
    elif element.tag == "br":
        text = text + "\n"

    #Processing parent text (A.K.A. element.tail) similarly as the actual tag
    if element.tail != None:        #If we have tail parent text (text after the closing tag until the next open/close tag)
        text = text + element.tail

    return text

def getDocumentText(document):
    """Returns a list with word plain text of a document tree in lxml format
    """
    docplaintext=""
    for element in document.getroot():
        if type(element) is etree._Element and element.tag != "script" and element.tag != "style": #Only elements, not scripts or other kind of tags without proper text
            docplaintext = docplaintext + getElementText(element,document)
    return docplaintext


parser = argparse.ArgumentParser(description='Generates (stdout) Stand-off Annotation of HTML documents given in Bitextor crawl format (stdin)')
parser.add_argument('-t', '--text', dest='text', action='store_true')
parser.add_argument('-x', '--xml', dest='text', action='store_false')

args = parser.parse_args()

#Input (stdin) in Bitextor crawl format:
#mime      encoding      url     html_content(base_64)       timestamp

#Output (stdout):
#mime      encoding      url     html_content(base_64)       timestamp     html_text(base_64)

for line in sys.stdin:
    fields=line.split('\t')
    fields = list(map(str.strip, fields)) #Strip all elements
    if args.text:
        soup = BeautifulSoup(base64.b64decode(fields[3]).decode("utf8"), "lxml")
        for script in soup(["script", "style", "img"]):
            script.extract()    # rip it out

        # get text
        text = soup.get_text()
        text = re.sub(r"\n+","\n",re.sub(r" *\n *","\n",re.sub(r" +"," ",re.sub(r"\r","", text))))
        fields.append(base64.b64encode(text.encode()).decode("utf8"))
    else:
        document = html5lib.parse(ftfy.fix_text(Cleaner(style=True, links=True, add_nofollow=True,page_structure=False, safe_attrs_only=False).clean_html(base64.b64decode(fields[3]).decode("utf8"))),treebuilder="lxml",namespaceHTMLElements=False)
        tree=etree.tostring(document)
        cleantree=tree.decode("utf8").replace("\t"," ")
        fields.append(base64.b64encode(cleantree.encode()).decode("utf8"))
    print('\t'.join(fields))
