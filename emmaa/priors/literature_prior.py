"""This module implements the LiteraturePrior class which automates
some of the steps involved in starting a model around a set of
literature searches. Example:

.. code:: python

    lp = LiteraturePrior('some_disease', 'Some Disease',
                         'This is a self-updating model of Some Disease',
                         search_strings=['some disease'],
                         assembly_config_template='nf')
    estmts = lp.get_statements()
    model = lp.make_model(estmts, upload_to_s3=True)

"""

from typing import List

import tqdm
import logging
import datetime
from collections import defaultdict
from indra.util import batch_iter
from indra_db import get_db
from indra_db.util import distill_stmts
from indra_db.client.principal import get_raw_stmt_jsons_from_papers
from indra.databases import mesh_client
from indra.statements import stmts_from_json
from . import SearchTerm
from emmaa.model import EmmaaModel
from emmaa.statements import EmmaaStatement


logger = logging.getLogger(__name__)


class LiteraturePrior:
    def __init__(self, name, human_readable_name, description,
                 search_strings=None, mesh_ids=None,
                 assembly_config_template=None, test: bool = True):
        """A class to construct a literature-based prior for an EMMAA model.

        Parameters
        ----------
        name : str
            The model name by which the model will be identified on S3.
        human_readable_name : str
            The human-readable display name for the model.
        description : str
            A human-readable description for the model.
        search_strings : list of str
            A list of search strings e.g., "diabetes" to find papers in the
            literature.
        mesh_ids : list of str
            A list of MeSH IDs that are used to search the literature as
            headings associated with papers.
        assembly_config_template : Optional[str]
            The name of another model from which the initial assembly
            configuration should be adopted.
        test :
            Should tests be included in the configuration?
        """
        self.name = name
        self.human_readable_name = human_readable_name
        self.description = description
        self.search_terms = \
            make_search_terms(search_strings or [], mesh_ids or [])
        if assembly_config_template:
            self.assembly_config = \
                self.get_config_from(assembly_config_template)
        else:
            self.assembly_config = {}
        self.test = test
        self.stmts = []

    def get_statements(self, mode='all', batch_size=100):
        """Return EMMAA Statements for this prior's literature set.

        Parameters
        ----------
        mode : 'all' or 'distilled'
            The 'distilled' mode makes sure that the "best", non-redundant
            set of raw statements are found across potentially redundant text
            contents and reader versions. The 'all' mode doesn't do such
            distillation but is significantly faster.
        batch_size : Optional[int]
            Determines how many PMIDs to fetch statements for in each
            iteration. Default: 100.

        Returns
        -------
        list of EmmaaStatement
            A list of EMMAA Statements corresponding to extractions from
            the subset of literature defined by this prior's search terms.
        """
        if self.stmts:
            return self.stmts
        terms_to_pmids = \
            EmmaaModel.search_pubmed(search_terms=self.search_terms,
                                     date_limit=None)
        pmids_to_terms = defaultdict(list)
        for term, pmids in terms_to_pmids.items():
            for pmid in pmids:
                pmids_to_terms[pmid].append(term)
        pmids_to_terms = dict(pmids_to_terms)
        all_pmids = set(pmids_to_terms.keys())
        raw_statements_by_pmid = \
            get_raw_statements_for_pmids(all_pmids, mode=mode,
                                         batch_size=batch_size)
        timestamp = datetime.datetime.now()
        for pmid, stmts in raw_statements_by_pmid.items():
            for stmt in stmts:
                self.stmts.append(EmmaaStatement(stmt, timestamp,
                                                 pmids_to_terms[pmid],
                                                 {'internal': True}))
        return self.stmts

    def get_config_from(self, assembly_config_template):
        """Return assembly config given a template model's name.

        Parameters
        ----------
        assembly_config_template : str
            The name of a model whose assembly config should be adopted.

        Returns
        -------
        dict
            The assembly config of the given template model.
        """
        from emmaa.model import load_config_from_s3
        config = load_config_from_s3(assembly_config_template)
        return config.get('assembly')

    def make_config(self, upload_to_s3=False):
        """Return a config dict fot the model, optionally upload to S3.

        Parameters
        ----------
        upload_to_s3 : Optional[bool]
            If True, the config is uploaded to S3 in the EMMAA bucket.
            Default: False

        Returns
        -------
        dict
            A config data structure.
        """
        config = {
            # These are provided by the user upon initialization
            'name': self.name,
            'human_readable_name': self.human_readable_name,
            'description': self.description,
            # We don't make tests by default
            'make_tests': False,
            # We run daily updates by default
            'run_daily_update': True,
            # We first show the model just on dev
            'dev_only': True,
            # These are the search terms constructed upon
            # initialization
            'search_terms': [st.to_json() for st in self.search_terms],
        }
        # This is adopted from the template specified upon
        # initialization
        if self.assembly_config:
            config["assembly"] = self.assembly_config

        if self.test:
            # We configure the large corpus tests by default
            config["test"] = {
                'statement_checking': {
                    'max_path_length': 10,
                    'max_paths': 1,
                },
                'mc_types': [
                    'signed_graph', 'unsigned_graph',
                ],
                'make_links': True,
                'test_corpus': ['large_corpus_tests'],
                'default_test_corpus': 'large_corpus_tests',
                'filters': {
                    'large_corpus_tests': 'filter_chem_mesh_go',
                },
            }

        if upload_to_s3:
            from emmaa.model import save_config_to_s3
            save_config_to_s3(self.name, config)
        return config

    def make_model(self, estmts, upload_to_s3=False):
        """Return, and optionally upload to S3 an initial EMMAA Model.

        Parameters
        ----------
        estmts : list of emmaa.statement.EmmaaStatement
            A list of prior EMMAA Statements to initialize the model with.
        upload_to_s3 : Optional[bool]
            If True, the model and the config are uploaded to S3, otherwise
            the model object is just returned without upload. Default: False

        Returns
        -------
        emmaa.model.EmmaaModel
            The EMMAA Model object constructed from the generated config
            and the given EMMAA Statements.
        """
        from emmaa.model import EmmaaModel
        config = self.make_config(upload_to_s3=upload_to_s3)
        model = EmmaaModel(name=self.name, config=config)
        model.add_statements(estmts)
        if upload_to_s3:
            model.save_to_s3()
        return model


