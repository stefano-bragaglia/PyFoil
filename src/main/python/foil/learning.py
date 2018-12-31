import math
from itertools import combinations
from itertools import permutations
from typing import Iterable
from typing import List
from typing import Optional
from typing import Set
from typing import Tuple

from foil.unification import is_variable
from foil.unification import Value
from foil.unification import Variable

_tabling = {}


class Expand:

    def __init__(self, variables: Set[Variable], arity: int):
        self._variables = tuple(variables)
        self._arity = arity

        self._combinations = combinations([v for v in range(arity + len(variables))] * arity, arity)
        self._visited = {}

    def __iter__(self):
        self._visited = {}
        return self

    def __next__(self):
        global _tabling

        for combo in self._combinations:
            if any(i < len(self._variables) for i in combo):
                signature = _tabling \
                    .setdefault(self._variables, {}) \
                    .setdefault(self._arity, {}) \
                    .setdefault(combo, self._as_terms(self._variables, combo))
                if signature not in self._visited:
                    return self._visited.setdefault(signature, list(signature))

        raise StopIteration()

    @staticmethod
    def _as_terms(variables: Tuple[Variable], combination: Tuple[int, ...]) -> Tuple[Variable]:
        terms = tuple()
        i, table = 0, {i: v for i, v in enumerate(variables)}
        for index in combination:
            if index not in table:
                while ('V%d' % i) in variables:
                    i += 1
                table[index] = 'V%d' % i
            terms = (*terms, table[index])

        return terms


def closure(variables: List[Variable], constants: List[Value], examples: List['Example']) -> List['Example']:
    from foil.models import Example
    from foil.models import Label

    values = constants * len(variables)
    for values in permutations(values, len(variables)):
        assignment = dict(zip(variables, values))
        if Example(assignment) in examples:
            continue

        example = Example(assignment, Label.NEGATIVE)
        if example not in examples:
            examples.append(example)

    return sorted(examples, key=lambda x: repr((x.label, *[(k, v) for k, v in sorted(x.assignment.items())])))


def learn(
        background: Iterable['Clause'],
        target: 'Literal',
        masks: Iterable['Mask'],
        positives: Iterable['Example'],
        negatives: Iterable['Example'],
) -> List['Clause']:
    hypothesis = []
    while positives:
        selection = build(background, hypothesis, target, masks, positives, negatives)
        if selection is None:
            break

        clause, covered = selection
        hypothesis.append(clause)
        positives = subtract(positives, covered)
        if not covered:
            break

    return hypothesis


def build(
        background: Iterable['Clause'],
        hypothesis: Iterable['Clause'],
        target: 'Literal',
        masks: Iterable['Mask'],
        positives: Iterable['Example'],
        negatives: Iterable['Example'],
) -> Optional[Tuple['Clause', List['Example']]]:
    from foil.models import Clause

    body = []
    while negatives:
        selection = choose(background, hypothesis, target, body, masks, positives, negatives)
        if selection is None:
            break

        candidate, covered = selection
        body.append(candidate)
        negatives = subtract(negatives, covered)
        if not covered:
            break

    if not body:
        return None

    return Clause(target, body), list(positives)


def choose(
        background: Iterable['Clause'],
        hypothesis: Iterable['Clause'],
        target: 'Literal',
        body: Iterable['Literal'],
        masks: Iterable['Mask'],
        positives: Iterable['Example'],
        negatives: Iterable['Example'],
) -> Optional[Tuple['Literal', List['Example']]]:
    from foil.models import Atom
    from foil.models import Literal

    best_score, best_candidate, best_negatives = None, None, None
    variables = {t for l in [target, *body] for t in l.terms if is_variable(t)}
    for mask in masks:
        for terms in Expand(variables, mask.arity):
            candidate = Literal(Atom(mask.functor, terms), mask.negated)
            if candidate != target and candidate not in body:
                positives_i = covers(background, hypothesis, target, [*body, candidate], positives)
                if best_score is not None and max_gain(positives, negatives, positives_i) < best_score:
                    continue

                negatives_i = covers(background, hypothesis, target, [*body, candidate], negatives)
                score = gain(positives, negatives, positives_i, negatives_i)
                if best_score is None or score > best_score:
                    best_score, best_candidate, best_negatives = score, candidate, negatives_i

    if best_score is None:
        return None

    # TODO check what is returned for positives and negatives (change again uncovers to covers?)
    return best_candidate, best_negatives


def covers(
        background: Iterable['Clause'],
        hypothesis: Iterable['Clause'],
        target: 'Literal',
        body: Iterable['Literal'],
        examples: Iterable['Example'],
) -> List['Example']:
    from foil.models import Clause
    from foil.models import Label
    from foil.models import Program

    program = Program(list({*background, *hypothesis, Clause(target, list(body))}))
    world = program.ground()

    covered = []
    for example in examples:
        fact = target.substitute(example.assignment)
        if example in covered \
                or example.label is Label.NEGATIVE and fact in world \
                or example.label is Label.POSITIVE and fact not in world:
            covered.append(example)

    return covered


def subtract(examples: Iterable['Example'], covered: Iterable['Example']) -> List['Example']:
    return [e for e in examples if e not in covered]


def gain(
        positives: Iterable['Example'],
        negatives: Iterable['Example'],
        positives_i: Iterable['Example'],
        negatives_i: Iterable['Example'],
) -> float:
    return common(positives, positives_i) * (entropy(positives_i, negatives_i) - entropy(positives, negatives))


def max_gain(
        positives: Iterable['Example'],
        negatives: Iterable['Example'],
        positives_i: Iterable['Example'],
) -> float:
    return common(positives, positives_i) * entropy(positives, negatives)


def common(positives: Iterable['Example'], positives_i: Iterable['Example']) -> int:
    return sum(1 for e in positives_i if e in positives)


def entropy(positives: Iterable['Example'], negatives: Iterable['Example']) -> float:
    if not negatives or not positives:
        return math.inf

    return -math.log2(len(list(positives)) / len([*positives, *negatives]))


def foil(problem: 'Problem', cache: bool = True) -> List['Clause']:
    global _tabling

    if cache and problem in _tabling:
        return _tabling[problem]

    hypothesis = learn(problem.clauses, problem.target, problem.get_masks(), problem.positives, problem.negatives)

    if not cache:
        return hypothesis

    return _tabling.setdefault(problem, hypothesis)
