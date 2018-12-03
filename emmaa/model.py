class EmmaaStatement(object):
    def __init__(self, stmt, date, search_terms):
        self.stmt = stmt
        self.date = date
        self.search_terms = search_terms


class EmmaaModel(object):
    def __init__(self):
        self.stmts = []

    def add_statements(self, stmts):
        self.stmts += stmts