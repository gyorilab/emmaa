import logging
import jsonpickle
from collections import defaultdict
from emmaa.model import load_config_from_s3, get_model_stats, \
    load_stmts_from_s3
from emmaa.model_tests import load_model_manager_from_s3
from emmaa.util import find_latest_s3_file, find_nth_latest_s3_file, \
    strip_out_date, EMMAA_BUCKET_NAME, load_json_from_s3, save_json_to_s3, \
    get_credentials, update_status
from indra.statements.statements import Statement
from indra.assemblers.english.assembler import EnglishAssembler
from indra.literature import pubmed_client, crossref_client, pmc_client
from indra_db import get_db
from indra_db.client.principal.curation import get_curations
from indra_db.util import unpack


logger = logging.getLogger(__name__)


CONTENT_TYPE_FUNCTION_MAPPING = {
    'statements': 'get_stmt_hashes',
    'applied_tests': 'get_applied_test_hashes',
    'passed_tests': 'get_passed_test_hashes',
    'paths': 'get_passed_test_hashes',
    'raw_papers': 'get_all_raw_paper_ids',
    'assembled_papers': 'get_all_assembled_paper_ids'}


TWITTER_MODEL_TYPES = {'pysb': '@PySysBio',
                       'pybel': '@pybelbio',
                       'signed_graph': 'Signed Graph',
                       'unsigned_graph': 'Unsigned Graph'}


class Round(object):
    """Parent class for classes analyzing one round of something (model or
    tests).

    Parameters
    ----------
    date_str : str
        Time when ModelManager responsible for this round was created.

    Attributes
    ----------

    function_mapping : dict
        A dictionary of strings mapping a type of content to a tuple of
        functions necessary to find delta for this type of content. First
        function in a tuple gets a list of all hashes for a given content type,
        while the second returns an English description of a given content type
        for a single hash.
    """
    def __init__(self, date_str):
        self.date_str = date_str
        self.function_mapping = CONTENT_TYPE_FUNCTION_MAPPING

    @classmethod
    def load_from_s3_key(cls, key):
        raise NotImplementedError("Method must be implemented in child class.")        

    def get_english_statement(self, stmt):
        ea = EnglishAssembler([stmt])
        sentence = ea.make_model()
        return ('', sentence, '')

    def find_delta_hashes(self, other_round, content_type, **kwargs):
        """Return a dictionary of changed hashes of a given content type. This
        method makes use of self.function_mapping dictionary.

        Parameters
        ----------
        other_round : emmaa.analyze_tests_results.TestRound
            A different instance of a TestRound
        content_type : str
            A type of the content to find delta. Accepted values:
            - statements
            - applied_tests
            - passed_tests
            - paths
        **kwargs : dict
            For some of content types, additional arguments must be
            provided sych as mc_type.
        Returns
        -------
        hashes : dict
            A dictionary containing lists of added and removed hashes of a
            given content type between two test rounds.
        """
        logger.info(f'Finding a hashes delta for {content_type}.')
        latest_hashes = getattr(
            self, self.function_mapping[content_type])(**kwargs)
        logger.info(f'Found {len(latest_hashes)} hashes in current round.')
        previous_hashes = getattr(
            other_round,
            other_round.function_mapping[content_type])(**kwargs)
        logger.info(f'Found {len(previous_hashes)} hashes in other round.')
        # Find hashes unique for each of the rounds - this is delta
        added_hashes = list(set(latest_hashes) - set(previous_hashes))
        removed_hashes = list(set(previous_hashes) - set(latest_hashes))
        hashes = {'added': added_hashes, 'removed': removed_hashes}
        return hashes


