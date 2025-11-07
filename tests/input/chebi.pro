/*

  Demonstration of a probabilistic ensemble scoring system,
  based on ontology FOL.

  This may be overkill for now, but it lends itself well to integrating
  more logical components, such as:

  - decomposing structures into has_part SMARTS structures
  - C3PO like mechanism that generates programs that derive more atomic predicates
    (   e.g. charge, ring structures, ..)
  
*/

:- use_module(library(lists)).

% ====================
% OWL-TYPE AXIOMS
% ====================



instance_of(I,D) :- is_a(C,D), instance_of(I,C).
unsat(I,C,D) :- instance_of(I,C), instance_of(I,D), disjoint(C,D).

evidence(not unsat(I,C,D)).

% this is a convenience for pure TBOx inference
% note we already get instance propagation above
is_a(C,D) :- is_a(C,Z),is_a(Z,D).


% ====================
% CHEMISTRY AXIOMS
% ====================
% these would come from an ontology like chemrof (maybe one day CHEBI)

% STEREOCHEMISTRY
% each carbon position can only adopt one of two configurations

has_stereochemical_configuration_at(I,Pos,Conf) :- instance_of(I,C),has_stereochemical_configuration_at(C,Pos,Conf).
illegal_stereochemistry(Chem,Pos) :- has_stereochemical_configuration_at(Chem,Pos,alpha),has_stereochemical_configuration_at(Chem,Pos,beta).
evidence(not illegal_stereochemistry(_,_)).


% TBOX
is_a(terpenoid,lipid).
 is_a(diterpenoid,terpenoid).

is_a(steroid,lipid). 
 is_a(hydroxy_steroid,steroid).
  is_a(n17hydroxy_steroid,hydroxy_steroid).
   is_a(n17beta_hydroxy_steroid,n17hydroxy_steroid).
   is_a(n17alpha_hydroxy_steroid,n17hydroxy_steroid).
  is_a(n11hydroxy_steroid,hydroxy_steroid).
   is_a(n11beta_hydroxy_steroid,n11hydroxy_steroid).
   is_a(n11alpha_hydroxy_steroid,n11hydroxy_steroid).

 is_a(steroid_hormone,steroid).
  is_a(steroid_hormone,hormone).
is_a(estrogen,hormone).


has_stereochemical_configuration_at(n17beta_hydroxy_steroid, 17, beta).
has_stereochemical_configuration_at(n17alpha_hydroxy_steroid, 17, alpha).
has_stereochemical_configuration_at(n11beta_hydroxy_steroid, 11, beta).
has_stereochemical_configuration_at(n11alpha_hydroxy_steroid, 11, alpha).


disjoint(steroid,carbohydrate).
disjoint(terpenoid,hydroxy_steroid). % JUST FOR DEMO PURPOSES


% ====================
% METHODS TBOX
% ====================

% Encodes an 'ontology' of methods
% these may have different axioms/rules for deriving performance

% simplification of c3p - very poor on one hierarchy, moderate on another
method_class_precision(c3p,C,0.07) :- is_a(C,hydroxy_steroid).
method_class_precision(c3p,C,0.40) :- \+ is_a(C,hydroxy_steroid).

method_class_specificity(c3p,C,0.20) :- is_a(C,hydroxy_steroid).
method_class_specificity(c3p,C,0.60) :- \+ is_a(C,hydroxy_steroid).

% let's assume CHEBI very precise but maybe missing a lot of edges
% (in reality I have my priors about which parts of chebi work better than others...)
method_class_precision(chebi,_,0.95).
method_class_specificity(chebi,_,0.90).

% let's make electra somewhere in between for the sake of a demo
method_class_precision(electra,_,0.70).
method_class_specificity(electra,_,0.80).

% roll up to a predicate that reifies truth value

prediction_t(I,C,M,true) :- prediction(I,C,M).
prediction_t(I,C,M,false) :- prediction(_,C,_),prediction(I,_,_), prediction(_, _, M), not prediction(I,C,M).

% overall probability of a classification
pc(I,C,M,true,P) :- prediction_t(I,C,M,true), method_class_precision(M,C,P).
pc(I,C,M,false,P) :- prediction_t(I,C,M,false), method_class_specificity(M,C,P).


% CPT for integrating probabilities of each sub-predictor (noisy-OR model)
% This assumes independence of each method - the framework here allows
% building a more sophisticated causal structure that would reflect
% the influence chebi had on the training set

