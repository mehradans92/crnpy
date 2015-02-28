#!/usr/bin/env python

"""Reaction class and functions."""

from collections import defaultdict
from functools import reduce
import sympy as sp
import copy

from .crncomplex import Complex, to_complex, sympify

__author__ = "Elisa Tonello"
__copyright__ = "Copyright (c) 2016, Elisa Tonello"
__license__ = "BSD"
__version__ = "0.0.1"


class Reaction(object):
    """A reaction is defined by a string reactionid,
    a reactant complex, a product complex,
    and a string or sympy expression representing the rate.

    Attributes: reactionid, reactant, product, rate, kinetic_param.
    """
    def __init__(self, reactionid, reactant, product, rate):
        self._reactionid = reactionid
        self._reactant = reactant
        self._product = product
        self._rate = rate

    def __copy__(self):
        return Reaction(self.reactionid, self.reactant, self.product, self.rate)
    def __deepcopy__(self, memo):
        return Reaction(copy.deepcopy(self.reactionid, self.reactant, self.product, self.rate, memo))

    @property
    def reactionid(self):
        """String id of the reaction."""
        return self._reactionid

    @property
    def reactant(self):
        """Reactant complex of the reaction."""
        return self._reactant

    @property
    def product(self):
        """Product complex of the reaction."""
        return self._product

    @property
    def rate(self):
        """Rate of the reaction."""
        return self._rate

    @property
    def _rate(self):
        return self.__rate
    @_rate.setter
    def _rate(self, value):
        self.__rate = sympify(value)
        if value is not None: self.__kinetic_param = self.rate / self.reactant.ma()

    @property
    def kinetic_param(self):
        """Rate of the reaction divided by the mass action monomial
        associated to the reactant."""
        return self._kinetic_param

    @property
    def _kinetic_param(self):
        return self.__kinetic_param
    @_kinetic_param.setter
    def _kinetic_param(self, value):
        self._rate = (sympify(value) * self.reactant.ma()).cancel()

    def __str__(self):
        return self.format()

    def  __repr__(self):
        return self.__str__()

    def __eq__(self, reaction):
        return self.reactant == reaction.reactant and \
               self.product == reaction.product and \
               (self.rate - reaction.rate).cancel() == 0

    def format(self, rate = False, precision = 3):
        """Return a string of the form
        reactant complex ->(k) product complex
        where k is the generalised kinetic parameter of the reaction if rate = False,
        otherwise the rate of the reaction."""
        return "{}: {} ->{} {}".format(self.reactionid,
                                       self.reactant,
                                       "(" + self.format_kinetics(rate, precision) + ")" if self.rate else "",
                                       self.product)

    def format_kinetics(self, rate = False, precision = 3):
        """Convert the kinetic parameter or rate to string.
        If rate = True, return a string representing the rate,
        otherwise one representing the kinetic parameter.
        If the kinetic parameter is a float, use exponent notation,
        with a number of digits equal to precision (3 is the default).
        If the reaction has no defined rate, return None."""
        k = None
        if self.rate:
            if isinstance(self.kinetic_param, sp.Float):
                k = "{:.{}e}".format(self.kinetic_param, precision)
                if rate:
                    k = k + "*" + str(self.reactant.ma())
            else:
                if rate:
                    k = str(self.rate)
                else:
                    k = str(self.kinetic_param)
        return k

    def latex(self, rate = False):
        """Return the latex code for the reaction."""
        return "{}: {} {} {}".format(sp.latex(sympify(self.reactionid)),
                                     sp.latex(self.reactant.symp()),
                                     str("\\xrightarrow{" + sp.latex(self.format_kinetics(rate)) + "}") if self.rate else str("\\rightarrow"),
                                     sp.latex(self.product.symp()))

    def remove_react_prod(self, species = None):
        """Remove common species between reactant and product.

        If a species is specified, only species is removed."""
        reactant = Complex(self.reactant)
        product = Complex(self.product)
        if species == None:
            common = reactant & product
            self._reactant = Complex(reactant - common)
            self._product = Complex(product - common)
        else:
            if species in reactant and species in product:
                if reactant[species] > product[species]:
                    self.reactant[species] = reactant[species] - product[species]
                    del self.product[species]
                if product[species] > reactant[species]:
                    self.product[species] = product[species] - reactant[species]
                    del self.reactant[species]
                if reactant[species] == product[species]:
                    del self.reactant[species]
                    del self.product[species]
        # Adjust kinetic parameter
        self.__kinetic_param = self.rate / self.reactant.ma()


    def _fix_ma(self, species = None):
        """Check the numerator of the reaction rate, and adds species
        to reactant and product if they divide the numerator but their
        stoichiometry does not match the degree in the rate."""
        num, denom = self.rate.as_numer_denom()
        remainder = (num / self.reactant.ma()).factor()

        if remainder.func.__name__ == 'Mul':
            mulargs = list(remainder.args) + [i.args[0] for i in remainder.args if i.func.__name__ == 'Mul'] \
                                           + [i.args[0] for i in remainder.args if i.func.__name__ == 'Pow']
            while any(sympify(s) in mulargs for s in species):
                for s in species:
                    if sympify(s) in mulargs:
                        if s in self.reactant: self.reactant[s] = self.reactant[s] + 1
                        else: self.reactant[s] = 1
                        if s in self.product: self.product[s] = self.product[s] + 1
                        else: self.product[s] = 1
                        remainder = remainder / sympify(s)
                        remainder = remainder.factor()
                        if remainder.func.__name__ == 'Mul':
                            mulargs = list(remainder.args) + [i.args[0] for i in remainder.args if i.func.__name__ == 'Mul'] \
                                                           + [i.args[0] for i in remainder.args if i.func.__name__ == 'Pow']
                        else: mulargs = []
            # update the kinetic parameter
            self.__kinetic_param = self.rate / self.reactant.ma()


    def _fix_denom(self, species):
        """Remove species that are involved in both reactant and product,
        if their concentration divides the denominator of the rate."""
        num, denom = (self.kinetic_param).as_numer_denom()
        remainder = denom.cancel()

        #if remainder.func.__name__ == 'Mul':
        if remainder != 1:
            mulargs = [remainder] + list(remainder.args) + [i.args[0] for i in remainder.args if i.func.__name__ == 'Mul'] \
                                                         + [i.args[0] for i in remainder.args if i.func.__name__ == 'Pow']
            while any(sympify(s) in mulargs and s in self.reactant and s in self.product for s in species):
                for s in species:
                    if sympify(s) in mulargs and s in self.reactant and s in self.product:
                        if self.reactant[s] == 1: del self.reactant[s]
                        else: self.reactant[s] = self.reactant[s] - 1
                        if self.product[s] == 1: del self.product[s]
                        else: self.product[s] = self.product[s] - 1
                        remainder = remainder / sympify(s)
                        remainder = remainder.factor()
                        if remainder.func.__name__ == 'Mul':
                            mulargs = list(remainder.args) + [i.args[0] for i in remainder.args if i.func.__name__ == 'Mul'] \
                                                           + [i.args[0] for i in remainder.args if i.func.__name__ == 'Pow']
                        else:
                            if str(remainder) in species: mulargs = [remainder]
                            else: mulargs = []
        # update the kinetic parameter
        self._kinetic_param = self.rate / self.reactant.ma()