class ModelRound(Round):
    """Analyzes the results of one model update round.

    Parameters
    ----------
    statements : list[indra.statements.Statement]
        A list of INDRA Statements used to assemble a model.
    date_str : str
        Time when ModelManager responsible for this round was created.
    paper_ids : list(str)
        A list of paper IDs used to get raw statements for this round.
    paper_id_type : str
        Type of paper ID used.

    Attributes
    ----------
    stmts_by_papers : dict
        A dictionary mapping the paper IDs to sets of hashes of assembled
        statements with evidences retrieved from these papers.
    """
    def __init__(self, statements, date_str, paper_ids=None,
                 paper_id_type='TRID', emmaa_statements=None):
        super().__init__(date_str)
        self.statements = statements
        self.paper_ids = paper_ids if paper_ids else []
        self.paper_id_type = paper_id_type
        self.emmaa_statements = emmaa_statements if emmaa_statements else []
        self.stmts_by_papers = self.get_assembled_stmts_by_paper(paper_id_type)

    @classmethod
    def load_from_s3_key(cls, key, bucket=EMMAA_BUCKET_NAME,
                         load_estmts=False):
        mm = load_model_manager_from_s3(key=key, bucket=bucket)
        if not mm:
            return
        statements = mm.model.assembled_stmts
        date_str = mm.date_str
        try:
            paper_ids = list(mm.model.paper_ids)
        except AttributeError:
            paper_ids = None
        paper_id_type = mm.model.reading_config.get('main_id_type', 'TRID')
        estmts = None
        if load_estmts:
            estmts, _ = load_stmts_from_s3(mm.model.name, bucket)
        return cls(statements, date_str, paper_ids, paper_id_type, estmts)

    def get_total_statements(self):
        """Return a total number of statements in a model."""
        total = len(self.statements)
        logger.info(f'An assembled model has {total} statements.')
        return total

    def get_stmt_hashes(self):
        """Return a list of hashes for all statements in a model."""
        return [str(stmt.get_hash(refresh=True)) for stmt in self.statements]

    def get_statement_types(self):
        """Return a sorted list of tuples containing a statement type and a
        number of times a statement of this type occured in a model.
        """
        statement_types = defaultdict(int)
        logger.info('Finding a distribution of statements types.')
        for stmt in self.statements:
            statement_types[type(stmt).__name__] += 1
        return sorted(statement_types.items(), key=lambda x: x[1], reverse=True)

    def get_agent_distribution(self):
        """Return a sorted list of tuples containing an agent name and a number
        of times this agent occured in statements of a model."""
        logger.info('Finding agent distribution among model statements.')
        agent_count = defaultdict(int)
        for stmt in self.statements:
            for agent in stmt.agent_list():
                if agent is not None:
                    agent_count[agent.name] += 1
        return sorted(agent_count.items(), key=lambda x: x[1], reverse=True)

    def get_statements_by_evidence(self):
        """Return a sorted list of tuples containing a statement hash and a
        number of times this statement occured in a model."""
        stmts_evidence = {}
        for stmt in self.statements:
            stmts_evidence[str(stmt.get_hash(refresh=True))] = len(stmt.evidence)
        logger.info('Sorting statements by evidence count.')
        return sorted(stmts_evidence.items(), key=lambda x: x[1], reverse=True)

    def get_english_statements_by_hash(self):
        """Return a dictionary mapping a statement and its English description."""
        stmts_by_hash = {}
        for stmt in self.statements:
            stmts_by_hash[str(stmt.get_hash(refresh=True))] = (
                self.get_english_statement(stmt))
        return stmts_by_hash

    def get_sources_distribution(self):
        logger.info('Finding distribution of sources of statement evidences.')
        sources_count = defaultdict(int)
        for stmt in self.statements:
            for evid in stmt.evidence:
                if evid.source_api:
                    sources_count[evid.source_api] += 1
        return sorted(sources_count.items(), key=lambda x: x[1], reverse=True)

    def get_all_raw_paper_ids(self):
        """Return all paper IDs used in this round."""
        return self.paper_ids

    def get_number_raw_papers(self):
        """Return a total number of papers in this round."""
        return len(self.paper_ids)

    def get_assembled_stmts_by_paper(self, id_type='TRID'):
        """Get a mapping of paper IDs (TRID or PII) to assembled statements."""
        logger.info('Mapping papers to statements')
        stmts_by_papers = {}
        for stmt in self.statements:
            stmt_hash = stmt.get_hash()
            for evid in stmt.evidence:
                paper_id = None
                if id_type == 'pii':
                    paper_id = evid.annotations.get('pii')
                if evid.text_refs:
                    paper_id = evid.text_refs.get(id_type)
                    if not paper_id:
                        paper_id = evid.text_refs.get(id_type.lower())
                if paper_id:
                    if paper_id in stmts_by_papers:
                        stmts_by_papers[paper_id].add(stmt_hash)
                    else:
                        stmts_by_papers[paper_id] = {stmt_hash}
        for k, v in stmts_by_papers.items():
            stmts_by_papers[k] = list(v)
        return stmts_by_papers

    def get_all_assembled_paper_ids(self):
        return list(self.stmts_by_papers.keys())

    def get_number_assembled_papers(self):
        return len(self.stmts_by_papers)

    def get_papers_distribution(self):
        """Return a sorted list of tuples containing a paper ID and a number
        of unique statements extracted from that paper."""
        logger.info('Finding paper distribution')
        paper_stmt_count = {paper_id: len(stmts) for (paper_id, stmts) in
                            self.stmts_by_papers.items()}
        return sorted(paper_stmt_count.items(), key=lambda x: x[1],
                      reverse=True)

    def get_raw_paper_counts(self):
        logger.info('Finding raw statement count per paper')
        if not self.emmaa_statements:
            logger.info('Did not load raw EMMAA statements')
            return {}
        raw_by_papers = defaultdict(int)
        for estmt in self.emmaa_statements:
            for evid in estmt.stmt.evidence:
                paper_id = None
                id_type = self.paper_id_type
                if id_type == 'pii':
                    paper_id = evid.annotations.get('pii')
                if evid.text_refs:
                    paper_id = evid.text_refs.get(id_type)
                    if not paper_id:
                        paper_id = evid.text_refs.get(id_type.lower())
                if paper_id:
                    raw_by_papers[paper_id] += 1
        return raw_by_papers

    def get_paper_titles_and_links(self, trids):
        """Return a dictionary mapping paper IDs to their titles."""
        if self.paper_id_type == 'pii':
            return {}, {}
        db = get_db('primary')
        trs = db.select_all(db.TextRef, db.TextRef.id.in_(trids))
        ref_dicts = [tr.get_ref_dict() for tr in trs]
        trid_to_title = {}
        trid_to_link = {}
        trid_to_pmids = {}
        trid_to_pmcids = {}
        trid_to_dois = {}
        check_in_db = []
        # Map TRIDs to available PMIDs, DOIs, PMCIDs in this order
        for ref_dict in ref_dicts:
            link = _get_publication_link(ref_dict)
            trid_to_link[str(ref_dict['TRID'])] = link
            if ref_dict.get('PMID'):
                trid_to_pmids[ref_dict['TRID']] = ref_dict['PMID']
            elif ref_dict.get('PMCID'):
                trid_to_pmcids[ref_dict['TRID']] = ref_dict['PMCID']
            elif ref_dict.get('DOI'):
                trid_to_dois[ref_dict['TRID']] = ref_dict['DOI']

        logger.info(f'From {len(trids)} TRIDs got {len(trid_to_pmids)} PMIDs,'
                    f' {len(trid_to_pmcids)} PMCIDs, {len(trid_to_dois)} DOIs')

        # First get titles for available PMIDs
        if trid_to_pmids:
            logger.info(f'Getting titles for {len(trid_to_pmids)} PMIDs')
            pmids = list(trid_to_pmids.values())
            pmids_to_titles = _get_pmid_titles(pmids)

            for trid, pmid in trid_to_pmids.items():
                if pmid in pmids_to_titles:
                    trid_to_title[str(trid)] = pmids_to_titles[pmid]
                else:
                    check_in_db.append(trid)

        # Then get titles for available PMCIDs
        if trid_to_pmcids:
            logger.info(f'Getting titles for {len(trid_to_pmcids)} PMCIDs')
            for trid, pmcid in trid_to_pmcids.items():
                title = _get_pmcid_title(pmcid)
                if title:
                    trid_to_title[str(trid)] = title
                else:
                    check_in_db.append(trid)

        # Then get titles for available DOIs
        if trid_to_dois:
            logger.info(f'Getting titles for {len(trid_to_dois)} DOIs')
            for trid, doi in trid_to_dois.items():
                title = _get_doi_title(doi)
                if title:
                    trid_to_title[str(trid)] = title
                else:
                    check_in_db.append(trid)

        # Try getting remaining titles from db
        if check_in_db:
            logger.info(f'Getting titles for {len(check_in_db)} remaining '
                        'TRIDs from DB')
            tcs = db.select_all(db.TextContent,
                                db.TextContent.text_ref_id.in_(check_in_db),
                                db.TextContent.text_type == 'title')
            for tc in tcs:
                title = unpack(tc.content)
                trid_to_title[str(tc.text_ref_id)] = title

        return trid_to_title, trid_to_link

    def get_curation_stats(self):
        if not self.emmaa_statements:
            logger.info('Did not load raw EMMAA statements')
            return
        curations = get_curations()
        curators_ev = defaultdict(set)
        curators_stmt = defaultdict(set)
        curators_ev_counts = {}
        curators_stmt_counts = {}
        curs_by_tags = defaultdict(int)
        curs_by_hash = defaultdict(list)
        cur_ev_dates = defaultdict(set)
        cur_stmt_dates = defaultdict(set)
        cur_ev_date_sum = []
        cur_stmt_date_sum = []
        for cur in curations:
            curs_by_hash[cur['source_hash']].append(cur)
        df = '%Y-%m-%d-00-00-00'
        for estmt in self.emmaa_statements:
            for ev in estmt.stmt.evidence:
                source_hash = ev.get_source_hash()
                curs_for_hash = curs_by_hash.get(source_hash)
                if curs_for_hash:
                    for cur in curs_for_hash:
                        curators_ev[cur['curator']].add(cur['source_hash'])
                        curators_stmt[cur['curator']].add(cur['pa_hash'])
                        curs_by_tags[cur['tag']] += 1
                        cur_ev_dates[cur['date'].strftime(df)].add(
                            cur['source_hash'])
                        cur_stmt_dates[cur['date'].strftime(df)].add(
                            cur['pa_hash'])
        for cur, entries in curators_ev.items():
            curators_ev_counts[cur] = len(entries)
        for cur, entries in curators_stmt.items():
            curators_stmt_counts[cur] = len(entries)
        current_ev_sum = 0
        current_stmt_sum = 0
        for date, entries in sorted(cur_ev_dates.items()):
            current_ev_sum += len(entries)
            cur_ev_date_sum.append((date, current_ev_sum))
        for date, entries in sorted(cur_stmt_dates.items()):
            current_stmt_sum += len(entries)
            cur_stmt_date_sum.append((date, current_stmt_sum))

        cur_stats = {
            'curators_ev_counts': sorted(
                curators_ev_counts.items(), key=lambda x: x[1], reverse=True),
            'curators_stmt_counts': sorted(
                curators_stmt_counts.items(), key=lambda x: x[1], reverse=True),
            'curs_by_tags': sorted(
                curs_by_tags.items(), key=lambda x: x[1], reverse=True),
            'cur_ev_dates': cur_ev_date_sum,
            'cur_stmt_dates': cur_stmt_date_sum
        }
        return cur_stats