% for now we unroll 2^|M| rules, this is obviously not scalable
% but it helps to be dumb and explicit for now...

% Case 1: c3p=T, electra=T, chebi=T
P :: ensemble_prediction(I,C) :- 
    pc(I,C,c3p,true,P1), pc(I,C,electra,true,P2), pc(I,C,chebi,true,P3), 
    P is 1-((1-P1) * (1-P2) * (1-P3)).

% Case 2: c3p=T, electra=T, chebi=F
P :: ensemble_prediction(I,C) :- 
    pc(I,C,c3p,true,P1), pc(I,C,electra,true,P2), pc(I,C,chebi,false,P3), 
    P is 1-((1-P1) * (1-P2) * P3).

% Case 3: c3p=T, electra=F, chebi=T
P :: ensemble_prediction(I,C) :- 
    pc(I,C,c3p,true,P1), pc(I,C,electra,false,P2), pc(I,C,chebi,true,P3), 
    P is 1-((1-P1) * P2 * (1-P3)).

% Case 4: c3p=T, electra=F, chebi=F
P :: ensemble_prediction(I,C) :- 
    pc(I,C,c3p,true,P1), pc(I,C,electra,false,P2), pc(I,C,chebi,false,P3), 
    P is 1-((1-P1) * P2 * P3).

% Case 5: c3p=F, electra=T, chebi=T
P :: ensemble_prediction(I,C) :- 
    pc(I,C,c3p,false,P1), pc(I,C,electra,true,P2), pc(I,C,chebi,true,P3), 
    P is 1-(P1 * (1-P2) * (1-P3)).

% Case 6: c3p=F, electra=T, chebi=F
P :: ensemble_prediction(I,C) :- 
    pc(I,C,c3p,false,P1), pc(I,C,electra,true,P2), pc(I,C,chebi,false,P3), 
    P is 1-(P1 * (1-P2) * P3).

% Case 7: c3p=F, electra=F, chebi=T
P :: ensemble_prediction(I,C) :- 
    pc(I,C,c3p,false,P1), pc(I,C,electra,false,P2), pc(I,C,chebi,true,P3), 
    P is 1-(P1 * P2 * (1-P3)).

% Case 8: c3p=F, electra=F, chebi=F
P :: ensemble_prediction(I,C) :- 
    pc(I,C,c3p,false,P1), pc(I,C,electra,false,P2), pc(I,C,chebi,false,P3), 
    P is 1-(P1 * P2 * P3).

% I guess we could just use the same predicate
instance_of(I,C) :- ensemble_prediction(I,C).

% ====================
% "ABox" - structure predictions
% ====================

% --------------------
% STRUCTURE: estetrol
% --------------------
% SMILES: C12=CC=C(C=C1CC[C@@]3([C@@]2(CC[C@]4([C@]3([C@H]([C@H]([C@@H]4O)O)O)[H])C)[H])[H])O

% c3p predictions
prediction(estetrol,n11beta_hydroxy_steroid,c3p). % this is wrong
prediction(estetrol,n11beta_hydroxy_steroid,c3p). % this is right

% prediction(estetrol,n11alpha_hydroxy_steroid,c3p). % REMOVE

% electra predictions
prediction(estetrol,n17beta_hydroxy_steroid,electra).

% chebi 'predictions'
prediction(estetrol,n17beta_hydroxy_steroid,chebi).

% --------------------
% STRUCTURE: tixocortol 
% --------------------
% SMILES: [H][C@@]12CCC3=CC(=O)CC[C@]3(C)[C@@]1([H])[C@@H](O)C[C@@]1(C)[C@@]2([H])CC[C@]1(O)C(=O)CS

% c3p predictions
prediction(tixocortol,diterpenoid,c3p).
prediction(tixocortol,n17beta_hydroxy_steroid,c3p). % pretend, to illustrate that this gets suppressed by the high confidence 17alpha from other sources

% electra
prediction(tixocortol,n11beta_hydroxy_steroid,electra).
 prediction(tixocortol,n17alpha_hydroxy_steroid,electra).

% chebi 'predictions'
prediction(tixocortol,n11beta_hydroxy_steroid,chebi).
prediction(tixocortol,n17alpha_hydroxy_steroid,chebi).


% ====================
% QUERY
% ====================

query(instance_of(I,C)).




