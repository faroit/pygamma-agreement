#!/usr/bin/env python
# encoding: utf-8

# The MIT License (MIT)

# Copyright (c) 2014-2019 CNRS

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

# AUTHORS
# Rachid RIAD
"""
##########
Alignement and disorder
##########

"""
from typing import List

import numpy as np
from scipy.special import binom

from matplotlib import pyplot as plt
from itertools import product
from functools import lru_cache
import cvxpy as cp

from pygamma.continuum import Continuum
from pygamma.dissimilarity import AbstractDissimilarity


class Error(Exception):
    """Base class for exceptions in this module."""
    pass


class SetPartitionError(Error):
    """Exception raised for errors in the partition of units of continuum.

    Attributes:
        message -- explanation of the error
    """

    def __init__(self, message):
        self.message = message


class AbstractAlignment:

    def __init__(
            self,
            continuum: Continuum,
            combined_dissimilarity: AbstractDissimilarity,
    ):

        self.continuum = continuum
        self.combined_dissimilarity = combined_dissimilarity

    @property
    def disorder(self) -> float:
        raise NotImplemented()


class UnitaryAlignement:
    """Unitary Alignement
    Parameters
    ----------
    continuum :
        Continuum where the unitary alignement is from
    n_tuple :
        n-tuple where n is the number of categories of the continuum
        The tuple is composed of (annotator, segment) couples
    combined_dissimilarity :
        combined_dissimilarity
    """

    def __init__(
            self,
            continuum: Continuum,
            n_tuple,
            combined_dissimilarity,
    ):

        self.continuum = continuum
        self.n_tuple = n_tuple
        assert len(n_tuple) == len(self.continuum)
        self.combined_dissimilarity = combined_dissimilarity

    @property
    @lru_cache(maxsize=None)
    def disorder(self):
        """Compute the disorder for the unitary alignement
        >>> unitary_alignement.compute_disorder() = ...
        Based on formula (6) of the original paper
        Note:
        unit is the equivalent of segment in pyannote
        """
        disorder = 0.0
        num_couples = 0
        for idx, (annotator_u, unit_u) in enumerate(self.n_tuple):
            for (annotator_v, unit_v) in self.n_tuple[idx + 1:]:
                # This is not as the paper formula (6)...
                # for (annotator_v, unit_v) in self.n_tuple:
                if unit_u is None or unit_v is None:
                    disorder += self.combined_dissimilarity.DELTA_EMPTY
                else:
                    disorder += self.combined_dissimilarity[(
                        unit_u, unit_v), (self.continuum[annotator_u][unit_u],
                                          self.continuum[annotator_v][unit_v])]
                num_couples += 1
        disorder = disorder / binom(len(self.n_tuple), 2)
        # disorder = disorder / num_couples
        assert num_couples == binom(len(self.n_tuple), 2)
        return disorder


class Alignement:
    """Alignement
    Parameters
    ----------
    continuum :
        Continuum where the unitary alignement is from
    set_unitary_alignments :
        set of unitary alignements that make a partition of the set of
        units/segments
    combined_dissimilarity :
        combined_dissimilarity
    """

    def __init__(
            self,
            continuum: Continuum,
            set_unitary_alignments: List[UnitaryAlignement],
            combined_dissimilarity,
    ):

        self.continuum = continuum
        self.set_unitary_alignments = set_unitary_alignments
        self.combined_dissimilarity = combined_dissimilarity

        # set partition tests for the unitary alignements
        for annotator in self.continuum.iterannotators():
            for unit in self.continuum[annotator].itersegments():
                found = 0
                for unitary_alignement in self.set_unitary_alignments:
                    if [annotator, unit] in unitary_alignement.n_tuple:
                        found += 1
                if found == 0:
                    raise SetPartitionError(
                        '{} {} not in the set of unitary alignements'.format(
                            annotator, unit))
                elif found > 1:
                    raise SetPartitionError('{} {} assigned twice'.format(
                        annotator, unit))

    @property
    def num_alignements(self):
        return len(self.set_unitary_alignments)

    @property
    @lru_cache(maxsize=None)
    def disorder(self):
        """Compute the disorder for the unitary alignement
        >>> unitary_alignement.compute_disorder() = ...
        Based on formula (6) of the original paper
        Note:
        unit is the equivalent of segment in pyannote
        """
        disorder = 0.0
        for unitary_alignement in self.set_unitary_alignments:
            disorder += unitary_alignement.disorder
        return disorder / self.num_alignements