class TestRound(Round):
    """Analyzes the results of one test round.

    Parameters
    ----------
    json_results : list[dict]
        A list of JSON formatted dictionaries to store information about the
        test results. The first dictionary contains information about the
        model. Each consecutive dictionary contains information about a single
        test applied to the model and test results.
    date_str : str
        Time when ModelManager responsible for this round was created.

    Attributes
    ----------
    mc_types_results : dict
        A dictionary mapping a type of a ModelChecker to a list of test
        results generated by this ModelChecker
    tests : list[indra.statements.Statement]
        A list of INDRA Statements used to make EMMAA tests.
    english_test_results : dict
        A dictionary mapping a test hash and a list containing its English
        description, result in Pass/Fail/n_a form and either a path if it
        was found or a result code if it was not.
    """
    def __init__(self, json_results, date_str):
        super().__init__(date_str)
        self.json_results = json_results
        mc_types = self.json_results[0].get('mc_types', ['pysb'])
        self.mc_types_results = {}
        for mc_type in mc_types:
            self.mc_types_results[mc_type] = self._get_results(mc_type)
        self.tests = self._get_tests()
        self.english_test_results = self._get_applied_tests_results()

    @classmethod
    def load_from_s3_key(cls, key, bucket=EMMAA_BUCKET_NAME):
        logger.info(f'Loading json from {key}')
        json_results = load_json_from_s3(bucket, key)
        date_str = json_results[0].get('date_str', strip_out_date(key))
        return cls(json_results, date_str)

    def get_applied_test_hashes(self):
        """Return a list of hashes for all applied tests."""
        return list(self.english_test_results.keys())

    def get_passed_test_hashes(self, mc_type='pysb'):
        """Return a list of hashes for passed tests."""
        return [test_hash for test_hash in self.english_test_results.keys() if
                self.english_test_results[test_hash][mc_type][0] == 'Pass']

    def get_total_applied_tests(self):
        """Return a number of all applied tests."""
        total = len(self.tests)
        logger.info(f'{total} tests were applied.')
        return total

    def get_number_passed_tests(self, mc_type='pysb'):
        """Return a number of all passed tests."""
        total = len(self.get_passed_test_hashes(mc_type))
        logger.info(f'{total} tests passed.')
        return total

    def passed_over_total(self, mc_type='pysb'):
        """Return a ratio of passed over total tests."""
        return self.get_number_passed_tests(mc_type)/self.get_total_applied_tests()

    def _get_applied_tests_results(self):
        """Return a dictionary mapping a test hash and a list containing its
        English description, result in Pass/Fail form and either a path if it
        was found or a result code if it was not."""
        tests_by_hash = {}
        logger.info('Retrieving test hashes, english tests and test results.')

        def get_pass_fail(res):
            # Here use result.path_found because we care if the path was found
            # and do not care about path length
            if res.path_found:
                return 'Pass'
            elif res.result_code == 'STATEMENT_TYPE_NOT_HANDLED':
                return 'n_a'
            else:
                return 'Fail'

        def get_path_or_code(ix, res, mc_type):
            path_or_code = None
            # Here use result.paths because we care about actual path (i.e.
            # we can't get a path exceeding max path length)
            if res.paths:
                try:
                    path_or_code = (
                        self.json_results[ix+1][mc_type]['path_json'])
                # if json doesn't contain some of the fields
                except KeyError:
                    pass
            # If path wasn't found or presented in json
            if not path_or_code:
                try:
                    path_or_code = (
                        self.json_results[ix+1][mc_type]['result_code'])
                except KeyError:
                    pass
            # Couldn't get either path or code description from json
            if not path_or_code:
                path_or_code = res.result_code
            return path_or_code

        for ix, test in enumerate(self.tests):
            test_hash = str(test.get_hash(refresh=True))
            tests_by_hash[test_hash] = {
                'test': self.get_english_statement(test)}
            for mc_type in self.mc_types_results:
                result = self.mc_types_results[mc_type][ix]
                tests_by_hash[test_hash][mc_type] = [
                        get_pass_fail(result),
                        get_path_or_code(ix, result, mc_type)]
        return tests_by_hash

    def get_path_stmt_counts(self):
        path_stmt_counts = self.json_results[0].get('path_stmt_counts')
        if path_stmt_counts:
            return sorted(
                path_stmt_counts.items(), key=lambda x: x[1], reverse=True)
        return []

    def _get_results(self, mc_type):
        unpickler = jsonpickle.unpickler.Unpickler()
        test_results = [unpickler.restore(result[mc_type]['result_json'])
                        for result in self.json_results[1:]]
        return test_results

    def _get_tests(self):
        tests = [Statement._from_json(res['test_json'])
                 for res in self.json_results[1:]]
        return tests


