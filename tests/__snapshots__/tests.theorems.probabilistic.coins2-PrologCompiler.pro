%% Predicate Definitions
% Probability(probability: float, that: That)
% That(sentence: Sentence)
% Coin(id: str)
% Heads(id: str)
% Tails(id: str)
% Win()

%% win

win :- heads(C).

%% probs

probability(Implies(Coin(?c), Heads(?c))) == 0.4.
probability(Implies(Coin(?c), Tails(?c))) == 0.6.