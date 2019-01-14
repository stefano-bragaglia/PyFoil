import math
from itertools import permutations
from typing import List
from typing import Optional

from foil.old.learning import Candidate
from foil.old.learning import Hypothesis
from foil.models import Assignment
from foil.models import Clause
from foil.models import Label
from foil.models import Literal
from foil.unification import is_variable


def foil(
        target: Literal,
        background: List[Clause],
        positives: List[Assignment],
        negatives: List[Assignment],
) -> List[Clause]:
    hypotheses = []
    while positives:
        hypothesis = find_clause(hypotheses, target, background, positives, negatives)
        if hypothesis is None:
            break

        positives = update_examples(positives, hypothesis.pos)
        hypotheses.append(hypothesis.clause)

    return hypotheses


def update_examples(examples, examples_i):
    """Add to the kb those examples what are represented in extended_examples
    List of omitted examples is returned."""
    return [e for e in examples if not is_covered(e, examples_i)]


def find_clause(
        hypotheses: List[Clause],
        target: Literal,
        background: List[Clause],
        positives: List[Assignment],
        negatives: List[Assignment],
) -> Optional[Hypothesis]:
    body, positives, negatives = [], [*positives], [*negatives]
    while negatives:
        candidate = find_literal(hypotheses, target, body, background, positives, negatives)
        if candidate is None:
            break

        positives = update(positives, candidate.pos)
        negatives = update(negatives, candidate.neg)
        body.append(candidate.literal)

    if not body:
        return None

    return Hypothesis(Clause(target, body), positives)


def find_literal(
        hypotheses: List[Clause],
        target: Literal,
        body: List[Literal],
        background: List[Clause],
        positives: List[Assignment],
        negatives: List[Assignment],
) -> Optional[Candidate]:
    candidate = None
    for literal in [
        Literal.parse('edge(X,V0)'), Literal.parse('edge(V0,Y)'),
        Literal.parse('edge(V0,X)'), Literal.parse('edge(Y,V0)'),
        Literal.parse('edge(Y,X)'), Literal.parse('edge(X,Y)'),
        Literal.parse('edge(X,X)'), Literal.parse('edge(Y,Y)'),
        Literal.parse('path(X,V0)'), Literal.parse('path(V0,Y)'),
        Literal.parse('path(V0,X)'), Literal.parse('path(Y,V0)'),
        Literal.parse('path(Y,X)'), Literal.parse('path(X,Y)'),
        Literal.parse('path(X,X)'), Literal.parse('path(Y,Y)'),
    ]:

        positives_i = expand(positives, literal, world, Label.POSITIVE)
        negatives_i = expand(negatives, literal, world, Label.NEGATIVE)
        score = gain(positives, negatives, positives_i, negatives_i)
        print('%.3f %s %d %d' % (score, literal, len(positives_i), len(negatives_i)))
        if candidate is None or score > candidate.score:
            candidate = Candidate(score, literal, positives_i, negatives_i)

    return candidate


def expand2(examples: List[Assignment], literal: Literal) -> List[Assignment]:
    if not examples:
        return []

    variables = []
    for variable in literal.terms:
        if is_variable(variable) and variable not in examples[0]:
            variables.append(variable)

    if not variables:
        return examples

    additions = []
    size = len(variables)
    for values in permutations([0, 1, 2, 3, 4, 5, 6, 7, 8] * size, size):
        addition = dict(zip(variables, values))
        if addition not in additions:
            additions.append(addition)

    extension = []
    for example in examples:
        for addition in additions:
            assignment = {**example, **addition}
            if assignment not in extension:
                extension.append(assignment)

    return extension


def filter2(examples: List[Assignment], literal: Literal, world: List[Literal], label: Label) -> List[Assignment]:
    result = []
    positive = label == Label.POSITIVE
    for example in examples:
        candidate = literal.substitute(example)
        if (positive and candidate not in world or not positive and candidate in world) and example not in result:
            result.append(example)

    return result


def is_complement(part: List[Assignment], other: List[Assignment], total: List[Assignment]) -> bool:
    if all(p not in other for p in part) and all(o not in part for o in other):
        combo = [*part, *other]

        return all(c in total for c in combo) and all(t in combo for t in total)

    return False


def expand(examples: List[Assignment], literal: Literal, world: List[Literal], label: Label) -> List[Assignment]:
    if not examples:
        return []

    variables = []
    for variable in literal.terms:
        if is_variable(variable) and variable not in examples[0]:
            variables.append(variable)

    positive = label == Label.POSITIVE
    if not variables:
        coverage = []
        for example in examples:
            candidate = literal.substitute(example)
            included = candidate in world
            if (positive and not included or not positive and included) and example not in coverage:
                coverage.append(example)

        return coverage

    additions = []
    size = len(variables)
    for values in permutations([0, 1, 2, 3, 4, 5, 6, 7, 8] * size, size):
        addition = dict(zip(variables, values))
        if addition not in additions:
            additions.append(addition)

    extension = []
    for example in examples:
        for addition in additions:
            assignment = {**example, **addition}
            candidate = literal.substitute(assignment)
            included = candidate in world
            if (positive and included or not positive and not included) and assignment not in extension:
                extension.append(assignment)

    return extension


def max_gain(pos: List[Assignment], neg: List[Assignment]) -> float:
    if not pos and not neg:
        return -1

    t = len(pos)
    e = entropy(pos, neg)

    return t * e