class StatsGenerator(object):
    """Parent class for classes generating statistic for a given round of
    tests or model update.

    Parameters
    ----------
    model_name : str
        A name of a model the tests were run against.
    latest_round : ModelRound or TestRound or None
        An instance of a ModelRound or TestRound to generate statistics for.
        If not given, will be generated by loading json from s3.
    previous_round : ModelRound or TestRound or None
        A different instance of a ModelRound or TestRound to find delta
        between two rounds. If not given, will be generated by loading json
        from s3.
    previous_json_stats : dict
        A JSON-formatted dictionary containing model or test statistics for
        the previous round.
    Attributes
    ----------
    json_stats : dict
        A JSON-formatted dictionary containing model or test statistics.
    """

    def __init__(self, model_name, latest_round=None, previous_round=None,
                 previous_json_stats=None, bucket=EMMAA_BUCKET_NAME):
        self.model_name = model_name
        self.bucket = bucket
        self.previous_date_str = None
        if not latest_round:
            self.latest_round = self._get_latest_round()
        else:
            self.latest_round = latest_round
        if not previous_json_stats:
            self.previous_json_stats = self._get_previous_json_stats()
        else:
            self.previous_json_stats = previous_json_stats
        if not previous_round:
            self.previous_round = self._get_previous_round()
        else:
            self.previous_round = previous_round
        self.json_stats = {}

    def make_changes_over_time(self):
        """Add changes to model and tests over time to json_stats."""
        raise NotImplementedError("Method must be implemented in child class.")

    def get_over_time(self, section, metrics, **kwargs):
        raise NotImplementedError("Method must be implemented in child class.")

    def get_dates(self):
        if not self.previous_json_stats:
            previous_dates = []
        else:
            previous_dates = (
                self.previous_json_stats['changes_over_time']['dates'])
        previous_dates.append(self.latest_round.date_str)
        return previous_dates

    def save_to_s3_key(self, stats_key):
        if self.json_stats:
            logger.info(f'Uploading statistics to {stats_key}')
            save_json_to_s3(self.json_stats, self.bucket, stats_key)

    def save_to_s3(self):
        raise NotImplementedError("Method must be implemented in child class.")

    def _get_latest_round(self):
        raise NotImplementedError("Method must be implemented in child class.")

    def _get_previous_round(self):
        raise NotImplementedError("Method must be implemented in child class.")

    def _get_previous_json_stats(self):
        raise NotImplementedError("Method must be implemented in child class.")