class BestAlignement:
    """Alignement
    Parameters
    ----------
    continuum :
        Continuum where the unitary alignment is from
    combined_dissimilarity :
        combined_dissimilarity
    """

    def __init__(
            self,
            continuum: Continuum,
            combined_dissimilarity,
    ):

        self.continuum = continuum
        self.combined_dissimilarity = combined_dissimilarity

        self.set_unitary_alignements = self.get_unitary_alignements_best()

        # set partition tests for the unitary alignements
        for annotator in self.continuum.iterannotators():
            for unit in self.continuum[annotator].itersegments():
                found = 0
                for unitary_alignement in self.set_unitary_alignements:
                    if [annotator, unit] in unitary_alignement.n_tuple:
                        found += 1
                if found == 0:
                    raise SetPartitionError(
                        '{} {} not in the set of unitary alignements'.format(
                            annotator, unit))
                elif found > 1:
                    raise SetPartitionError('{} {} assigned twice'.format(
                        annotator, unit))

    @property
    def num_alignements(self):
        return len(self.set_unitary_alignements)

    def get_unitary_alignements_best(self):
        set_of_possible_segments = []
        for annotator in self.continuum.iterannotators():
            set_of_possible_segments.append(
                [[annotator, el]
                 for el in list(self.continuum[annotator].itersegments()) +
                 [None]])

        set_of_possible_tuples = list(product(*set_of_possible_segments))
        # Property section 5.1.1 to reduce initial complexity
        set_of_possible_unitary_alignements = []
        for n_tuple in set_of_possible_tuples:
            unitary_alignement = UnitaryAlignement(
                self.continuum, n_tuple, self.combined_dissimilarity)

            # Property section 5.1.1 to reduce initial complexity
            disorder = unitary_alignement.disorder
            if disorder < len(self.continuum) * (
                    self.combined_dissimilarity.DELTA_EMPTY):
                set_of_possible_unitary_alignements.append(unitary_alignement)

        # Definition of the integer linear program
        num_possible_unitary_alignements = len(
            set_of_possible_unitary_alignements)
        x = cp.Variable(shape=num_possible_unitary_alignements, boolean=True)
        d = np.array([
            unitary_alignement.disorder
            for unitary_alignement in set_of_possible_unitary_alignements
        ])

        # Constraints matrix
        A = np.zeros((self.continuum.num_units,
                      num_possible_unitary_alignements))

        curr_idx = 0
        # fill unitary alignements matching with units
        for annotator in self.continuum.iterannotators():
            for unit in list(self.continuum[annotator].itersegments()):
                for idx_ua, unitary_alignement in enumerate(
                        set_of_possible_unitary_alignements):
                    if [annotator, unit] in unitary_alignement.n_tuple:
                        A[curr_idx][idx_ua] = 1
                curr_idx += 1
        obj = cp.Minimize(d.T * x)
        constraints = [cp.matmul(A, x) == 1]
        prob = cp.Problem(obj, constraints)

        optimal_disorder = prob.solve()
        set_unitary_alignements = []

        # compare with 0.9 as cvxpy returns 1.000 or small values 10e-14
        for idx, choosen_unitary_alignement in enumerate(list(x.value > 0.9)):
            if choosen_unitary_alignement:
                set_unitary_alignements.append(
                    set_of_possible_unitary_alignements[idx])
        return set_unitary_alignements

    @property
    @lru_cache(maxsize=None)
    def disorder(self):
        """Compute the disorder for the unitary alignement
        >>> unitary_alignement.compute_disorder() = ...
        Based on formula (6) of the original paper
        Note:
        unit is the equivalent of segment in pyannote
        """
        disorder = 0.0
        for unitary_alignement in self.set_unitary_alignements:
            disorder += unitary_alignement.disorder
        return disorder / self.num_alignements
