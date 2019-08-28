"""Example how to debug a transformer outside of Driverless AI (optional)"""
import datatable as dt
import numpy as np
import pandas as pd
from h2oaicore.transformer_utils import CustomTransformer

class SpellingCorrectionTransformer(CustomTransformer):
    _numeric_output = False
    _modules_needed_by_name = ['spellchecker']

    @property
    def display_name(self):
        return "Text"

    @staticmethod
    def get_default_properties():
        return dict(col_type="text", min_cols=1, max_cols=1, relative_importance=1)

    def fit_transform(self, X: dt.Frame, y: np.array = None):
        return self.transform(X)

    def correction(self, x):
        from spellchecker import SpellChecker
        spell = SpellChecker()
        x = x.lower()
        misspells = spell.unknown(x.split())
        corrected = [spell.correction(w) if w in misspells else w for w in x.split()]
        corrected = " ".join(corrected)
        return corrected

    def transform(self, X: dt.Frame):
        return X.to_pandas().astype(str).iloc[:, 0].apply(lambda x: self.correction(x))