class ModelStatsGenerator(StatsGenerator):
    """Generates statistic for a given model update round.

    Parameters
    ----------
    model_name : str
        A name of a model the tests were run against.
    latest_round : emmaa.analyze_tests_results.ModelRound
        An instance of a ModelRound to generate statistics for. If not given,
        will be generated by loading model data from s3.
    previous_round : emmaa.analyze_tests_results.ModelRound
        A different instance of a ModelRound to find delta between two rounds.
        If not given, will be generated by loading model data from s3.
    previous_json_stats : list[dict]
        A JSON-formatted dictionary containing model statistics for previous
        update round.

    Attributes
    ----------
    json_stats : dict
        A JSON-formatted dictionary containing model statistics.
    """

    def __init__(self, model_name, latest_round=None, previous_round=None,
                 previous_json_stats=None, bucket=EMMAA_BUCKET_NAME):
        super().__init__(model_name, latest_round, previous_round,
                         previous_json_stats, bucket)

    def make_stats(self):
        """Check if two latest model rounds were found and add statistics to
        json_stats dictionary. If both latest round and previous round
        were passed or found on s3, a dictionary will have three key-value
        pairs: model_summary, model_delta, and changes_over_time.
        """
        if not self.latest_round:
            logger.info(f'Latest round for {self.model_name} is not found.')
            return
        if self.previous_json_stats and not self.previous_round:
            logger.info(f'Latest stats are found but latest round is not.')
            return
        logger.info(f'Generating stats for {self.model_name}.')
        self.make_model_summary()
        self.make_model_delta()
        self.make_paper_delta()
        self.make_paper_summary()
        self.make_curation_summary()
        self.make_changes_over_time()

    def make_model_summary(self):
        """Add latest model state summary to json_stats."""
        logger.info(f'Generating model summary for {self.model_name}.')
        self.json_stats['model_summary'] = {
            'model_name': self.model_name,
            'number_of_statements': self.latest_round.get_total_statements(),
            'stmts_type_distr': self.latest_round.get_statement_types(),
            'agent_distr': self.latest_round.get_agent_distribution(),
            'stmts_by_evidence': self.latest_round.get_statements_by_evidence(),
            'sources': self.latest_round.get_sources_distribution(),
            'all_stmts': self.latest_round.get_english_statements_by_hash()
        }

    def make_model_delta(self):
        """Add model delta between two latest model states to json_stats."""
        logger.info(f'Generating model delta for {self.model_name}.')
        if not self.previous_round:
            self.json_stats['model_delta'] = {
                'statements_hashes_delta': {'added': [], 'removed': []}}
        else:
            stmts_delta = self.latest_round.find_delta_hashes(
                self.previous_round, 'statements')
            self.json_stats['model_delta'] = {
                'statements_hashes_delta': stmts_delta}
            msg = _make_twitter_msg(self.model_name, 'stmts', stmts_delta,
                                    self.latest_round.date_str[:10])
            if msg:
                logger.info(msg)

    def make_paper_summary(self):
        """Add latest paper summary to json_stats."""
        logger.info(f'Generating model summary for {self.model_name}.')
        self.json_stats['paper_summary'] = {
            'raw_paper_ids': self.latest_round.get_all_raw_paper_ids(),
            'number_of_raw_papers': self.latest_round.get_number_raw_papers(),
            'assembled_paper_ids': (
                self.latest_round.get_all_assembled_paper_ids()),
            'number_of_assembled_papers': (
                self.latest_round.get_number_assembled_papers()),
            'stmts_by_paper': self.latest_round.stmts_by_papers,
            'paper_distr': self.latest_round.get_papers_distribution(),
            'raw_paper_counts': self.latest_round.get_raw_paper_counts()
        }
        freq_trids = [pair[0] for pair in
                      self.json_stats['paper_summary']['paper_distr'][:10]]
        new_trids = self.json_stats['paper_delta']['raw_paper_ids_delta'][
            'added']
        trids = list(set(freq_trids).union(set(new_trids)))
        titles, links = self.latest_round.get_paper_titles_and_links(trids)
        self.json_stats['paper_summary']['paper_titles'] = titles
        self.json_stats['paper_summary']['paper_links'] = links

    def make_paper_delta(self):
        """Add paper delta between two latest model states to json_stats."""
        logger.info(f'Generating paper delta for {self.model_name}.')
        if not self.previous_round or not self.previous_round.paper_ids:
            self.json_stats['paper_delta'] = {
                'raw_paper_ids_delta': {'added': [], 'removed': []},
                'assembled_paper_ids_delta': {'added': [], 'removed': []}}
        else:
            raw_paper_delta = self.latest_round.find_delta_hashes(
                self.previous_round, 'raw_papers')
            assembled_paper_delta = self.latest_round.find_delta_hashes(
                self.previous_round, 'assembled_papers')
            self.json_stats['paper_delta'] = {
                'raw_paper_ids_delta': raw_paper_delta,
                'assembled_paper_ids_delta': assembled_paper_delta}
            logger.info(f'Read {len(raw_paper_delta["added"])} new papers.')
            logger.info(f'Got assembled statements from '
                        f'{len(assembled_paper_delta["added"])} new papers.')

    def make_curation_summary(self):
        """Add latest curation summary to json_stats."""
        logger.info(f'Generating curation summary for { self.model_name}.')
        cur_stats = self.latest_round.get_curation_stats()
        self.json_stats['curation_summary'] = cur_stats

    def make_changes_over_time(self):
        """Add changes to model over time to json_stats."""
        logger.info(f'Comparing changes over time for {self.model_name}.')
        self.json_stats['changes_over_time'] = {
            'number_of_statements': self.get_over_time(
                'model_summary', 'number_of_statements'),
            'number_of_raw_papers': self.get_over_time(
                'paper_summary', 'number_of_raw_papers'),
            'number_of_assembled_papers': self.get_over_time(
                'paper_summary', 'number_of_assembled_papers'),
            'dates': self.get_dates()}

    def get_over_time(self, section, metrics, mc_type='pysb'):
        logger.info(f'Getting changes over time in {metrics} '
                    f'for {self.model_name}.')
        # First available stats
        if not self.previous_json_stats:
            previous_data = []
        else:
            previous_data = (
                self.previous_json_stats['changes_over_time'].get(metrics, []))
        previous_data.append(self.json_stats[section][metrics])
        return previous_data

    def save_to_s3(self):
        date_str = self.latest_round.date_str
        stats_key = (
            f'model_stats/{self.model_name}/model_stats_{date_str}.json')
        super().save_to_s3_key(stats_key)

    def _get_latest_round(self):
        latest_key = find_latest_s3_file(
            self.bucket, f'results/{self.model_name}/model_manager_',
            extension='.pkl')
        if latest_key is None:
            logger.info(f'Could not find a key to the latest model manager '
                        f'for {self.model_name} model.')
            return
        logger.info(f'Loading latest round from {latest_key}')
        mr = ModelRound.load_from_s3_key(latest_key, bucket=self.bucket,
                                         load_estmts=True)
        return mr

    def _get_previous_round(self):
        if not self.previous_json_stats:
            logger.info('Not loading previous round without previous stats')
            return
        previous_key = (f'results/{self.model_name}/model_manager_'
                        f'{self.previous_date_str}.pkl')
        if previous_key is None:
            logger.info(f'Could not find a key to the previous model manager '
                        f'for {self.model_name} model.')
            return
        logger.info(f'Loading previous round from {previous_key}')
        mr = ModelRound.load_from_s3_key(previous_key, bucket=self.bucket)
        return mr

    def _get_previous_json_stats(self):
        key = find_latest_s3_file(
            self.bucket, f'model_stats/{self.model_name}/model_stats_', '.json')
        # This is the first time statistics is generated for this model
        if key is None:
            logger.info(f'Could not find a key to the previous statistics ')
            return
        # If stats for this date exists, previous stats is the second latest
        if strip_out_date(key) == self.latest_round.date_str:
            logger.info(f'Statistics for latest round already exists')
            key = find_nth_latest_s3_file(
                1, self.bucket, f'model_stats/{self.model_name}/model_stats_',
                '.json')
        # Store the date string to find previous round with it
        self.previous_date_str = strip_out_date(key)
        logger.info(f'Loading earlier statistics from {key}')
        previous_json_stats = load_json_from_s3(self.bucket, key)
        return previous_json_stats


