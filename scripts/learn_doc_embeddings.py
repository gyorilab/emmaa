"""This script finds all text references that support a given
EMMAA model, obtains the text content for these references,
and calculates per-document embeddings for them using
SPECTER (https://github.com/allenai/specter)."""
import os
import sys
import tqdm
import pickle
import logging
from transformers import AutoTokenizer, AutoModel
from emmaa.model_tests import load_model_manager_from_s3
from indra.util import batch_iter
from indra.literature.adeft_tools import universal_extract_text
from indra_db.util.content_scripts import TextContentSessionHandler


logger = logging.getLogger('learn_embeddings')

#text_ref_priority = ['TRID', 'PMID', 'PMCID', 'DOI', 'URL']
text_ref_priority = ['TRID']


def get_prioritized_text_ref(text_refs):
    """Return a single text ref tuple that is prioritized."""
    for ref_ns in text_ref_priority:
        if ref_ns in text_refs:
            return (ref_ns, text_refs[ref_ns])
    return None, None


def get_text_for_ref(tc, ref_ns, ref_id):
    """Return the best available text content for a text ref tuple."""
    print('Getting text for %s:%s' % (ref_ns, ref_id))
    content = tc.get_text_content_from_text_refs({ref_ns: ref_id})
    if not content:
        return None
    text = universal_extract_text(content)
    if text:
        print('Text length: %d' % len(text))
    return text


def get_all_text_refs(statements):
    """Get all prioritized text refs for a set of statements."""
    print('Getting all text refs from %d statements' %
          len(statements))
    all_text_refs = set()
    for statement in tqdm.tqdm(statements):
        for ev in statement.evidence:
            ref_ns, ref_id = get_prioritized_text_ref(ev.text_refs)
            if ref_ns is not None:
                all_text_refs.add((ref_ns, ref_id))
    return sorted(all_text_refs)


def get_embeddings(tokenizer, model, texts):
    """Return the embeddings for a list of texts."""
    inputs = tokenizer(texts,
                       padding=True,
                       truncation=True,
                       return_tensors="pt",
                       max_length=512)
    result = model(**inputs)
    embeddings = result.last_hidden_state[:, 0, :]
    return embeddings


if __name__ == '__main__':
    model_name = sys.argv[1]
    tc = TextContentSessionHandler()
    tokenizer = AutoTokenizer.from_pretrained('allenai/specter')
    model = AutoModel.from_pretrained('allenai/specter')

    text_refs_cache = '%s_text_refs.pkl' % model_name
    if os.path.exists(text_refs_cache):
        with open(text_refs_cache, 'rb') as fh:
            text_refs = pickle.load(fh)
        print('Loaded %d refs from cache' % len(text_refs))
    else:
        print('Loading model manager for %s' % model_name)
        model_manager = load_model_manager_from_s3(model_name)
        text_refs = get_all_text_refs(model_manager.model.assembled_stmts)
        print('Got a total of %d text refs' % len(text_refs))
        with open(text_refs_cache, 'wb') as fh:
            pickle.dump(text_refs, fh)

    all_embeddings = {}
    for text_ref_batch in tqdm.tqdm(batch_iter(text_refs, batch_size=100,
                                               return_func=list),
                                    total=len(text_refs)):
        texts = []
        embeddings_idxs = {}
        for idx, text_ref in enumerate(text_ref_batch):
            text = get_text_for_ref(tc, *text_ref)
            if text:
                texts.append(text)
                embeddings_idxs[text_ref] = idx
        embeddings = get_embeddings(tokenizer, model, texts)
        for text_ref in text_ref_batch:
            if text_ref in embeddings_idxs:
                all_embeddings[text_ref] = \
                    embeddings[embeddings_idxs[text_ref]]
            else:
                all_embeddings[text_ref] = None
    with open('%s_document_embeddings.pkl' % model_name, 'wb') as fh:
        pickle.dump(all_embeddings, fh)