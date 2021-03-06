
#!/usr/bin/env python

import argparse
import sys
import os
import os.path
from collections import defaultdict

import numpy as np
from nltk.tokenize import wordpunct_tokenize

from scorer import CosineDistanceScorer, EnglishWordExtractor, _ngram_helper

sys.path.append("{0}/..".format(os.path.dirname(os.path.realpath(__file__))))
from utils.common import open_gzip_or_plain

def munge_file_path(filepath):
  if os.path.isfile(filepath):
    return filepath
  if os.path.isfile(filepath + ".gz"):
    return filepath + ".gz"
  if os.path.isfile(filepath + ".xz"):
    return filepath + ".xz"
  if os.path.isfile(filepath + ".bz2"):
        return filepath + ".bz2"
      
  # return nothing. file does not exist
  return None
  
def load_extracted(filepath):
    #print("BEFORE filepath", filepath)
    filepath = munge_file_path(filepath)
    #print("AFTER filepath", filepath)
    
    with open_gzip_or_plain(filepath) as f:
        documents = defaultdict(list)

        for line in f:
            line_split = line.strip().split('\t', 1)
            if len(line_split) != 2:
                continue

            url, text = line_split
            documents[url].append(text)

        return {d: "\n".join(documents[d]) for d in documents}


def map_dic2list(documents):
    mapping = []
    text = []

    for idx, d in enumerate(documents):
        mapping.append(d)
        text.append(documents[d])

    return {
        'text': text,
        'mapping': mapping
    }


def match(score_matrix_csr, threshold):
    score_matrix_coo = score_matrix_csr.tocoo()
    matches = []
    visited_cols = set()
    visited_rows = set()

    smaller_dim = min(score_matrix_coo.shape)
    sorted_indices = np.argsort(
        score_matrix_coo.data, axis=None, kind='quicksort')

    for idx in sorted_indices[::-1]:
        curr_row = score_matrix_coo.row[idx]
        if curr_row in visited_rows:
            continue

        curr_col = score_matrix_coo.col[idx]
        if curr_col in visited_cols:
            continue

        if score_matrix_csr[int(curr_row), int(curr_col)] < threshold:
            break

        matches.append((curr_row, curr_col))
        visited_cols.add(curr_col)
        visited_rows.add(curr_row)

        if len(matches) >= smaller_dim:
            break

    match_costs = [score_matrix_csr[int(r), int(c)] for r, c in matches]

    return match_costs, matches


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--english', help='path to the extracted English text', required=True)
    parser.add_argument(
        '--translated', help='path to the translated foreign text', required=True)
    parser.add_argument('--min_count', type=int, default=2)
    parser.add_argument('--ngram_size', type=int, default=2)
    parser.add_argument('--tfidfsmooth', type=int, default=20)
    parser.add_argument(
        '--ignore', help='n-grams from this corpus will be ignored in distance scorer')
    parser.add_argument('--output_matches', help='output file', required=True)
    parser.add_argument('--threshold', type=float, default=0.1)
    parser.add_argument('--batch_size', type=int, default=10000)

    args = parser.parse_args()

    sys.stderr.write("threshold: {0}\n".format(args.threshold))
    sys.stderr.write("batch_size: {0}\n".format(args.batch_size))

    docs_english = load_extracted(args.english)
    docs_translated = load_extracted(args.translated)

    if len(docs_translated) == 0 or len(docs_english) == 0:
        sys.stderr.write("No document alignments feasible: "+str(len(docs_translated))+" documents in foreign language and "+str(len(docs_english))+" documents in English.\n")
        open(args.output_matches, 'a').close()

    else:

        obj_english = map_dic2list(docs_english)
        obj_translated = map_dic2list(docs_translated)
    
        to_ignore = None
        if args.ignore:
            with open(args.ignore, 'r') as f:
                content = f.read().replace('\n', ' ').replace('  ', ' ')
                to_ignore = set(_ngram_helper(
                    wordpunct_tokenize(content), args.ngram_size, False))
    
        word_extractor = EnglishWordExtractor(
            n=args.ngram_size, ignore_set=to_ignore)
        scorer = CosineDistanceScorer(extraction_mapper=word_extractor,
                                      min_count=args.min_count,
                                      metric='cosine',
                                      smooth=args.tfidfsmooth,
                                      threshold=args.threshold,
                                      batch_size=args.batch_size)
        m_csr = scorer.score(obj_english['text'], obj_translated['text'])
        if m_csr == None:
            sys.stderr.write("Documents do not contain any useful information to be used in alignment.\n")
            open(args.output_matches, 'a').close()
        else:
            match_costs, matches = match(m_csr, threshold=args.threshold)
    
            with open(args.output_matches, 'w') as f:
                for idx, match in enumerate(matches):
                    surl = obj_english['mapping'][matches[idx][0]]
                    turl = obj_translated['mapping'][matches[idx][1]]
                    f.write("{0:.5f}\t{1}\t{2}\n".format(match_costs[idx], surl, turl))