class TestStatsGenerator(StatsGenerator):
    """Generates statistic for a given test round.

    Parameters
    ----------
    model_name : str
        A name of a model the tests were run against.
    test_corpus_str : str
        A name of a test corpus the model was tested against.
    latest_round : emmaa.analyze_tests_results.TestRound
        An instance of a TestRound to generate statistics for. If not given,
        will be generated by loading test results from s3.
    previous_round : emmaa.analyze_tests_results.TestRound
        A different instance of a TestRound to find delta between two rounds.
        If not given, will be generated by loading test results from s3.
    previous_json_stats : list[dict]
        A JSON-formatted dictionary containing test statistics for previous
        test round.

    Attributes
    ----------
    json_stats : dict
        A JSON-formatted dictionary containing test statistics.
    """

    def __init__(self, model_name, test_corpus_str='large_corpus_tests',
                 latest_round=None, previous_round=None,
                 previous_json_stats=None, bucket=EMMAA_BUCKET_NAME):
        self.test_corpus = test_corpus_str
        super().__init__(model_name, latest_round, previous_round,
                         previous_json_stats, bucket)

    def make_stats(self):
        """Check if two latest test rounds were found and add statistics to
        json_stats dictionary. If both latest round and previous round
        were passed or found on s3, a dictionary will have three key-value
        pairs: test_round_summary, tests_delta, and changes_over_time.
        """
        if not self.latest_round:
            logger.info(f'Latest round for {self.model_name} is not found.')
            return
        if self.previous_json_stats and not self.previous_round:
            logger.info(f'Latest stats are found but latest round is not.')
            return
        logger.info(f'Generating stats for {self.model_name}.')
        self.make_test_summary()
        self.make_tests_delta()
        self.make_changes_over_time()

    def make_test_summary(self):
        """Add latest test round summary to json_stats."""
        logger.info(f'Generating test summary for {self.model_name}.')
        self.json_stats['test_round_summary'] = {
            'test_data': self.latest_round.json_results[0].get('test_data'),
            'number_applied_tests': self.latest_round.get_total_applied_tests(),
            'all_test_results': self.latest_round.english_test_results,
            'path_stmt_counts': self.latest_round.get_path_stmt_counts()}
        for mc_type in self.latest_round.mc_types_results:
            self.json_stats['test_round_summary'][mc_type] = {
                'number_passed_tests': (
                    self.latest_round.get_number_passed_tests(mc_type)),
                'passed_ratio': self.latest_round.passed_over_total(mc_type)}

    def make_tests_delta(self):
        """Add tests delta between two latest test rounds to json_stats."""
        logger.info(f'Generating tests delta for {self.model_name}.')
        date = self.latest_round.date_str[:10]
        test_name = None
        test_data = self.latest_round.json_results[0].get('test_data')
        if test_data:
            test_name = test_data.get('name')
        if not self.previous_round:
            tests_delta = {
                'applied_hashes_delta': {'added': [], 'removed': []}}
        else:
            applied_delta = self.latest_round.find_delta_hashes(
                self.previous_round, 'applied_tests')
            tests_delta = {
                'applied_hashes_delta': applied_delta}
            msg = _make_twitter_msg(
                self.model_name, 'applied_tests', applied_delta, date,
                test_corpus=self.test_corpus, test_name=test_name)
            if msg:
                logger.info(msg)

        for mc_type in self.latest_round.mc_types_results:
            if not self.previous_round or mc_type not in \
                    self.previous_round.mc_types_results:
                tests_delta[mc_type] = {
                    'passed_hashes_delta': {'added': [], 'removed': []}}
            else:
                passed_delta = self.latest_round.find_delta_hashes(
                    self.previous_round, 'passed_tests', mc_type=mc_type)
                tests_delta[mc_type] = {
                    'passed_hashes_delta': passed_delta}
                msg = _make_twitter_msg(
                    self.model_name, 'passed_tests', passed_delta, date,
                    mc_type, test_corpus=self.test_corpus, test_name=test_name)
                if msg:
                    logger.info(msg)
        self.json_stats['tests_delta'] = tests_delta

    def make_changes_over_time(self):
        """Add changes to tests over time to json_stats."""
        logger.info(f'Comparing changes over time for {self.model_name}.')
        self.json_stats['changes_over_time'] = {
            'number_applied_tests': self.get_over_time(
                'test_round_summary', 'number_applied_tests'),
            'dates': self.get_dates()}
        for mc_type in self.latest_round.mc_types_results:
            self.json_stats['changes_over_time'][mc_type] = {
                'number_passed_tests': self.get_over_time(
                    'test_round_summary', 'number_passed_tests', mc_type),
                'passed_ratio': self.get_over_time(
                    'test_round_summary', 'passed_ratio', mc_type)}

    def get_over_time(self, section, metrics, mc_type='pysb'):
        logger.info(f'Getting changes over time in {metrics} '
                    f'for {self.model_name}.')
        # Not mc_type relevant data
        if metrics == 'number_applied_tests':
            # First available stats
            if not self.previous_json_stats:
                previous_data = []
            else:
                previous_data = (
                    self.previous_json_stats['changes_over_time'][metrics])
            previous_data.append(self.json_stats[section][metrics])
        # Mc_type relevant data
        else:
            # First available stats
            if not self.previous_json_stats:
                previous_data = []
            else:
                # This mc_type wasn't available in previous stats
                if mc_type not in \
                        self.previous_json_stats['changes_over_time']:
                    previous_data = []
                else:
                    previous_data = (
                        self.previous_json_stats[
                            'changes_over_time'][mc_type][metrics])
            previous_data.append(self.json_stats[section][mc_type][metrics])
        return previous_data

    def save_to_s3(self):
        date_str = self.latest_round.date_str
        stats_key = (f'stats/{self.model_name}/test_stats_{self.test_corpus}_'
                     f'{date_str}.json')
        super().save_to_s3_key(stats_key)

    def _get_latest_round(self):
        latest_key = find_latest_s3_file(
            self.bucket,
            f'results/{self.model_name}/results_{self.test_corpus}',
            extension='.json')
        if latest_key is None:
            logger.info(f'Could not find a key to the latest test results '
                        f'for {self.model_name} model.')
            return
        logger.info(f'Loading latest round from {latest_key}')
        tr = TestRound.load_from_s3_key(latest_key, bucket=self.bucket)
        return tr

    def _get_previous_round(self):
        if not self.previous_json_stats:
            logger.info('Not loading previous round without previous stats')
            return
        previous_key = (f'results/{self.model_name}/results_{self.test_corpus}'
                        f'_{self.previous_date_str}.json')
        if previous_key is None:
            logger.info(f'Could not find a key to the previous test results '
                        f'for {self.model_name} model.')
            return
        logger.info(f'Loading previous round from {previous_key}')
        tr = TestRound.load_from_s3_key(previous_key, bucket=self.bucket)
        return tr

    def _get_previous_json_stats(self):
        key = find_latest_s3_file(
            self.bucket,
            f'stats/{self.model_name}/test_stats_{self.test_corpus}_', '.json')
        # This is the first time statistics is generated for this model
        if key is None:
            logger.info(f'Could not find a key to the previous statistics ')
            return
        # If stats for this date exists, previous stats is the second latest
        if strip_out_date(key) == self.latest_round.date_str:
            logger.info(f'Statistics for latest round already exists')
            key = find_nth_latest_s3_file(
                1, self.bucket,
                f'stats/{self.model_name}/test_stats_{self.test_corpus}_',
                '.json')
        # Store the date string to find previous round with it
        self.previous_date_str = strip_out_date(key)
        logger.info(f'Loading earlier statistics from {key}')
        previous_json_stats = load_json_from_s3(self.bucket, key)
        return previous_json_stats


