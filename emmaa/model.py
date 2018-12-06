import yaml
import time
import boto3
import pickle
import logging
from indra.databases import ndex_client
import indra.tools.assemble_corpus as ac
from indra.literature import pubmed_client
from indra.assemblers.cx import CxAssembler
from emmaa.priors import SearchTerm
from emmaa.readers.aws_reader import read_pmid_search_terms


logger = logging.getLogger(__name__)


class EmmaaModel(object):
    """"Represents an EMMAA model.

    Parameters
    ----------
    name : str
        The name of the model.
    config : dict
        A configuration dict that is typically loaded from a YAML file.

    Attributes
    ----------
    ndex_network : str
        The identifier of the NDEx network corresponding to the model.
    """
    def __init__(self, name, config):
        self.name = name
        self.stmts = []
        self.search_terms = []
        self.ndex_network = None
        self._load_config(config)

    def add_statements(self, stmts):
        """"Add a set of EMMAA Statements to the model

        Parameters
        ----------
        stmts : list[emmaa.EmmaaStatement]
            A list of EMMAA Statements to add to the model
        """
        self.stmts += stmts

    def get_indra_stmts(self):
        """Return the INDRA Statements contained in the model.

        Returns
        -------
        list[indra.statements.Statement]
            The list of INDRA Statements that are extracted from the EMMAA
            Statements.
        """
        return [es.stmt for es in self.stmts]

    def _load_config(self, config):
        self.search_terms = [SearchTerm.from_json(s) for s in
                             config['search_terms']]
        self.ndex_network = config['ndex']['network']

    def search_literature(self, date_limit=None):
        """Search for the model's search terms in the literature.

        Parameters
        ----------
        date_limit : Optional[int]
            The number of days to search back from today.

        Returns
        -------
        pmid_to_terms : dict
            A dict representing all the PMIDs returned by the searches as keys,
            and the search terms for which the given PMID was produced as
            values.
        """
        term_to_pmids = {}
        for term in self.search_terms:
            pmids = pubmed_client.get_ids(term, reldate=date_limit)
            logger.info(f'{len(pmids)} PMIDs found for {term}')
            term_to_pmids[term] = pmids
            time.sleep(0.5)
        pmid_to_terms = {}
        for term, pmids in term_to_pmids.items():
            for pmid in pmids:
                try:
                    pmid_to_terms[pmid].append(term)
                except KeyError:
                    pmid_to_terms[pmid] = [term]
        return pmid_to_terms

    def get_new_readings(self):
        """Search new literature, read, and add to model statements"""
        pmid_to_terms = self.search_literature(date_limit=10)
        estmts = read_pmid_search_terms(pmid_to_terms)
        self.extend_unique(estmts)

    def extend_unique(self, estmts):
        """Extend model statements only if it is not already there."""
        source_hashes = {est.stmt.get_hash(shallow=False)
                         for est in self.stmts}
        for estmt in estmts:
            if estmt.stmt.get_hash(shallow=False) not in source_hashes:
                self.stmts.append(estmt)

    def run_assembly(self):
        """Run INDRA's assembly pipeline on the Statements.

        Returns
        -------
        stmts : list[indra.statements.Statement]
            The list of assembled INDRA Statements.
        """
        stmts = self.get_indra_stmts()
        stmts = ac.filter_no_hypothesis(stmts)
        stmts = ac.map_grounding(stmts)
        stmts = ac.map_sequence(stmts)
        stmts = ac.filter_human_only(stmts)
        stmts = ac.run_preassembly(stmts, return_toplevel=False)
        return stmts

    def upload_to_ndex(self):
        """Upload the assembled model as CX to NDEx"""
        assembled_stmts = self.run_assembly()
        cxa = CxAssembler(assembled_stmts, network_name=self.name)
        cxa.make_model()
        cx_str = cxa.print_cx()
        ndex_client.update_network(cx_str, self.ndex_network)

    def save_to_s3(self):
        fname = f'{self.name}_statements.pkl'
        client = boto3.client('s3')
        client.put_object(Body=pickle.dumps(self.stmts), Bucket='emmaa',
                          Key=fname)

    def load_from_s3(self):
        fname = f'{self.name}_statements.pkl'
        client = boto3.client('s3')
        obj = client.get_object(Bucket='emmaa', Key=fname)
        stmts = pickle.loads(obj['Body'].read())
        self.stmts = stmts


def load_model(name, config_file):
    with open(config_file, 'r') as fh:
        config = yaml.load(fh)
    em = EmmaaModel(name, config)
    #em.load_from_s3()
    return em