def get_raw_statements_for_pmids(pmids, mode='all', batch_size=100):
    """Return EmmaaStatements based on extractions from given PMIDs.

    Parameters
    ----------
    pmids : set or list of str
        A set of PMIDs to find raw INDRA Statements for in the INDRA DB.
    mode : 'all' or 'distilled'
        The 'distilled' mode makes sure that the "best", non-redundant
        set of raw statements are found across potentially redundant text
        contents and reader versions. The 'all' mode doesn't do such
        distillation but is significantly faster.
    batch_size : Optional[int]
        Determines how many PMIDs to fetch statements for in each
        iteration. Default: 100.

    Returns
    -------
    dict
        A dict keyed by PMID with values INDRA Statements obtained
        from the given PMID.
    """
    db = get_db('primary')
    logger.info(f'Getting raw statements for {len(pmids)} PMIDs')
    all_stmts = defaultdict(list)
    for pmid_batch in tqdm.tqdm(batch_iter(pmids, return_func=set,
                                           batch_size=batch_size),
                                total=len(pmids)/batch_size):
        if mode == 'distilled':
            clauses = [
                db.TextRef.pmid.in_(pmid_batch),
                db.TextContent.text_ref_id == db.TextRef.id,
                db.Reading.text_content_id == db.TextContent.id,
                db.RawStatements.reading_id == db.Reading.id]
            distilled_stmts = distill_stmts(db, get_full_stmts=True,
                                            clauses=clauses)
            for stmt in distilled_stmts:
                all_stmts[stmt.evidence[0].pmid].append(stmt)
        else:
            id_stmts = \
                get_raw_stmt_jsons_from_papers(pmid_batch, id_type='pmid',
                                               db=db)
            for pmid, stmt_jsons in id_stmts.items():
                all_stmts[pmid] += stmts_from_json(stmt_jsons)
    all_stmts = dict(all_stmts)
    return all_stmts


def make_search_terms(
    search_strings: List[str],
    mesh_ids: List[str],
) -> List[SearchTerm]:
    """Return EMMAA SearchTerms based on search strings and MeSH IDs.

    Parameters
    ----------
    search_strings :
        A list of search strings e.g., "diabetes" to find papers in the
        literature.
    mesh_ids :
        A list of MeSH IDs that are used to search the literature as headings
        associated with papers.

    Returns
    -------
    :
        A list of EMMAA SearchTerm objects constructed from the search strings
        and the MeSH IDs.
    """
    if not search_strings and not mesh_ids:
        raise ValueError("Need at least one of search_strings or mesh_ids")
    search_terms = []
    for search_string in search_strings:
        search_term = SearchTerm(type='other', name=search_string,
                                 db_refs={}, search_term=search_string)
        search_terms.append(search_term)
    for mesh_id in mesh_ids:
        mesh_name = mesh_client.get_mesh_name(mesh_id)
        # TODO explicitly handle mesh_id.startswith("C")?
        suffix = 'mh' if mesh_id.startswith('D') else 'nm'
        search_term = SearchTerm(type='mesh', name=mesh_name,
                                 db_refs={'MESH': mesh_id},
                                 search_term=f'{mesh_name} [{suffix}]')
        search_terms.append(search_term)
    return search_terms