def generate_stats_on_s3(
        model_name, mode, test_corpus_str='large_corpus_tests',
        upload_stats=True, bucket=EMMAA_BUCKET_NAME):
    """Generate statistics for latest round of model update or tests.

    Parameters
    ----------
    model_name : str
        A name of EmmaaModel.
    mode : str
        Type of stats to generate (model or tests)
    test_corpus_str : str
        A name of a test corpus.
    upload_stats : Optional[bool]
        Whether to upload latest statistics about model and a test.
        Default: True
    """
    if mode == 'model':
        sg = ModelStatsGenerator(model_name, bucket=bucket)
    elif mode == 'tests':
        sg = TestStatsGenerator(model_name, test_corpus_str, bucket=bucket)
    else:
        raise TypeError('Mode must be either model or tests')
    sg.make_stats()
    # Optionally upload stats to S3
    if upload_stats:
        sg.save_to_s3()
    return sg


def _make_twitter_msg(model_name, msg_type, delta, date, mc_type=None,
                      test_corpus=None, test_name=None, new_papers=None):
    if len(delta['added']) == 0:
        logger.info(f'No {msg_type} delta found')
        return
    if not test_name:
        test_name = test_corpus
    plural = 's' if len(delta['added']) > 1 else ''
    if msg_type == 'stmts':
        if not new_papers:
            logger.info(f'No new papers found')
            return
        else:
            paper_plural = 's' if new_papers > 1 else ''
            msg = (f'Today I read {new_papers} new publication{paper_plural} '
                   f'and learned {len(delta["added"])} new mechanism{plural}. '
                   f'See https://emmaa.indra.bio/dashboard/{model_name}'
                   f'?tab=model&date={date}#addedStmts for more '
                   'details.')
    elif msg_type == 'applied_tests':
        msg = (f'Today I applied {len(delta["added"])} new test{plural} in '
               f'the {test_name}. See '
               f'https://emmaa.indra.bio/dashboard/{model_name}?tab=tests'
               f'&test_corpus={test_corpus}&date={date}#newAppliedTests for '
               'more details.')
    elif msg_type == 'passed_tests' and mc_type:
        msg = (f'Today I explained {len(delta["added"])} new '
               f'observation{plural} in the {test_name} with my '
               f'{TWITTER_MODEL_TYPES[mc_type]} model. See '
               f'https://emmaa.indra.bio/dashboard/{model_name}?tab=tests'
               f'&test_corpus={test_corpus}&date={date}#newPassedTests for '
               'more details.')
    else:
        raise TypeError(f'Invalid message type: {msg_type}.')
    return msg


