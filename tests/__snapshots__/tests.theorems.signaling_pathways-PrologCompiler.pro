%% Predicate Definitions
% Protein(name: str)
% ModifiedProtein(protein: Protein, modification: ModificationType, site: Optional, active: bool)
% Complex(name: Optional)
% Kinase(protein: Protein)
% Phosphatase(protein: Protein)
% GTPase(protein: Protein)
% GEF(protein: Protein, target: Protein)
% GAP(protein: Protein, target: Protein)
% Ligand(name: str)
% Receptor(protein: Protein)
% LigandReceptorBinding(ligand: Ligand, receptor: Receptor, active: bool)
% Activation(upstream: Protein, downstream: Protein)
% PhosphorylationEvent(kinase: Protein, substrate: Protein, site: str)
% Translocation(protein: Protein, from_compartment: str, to_compartment: str)
% Compartment(name: str)
% ProteinLocation(protein: Protein, compartment: Compartment)

%% receptor_activation_by_ligand

modifiedprotein(protein(Receptor_name), 'PHOSPHORYLATION', _, True) :- ligand(Ligand_name), receptor(protein(Receptor_name)), ligandreceptorbinding(ligand(Ligand_name), receptor(protein(Receptor_name)), True).

%% rtk_activates_grb2_sos

complex('GRB2-SOS') :- modifiedprotein(protein(Receptor_name), 'PHOSPHORYLATION', _, True).
activation(protein(Receptor_name), protein('SOS')) :- modifiedprotein(protein(Receptor_name), 'PHOSPHORYLATION', _, True).

%% sos_activates_ras

modifiedprotein(protein('RAS'), 'GTP_BOUND', _, True) :- protein('SOS'), protein('RAS'), gef(protein('SOS'), protein('RAS')), activation(protein('SOS'), protein('RAS')).

%% ras_activates_raf

modifiedprotein(protein('RAF'), 'PHOSPHORYLATION', 'S338', True) :- modifiedprotein(protein('RAS'), 'GTP_BOUND', _, True).
activation(protein('RAS'), protein('RAF')) :- modifiedprotein(protein('RAS'), 'GTP_BOUND', _, True).

%% raf_phosphorylates_mek

phosphorylationevent(protein(Raf_name), protein(Mek_name), 'S218') :- modifiedprotein(protein(Raf_name), 'PHOSPHORYLATION', _, True), kinase(protein(Raf_name)), protein(Mek_name).
phosphorylationevent(protein(Raf_name), protein(Mek_name), 'S222') :- modifiedprotein(protein(Raf_name), 'PHOSPHORYLATION', _, True), kinase(protein(Raf_name)), protein(Mek_name).
modifiedprotein(protein(Mek_name), 'PHOSPHORYLATION', 'S218', True) :- modifiedprotein(protein(Raf_name), 'PHOSPHORYLATION', _, True), kinase(protein(Raf_name)), protein(Mek_name).
modifiedprotein(protein(Mek_name), 'PHOSPHORYLATION', 'S222', True) :- modifiedprotein(protein(Raf_name), 'PHOSPHORYLATION', _, True), kinase(protein(Raf_name)), protein(Mek_name).
activation(protein(Raf_name), protein(Mek_name)) :- modifiedprotein(protein(Raf_name), 'PHOSPHORYLATION', _, True), kinase(protein(Raf_name)), protein(Mek_name).

%% mek_phosphorylates_erk

