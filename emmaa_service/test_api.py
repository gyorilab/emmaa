import unittest

from .api import app


class EmmaaApiTest(unittest.TestCase):

    def setUp(self):
        app.testing = True
        self.app = app.test_client()

    def test_query_endpoint(self):
        """Test if we can submit a simple model query

        NOTE: only tests that the query was received by the API and that it
        was properly formatted.
        """

        test_query = {'user': {'email': 'joshua@emmaa.com',
                               'name': 'joshua',
                               'slack_id': '123456abcdef'},
                      'models': ['aml', 'luad'],
                      'query': {'objectSelection': 'ERK',
                                'subjectSelection': 'BRAF',
                                'typeSelection': 'activation'},
                      'register': 'false',
                      'test': 'true'}

        resp = self.app.post('/query/submit', json=test_query)

        assert resp.status_code == 200

    def test_query(self):
        """Test querying a model"""

        test_query = {'user': {'email': 'joshua@emmaa.com',
                                   'name': 'joshua',
                                   'slack_id': '123456abcdef'},
                          'models': ['rasmodel'],
                          'query': {'objectSelection': 'AKT1',
                                    'subjectSelection': 'PIK3CA',
                                    'typeSelection': 'activation'},
                          'register': 'false'}

        resp = self.app.post('/query/submit', json=test_query)

        assert resp.status_code == 200