def tweet_deltas(model_name, test_corpora, date, bucket=EMMAA_BUCKET_NAME):
    model_stats, _ = get_model_stats(model_name, 'model', date=date)
    test_stats_by_corpus = {}
    for test_corpus in test_corpora:
        test_stats, _ = get_model_stats(model_name, 'test', tests=test_corpus,
                                        date=date)
        if not test_stats:
            logger.info(f'Could not find test stats for {test_corpus}')
        test_stats_by_corpus[test_corpus] = test_stats
    if not model_stats or not test_stats_by_corpus:
        logger.warning('Stats are not found, not tweeting')
        return
    config = load_config_from_s3(model_name, bucket)
    twitter_key = config.get('twitter')
    twitter_cred = get_credentials(twitter_key)
    if not twitter_cred:
        logger.warning('Twitter credentials are not found, not tweeting')
    # Model message
    stmts_delta = model_stats['model_delta']['statements_hashes_delta']
    paper_delta = model_stats['paper_delta']['raw_paper_ids_delta']
    new_papers = len(paper_delta['added'])
    stmts_msg = _make_twitter_msg(model_name, 'stmts', stmts_delta, date,
                                  new_papers=new_papers)
    if stmts_msg:
        logger.info(stmts_msg)
        if twitter_cred:
            update_status(stmts_msg, twitter_cred)

    # Tests messages
    for test_corpus, test_stats in test_stats_by_corpus.items():
        test_name = None
        test_data = test_stats['test_round_summary'].get('test_data')
        if test_data:
            test_name = test_data.get('name')
        for k, v in test_stats['tests_delta'].items():
            if k == 'applied_hashes_delta':
                applied_delta = v
                applied_msg = _make_twitter_msg(
                    model_name, 'applied_tests', applied_delta, date,
                    test_corpus=test_corpus, test_name=test_name)
                if applied_msg:
                    logger.info(applied_msg)
                    if twitter_cred:
                        update_status(applied_msg, twitter_cred)
            else:
                mc_type = k
                passed_delta = v['passed_hashes_delta']
                passed_msg = _make_twitter_msg(
                    model_name, 'passed_tests', passed_delta,
                    date, mc_type, test_corpus=test_corpus,
                    test_name=test_name)
                if passed_msg:
                    logger.info(passed_msg)
                    if twitter_cred:
                        update_status(passed_msg, twitter_cred)

    logger.info('Done tweeting')


def _get_pmid_titles(pmids):
    pmids_to_titles = {}
    n = 200
    n_batches = len(pmids) // n
    if len(pmids) % n:
        n_batches += 1
    for i in range(n_batches):
        start = n * i
        end = start + n
        batch = pmids[start: end]
        m = pubmed_client.get_metadata_for_ids(batch)
        for pmid, metadata in m.items():
            pmids_to_titles[pmid] = metadata['title']
    return pmids_to_titles


def _get_doi_title(doi):
    m = crossref_client.get_metadata(doi)
    if m:
        title = m.get('title')
        if title:
            return title[0]


def _get_pmcid_title(pmcid):
    title = pmc_client.get_title(pmcid)
    return title


def _get_publication_link(text_refs):
    if text_refs.get('PMCID'):
        name = 'PMC'
        link = f'https://www.ncbi.nlm.nih.gov/pmc/articles/{text_refs["PMCID"]}'
    elif text_refs.get('PMID'):
        name = 'PubMed'
        link = f'https://pubmed.ncbi.nlm.nih.gov/{text_refs["PMID"]}'
    elif text_refs.get('DOI'):
        name = 'DOI'
        link = f'https://dx.doi.org/{text_refs["DOI"]}'
    elif text_refs.get('URL'):
        name = 'other'
        link = text_refs['URL']
    return (link, name)