phosphorylationevent(protein(Mek_name), protein(Erk_name), 'T185') :- modifiedprotein(protein(Mek_name), 'PHOSPHORYLATION', 'S218', True), modifiedprotein(protein(Mek_name), 'PHOSPHORYLATION', 'S222', True), kinase(protein(Mek_name)), protein(Erk_name).
phosphorylationevent(protein(Mek_name), protein(Erk_name), 'Y187') :- modifiedprotein(protein(Mek_name), 'PHOSPHORYLATION', 'S218', True), modifiedprotein(protein(Mek_name), 'PHOSPHORYLATION', 'S222', True), kinase(protein(Mek_name)), protein(Erk_name).
modifiedprotein(protein(Erk_name), 'PHOSPHORYLATION', 'T185', True) :- modifiedprotein(protein(Mek_name), 'PHOSPHORYLATION', 'S218', True), modifiedprotein(protein(Mek_name), 'PHOSPHORYLATION', 'S222', True), kinase(protein(Mek_name)), protein(Erk_name).
modifiedprotein(protein(Erk_name), 'PHOSPHORYLATION', 'Y187', True) :- modifiedprotein(protein(Mek_name), 'PHOSPHORYLATION', 'S218', True), modifiedprotein(protein(Mek_name), 'PHOSPHORYLATION', 'S222', True), kinase(protein(Mek_name)), protein(Erk_name).
activation(protein(Mek_name), protein(Erk_name)) :- modifiedprotein(protein(Mek_name), 'PHOSPHORYLATION', 'S218', True), modifiedprotein(protein(Mek_name), 'PHOSPHORYLATION', 'S222', True), kinase(protein(Mek_name)), protein(Erk_name).

%% erk_nuclear_translocation

translocation(protein(Erk_name), 'cytoplasm', 'nucleus') :- modifiedprotein(protein(Erk_name), 'PHOSPHORYLATION', 'T185', True), modifiedprotein(protein(Erk_name), 'PHOSPHORYLATION', 'Y187', True), proteinlocation(protein(Erk_name), compartment('cytoplasm')).
proteinlocation(protein(Erk_name), compartment('nucleus')) :- modifiedprotein(protein(Erk_name), 'PHOSPHORYLATION', 'T185', True), modifiedprotein(protein(Erk_name), 'PHOSPHORYLATION', 'Y187', True), proteinlocation(protein(Erk_name), compartment('cytoplasm')).

%% gap_inactivates_ras



%% phosphatase_inactivates_protein



%% pi3k_pathway_crosstalk

activation(protein(Receptor_name), protein('PI3K')) :- modifiedprotein(protein(Receptor_name), 'PHOSPHORYLATION', _, True).
modifiedprotein(protein('PI3K'), 'PHOSPHORYLATION', _, True) :- modifiedprotein(protein(Receptor_name), 'PHOSPHORYLATION', _, True).

%% pi3k_activates_akt

activation(protein('PI3K'), protein('AKT')) :- modifiedprotein(protein('PI3K'), 'PHOSPHORYLATION', _, True).
modifiedprotein(protein('AKT'), 'PHOSPHORYLATION', 'T308', True) :- modifiedprotein(protein('PI3K'), 'PHOSPHORYLATION', _, True).

%% erk_negative_feedback

phosphorylationevent(protein(Erk_name), protein('SOS'), 'S1132') :- modifiedprotein(protein(Erk_name), 'PHOSPHORYLATION', 'T185', True), modifiedprotein(protein(Erk_name), 'PHOSPHORYLATION', 'Y187', True).
modifiedprotein(protein('SOS'), 'PHOSPHORYLATION', 'S1132', False) :- modifiedprotein(protein(Erk_name), 'PHOSPHORYLATION', 'T185', True), modifiedprotein(protein(Erk_name), 'PHOSPHORYLATION', 'Y187', True).

%% erk_activates_transcription_factors

phosphorylationevent(protein(Erk_name), protein(Tf_name), 'S') :- modifiedprotein(protein(Erk_name), 'PHOSPHORYLATION', 'T185', True), modifiedprotein(protein(Erk_name), 'PHOSPHORYLATION', 'Y187', True), proteinlocation(protein(Erk_name), compartment('nucleus')), protein(Tf_name).
modifiedprotein(protein(Tf_name), 'PHOSPHORYLATION', 'S', True) :- modifiedprotein(protein(Erk_name), 'PHOSPHORYLATION', 'T185', True), modifiedprotein(protein(Erk_name), 'PHOSPHORYLATION', 'Y187', True), proteinlocation(protein(Erk_name), compartment('nucleus')), protein(Tf_name).
activation(protein(Erk_name), protein(Tf_name)) :- modifiedprotein(protein(Erk_name), 'PHOSPHORYLATION', 'T185', True), modifiedprotein(protein(Erk_name), 'PHOSPHORYLATION', 'Y187', True), proteinlocation(protein(Erk_name), compartment('nucleus')), protein(Tf_name).