def gain(pos: List[Assignment], neg: List[Assignment], pos_i: List[Assignment], neg_i: List[Assignment]) -> float:
    if not pos and not neg or not pos_i and not neg_i:
        return -1

    t = common(pos, pos_i)
    e = entropy(pos, neg)
    e_i = entropy(pos_i, neg_i, True)

    return t * (e - e_i)


def common(pos: List[Assignment], pos_i: List[Assignment]) -> float:
    reference = [pi.items() for pi in pos_i]
    return sum(1 for e in pos if any(all(item in items for item in e.items()) for items in reference))


def entropy(pos: List[Assignment], neg: List[Assignment], extra: bool = False) -> float:
    num = len(pos)
    den = num + len(neg)
    ratio = num / den
    if extra:
        ratio += 1e-12

    return -math.log2(ratio)


def update(examples: List[Assignment], examples_i: List[Assignment]) -> List[Assignment]:
    return [e for e in examples if not is_covered(e, examples_i)]


def is_covered(example: Assignment, examples_i: List[Assignment]) -> bool:
    return any(is_included(example, example_i) for example_i in examples_i)


def is_included(example: Assignment, example_i: Assignment) -> bool:
    return all(item in example_i.items() for item in example.items())


if __name__ == '__main__':
    target = Literal.parse('path(X,Y)')
    positives = [
        {'X': 0, 'Y': 1}, {'X': 0, 'Y': 2}, {'X': 0, 'Y': 3}, {'X': 0, 'Y': 4}, {'X': 0, 'Y': 5},
        {'X': 0, 'Y': 6}, {'X': 0, 'Y': 8}, {'X': 1, 'Y': 2}, {'X': 3, 'Y': 2}, {'X': 3, 'Y': 4},
        {'X': 3, 'Y': 5}, {'X': 3, 'Y': 6}, {'X': 3, 'Y': 8}, {'X': 4, 'Y': 5}, {'X': 4, 'Y': 6},
        {'X': 4, 'Y': 8}, {'X': 6, 'Y': 8}, {'X': 7, 'Y': 6}, {'X': 7, 'Y': 8},
    ]
    negatives = [
        {'X': 0, 'Y': 0}, {'X': 0, 'Y': 7}, {'X': 1, 'Y': 0}, {'X': 1, 'Y': 1}, {'X': 1, 'Y': 3},
        {'X': 1, 'Y': 4}, {'X': 1, 'Y': 5}, {'X': 1, 'Y': 6}, {'X': 1, 'Y': 7}, {'X': 1, 'Y': 8},
        {'X': 2, 'Y': 0}, {'X': 2, 'Y': 1}, {'X': 2, 'Y': 2}, {'X': 2, 'Y': 3}, {'X': 2, 'Y': 4},
        {'X': 2, 'Y': 5}, {'X': 2, 'Y': 6}, {'X': 2, 'Y': 7}, {'X': 2, 'Y': 8}, {'X': 3, 'Y': 0},
        {'X': 3, 'Y': 1}, {'X': 3, 'Y': 3}, {'X': 3, 'Y': 7}, {'X': 4, 'Y': 0}, {'X': 4, 'Y': 1},
        {'X': 4, 'Y': 2}, {'X': 4, 'Y': 3}, {'X': 4, 'Y': 4}, {'X': 4, 'Y': 7}, {'X': 5, 'Y': 0},
        {'X': 5, 'Y': 1}, {'X': 5, 'Y': 2}, {'X': 5, 'Y': 3}, {'X': 5, 'Y': 4}, {'X': 5, 'Y': 5},
        {'X': 5, 'Y': 6}, {'X': 5, 'Y': 7}, {'X': 5, 'Y': 8}, {'X': 6, 'Y': 0}, {'X': 6, 'Y': 1},
        {'X': 6, 'Y': 2}, {'X': 6, 'Y': 3}, {'X': 6, 'Y': 4}, {'X': 6, 'Y': 5}, {'X': 6, 'Y': 6},
        {'X': 6, 'Y': 7}, {'X': 7, 'Y': 0}, {'X': 7, 'Y': 1}, {'X': 7, 'Y': 2}, {'X': 7, 'Y': 3},
        {'X': 7, 'Y': 4}, {'X': 7, 'Y': 5}, {'X': 7, 'Y': 7}, {'X': 8, 'Y': 0}, {'X': 8, 'Y': 1},
        {'X': 8, 'Y': 2}, {'X': 8, 'Y': 3}, {'X': 8, 'Y': 4}, {'X': 8, 'Y': 5}, {'X': 8, 'Y': 6},
        {'X': 8, 'Y': 7}, {'X': 8, 'Y': 8},
    ]
    background = [
        Clause.parse('edge(0,1).'), Clause.parse('edge(0,3).'), Clause.parse('edge(1,2).'),
        Clause.parse('edge(3,2).'), Clause.parse('edge(3,4).'), Clause.parse('edge(4,5).'),
        Clause.parse('edge(4,6).'), Clause.parse('edge(6,8).'), Clause.parse('edge(7,6).'),
        Clause.parse('edge(7,8).'),
    ]

    # for clause in foil(target, background, positives, negatives):
    #     print(clause)

    candidate = find_literal([], target, [], background, positives, negatives)

    print(candidate)