def _split_reaction(reaction):
    """Split a reaction into separate reactions, one
    for each addend in rate (compare to split_reactions_monom)."""
    ratenumer, ratedenom = reaction.rate.as_numer_denom()
    ratenumer = ratenumer.expand()
    if ratenumer.func.__name__ == 'Add':
        reactions = []
        rateadds = list(ratenumer.args)

        for ra in range(len(rateadds)):
            reactions.append(Reaction(reaction.reactionid + "_" + str(ra), \
                                      reaction.reactant, \
                                      reaction.product, \
                                      rateadds[ra] / ratedenom))
        return reactions
    else: return [reaction]


def _split_reaction_monom(reaction, species):
    """Split a reaction into separate reactions, one
    for each monomial in rate (compare to split_reactions)."""
    ratenumer, ratedenom = reaction.rate.cancel().as_numer_denom()
    ratenumer = ratenumer.expand()
    species = map(sympify, species)
    ratendict = sp.Poly(ratenumer, *species).as_dict()
    if len(ratendict) > 1:
        reactions = []

        i = 0
        for degrees in ratendict:
            i = i + 1
            ratenpart = sp.Mul(*[species[r]**degrees[r] for r in range(len(species))]) * ratendict[degrees]
            reactions.append(Reaction(reaction.reactionid + "_" + str(i), \
                                      reaction.reactant, \
                                      reaction.product, \
                                      ratenpart / ratedenom))
        return reactions
    return [reaction]


def merge_reactions(reactions):
    """Merge reactions with same reactants and products."""
    react = defaultdict(list)
    newreactions = []
    for reaction in reactions:
        react[(tuple(sorted(reaction.reactant.items())), tuple(sorted(reaction.product.items())))].append(reaction)
    for c in react:
        if react[c][0].reactant != react[c][0].product:
            newreactions.append(Reaction(''.join([reaction.reactionid for reaction in react[c]]), \
                                         react[c][0].reactant, \
                                         react[c][0].product, \
                                         sum([reaction.rate for reaction in react[c]]).cancel()))
    return sorted(newreactions, key = lambda r: r.reactionid)


def _same_denom(reactions):
    """Change the rates so that they all have the same denominator."""
    numers, denoms = zip(*[reaction.rate.as_numer_denom() for reaction in reactions])
    commondenom = reduce(sp.lcm, denoms)
    newreactions = []
    for r in range(len(reactions)):
        reaction = reactions[r]
        if (denoms[r] - commondenom).cancel() != 0:
            diff = (commondenom / denoms[r]).cancel().expand()
            if diff.func.__name__ == 'Add':
                rateadds = list(diff.args)
                for ra in range(len(rateadds)):
                    newreactions.append(Reaction(reaction.reactionid + "_" + str(ra), \
                                                 reaction.reactant, \
                                                 reaction.product, \
                                                 rateadds[ra] * numers[r] / commondenom))
            else:
                newreactions.append(Reaction(reaction.reactionid, \
                                             reaction.reactant, \
                                             reaction.product, \
                                             diff * numers[r] / commondenom))
        else: newreactions.append(reactions[r])
    return newreactions


def translate(reaction, c):
    """Translate the reaction by c.
    Return the reaction (r + Id_c), where c has been added to both reactant and product.
    The rate is unchanged."""
    rid = reaction.reactionid + "_" + str(c).replace(" ", "").replace("+", "_").replace("-", "m")
    return Reaction(rid, Complex(reaction.reactant + c), Complex(reaction.product + c), reaction.rate)


def reaction_path(reactions):
    """Translate the reactions so that they can be composed,
    in the given order."""
    additions = [reduce(lambda a, b: a + b,
                        [reactions[i].product for i in range(h)] +
                        [reactions[i].reactant for i in range(h+1, len(reactions))])
                 for h in range(len(reactions))]
    c = Complex(reduce(lambda a, b: a & b, additions))
    additions = [Complex(additions[h]-c) for h in range(len(additions))]
    return [translate(reactions[h], additions[h]) for h in range(len(reactions))], additions
